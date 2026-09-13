"""Credencial de download do CDN privado do Studio (app/cdn.py).

O servidor de licencas so' emite a assinatura do CDN para um pedido assinado
pela chave desta instalacao. Estes testes conferem o lado do app: o pedido sai
no formato que o servidor verifica, o token e' reaproveitado ate' a hora de
renovar, uma falha nao faz cada job esperar o timeout, e o worker recebe so' o
necessario para montar a URL.
"""
from __future__ import annotations

import base64
import io
import json
import time
import urllib.error

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app import cdn
from app.config import settings

TOKEN = {'base': 'https://cdn.eterzion.com/studio', 'scope': 'studio', 'exp': 1788021600,
         'sig': 'ab' * 32, 'token': '1788021600.' + 'ab' * 32}


@pytest.fixture(autouse=True)
def estado_limpo(monkeypatch):
    monkeypatch.setattr(settings, 'licensing_service_url', 'https://licencas.invalido')
    monkeypatch.setattr(cdn, '_cache', None)
    monkeypatch.setattr(cdn, '_falhou_em', 0.0)


class _Resposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _servidor(monkeypatch, responder):
    pedidos = []

    def urlopen(req, timeout=None):
        pedidos.append(req)
        return responder(req)

    monkeypatch.setattr(cdn.urllib.request, 'urlopen', urlopen)
    return pedidos


def test_o_pedido_sai_assinado_pela_chave_da_instalacao(monkeypatch):
    from app import security

    token = dict(TOKEN, renew_after=time.time() + 3600)
    pedidos = _servidor(monkeypatch, lambda req: _Resposta(json.dumps(token).encode()))
    assert cdn.download_token() == token

    req = pedidos[0]
    assert req.full_url == 'https://licencas.invalido/downloads/token'
    # Sem User-Agent do app, o Cloudflare de license.eterzion.com barra o
    # `Python-urllib` com "error code: 1010" -- visto em producao.
    assert req.get_header('User-agent', '').startswith('EterzionStudio/')
    corpo = json.loads(req.data)
    identidade = security.ensure_identity()
    assert corpo['install_id'] == identidade.install_id
    assert abs(corpo['timestamp'] - time.time()) < 60
    # Exatamente o que o servidor verifica (eterzion_licensing_service/app/downloads.py).
    mensagem = f"eterzion-download-token:{corpo['install_id']}:{corpo['timestamp']}".encode()
    Ed25519PublicKey.from_public_bytes(identidade.signing_public_key_bytes).verify(
        base64.b64decode(corpo['signature_b64']), mensagem)


def test_reaproveita_ate_a_hora_de_renovar(monkeypatch):
    pedidos = _servidor(monkeypatch, lambda req: _Resposta(json.dumps(
        dict(TOKEN, renew_after=time.time() + 3600)).encode()))
    cdn.download_token()
    cdn.download_token()
    assert len(pedidos) == 1


def test_falha_nao_faz_cada_job_esperar_o_timeout(monkeypatch):
    """O token e' pedido na thread que manda cada job ao worker. Com o servidor
    fora do ar, sem a espera, cada job pagaria os 10 s de timeout."""
    def fora_do_ar(req):
        raise urllib.error.URLError('recusada')

    pedidos = _servidor(monkeypatch, fora_do_ar)
    assert cdn.download_token() is None
    assert cdn.download_token() is None
    assert len(pedidos) == 1


def test_licenca_inativa_nao_e_erro(monkeypatch):
    def recusa(req):
        raise urllib.error.HTTPError(req.full_url, 403, 'licenca_inativa', {}, None)

    _servidor(monkeypatch, recusa)
    assert cdn.download_token() is None


def test_sem_servico_de_licencas_nem_tenta(monkeypatch):
    monkeypatch.setattr(settings, 'licensing_service_url', '')
    pedidos = _servidor(monkeypatch, lambda req: pytest.fail('nao devia pedir'))
    assert cdn.download_token() is None
    assert pedidos == []


def test_url_do_modelo_leva_a_assinatura_na_query():
    url = cdn.mirror_url_for('4x modelo.safetensors', TOKEN)
    assert url.startswith('https://cdn.eterzion.com/studio/models/4x%20modelo.safetensors?')
    assert f"exp={TOKEN['exp']}" in url and f"sig={TOKEN['sig']}" in url


def test_worker_recebe_so_o_necessario(monkeypatch):
    from app import jobs

    monkeypatch.setattr(cdn, 'download_token', lambda: dict(TOKEN, renew_after=0, token='x'))
    assert jobs._cdn_token_for_worker() == {'base': TOKEN['base'], 'exp': TOKEN['exp'], 'sig': TOKEN['sig']}
    monkeypatch.setattr(cdn, 'download_token', lambda: None)
    assert jobs._cdn_token_for_worker() is None


def test_worker_sem_token_nao_liga_espelho():
    from eterzion_upscale import processing

    cdn.install_mirror_from_message(None)
    assert processing._mirror_url_for('x.pth') is None
    cdn.install_mirror_from_message({'base': TOKEN['base'], 'exp': 1, 'sig': 'ab'})
    try:
        assert processing._mirror_url_for('x.pth') == 'https://cdn.eterzion.com/studio/models/x.pth?exp=1&sig=ab'
    finally:
        processing.set_mirror_url_factory(None)


def test_rota_local_do_updater(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routes import downloads_router

    app = FastAPI()
    app.include_router(downloads_router, prefix='/downloads')
    cliente = TestClient(app)

    monkeypatch.setattr(cdn, 'download_token', lambda: None)
    assert cliente.get('/downloads/token').status_code == 204

    monkeypatch.setattr(cdn, 'download_token', lambda: dict(TOKEN, renew_after=123))
    dados = cliente.get('/downloads/token').json()
    assert dados == {'base': TOKEN['base'], 'token': TOKEN['token'], 'exp': TOKEN['exp'], 'renew_after': 123}
