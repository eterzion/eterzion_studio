"""T012/T013 — `GET /compression/capabilities` na rota, não só no módulo.

O teste do módulo prova que a lógica está certa. Este prova que o que sai pelo
fio continua certo: schema, serialização e a guarda de vazamento aplicada à
resposta HTTP real, que é onde o Princípio V pode se perder sem ninguém notar.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.compression import config
from app.main import app

# Mesma lista do teste do módulo, repetida de propósito: se alguém afrouxar uma
# delas, a outra ainda reprova.
NOMES_INTERNOS = (
    'nvenc', 'qsv', 'amf', 'vaapi', 'videotoolbox',
    'libx264', 'libx265', 'x264', 'x265',
    'libvpx', 'libaom', 'libsvtav1', 'librav1e',
    'libopus', 'libvorbis', 'libmp3lame', 'libwebp', 'pcm_s16le',
    'opencv', 'cv2', 'pillow',
)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_responde_as_quatro_midias(client):
    corpo = client.get('/compression/capabilities').json()
    assert set(corpo) == {'image', 'video', 'audio', 'animation'}


def test_nenhuma_implementacao_e_nomeada_pelo_fio(client):
    texto = client.get('/compression/capabilities').text.lower()
    vazados = [n for n in NOMES_INTERNOS if n in texto]
    assert not vazados, f'nomes internos na resposta HTTP: {vazados}'


def test_os_codecs_declarados_aparecem_todos(client):
    """Ausência silenciosa é pior que indisponibilidade declarada: a interface
    não conseguiria explicar o que não recebeu."""
    corpo = client.get('/compression/capabilities').json()
    valores = {e['value'] for e in corpo['video']['video_codecs']}
    assert valores == set(config.VIDEO_CODEC_ENCODERS)


def test_a_compatibilidade_so_lista_codecs_que_a_resposta_diz_disponiveis(client):
    """Coerência interna da resposta: oferecer numa chave o que a outra recusa
    seria a interface acertando por sorte."""
    corpo = client.get('/compression/capabilities').json()
    disponiveis = {e['value'] for e in corpo['video']['video_codecs'] if e['available']}
    for combinacao in corpo['video']['compatibility'].values():
        assert set(combinacao['video']) <= disponiveis


def test_o_schema_recusa_campo_desconhecido():
    """`extra='forbid'` em toda a árvore: um campo novo que a interface não
    conhece é erro de contrato, não algo a ignorar em silêncio."""
    from app.schemas import CapabilityEntry

    with pytest.raises(Exception):
        CapabilityEntry(value='x', available=True, campo_inventado=1)
