"""T017 — `POST /compression/estimate` pelo fio.

A propriedade mais importante desta rota não é o número que ela devolve: é que
chamá-la não faz nada. Ela é acionada a cada movimento de slider, e uma
estimativa com efeito colateral seriam dezenas de arquivos por sessão.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import media_handles
from app.main import app


@pytest.fixture
def client():
    media_handles.clear()
    with TestClient(app) as test_client:
        yield test_client
    media_handles.clear()


@pytest.fixture
def imagem(tmp_path):
    import random

    rng = random.Random(1)
    img = Image.new('RGB', (640, 480))
    img.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256))
                 for _ in range(640 * 480)])
    caminho = tmp_path / 'foto.png'
    img.save(caminho)
    return str(caminho)


def _handle(imagem: str) -> str:
    """A Central reusa o mesmo registro do Princípio XIII, por `register_media`,
    que detecta o tipo pelo conteúdo — `register` é do editor de vídeo e recusa
    qualquer coisa que não seja vídeo."""
    return media_handles.register_media(imagem)


def test_estima_uma_imagem(client, imagem):
    handle = _handle(imagem)
    r = client.post('/compression/estimate', json={
        'handle_id': handle, 'media_kind': 'image',
        'settings': {'output_format': 'jpeg', 'quality': 80},
    })
    assert r.status_code == 200
    corpo = r.json()
    assert corpo['estimated_bytes'] > 0
    assert corpo['confidence'] in ('measured_sample', 'derived')
    assert corpo['assumptions']


def test_a_estimativa_nao_cria_job_nem_escreve_arquivo(client, imagem, tmp_path):
    from app import jobs

    handle = _handle(imagem)
    jobs_antes = len(jobs.jobs)
    arquivos_antes = set(os.listdir(tmp_path))

    for qualidade in (30, 50, 70, 90):
        client.post('/compression/estimate', json={
            'handle_id': handle, 'media_kind': 'image',
            'settings': {'output_format': 'webp', 'quality': qualidade},
        })

    assert len(jobs.jobs) == jobs_antes
    assert set(os.listdir(tmp_path)) == arquivos_antes


def test_a_mesma_pergunta_devolve_a_mesma_resposta(client, imagem):
    """Idempotente: a interface recalcula a cada mudança, e um número que
    oscilasse sozinho faria a estimativa parecer instável."""
    handle = _handle(imagem)
    corpo = {'handle_id': handle, 'media_kind': 'image',
             'settings': {'output_format': 'jpeg', 'quality': 75}}
    primeira = client.post('/compression/estimate', json=corpo).json()
    segunda = client.post('/compression/estimate', json=corpo).json()
    assert primeira['estimated_bytes'] == segunda['estimated_bytes']


def test_alvo_impossivel_responde_200_com_below_floor(client, imagem):
    """Não é erro: o alvo é pergunta legítima e a resposta é "só destruindo a
    mídia". FR-020 pede dizer antes — e dizer é responder."""
    handle = _handle(imagem)
    r = client.post('/compression/estimate', json={
        'handle_id': handle, 'media_kind': 'image',
        'settings': {'output_format': 'jpeg'},
        'target': {'value': 1, 'unit': 'KB'},
    })
    assert r.status_code == 200
    assert r.json()['feasibility'] == 'below_floor'


def test_alvo_atingivel_devolve_as_configuracoes_derivadas(client, imagem):
    handle = _handle(imagem)
    original = os.path.getsize(imagem)
    r = client.post('/compression/estimate', json={
        'handle_id': handle, 'media_kind': 'image',
        'settings': {'output_format': 'jpeg'},
        'target': {'value': original / 4 / 1000, 'unit': 'KB'},
    })
    corpo = r.json()
    assert corpo['feasibility'] == 'ok'
    assert corpo['resolved_settings']['quality'] >= 1


def test_handle_desconhecido_e_404(client):
    r = client.post('/compression/estimate', json={
        'handle_id': 'vh_naoexiste', 'media_kind': 'image', 'settings': {},
    })
    assert r.status_code == 404


def test_campo_desconhecido_e_recusado(client, imagem):
    """`extra='forbid'`: um campo que a rota não conhece é erro de contrato,
    nunca algo a ignorar em silêncio."""
    r = client.post('/compression/estimate', json={
        'handle_id': _handle(imagem), 'media_kind': 'image',
        'settings': {}, 'campo_inventado': 1,
    })
    assert r.status_code == 422


def test_a_resposta_nao_nomeia_biblioteca(client, imagem):
    texto = client.post('/compression/estimate', json={
        'handle_id': _handle(imagem), 'media_kind': 'image',
        'settings': {'output_format': 'avif', 'quality': 60},
    }).text.lower()
    for nome in ('pillow', 'opencv', 'cv2', 'ffmpeg', 'libaom'):
        assert nome not in texto
