"""A exportacao do Audio: formato, qualidade, destino -- pelo nucleo comum.

Antes o resultado ficava so' na pasta interna do app, no formato do original,
e a "restauracao" de musica copiava um WAV para um arquivo com a extensao do
original (uma musica .mp3 saia chamada .mp3 com conteudo WAV).
"""
from __future__ import annotations

import asyncio
import io
import math
import struct
import wave
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import exportacao_de_audio, jobs
from app.config import settings
from app.routes import jobs_router
from eterzion_upscale.media import ffprobe_json


def _wav_bytes(segundos: float = 1.0, taxa: int = 44_100) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(taxa)
        quadros = bytearray()
        for i in range(int(segundos * taxa)):
            v = int(8000 * math.sin(2 * math.pi * 440 * i / taxa))
            quadros += struct.pack('<hh', v, v)
        w.writeframes(bytes(quadros))
    return buffer.getvalue()


def _codec(caminho) -> str:
    return next(s['codec_name'] for s in ffprobe_json(str(caminho))['streams']
                if s['codec_type'] == 'audio')


@pytest.fixture
def interna(tmp_path, monkeypatch):
    pasta = tmp_path / 'interna'
    pasta.mkdir()
    monkeypatch.setattr(settings, 'outputs_dir', str(pasta))
    return pasta


@pytest.fixture
def musica(tmp_path):
    caminho = tmp_path / 'musica.mp3'
    caminho.write_bytes(b'nao e lido: o processamento e falso nestes testes')
    return caminho


# ------------------------------------------------------------ o modulo --


def test_keep_e_o_formato_do_original():
    assert exportacao_de_audio.formato_de_saida('keep', 'C:/a/voz.M4A') == 'm4a'
    assert exportacao_de_audio.formato_de_saida(None, 'voz.flac') == 'flac'
    assert exportacao_de_audio.formato_de_saida('.MP3', 'voz.flac') == 'mp3'


def test_formato_desconhecido_e_recusado(tmp_path):
    with pytest.raises(exportacao_de_audio.RecusaDeAudio) as erro:
        exportacao_de_audio.verificar('aiff', duracao_segundos=10, perfil=None, pasta=str(tmp_path))
    assert erro.value.reason == 'format_unavailable'


def test_falta_de_espaco_e_recusada_antes(tmp_path, monkeypatch):
    import shutil
    from collections import namedtuple

    uso = namedtuple('uso', 'total used free')
    monkeypatch.setattr(shutil, 'disk_usage', lambda _p: uso(10, 10, 1_000))
    with pytest.raises(exportacao_de_audio.RecusaDeAudio) as erro:
        exportacao_de_audio.verificar('wav', duracao_segundos=60, perfil=None, pasta=str(tmp_path))
    assert erro.value.reason == 'insufficient_disk'
    assert erro.value.detail['required_bytes'] == 60 * 48_000 * 4


def test_codifica_de_verdade_no_formato_pedido(tmp_path):
    intermediario = tmp_path / 'i.wav'
    intermediario.write_bytes(_wav_bytes())
    exportacao_de_audio.codificar(str(intermediario), str(tmp_path / 's.mp3'), 'mp3', 'quality')
    assert _codec(tmp_path / 's.mp3') == 'mp3'
    bits = int(ffprobe_json(str(tmp_path / 's.mp3'))['format']['bit_rate'])
    assert bits > 256_000, 'a qualidade "quality" deveria dar 320k'


def test_wav_para_wav_so_muda_de_lugar(tmp_path):
    intermediario = tmp_path / 'i.wav'
    intermediario.write_bytes(_wav_bytes(0.1))
    exportacao_de_audio.codificar(str(intermediario), str(tmp_path / 's.wav'), 'wav', None)
    assert (tmp_path / 's.wav').read_bytes() == _wav_bytes(0.1)
    assert not intermediario.exists()


# ------------------------------------------------------------ musica --


@pytest.fixture
def masterizacao_falsa(monkeypatch):
    """O MasteringEngine grava um WAV de verdade no caminho que recebe."""
    from app.audio_engine import mastering

    class Analise:
        integrated_lufs = -14.0
        true_peak_db = -1.0
        dynamic_range_db = 8.0
        clipping_ratio = 0.0

    class Resultado:
        audio_analysis = Analise()
        quality_verdict = None

    recebidos: list[str] = []

    def run(self, modo, origem, saida, **kw):
        recebidos.append(saida)
        Path(saida).write_bytes(_wav_bytes(0.5))
        return Resultado()

    monkeypatch.setattr(mastering.MasteringEngine, 'run', run)
    return recebidos


