"""O upscale de video e' entregue na pasta escolhida, pelo nucleo de destino.

Antes o resultado ficava so' na pasta interna do app, com o nome do job
(`job_1a2b3c4d.mp4`): a pasta do painel de exportacao do Video era ignorada
sempre que um modelo rodava.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import jobs
from app.config import settings
from app.routes import jobs_router

FIXTURES = Path(__file__).resolve().parent / 'fixtures'


@pytest.fixture
def interna(tmp_path, monkeypatch):
    pasta = tmp_path / 'interna'
    pasta.mkdir()
    monkeypatch.setattr(settings, 'outputs_dir', str(pasta))
    return pasta


# ------------------------------------------------------------------ o job --


def _job_de_video(origem, params):
    job_id = jobs.create_job(origem, 'clip.mp4', params, media_type='video', operation='enhance',
                             content_type_detected='real_video')
    jobs.jobs[job_id]['status'] = 'queued'
    return job_id


def test_o_resultado_vai_para_o_destino_e_nao_fica_na_pasta_interna(
        tmp_path, interna, real_input_file, default_job_params, fake_supervisor):
    destino = tmp_path / 'saida' / 'clip_upscaled.mp4'
    params = default_job_params(output_path=str(destino),
                                output_target={'format': 'mp4', 'conflict': 'rename'})
    job_id = _job_de_video(real_input_file, params)

    asyncio.run(jobs._process_job(job_id))

    job = jobs.get_job(job_id)
    assert job['status'] == 'done', job.get('error')
    assert job['output_path'] == str(destino)
    assert destino.read_bytes() == fake_supervisor._write_master_bytes
    assert job['output_meta']['size_bytes'] == destino.stat().st_size
    assert list(interna.iterdir()) == []
    assert [p.name for p in destino.parent.iterdir()] == ['clip_upscaled.mp4']


def test_sem_destino_continua_na_pasta_interna(
        interna, real_input_file, default_job_params, fake_supervisor):
    # Clientes que nao mandam `output_target` nao mudam de comportamento.
    job_id = _job_de_video(real_input_file, default_job_params())
    asyncio.run(jobs._process_job(job_id))
    assert jobs.get_job(job_id)['output_path'] == str(interna / f'{job_id}.mp4')


def test_um_arquivo_que_apareceu_na_fila_nao_e_sobrescrito(
        tmp_path, interna, real_input_file, default_job_params, fake_supervisor):
    destino = tmp_path / 'clip_upscaled.mp4'
    params = default_job_params(output_path=str(destino),
                                output_target={'format': 'mp4', 'conflict': 'rename'})
    job_id = _job_de_video(real_input_file, params)
    destino.write_bytes(b'gravado enquanto o job esperava')

    asyncio.run(jobs._process_job(job_id))

    assert destino.read_bytes() == b'gravado enquanto o job esperava'
    assert jobs.get_job(job_id)['output_path'] == str(tmp_path / 'clip_upscaled (1).mp4')


# ----------------------------------------------------------------- a rota --


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(jobs_router, prefix='/jobs')
    return TestClient(app)


@pytest.fixture
def video(tmp_path):
    fonte = FIXTURES / 'curto.mp4'
    if not fonte.exists():
        pytest.skip('fixtures ausentes — rode tests/fixtures/make_video_fixtures.py')
    copia = tmp_path / 'clip.mp4'
    copia.write_bytes(fonte.read_bytes())
    return copia


def _corpo(video, **alvo):
    return {'media_request': {
        'media_type': 'video', 'operation': 'enhance', 'content_type_override': 'real_video',
        'scale': '2x', 'input_path': str(video), 'secondary_elements_ack': True,
        'output_target': {'format': 'mp4', **alvo},
    }}


def test_a_rota_resolve_o_destino_antes_do_job(client, video):
    # Mesma pasta, mesmo nome e mesmo formato: cai no original, que nunca e'
    # sobrescrito -- nem com "sobrescrever".
    r = client.post('/jobs/local', json=_corpo(video, conflict='overwrite'))
    assert r.status_code == 200, r.text
    params = jobs.get_job(r.json()['id'])['params']
    assert params['output_path'] == str(video.parent / 'clip_upscaled.mp4')


def test_perguntar_recusa_com_409_antes_do_job(client, video, tmp_path):
    (tmp_path / 'saida').mkdir()
    (tmp_path / 'saida' / 'clip.mp4').write_bytes(b'ja existe')
    antes = set(jobs.jobs)
    r = client.post('/jobs/local', json=_corpo(video, directory=str(tmp_path / 'saida'),
                                               conflict='ask'))
    assert r.status_code == 409
    assert r.json()['detail']['reason'] == 'conflict'
    assert r.json()['detail']['path'] == str(tmp_path / 'saida' / 'clip.mp4')
    assert set(jobs.jobs) == antes
