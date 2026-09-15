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


def aplicar_edicoes(caminho_png: str, edits: dict[str, Any] | None) -> tuple[int, int] | None:
    """Aplica ajustes de cor, efeitos e transformacao ao PNG, no lugar.

    Os mesmos filtros do Video (video_edits.build_filter_chain), entao o mesmo
    brilho da' o mesmo resultado nos dois modos, e a previa (o shader que
    reproduz o `eq`/`hue` do FFmpeg) vale para os dois. Depois do modelo, como
    no Video: o modelo recebe a foto original.

    A transparencia passa a parte. Os filtros de cor e de efeito trabalham em
    YUV, e a granulacao sujaria o canal alfa; entao o RGB leva a cadeia inteira,
    e o alfa so' as etapas geometricas da mesma cadeia (recortar, girar,
    espelhar) -- a geometria sai identica e o alfa, limpo.

    Devolve (largura, altura) do resultado, ou None quando nao havia o que
    aplicar."""
    import tempfile

    import cv2
    import numpy as np

    from app import video_edits
    from eterzion_upscale.media import imread, imwrite, run_ffmpeg

    if not edits:
        return None
    imagem = imread(caminho_png)
    altura, largura = imagem.shape[:2]
    # Imagem nao tem trecho nem audio: so' o que tem sentido num quadro.
    so_imagem = {chave: edits.get(chave) for chave in ('adjustments', 'effects', 'transform')}
    cadeia = video_edits.build_filter_chain(so_imagem, largura, altura)
    if not cadeia:
        return None
    geometria = video_edits.build_filter_chain({'transform': so_imagem.get('transform')},
                                               largura, altura)

    tem_alfa = imagem.ndim == 3 and imagem.shape[2] == 4
    pasta = os.path.dirname(os.path.abspath(caminho_png))
    temporarios: list[str] = []

    def passar(matriz: np.ndarray, filtros: list[str]) -> np.ndarray:
        entrada = tempfile.mktemp(suffix='.png', dir=pasta)
        saida = tempfile.mktemp(suffix='.png', dir=pasta)
        temporarios.extend([entrada, saida])
        imwrite(entrada, matriz)
        run_ffmpeg(lambda f: f.input(entrada).output(
            saida, {'vf': ','.join(filtros), 'frames:v': 1}))
        return imread(saida)

    # A conversao RGB -> YUV explicita, em BT.709 e faixa limitada: e' a que o
    # shader da previa usa (useVideoPreviewPipeline.ts). Deixada ao padrao, o
    # FFmpeg converteria um PNG em BT.601, e saturacao e matiz sairiam
    # diferentes do que a pessoa viu.
    cadeia_de_cor = ['scale=out_color_matrix=bt709:out_range=tv', 'format=yuv444p', *cadeia,
                     'scale=in_color_matrix=bt709:in_range=tv', 'format=rgb24']
    try:
        cor = passar(imagem[..., :3] if tem_alfa else imagem, cadeia_de_cor)
        if tem_alfa:
            alfa = imagem[..., 3]
            alfa = passar(alfa, geometria) if geometria else alfa
            if alfa.ndim == 3:
                alfa = cv2.cvtColor(alfa, cv2.COLOR_BGR2GRAY)
            if alfa.dtype != cor.dtype:
                # O FFmpeg devolve 8 bits depois dos filtros de cor; o alfa de
                # um PNG de 16 bits acompanha.
                alfa = (alfa / 257).astype(cor.dtype) if alfa.dtype == np.uint16 else alfa.astype(cor.dtype)
            if cor.ndim == 2:
                cor = cv2.cvtColor(cor, cv2.COLOR_GRAY2BGR)
            cor = np.dstack([cor[..., :3], alfa])
        imwrite(caminho_png, cor)
        return cor.shape[1], cor.shape[0]
    finally:
        for caminho in temporarios:
            if os.path.exists(caminho):
                os.remove(caminho)


def codificar(intermediario: str, saida: str, formato: str, perfil: str | None) -> None:
    """Do intermediario PNG para `saida`. PNG para PNG so' muda de lugar."""
    from app.processing import Upscaler

    if formato == 'png' and intermediario.lower().endswith('.png'):
        shutil.move(intermediario, saida)
        return
    qualidade = QUALIDADE_POR_PERFIL.get(perfil or 'balanced') if com_perda(formato) else None
    Upscaler.export(intermediario, saida, qualidade)
