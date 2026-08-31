"""T037 — o tamanho-alvo de imagem, medido no arquivo que saiu.

O teste do estimador já verifica que a busca encontra uma qualidade. Este
verifica a única coisa que interessa à pessoa: **o arquivo produzido cabe no
tamanho pedido**. São afirmações diferentes, e a distância entre elas é onde o
alvo vira decoração — a busca acerta, o valor não entra nas configurações, e sai
um arquivo com a qualidade padrão que ninguém pediu.

O caminho medido é o de ponta a ponta, pela rota: é ali que a resolução do alvo
acontece, e testar o estimador isolado deixaria justamente a ligação de fora.
"""
from __future__ import annotations

import os
import random

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import jobs, media_handles
from app.compression import estimator
from app.main import app
from tests.test_compression_job import _aguardar


@pytest.fixture
def client():
    media_handles.clear()
    jobs.jobs.clear()
    with TestClient(app) as c:
        yield c
    media_handles.clear()
    jobs.jobs.clear()


@pytest.fixture
def foto(tmp_path):
    """Gradiente com ruído leve.

    Cor sólida comprime ao mínimo em qualquer qualidade e ruído puro é
    incompressível — nos dois casos o alvo seria atingido ou impossível por
    acidente do conteúdo, e o teste não diria nada sobre a busca.
    """
    rng = random.Random(11)
    largura, altura = 640, 480
    img = Image.new('RGB', (largura, altura))
    img.putdata([
        (
            min(255, x * 255 // largura + rng.randrange(-12, 13)) % 256,
            min(255, y * 255 // altura + rng.randrange(-12, 13)) % 256,
            (x + y) % 256,
        )
        for y in range(altura) for x in range(largura)
    ])
    caminho = tmp_path / 'foto.png'
    img.save(caminho)
    return caminho


def _comprimir(client, foto, destino, **corpo) -> dict:
    handle = media_handles.register_media(str(foto))
    resposta = client.post('/compression/jobs', json={
        'handle_id': handle, 'media_kind': 'image',
        'export': {'directory': str(destino)}, **corpo})
    return resposta


def test_o_arquivo_produzido_cabe_no_alvo(client, foto, tmp_path):
    destino = tmp_path / 'saida'
    destino.mkdir()
    original = os.path.getsize(foto)
    alvo_kb = original / 4 / 1000

    r = _comprimir(client, foto, destino,
                   settings={'output_format': 'jpeg'},
                   target={'value': alvo_kb, 'unit': 'KB'})
    assert r.status_code == 202, r.text

    job_id = r.json()['job_id']
    _aguardar(job_id)
    job = jobs.get_job(job_id)
    assert job['status'] == 'done', job.get('error')

    produzido = os.path.getsize(job['output_path'])
    alvo_bytes = estimator.target_to_bytes(alvo_kb, 'KB')
    # A busca é sobre uma amostra, então o resultado final pode passar um pouco.
    # A margem é declarada e apertada; passar muito seria a mesma coisa que
    # ignorar o alvo.
    assert produzido <= alvo_bytes * 1.15, (
        f'pedido ~{alvo_bytes} B, saiu {produzido} B')


def test_a_resposta_ja_traz_a_estimativa_do_alvo(client, foto, tmp_path):
    """FR-020: dizer antes. A estimativa acompanha o 202 para a interface poder
    mostrar o número sem uma segunda chamada."""
    destino = tmp_path / 'saida'
    destino.mkdir()
    alvo_kb = os.path.getsize(foto) / 4 / 1000

    corpo = _comprimir(client, foto, destino,
                       settings={'output_format': 'jpeg'},
                       target={'value': alvo_kb, 'unit': 'KB'}).json()
    assert corpo['estimate'] is not None
    assert corpo['estimate']['feasibility'] == 'ok'
    assert corpo['estimate']['resolved_settings']


def test_alvo_abaixo_do_piso_e_recusado_antes_de_criar_job(client, foto, tmp_path):
    """Recusar depois de a barra começar já custou o tempo da pessoa (FR-064)."""
    destino = tmp_path / 'saida'
    destino.mkdir()
    antes = len(jobs.jobs)

    r = _comprimir(client, foto, destino,
                   settings={'output_format': 'jpeg'},
                   target={'value': 0.5, 'unit': 'KB'})
    assert r.status_code == 422
    assert r.json()['detail']['reason'] == 'target_below_floor'
    assert len(jobs.jobs) == antes
    assert not list(destino.iterdir()), 'a recusa escreveu arquivo'


def test_sem_alvo_a_qualidade_pedida_e_respeitada(client, foto, tmp_path):
    """O contraponto: sem alvo, nada é resolvido por busca, e a qualidade que a
    pessoa escolheu é a que vale.

    Sem este teste, uma resolução de alvo que rodasse sempre passaria
    despercebida — o arquivo sairia menor e pareceria certo.
    """
    destino = tmp_path / 'saida'
    destino.mkdir()

    alto = _comprimir(client, foto, destino, settings={'output_format': 'jpeg', 'quality': 95})
    _aguardar(alto.json()['job_id'])
    caminho_alto = jobs.get_job(alto.json()['job_id'])['output_path']

    baixo = _comprimir(client, foto, destino, settings={'output_format': 'jpeg', 'quality': 30})
    _aguardar(baixo.json()['job_id'])
    caminho_baixo = jobs.get_job(baixo.json()['job_id'])['output_path']

    assert os.path.getsize(caminho_alto) > os.path.getsize(caminho_baixo)
