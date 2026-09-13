"""Links de download do Studio: só para instalação ativada, com licença ativa.

Os instaladores e os modelos do Studio ficam num bucket PRIVADO do R2, servido
pelo Worker de `cdn.eterzion.com` (repositório eterzion_assets). O Worker não
consulta ninguém: ele confere um HMAC-SHA256 de `"studio:<exp>"` com a chave
que ele e este serviço compartilham. Este módulo é quem decide se uma
instalação merece essa assinatura.

Por que o pedido precisa vir ASSINADO pela instalação, e não só trazer o
`install_id`: o `install_id` circula em URLs e logs, não é segredo. Quem o
descobrisse pegaria links de download no lugar de uma instalação ativada. Cada
instalação registra uma chave Ed25519 na ativação
(`installations.signing_public_key_b64`), e o app assina
`"eterzion-download-token:<install_id>:<unix_ts>"` com a chave privada, que
nunca sai da máquina dele.

Formato da assinatura do Worker (o mesmo do catálogo do eterzion_assets,
`signed-url.service.ts`): hex minúsculo de HMAC-SHA256, chave = bytes UTF-8 da
string da chave, mensagem = `"<escopo>:<exp>"`. O escopo aqui é sempre
`studio`, e a chave é EXCLUSIVA do Studio: se este serviço tivesse a chave do
catálogo, poderia assinar qualquer escopo dele, e trocá-la quebraria o painel e
o servidor do jogo.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import math
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app import licensing
from app.config import settings

ESCOPO = 'studio'
PROPOSITO = 'eterzion-download-token'
# Relógio da máquina do usuário x relógio da VPS. Cinco minutos cobre fuso mal
# configurado sem deixar uma assinatura capturada valer por muito tempo.
FOLGA_RELOGIO_S = 300


class DownloadTokenError(Exception):
    def __init__(self, status: int, motivo: str):
        super().__init__(motivo)
        self.status = status
        self.motivo = motivo


def canonical_request(install_id: str, timestamp: int) -> bytes:
    return f'{PROPOSITO}:{install_id}:{timestamp}'.encode('utf-8')


def assinar_escopo(chave: str, exp: int) -> str:
    """O mesmo HMAC que o Worker confere."""
    return hmac.new(chave.encode('utf-8'), f'{ESCOPO}:{exp}'.encode('utf-8'), hashlib.sha256).hexdigest()


def _exp_alinhado(agora: float, ttl: int, alinhamento: int) -> int:
    """Alinhar a expiração faz o link ser o MESMO para todos durante a janela --
    o que deixa o cache da borda do Cloudflare ser aproveitado entre usuários
    (a chave de cache do Worker ignora a query, mas o link estável também ajuda
    o updater a não refazer downloads)."""
    alvo = agora + ttl
    return int(math.ceil(alvo / alinhamento) * alinhamento) if alinhamento > 0 else int(alvo)


def _verifica_assinatura(chave_publica_b64: str, mensagem: bytes, assinatura_b64: str) -> bool:
    try:
        chave = Ed25519PublicKey.from_public_bytes(base64.b64decode(chave_publica_b64))
        chave.verify(base64.b64decode(assinatura_b64, validate=True), mensagem)
        return True
    except (InvalidSignature, ValueError, binascii.Error):
        return False


def verificar_pedido(install_id: str, timestamp: int, assinatura_b64: str, proposito: str,
                     agora: float | None = None) -> None:
    """Confere que o pedido veio da propria instalacao: assinatura Ed25519 de
    `"<proposito>:<install_id>:<unix_ts>"` com a chave registrada na ativacao,
    dentro da folga de relogio. O proposito no texto assinado impede que uma
    assinatura feita para uma rota sirva em outra.

    Erros com o mesmo 401 para "instalação desconhecida" e "assinatura errada":
    distinguir os dois ensinaria a quem tenta adivinhar quais install_id existem.
    """
    agora = time.time() if agora is None else agora
    if abs(agora - timestamp) > FOLGA_RELOGIO_S:
        raise DownloadTokenError(401, 'nao_autorizado')
    instalacao = licensing.get_installation(install_id)
    mensagem = f'{proposito}:{install_id}:{timestamp}'.encode('utf-8')
    if instalacao is None or not _verifica_assinatura(
            instalacao['signing_public_key_b64'], mensagem, assinatura_b64):
        raise DownloadTokenError(401, 'nao_autorizado')


def emitir_token(install_id: str, timestamp: int, assinatura_b64: str, agora: float | None = None) -> dict:
    """Confere quem pede e devolve a assinatura de download do escopo `studio`."""
    chave = settings.studio_cdn_signing_key
    if not chave:
        raise DownloadTokenError(503, 'downloads_nao_configurados')
    agora = time.time() if agora is None else agora

    verificar_pedido(install_id, timestamp, assinatura_b64, PROPOSITO, agora)

    licenca = licensing.installation_license(install_id)
    if licenca is None or licenca.status != 'active':
        raise DownloadTokenError(403, 'licenca_inativa')
    licensing.touch_installation(install_id)

    exp = _exp_alinhado(agora, settings.studio_cdn_token_ttl_seconds, settings.studio_cdn_token_align_seconds)
    assinatura = assinar_escopo(chave, exp)
    return {
        'base': settings.studio_cdn_base.rstrip('/'),
        'scope': ESCOPO,
        'exp': exp,
        'sig': assinatura,
        # O updater manda isto no header Authorization; o download de modelos
        # usa exp/sig na query. O Worker aceita os dois.
        'token': f'{exp}.{assinatura}',
        # Renovar com folga, antes de o link vencer no meio de um download.
        'renew_after': exp - min(1800, settings.studio_cdn_token_ttl_seconds // 4),
    }
