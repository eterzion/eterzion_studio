"""A Imagem numa etapa so', e a garantia de que a origem sobrevive a ela.

O nome padrao do resultado e' o do original, e a pasta padrao e' a do original
-- entao, por construcao, o destino padrao e' a propria origem quando o formato
nao muda. O Principio XV proibe resolver isso sobrescrevendo, inclusive com
"sobrescrever": essa instrucao e' sobre outro arquivo, nunca sobre o original
de onde a pessoa esta' partindo.

Antes a exportacao era uma segunda etapa, por uma rota propria com as proprias
regras de nome. Agora o destino e' resolvido pelo nucleo comum
(app/destino.py) quando o job e' criado, e o job entrega o resultado. Os testes
passam pela rota e pelo job de verdade e leem o disco depois -- um teste que
parasse nos ajudantes passaria com a guarda apagada.
"""
from __future__ import annotations

import asyncio
import os

import cv2
import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import jobs
from app.config import settings
from app.routes import jobs_router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(jobs_router, prefix='/jobs')
    return TestClient(app)


@pytest.fixture
def interna(tmp_path, monkeypatch):
    pasta = tmp_path / 'interna'
    pasta.mkdir()
    monkeypatch.setattr(settings, 'outputs_dir', str(pasta))
    return pasta


@pytest.fixture
def foto(tmp_path):
    caminho = tmp_path / 'foto.png'
    ok, dados = cv2.imencode('.png', np.full((10, 10, 3), 90, dtype=np.uint8))
    assert ok
    caminho.write_bytes(dados.tobytes())
    return caminho


def _processar(client, foto, **alvo) -> dict:
    corpo = {'media_request': {
        'media_type': 'image', 'operation': 'enhance', 'content_type_override': 'photo',
        'scale': '4x', 'input_path': str(foto), 'output_target': {'format': 'png', **alvo},
    }}
    r = client.post('/jobs/local', json=corpo)
    assert r.status_code == 200, r.text
    job_id = r.json()['id']
    jobs.jobs[job_id]['status'] = 'queued'
    asyncio.run(jobs._process_job(job_id))
    job = jobs.get_job(job_id)
    assert job['status'] == 'done', job.get('error')
    return job


class TestTheSourceIsNeverTheDestination:
    def test_default_does_not_land_on_the_source(self, client, foto, interna, fake_supervisor):
        antes = foto.read_bytes()
        job = _processar(client, foto)
        assert job['output_path'] == str(foto.parent / 'foto_upscaled.png')
        assert foto.read_bytes() == antes, 'a origem foi alterada'

    def test_explicit_overwrite_of_the_source_name_still_spares_the_source(
            self, client, foto, interna, fake_supervisor):
        antes = foto.read_bytes()
        job = _processar(client, foto, filename='foto', conflict='overwrite')
        assert job['output_path'] == str(foto.parent / 'foto_upscaled.png')
        assert foto.read_bytes() == antes, 'a origem foi alterada'

    def test_a_different_folder_keeps_the_plain_source_name(
            self, client, foto, interna, tmp_path, fake_supervisor):
        saida = tmp_path / 'saida'
        job = _processar(client, foto, directory=str(saida))
        assert job['output_path'] == str(saida / 'foto.png')


