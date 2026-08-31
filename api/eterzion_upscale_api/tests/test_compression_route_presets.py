"""T020 — as rotas de preset pelo fio."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.compression import presets
from app.main import app


@pytest.fixture(autouse=True)
def armazenamento(tmp_path, monkeypatch):
    monkeypatch.setattr(presets, '_store_path',
                        lambda: str(tmp_path / 'compression-presets.json'))


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_lista_as_tres_origens(client):
    origens = {p['origin'] for p in client.get('/compression/presets').json()['presets']}
    assert {'builtin', 'platform'} <= origens


def test_filtra_por_tipo_de_midia(client):
    corpo = client.get('/compression/presets', params={'media_kind': 'audio'}).json()
    assert {p['media_kind'] for p in corpo['presets']} == {'audio'}


def test_cria_renomeia_e_exclui(client):
    criado = client.post('/compression/presets', json={
        'name': 'Web 85', 'media_kind': 'image',
        'settings': {'quality': 85, 'output_format': 'webp'}}).json()
    assert criado['origin'] == 'user'

    renomeado = client.patch(f"/compression/presets/{criado['id']}",
                             json={'name': 'Web 90'}).json()
    assert renomeado['name'] == 'Web 90'

    assert client.delete(f"/compression/presets/{criado['id']}").status_code == 204
    ids = {p['id'] for p in client.get('/compression/presets').json()['presets']}
    assert criado['id'] not in ids


def test_alterar_um_interno_responde_409(client):
    """Em vez de aceitar e ignorar. Aceitar prometeria uma alteração que não
    acontece."""
    interno = next(p for p in client.get('/compression/presets').json()['presets']
                   if p['origin'] == 'builtin')
    r = client.patch(f"/compression/presets/{interno['id']}", json={'name': 'Meu'})
    assert r.status_code == 409
    assert r.json()['detail']['reason'] == 'readonly_preset'


def test_configuracao_incompativel_com_a_midia_e_422(client):
    r = client.post('/compression/presets', json={
        'name': 'Errado', 'media_kind': 'image', 'settings': {'crf': 20}})
    assert r.status_code == 422
    assert r.json()['detail']['reason'] == 'incompatible_settings'


def test_duplicar_um_interno_cria_um_do_usuario(client):
    interno = next(p for p in client.get('/compression/presets').json()['presets']
                   if p['origin'] == 'builtin' and p['media_kind'] == 'image')
    copia = client.post(f"/compression/presets/{interno['id']}/duplicate",
                        params={'name': 'Minha versão'}).json()
    assert copia['origin'] == 'user'
    assert copia['settings'] == interno['settings']


def test_preset_desconhecido_e_404(client):
    assert client.delete('/compression/presets/user.naoexiste').status_code == 404


def test_campo_desconhecido_e_recusado(client):
    r = client.post('/compression/presets', json={
        'name': 'X', 'media_kind': 'image', 'settings': {}, 'inventado': 1})
    assert r.status_code == 422


def test_a_resposta_nao_nomeia_encoder(client):
    """Os presets de vídeo carregam CRF e preset de velocidade — vocabulário que
    a exceção da v4.0.0 permite. Nome de encoder, não."""
    texto = client.get('/compression/presets').text.lower()
    for nome in ('nvenc', 'libx264', 'libvpx', 'libaom', 'libsvtav1', 'qsv', 'amf'):
        assert nome not in texto
