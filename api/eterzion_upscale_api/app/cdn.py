"""Credencial de download do CDN do Studio (instaladores e modelos no R2).

O Worker de `cdn.eterzion.com/studio/` só serve para quem apresenta uma
assinatura que o servidor de licenças emitiu -- e ele só emite para instalação
ativada, com licença ativa, num pedido assinado pela chave desta instalação
(`POST /downloads/token`, api/eterzion_licensing_service/app/downloads.py).

Dois consumidores:

- o updater do Electron, pela rota local `GET /downloads/token`, que manda o
  token no cabeçalho `Authorization: Bearer <exp>.<sig>`;
- o download de modelos (biblioteca eterzion_upscale), que monta a URL com
  `?exp=&sig=` -- ver `mirror_url_for`.

Sem licença, sem serviço de licenças configurado ou sem rede, `download_token()`
devolve None: o updater pula a verificação e os modelos caem na fonte original.
Nada disso é erro para quem usa o app.
"""
from __future__ import annotations

import base64
import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from app.config import settings

logger = logging.getLogger(__name__)

PROPOSITO = 'eterzion-download-token'  # o mesmo do servidor de licenças

_lock = threading.Lock()
_cache: dict | None = None
# Depois de uma falha, nao tentar de novo por um tempo. O token e' pedido na
# mesma thread que manda cada job ao worker: com o servidor de licencas fora do
# ar, sem isto, CADA job esperaria o timeout de 10 s.
_ESPERA_APOS_FALHA_S = 300
_falhou_em: float = 0.0


def _pedir_token() -> dict:
    from app import security

    identidade = security.ensure_identity()
    agora = int(time.time())
    assinatura = identidade.sign(f'{PROPOSITO}:{identidade.install_id}:{agora}'.encode('utf-8'))
    corpo = json.dumps({
        'install_id': identidade.install_id,
        'timestamp': agora,
        'signature_b64': base64.b64encode(assinatura).decode('ascii'),
    }).encode('utf-8')
    req = urllib.request.Request(
        f'{settings.licensing_service_url.rstrip("/")}/downloads/token', data=corpo, method='POST',
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 - URL fixa, da configuração
        return json.loads(resp.read().decode('utf-8'))


def download_token() -> dict | None:
    """O token em cache enquanto ainda não passou da hora de renovar."""
    global _cache, _falhou_em
    if not settings.licensing_service_url:
        return None
    with _lock:
        agora = time.time()
        if _cache is not None and agora < _cache.get('renew_after', 0):
            return _cache
        if _cache is None and agora - _falhou_em < _ESPERA_APOS_FALHA_S:
            return None
        try:
            _cache = _pedir_token()
        except urllib.error.HTTPError as erro:
            # 403 = licença inativa; 401 = instalação não reconhecida; 503 =
            # CDN ainda não configurado no servidor. Nenhum deles é falha do
            # app: só não há download pelo CDN agora.
            logger.info('sem credencial de download do CDN (HTTP %s)', erro.code)
            _cache, _falhou_em = None, agora
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as erro:
            logger.info('servico de licencas inalcancavel para o CDN: %s', erro)
            _cache, _falhou_em = None, agora
        return _cache


def mirror_url_for(filename: str, token: dict | None = None) -> str | None:
    """URL assinada de um modelo no CDN, ou None (e aí vale a fonte original)."""
    token = token if token is not None else download_token()
    if not token:
        return None
    consulta = urllib.parse.urlencode({'exp': token['exp'], 'sig': token['sig']})
    return f"{token['base'].rstrip('/')}/models/{urllib.parse.quote(filename)}?{consulta}"


def install_mirror() -> None:
    """Liga o espelho do CDN no processo da API: o token é buscado (e renovado)
    quando um modelo precisa ser baixado."""
    from eterzion_upscale import processing

    processing.set_mirror_url_factory(mirror_url_for)


def install_mirror_from_message(token: dict | None) -> None:
    """No worker isolado, com o token que veio na mensagem do job. O worker não
    fala com o servidor de licenças: sem token na mensagem, sem espelho -- e o
    download cai na fonte original, em vez de tentar a rede por conta própria."""
    from eterzion_upscale import processing

    processing.set_mirror_url_factory((lambda nome: mirror_url_for(nome, token)) if token else None)