class TestOneStep:
    def test_the_result_is_in_the_destination_and_no_master_is_left(
            self, client, foto, interna, tmp_path, fake_supervisor):
        saida = tmp_path / 'saida'
        job = _processar(client, foto, format='jpg', directory=str(saida), profile='quality')
        destino = saida / 'foto.jpg'
        assert job['output_path'] == str(destino)
        assert destino.read_bytes()[:2] == b'\xff\xd8', 'deveria ser JPEG de verdade'
        assert job['output_meta']['size_bytes'] == destino.stat().st_size
        assert list(interna.iterdir()) == [], 'o master ficou para tras'

    def test_without_a_destination_the_result_stays_inside(
            self, client, foto, interna, fake_supervisor):
        corpo = {'media_request': {
            'media_type': 'image', 'operation': 'enhance', 'content_type_override': 'photo',
            'scale': '4x', 'input_path': str(foto)}}
        job_id = client.post('/jobs/local', json=corpo).json()['id']
        jobs.jobs[job_id]['status'] = 'queued'
        asyncio.run(jobs._process_job(job_id))
        assert jobs.get_job(job_id)['output_path'] == str(interna / f'{job_id}_master.png')

    def test_ask_refuses_with_409_before_the_job(self, client, foto, tmp_path):
        (tmp_path / 'foto.webp').write_bytes(b'ja existe')
        antes = set(jobs.jobs)
        corpo = {'media_request': {
            'media_type': 'image', 'operation': 'enhance', 'content_type_override': 'photo',
            'scale': '4x', 'input_path': str(foto),
            'output_target': {'format': 'webp', 'conflict': 'ask'}}}
        r = client.post('/jobs/local', json=corpo)
        assert r.status_code == 409
        assert r.json()['detail']['path'] == str(tmp_path / 'foto.webp')
        assert set(jobs.jobs) == antes

    def test_unknown_format_is_refused_before_the_job(self, client, foto):
        corpo = {'media_request': {
            'media_type': 'image', 'operation': 'enhance', 'content_type_override': 'photo',
            'scale': '4x', 'input_path': str(foto), 'output_target': {'format': 'bmp'}}}
        r = client.post('/jobs/local', json=corpo)
        assert r.status_code == 422
        assert r.json()['detail']['reason'] == 'format_unavailable'


def test_profile_sets_the_jpeg_quality(tmp_path):
    from app import exportacao_de_imagem

    ruido = np.random.default_rng(1).integers(0, 255, (64, 64, 3), dtype=np.uint8)
    tamanhos = {}
    for perfil in ('fast', 'quality'):
        intermediario = tmp_path / f'{perfil}.png'
        cv2.imwrite(str(intermediario), ruido)
        saida = tmp_path / f'{perfil}.jpg'
        exportacao_de_imagem.codificar(str(intermediario), str(saida), 'jpg', perfil)
        tamanhos[perfil] = os.path.getsize(saida)
    assert tamanhos['quality'] > tamanhos['fast']


class TestImageEdits:
    """Ajustes, efeitos e transformacao da Imagem: os filtros do Video, depois
    do modelo, com a transparencia preservada."""

    def test_rotation_and_colour_reach_the_delivered_file(
            self, client, foto, interna, tmp_path, fake_supervisor):
        fake_supervisor.configure_result((10, 10), (40, 20))
        ok, dados = cv2.imencode('.png', np.full((20, 40, 3), 90, dtype=np.uint8))
        fake_supervisor._write_master_bytes = dados.tobytes()
        corpo = {'media_request': {
            'media_type': 'image', 'operation': 'enhance', 'content_type_override': 'photo',
            'scale': '4x', 'input_path': str(foto),
            'output_target': {'format': 'png', 'directory': str(tmp_path / 'saida')},
            'edits': {'adjustments': {'brightness': 0.2, 'brightness_enabled': True},
                      'transform': {'rotation_degrees': 90}}}}
        job_id = client.post('/jobs/local', json=corpo).json()['id']
        jobs.jobs[job_id]['status'] = 'queued'
        asyncio.run(jobs._process_job(job_id))
        job = jobs.get_job(job_id)
        assert job['status'] == 'done', job.get('error')

        resultado = cv2.imread(job['output_path'])
        assert resultado.shape[:2] == (40, 20), 'girar 90 graus deveria trocar largura e altura'
        assert (job['output_meta']['width'], job['output_meta']['height']) == (20, 40)
        assert resultado.mean() > 110, 'o brilho nao foi aplicado'

    def test_transparency_survives_the_filters(self, tmp_path):
        from app import exportacao_de_imagem

        imagem = np.zeros((40, 60, 4), np.uint8)
        imagem[..., :3] = (40, 120, 200)
        imagem[10:30, 20:40, 3] = 255
        caminho = tmp_path / 'rgba.png'
        cv2.imwrite(str(caminho), imagem)

        exportacao_de_imagem.aplicar_edicoes(str(caminho), {
            'effects': {'grain_enabled': True, 'grain_strength': 40},
            'transform': {'rotation_degrees': 90, 'flip_horizontal': True}})

        saida = cv2.imread(str(caminho), cv2.IMREAD_UNCHANGED)
        assert saida.shape == (60, 40, 4)
        # A granulacao nao pode sujar o alfa: continua so' 0 e 255.
        assert set(np.unique(saida[..., 3]).tolist()) == {0, 255}
        # E a geometria do alfa acompanha a da cor (girado e espelhado).
        esperado = np.fliplr(np.rot90(imagem[..., 3], k=-1))
        assert np.array_equal(saida[..., 3], esperado)

    def test_neutral_edits_leave_the_file_alone(self, tmp_path):
        from app import exportacao_de_imagem

        caminho = tmp_path / 'a.png'
        cv2.imwrite(str(caminho), np.full((8, 8, 3), 50, np.uint8))
        antes = caminho.read_bytes()
        assert exportacao_de_imagem.aplicar_edicoes(str(caminho), {
            'adjustments': {'brightness': 0.5, 'brightness_enabled': False}}) is None
        assert caminho.read_bytes() == antes


