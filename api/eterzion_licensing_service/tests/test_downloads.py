"""POST /downloads/token — link de download so' para instalacao ativada.

O Worker de cdn.eterzion.com confere HMAC-SHA256 de "studio:<exp>". Este
servico e' quem decide se uma instalacao merece essa assinatura, e o pedido
precisa vir assinado pela chave Ed25519 que a instalacao registrou na ativacao:
o install_id sozinho circula em URLs e logs e nao prova nada.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app import downloads, licensing
from app.config import settings

CHAVE = 'k' * 64


@pytest.fixture(autouse=True)
def chave_do_studio(monkeypatch):
    monkeypatch.setattr(settings, 'studio_cdn_signing_key', CHAVE)


@pytest.fixture
def instalacao_ativa(license_factory):
    """Uma instalacao ativada de verdade, com a chave privada em maos para
    assinar como o app assinaria."""
    privada = Ed25519PrivateKey.generate()
    publica = base64.b64encode(privada.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    lic = license_factory(activation_limit=2)
    licensing.activate_installation(lic.id, 'inst-1', publica, base64.b64encode(b'x' * 32).decode())
    return {'install_id': 'inst-1', 'privada': privada, 'licenca': lic}


def _pedido(inst, ts=None, chave=None):
    ts = int(time.time()) if ts is None else ts
    assinatura = (chave or inst['privada']).sign(downloads.canonical_request(inst['install_id'], ts))
    return {'install_id': inst['install_id'], 'timestamp': ts,
            'signature_b64': base64.b64encode(assinatura).decode()}


def test_instalacao_ativa_recebe_a_assinatura_que_o_worker_confere(client, instalacao_ativa):
    res = client.post('/downloads/token', json=_pedido(instalacao_ativa))
    assert res.status_code == 200, res.text
    dados = res.json()
    esperado = hmac.new(CHAVE.encode(), f"studio:{dados['exp']}".encode(), hashlib.sha256).hexdigest()
    assert dados['sig'] == esperado
    assert dados['scope'] == 'studio'
    assert dados['token'] == f"{dados['exp']}.{dados['sig']}"
    assert dados['base'] == 'https://cdn.eterzion.com/studio'
    assert time.time() < dados['renew_after'] < dados['exp']


def test_mesmo_vetor_do_catalogo():
    """Byte a byte o esquema do signed-url.service.ts do eterzion_assets:
    chave como string UTF-8, mensagem "<escopo>:<exp>", hex minusculo."""
    assert downloads.assinar_escopo('segredo', 1788021600) == hmac.new(
        b'segredo', b'studio:1788021600', hashlib.sha256).hexdigest()


def test_assinatura_de_outra_chave_e_recusada(client, instalacao_ativa):
    impostor = Ed25519PrivateKey.generate()
    res = client.post('/downloads/token', json=_pedido(instalacao_ativa, chave=impostor))
    assert res.status_code == 401


def test_instalacao_desconhecida_recebe_o_mesmo_401(client, instalacao_ativa):
    """Mesmo codigo e mesma resposta que assinatura errada: distinguir os dois
    ensinaria quais install_id existem."""
    pedido = _pedido(instalacao_ativa)
    pedido['install_id'] = 'nao-existe'
    res = client.post('/downloads/token', json=pedido)
    assert res.status_code == 401
    assert res.json() == client.post('/downloads/token', json=_pedido(
        instalacao_ativa, chave=Ed25519PrivateKey.generate())).json()


def test_horario_fora_da_folga_e_recusado(client, instalacao_ativa):
    """Uma assinatura capturada nao vale depois de alguns minutos."""
    velho = int(time.time()) - downloads.FOLGA_RELOGIO_S - 60
    assert client.post('/downloads/token', json=_pedido(instalacao_ativa, ts=velho)).status_code == 401


def test_licenca_revogada_nao_baixa(client, instalacao_ativa):
    licensing.set_license_status(instalacao_ativa['licenca'].id, 'revoked')
    res = client.post('/downloads/token', json=_pedido(instalacao_ativa))
    assert res.status_code == 403
    assert res.json()['detail'] == 'licenca_inativa'


def test_sem_chave_configurada_a_rota_fica_desligada(client, instalacao_ativa, monkeypatch):
    monkeypatch.setattr(settings, 'studio_cdn_signing_key', '')
    assert client.post('/downloads/token', json=_pedido(instalacao_ativa)).status_code == 503


def test_exp_alinhado_e_estavel_na_janela():
    """Todos que pedem na mesma janela recebem o mesmo link -- aproveita o
    cache da borda."""
    a = downloads._exp_alinhado(1_000_000, 21600, 3600)
    b = downloads._exp_alinhado(1_000_000 + 100, 21600, 3600)  # mesma janela de 1 h
    assert a % 3600 == 0 and a >= 1_000_000 + 21600
    assert a == b
