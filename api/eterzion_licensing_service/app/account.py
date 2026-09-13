"""Dados da licenca para a propria instalacao: o final da chave e o e-mail da compra.

O app mostra os dois no popover da licenca, para a pessoa saber QUAL licenca
esta' ativa naquela maquina.

O pedido vem assinado pela instalacao, como o de download (app/downloads.py). A
rota de status (`GET /activations/{install_id}/status`) responde a qualquer um
que saiba um install_id -- que circula em URLs e logs -- e por isso nao pode
carregar o e-mail, que e' dado pessoal.

Da chave vao so' os 4 ultimos caracteres: o bastante para reconhecer a licenca,
sem pôr a chave inteira na tela de quem olha por cima do ombro.
"""
from __future__ import annotations

from app import licensing
from app.downloads import DownloadTokenError, verificar_pedido

PROPOSITO = 'eterzion-license-details'


def canonical_request(install_id: str, timestamp: int) -> bytes:
    return f'{PROPOSITO}:{install_id}:{timestamp}'.encode('utf-8')


def detalhes(install_id: str, timestamp: int, assinatura_b64: str, agora: float | None = None) -> dict:
    verificar_pedido(install_id, timestamp, assinatura_b64, PROPOSITO, agora)
    licenca = licensing.installation_license(install_id)
    if licenca is None:
        # A instalacao existe (a assinatura conferiu) mas perdeu o vinculo --
        # mesma resposta de "desconhecida", pelo mesmo motivo de la'.
        raise DownloadTokenError(401, 'nao_autorizado')
    return {'license_last4': licenca.id[-4:], 'email': licenca.email}