def _shader(rgb: np.ndarray, brilho: float, contraste: float, saturacao: float, matiz: float) -> np.ndarray:
    """O que o shader da previa faz (useVideoPreviewPipeline.ts), em numpy:
    BT.709, luma em faixa limitada, eq e hue na mesma ordem."""
    rgb = rgb.astype(np.float64) / 255.0
    para_yuv = np.array([[0.2126, 0.7152, 0.0722],
                         [-0.114572, -0.385428, 0.5],
                         [0.5, -0.454153, -0.045847]])
    para_rgb = np.array([[1.0, 0.0, 1.5748],
                         [1.0, -0.187324, -0.468124],
                         [1.0, 1.8556, 0.0]])
    yuv = rgb @ para_yuv.T
    y = (16 + 219 * yuv[..., 0]) / 255
    y = np.clip(contraste * (y - 0.5) + 0.5 + brilho, 0, 1)
    y = (y * 255 - 16) / 219
    u, v = yuv[..., 1] * saturacao, yuv[..., 2] * saturacao
    c, s = np.cos(np.radians(matiz)), np.sin(np.radians(matiz))
    u, v = u * c - v * s, u * s + v * c
    return np.clip(np.stack([y, u, v], -1) @ para_rgb.T, 0, 1) * 255


def test_the_file_matches_what_the_preview_showed(tmp_path):
    """Paridade entre o arquivo e a previa: o mesmo brilho, contraste,
    saturacao e matiz, medidos em cores de verdade."""
    from app import exportacao_de_imagem

    cores = np.array([[200, 60, 40], [40, 160, 90], [30, 70, 210], [128, 128, 128],
                      [240, 220, 180], [20, 20, 30]], np.uint8)
    rgb = np.repeat(np.repeat(cores[None, :, :], 8, axis=0), 8, axis=1)  # blocos 8x8
    caminho = tmp_path / 'cores.png'
    cv2.imwrite(str(caminho), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))

    exportacao_de_imagem.aplicar_edicoes(str(caminho), {'adjustments': {
        'brightness': 0.08, 'brightness_enabled': True, 'contrast': 1.2, 'contrast_enabled': True,
        'saturation': 1.4, 'saturation_enabled': True, 'hue_degrees': 25, 'hue_degrees_enabled': True}})

    saida = cv2.cvtColor(cv2.imread(str(caminho)), cv2.COLOR_BGR2RGB).astype(np.float64)
    esperado = _shader(rgb, 0.08, 1.2, 1.4, 25)
    # O centro de cada bloco, longe da borda onde a subamostragem mistura cores.
    centros = (slice(2, None, 8), slice(4, None, 8))
    diferenca = np.abs(saida[centros] - esperado[centros]).max()
    assert diferenca <= 6, f'o arquivo diverge da previa em ate {diferenca:.1f} niveis'
