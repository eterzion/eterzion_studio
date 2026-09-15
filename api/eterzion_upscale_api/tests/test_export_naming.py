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
