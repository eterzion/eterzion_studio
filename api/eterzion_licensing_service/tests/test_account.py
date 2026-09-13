"""POST /activations/details -- o final da chave e o e-mail, so' para a propria
instalacao.

O e-mail e' dado pessoal: a rota exige o mesmo pedido assinado do download
(app/downloads.py), e a rota de status, que responde a quem souber um
install_id, continua sem ele.
"""
from __future__ import annotations

import base64
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app import account, downloads, licensing


@pytest.fixture
def instalacao(license_factory):
    privada = Ed25519PrivateKey.generate()
    publica = base64.b64encode(privada.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    lic = license_factory(activation_limit=2, email='cliente@example.com')
    licensing.activate_installation(lic.id, 'inst-1', publica, base64.b64encode(b'x' * 32).decode())
    return {'install_id': 'inst-1', 'privada': privada, 'licenca': lic}


def _pedido(inst, ts=None, chave=None, mensagem=None):
    ts = int(time.time()) if ts is None else ts
    texto = mensagem(inst['install_id'], ts) if mensagem else account.canonical_request(inst['install_id'], ts)
    assinatura = (chave or inst['privada']).sign(texto)
    return {'install_id': inst['install_id'], 'timestamp': ts,
            'signature_b64': base64.b64encode(assinatura).decode()}


def test_devolve_o_final_da_chave_e_o_email(client, instalacao):
    res = client.post('/activations/details', json=_pedido(instalacao))
    assert res.status_code == 200, res.text
    assert res.json() == {'license_last4': instalacao['licenca'].id[-4:], 'email': 'cliente@example.com'}


def test_nunca_devolve_a_chave_inteira(client, instalacao):
    corpo = client.post('/activations/details', json=_pedido(instalacao)).text
    assert instalacao['licenca'].id not in corpo


def test_assinatura_de_outra_chave_e_recusada(client, instalacao):
    res = client.post('/activations/details', json=_pedido(instalacao, chave=Ed25519PrivateKey.generate()))
    assert res.status_code == 401


def test_assinatura_feita_para_o_download_nao_serve_aqui(client, instalacao):
    """O proposito faz parte do texto assinado: um token de download capturado
    nao abre o e-mail."""
    res = client.post('/activations/details', json=_pedido(instalacao, mensagem=downloads.canonical_request))
    assert res.status_code == 401


def test_instalacao_desconhecida_recebe_o_mesmo_401(client, instalacao):
    pedido = _pedido(instalacao)
    pedido['install_id'] = 'nao-existe'
    res = client.post('/activations/details', json=pedido)
    assert res.status_code == 401
    assert res.json() == client.post('/activations/details', json=_pedido(
        instalacao, chave=Ed25519PrivateKey.generate())).json()


def test_horario_fora_da_folga_e_recusado(client, instalacao):
    velho = int(time.time()) - downloads.FOLGA_RELOGIO_S - 60
    assert client.post('/activations/details', json=_pedido(instalacao, ts=velho)).status_code == 401


def test_status_continua_sem_email(client, instalacao):
    """A rota sem assinatura nao pode vazar o e-mail."""
    corpo = client.get('/activations/inst-1/status').text
    assert 'cliente@example.com' not in corpo