def _job_de_musica(origem, params):
    job_id = jobs.create_job(str(origem), origem.name, params, media_type='audio',
                             operation='enhance', content_type_detected='music')
    jobs.jobs[job_id]['status'] = 'queued'
    return job_id


def test_musica_e_entregue_no_destino_no_formato_pedido(
        tmp_path, interna, musica, default_job_params, masterizacao_falsa):
    destino = tmp_path / 'saida' / 'musica_enhanced.mp3'
    params = default_job_params(output_path=str(destino),
                                output_target={'format': 'keep', 'conflict': 'rename',
                                               'profile': 'balanced'})
    job_id = _job_de_musica(musica, params)

    asyncio.run(jobs._process_job(job_id))

    job = jobs.get_job(job_id)
    assert job['status'] == 'done', job.get('error')
    assert job['output_path'] == str(destino)
    # O conteudo e' o do nome: MP3 de verdade, nao um WAV chamado .mp3.
    assert _codec(destino) == 'mp3'
    assert masterizacao_falsa[0].endswith('.wav'), 'o intermediario deve ser sem perda'
    assert list(interna.iterdir()) == []
    assert [p.name for p in destino.parent.iterdir()] == ['musica_enhanced.mp3']


def test_musica_sem_destino_fica_na_pasta_interna_como_wav(
        interna, musica, default_job_params, masterizacao_falsa):
    # O defeito da restauracao: o arquivo levava a extensao do original.
    job_id = _job_de_musica(musica, default_job_params())
    asyncio.run(jobs._process_job(job_id))
    saida = jobs.get_job(job_id)['output_path']
    assert saida == str(interna / f'{job_id}.wav')
    assert _codec(saida).startswith('pcm_')


# ------------------------------------------------------------ voz --


def test_voz_e_entregue_no_destino(tmp_path, interna, default_job_params, fake_supervisor):
    origem = tmp_path / 'voz.wav'
    origem.write_bytes(_wav_bytes(0.2))
    fake_supervisor._write_master_bytes = _wav_bytes(0.5)
    destino = tmp_path / 'saida' / 'voz.flac'
    params = default_job_params(output_path=str(destino),
                                output_target={'format': 'flac', 'conflict': 'rename'})
    job_id = jobs.create_job(str(origem), 'voz.wav', params, media_type='audio',
                             operation='enhance', content_type_detected='speech')
    jobs.jobs[job_id]['status'] = 'queued'

    asyncio.run(jobs._process_job(job_id))

    job = jobs.get_job(job_id)
    assert job['status'] == 'done', job.get('error')
    assert job['output_path'] == str(destino)
    assert _codec(destino) == 'flac'
    assert fake_supervisor.process_calls[0]['master_path'].endswith('.wav')
    assert list(interna.iterdir()) == []


# ------------------------------------------------------------ a rota --


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(jobs_router, prefix='/jobs')
    return TestClient(app)


def _corpo(origem, **alvo):
    return {'media_request': {
        'media_type': 'audio', 'operation': 'enhance', 'content_type_override': 'music',
        'input_path': str(origem), 'output_target': {'format': 'keep', **alvo},
    }}


@pytest.fixture
def faixa(tmp_path):
    caminho = tmp_path / 'faixa.wav'
    caminho.write_bytes(_wav_bytes(0.5))
    return caminho


def test_a_rota_resolve_o_destino_com_o_sufixo_quando_cairia_no_original(client, faixa):
    r = client.post('/jobs/local', json=_corpo(faixa, conflict='overwrite'))
    assert r.status_code == 200, r.text
    assert jobs.get_job(r.json()['id'])['params']['output_path'] == \
        str(faixa.parent / 'faixa_enhanced.wav')


def test_perguntar_recusa_com_409_antes_do_job(client, faixa, tmp_path):
    (tmp_path / 'faixa.flac').write_bytes(b'ja existe')
    antes = set(jobs.jobs)
    r = client.post('/jobs/local', json=_corpo(faixa, format='flac', conflict='ask'))
    assert r.status_code == 409
    assert r.json()['detail']['path'] == str(tmp_path / 'faixa.flac')
    assert set(jobs.jobs) == antes


def test_formato_que_nao_existe_e_recusado_antes_do_job(client, faixa):
    antes = set(jobs.jobs)
    r = client.post('/jobs/local', json=_corpo(faixa, format='aiff'))
    assert r.status_code == 422
    assert r.json()['detail']['reason'] == 'format_unavailable'
    assert set(jobs.jobs) == antes
