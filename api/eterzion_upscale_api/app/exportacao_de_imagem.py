"""A exportacao da Imagem numa etapa so': formato, qualidade e entrega no destino.

Antes eram duas: o job gravava um "master" PNG na pasta interna, e a pessoa
exportava depois, por uma rota propria, com as proprias regras de nome e
conflito. O master nunca era apagado, e ate' exportar o antes/depois comparava
a original com ela mesma.

Agora o formato e a qualidade sao escolhidos antes de processar, como no Video
e no Audio. O modelo continua gravando um PNG sem perda na pasta interna (o
intermediario); a entrega codifica uma vez, no formato pedido, num temporario
na pasta do destino (app/destino.py), e apaga o intermediario.
"""
from __future__ import annotations

import os
import shutil
from typing import Any

# O perfil vira a qualidade do JPEG/WebP, como o perfil vira bitrate no Audio.
# PNG e TIFF nao tem qualidade a escolher.
QUALIDADE_POR_PERFIL = {'fast': 80, 'balanced': 90, 'quality': 97}

FORMATOS = ('png', 'jpg', 'webp', 'tiff')
_SINONIMOS = {'jpeg': 'jpg', 'tif': 'tiff'}

# Para a conferencia de espaco: o teto de um PNG/TIFF (RGBA sem compressao) e
# uma fracao generosa dele para os formatos com perda.
_BYTES_POR_PIXEL_SEM_PERDA = 4
_FRACAO_COM_PERDA = 0.25


class RecusaDeImagem(Exception):
    """`reason` e' chave, nunca frase (Principio XIV)."""

    def __init__(self, reason: str, message: str, detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.reason = reason
        self.detail = detail or {}


def formato_de_saida(pedido: str | None, origem: str) -> str:
    """O formato que sera' gravado. `keep` (ou nada) = o do original."""
    formato = (pedido or 'keep').lower().lstrip('.')
    if formato == 'keep':
        formato = os.path.splitext(origem)[1].lstrip('.').lower()
    return _SINONIMOS.get(formato, formato)


def com_perda(formato: str) -> bool:
    return formato in ('jpg', 'webp')


def verificar(formato: str, *, largura: int | None, altura: int | None, pasta: str) -> None:
    """As recusas que cabem antes do job: formato que nao existe, formato que
    esta maquina nao grava, e falta de espaco no destino."""
    from eterzion_upscale.media import image_format_works

    if formato not in FORMATOS:
        raise RecusaDeImagem('format_unavailable', f'Formato de imagem não suportado: {formato}.',
                             {'format': formato})
    if not image_format_works(formato):
        raise RecusaDeImagem('encoder_unavailable', 'Este computador não grava este formato.',
                             {'format': formato})
    if not largura or not altura:
        return
    necessario = int(largura * altura * _BYTES_POR_PIXEL_SEM_PERDA
                     * (_FRACAO_COM_PERDA if com_perda(formato) else 1))
    try:
        livre = shutil.disk_usage(pasta).free
    except OSError:
        return  # nao medivel nao e' o mesmo que insuficiente
    if livre < necessario:
        raise RecusaDeImagem('insufficient_disk', 'Não há espaço em disco para o resultado.',
                             {'required_bytes': necessario, 'free_bytes': livre})


def codificar(intermediario: str, saida: str, formato: str, perfil: str | None) -> None:
    """Do intermediario PNG para `saida`. PNG para PNG so' muda de lugar."""
    from app.processing import Upscaler

    if formato == 'png' and intermediario.lower().endswith('.png'):
        shutil.move(intermediario, saida)
        return
    qualidade = QUALIDADE_POR_PERFIL.get(perfil or 'balanced') if com_perda(formato) else None
    Upscaler.export(intermediario, saida, qualidade)
