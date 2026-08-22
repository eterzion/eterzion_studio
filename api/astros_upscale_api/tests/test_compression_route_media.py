"""T025e/T025f (lado do backend) — importar qualquer mídia, e só dizer o que se sabe.

Duas propriedades:

- o tipo vem do conteúdo, nunca da extensão (FR-007);
- o que a sondagem não obteve chega **ausente**, nunca zerado (FR-010) — `None`
  fala da sondagem, `0` falaria da mídia.
"""
from __future__ import annotations

import shutil

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import media_handles
from app.main import app


@pytest.fixture
def client():
    media_handles.clear()
    with TestClient(app) as c:
        yield c
    media_handles.clear()


@pytest.fixture
def png(tmp_path):
    caminho = tmp_path / 'foto.png'
    Image.new('RGB', (64, 48), (30, 90, 200)).save(caminho)
    return caminho


def test_importa_uma_imagem_e_descreve_o_que_sondou(client, png):
    r = client.post('/compression/media', json={'path': str(png)})
    assert r.status_code == 201, r.text
    corpo = r.json()

    assert corpo['media_kind'] == 'image'
    assert corpo['display_name'] == 'foto.png'
    assert (corpo['width'], corpo['height']) == (64, 48)
    assert corpo['size_bytes'] > 0


def test_o_caminho_nao_volta_na_resposta(client, png):
    """Não há campo de caminho no schema, e nunca pode haver. O teste existe
    porque acrescentar um seria fácil e passaria por revisão."""
    corpo = client.post('/compression/media', json={'path': str(png)}).json()
    assert 'path' not in corpo
    assert str(png) not in str(corpo)


def test_a_extensao_nao_decide(client, png, tmp_path):
    """Um JPEG chamado `.png`. Confiar na extensão ofereceria os controles do
    formato errado e falharia depois — a falha tardia que o Princípio XIII
    existe para evitar."""
    jpeg = tmp_path / 'real.jpg'
    Image.new('RGB', (32, 32), (200, 10, 10)).save(jpeg, 'JPEG')
    mentiroso = tmp_path / 'mentiroso.png'
    shutil.copyfile(jpeg, mentiroso)

    corpo = client.post('/compression/media', json={'path': str(mentiroso)}).json()
    assert corpo['media_kind'] == 'image'
    # A detecção olhou os bytes: um PNG de verdade daria as mesmas dimensões,
    # então o que prova a leitura do conteúdo é o arquivo ter sido aceito e
    # descrito com as dimensões do JPEG que ele realmente é.
    assert (corpo['width'], corpo['height']) == (32, 32)


def test_campo_nao_sondado_chega_ausente_e_nao_zerado(client, png):
    """Uma imagem não tem duração, bitrate, canais nem taxa de amostragem. A
    resposta tem que **omitir** os quatro, não devolvê-los como zero."""
    corpo = client.post('/compression/media', json={'path': str(png)}).json()
    for campo in ('duration_seconds', 'audio_bitrate_bps', 'channels', 'sample_rate',
                  'video_codec', 'frame_rate'):
        assert corpo.get(campo) is None, f'{campo} veio preenchido para uma imagem'


def test_arquivo_inexistente_e_404(client, tmp_path):
    r = client.post('/compression/media', json={'path': str(tmp_path / 'nada.png')})
    assert r.status_code == 404
    assert r.json()['detail']['reason'] == 'not_found'


def test_arquivo_que_nao_e_midia_e_415(client, tmp_path):
    texto = tmp_path / 'leiame.txt'
    texto.write_text('isto não é mídia', encoding='utf-8')
    r = client.post('/compression/media', json={'path': str(texto)})
    assert r.status_code == 415
    assert r.json()['detail']['reason'] == 'unsupported_media'


def test_campo_desconhecido_e_recusado(client, png):
    r = client.post('/compression/media', json={'path': str(png), 'media_kind': 'image'})
    assert r.status_code == 422
