"""GET /image/export-options — o espelho, para imagem, da pergunta que
`/video/export-options` responde para vídeo: o que esta máquina consegue
escrever, não o que a lista permite.

A exportação de imagem re-codifica pelo OpenCV, e builds de OpenCV diferem em
quais codecs carregam — WebP e TIFF são opcionais, e `opencv-python-headless`
não é a mesma build que a completa. Oferecer um formato que a build não escreve
faz a exportação falhar depois da escolha, que é o que o Princípio XIII proíbe.
"""
from __future__ import annotations

from typing import get_args

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import ExportFormat
from eterzion_upscale.media import image_format_works


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_reports_every_permitted_format(client):
    """A rota e o schema do pedido têm que falar do mesmo conjunto, ou a
    interface oferece o que a rota recusa."""
    body = client.get('/image/export-options').json()
    assert {entry['value'] for entry in body['formats']} == set(get_args(ExportFormat))


def test_availability_comes_from_a_real_probe(client):
    """Não de uma tabela: o teste compara a resposta com o que a build responde
    quando de fato mandam ela codificar."""
    body = client.get('/image/export-options').json()
    for entry in body['formats']:
        assert entry['available'] == image_format_works(f".{entry['value']}")


def test_an_unavailable_format_carries_a_reason_and_an_available_one_does_not(client):
    for entry in client.get('/image/export-options').json()['formats']:
        if entry['available']:
            assert entry['unavailable_reason'] is None
        else:
            assert entry['unavailable_reason'] == 'unsupported_build'


def test_the_reason_is_a_key_not_a_library_name(client):
    """Princípio V nesta superfície também: 'OpenCV' não é assunto do cliente,
    e a interface é quem traduz a chave (Princípio XIV)."""
    corpo = client.get('/image/export-options').text
    for vazado in ('opencv', 'cv2', 'libwebp', 'libjpeg'):
        assert vazado not in corpo.lower()


def test_png_is_always_writable():
    """Se nem PNG passa, quem quebrou foi a sonda, não a máquina — o OpenCV não
    existe sem ele."""
    assert image_format_works('.png')


def test_an_invented_extension_is_not_writable():
    assert not image_format_works('.naoexiste')
