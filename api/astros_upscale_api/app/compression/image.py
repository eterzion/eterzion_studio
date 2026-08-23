"""Compressão de imagem, sobre Pillow.

**Por que Pillow e não o OpenCV que o resto do produto usa** (Decisão 1 de
research.md): `cv2.imencode` descarta todos os metadados, sempre, sem opção. Das
sete políticas que o FR-028 pede, só uma seria implementável com ele — a de
remover tudo — e ela seria implementada por acidente, não por escolha. Pillow
ainda grava AVIF nativamente, dispensando o subprocesso de FFmpeg que o caminho
atual usa para isso.

`astros_upscale.optimize` continua servindo o fluxo que já existe. A duplicação
está registrada em analysis.md, achado 5, com a dívida anotada — unificar
mexeria num caminho que funciona e está fora desta feature (FR-069).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from . import config


class ImageCompressionError(ValueError):
    """Motivo como chave, nunca frase — a interface traduz (Princípio XIV)."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


# ------------------------------- metadados ------------------------------- #

# As sete políticas do FR-028. O padrão é `essential_only`, e a escolha tem
# consequência visível: orientação e perfil de cor **mudam a imagem** quando
# removidos — uma foto de retrato vira paisagem, as cores saem do lugar. GPS e
# comentários não mudam nada e são exatamente o que ninguém quer publicar junto.
METADATA_POLICIES = (
    'preserve_all', 'essential_only', 'strip_exif', 'strip_gps',
    'strip_comments', 'strip_icc', 'strip_all',
)
DEFAULT_METADATA_POLICY = 'essential_only'

# Tags EXIF que preservamos em `essential_only`.
_EXIF_ORIENTATION = 274
_EXIF_ESSENTIAL = frozenset({_EXIF_ORIENTATION})
# O IFD de GPS inteiro.
_EXIF_GPS_IFD = 34853
_EXIF_COMMENT_TAGS = frozenset({270, 37510, 40092})  # ImageDescription, UserComment, XPComment


@dataclass
class ImageSettings:
    output_format: str = 'jpeg'
    quality: int = 82
    lossless: bool = False
    metadata_policy: str = DEFAULT_METADATA_POLICY
    width: int | None = None
    height: int | None = None
    percent: float | None = None
    # Um dos degraus de `config.RESOLUTION_PRESETS` (FR-027). Existe além de
    # `width`/`height` porque é a forma como a pessoa pensa — "1080p", não
    # "1920 por 1080" — e porque a caixa do preset é um teto, não uma medida
    # exata: um retrato 1080×1920 já cabe em 1080p e não deve ser tocado.
    resolution: str | None = None
    preserve_aspect: bool = True
    # Ligado por padrão: compressão que aumenta a resolução é quase sempre
    # engano de digitação, e aumentar não reduz arquivo nenhum.
    prevent_upscale: bool = True
    # Por formato — presentes só onde se aplicam (FR-029).
    png_compress_level: int | None = None
    chroma_subsampling: str | None = None
    progressive: bool | None = None
    effort: int | None = None
    speed: int | None = None

    @classmethod
    def from_dict(cls, dados: dict[str, Any]) -> 'ImageSettings':
        conhecidos = {campo for campo in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in dados.items() if k in conhecidos})


def compress(source_path: str, output_path: str, settings: ImageSettings) -> dict[str, Any]:
    """Comprime `source_path` em `output_path` e devolve o que de fato aplicou.

    **Nunca escreve sobre a origem** (Princípio XV). A verificação é aqui, e não
    confiada ao chamador: um caminho de saída que resolve para a entrada é o
    caso em que "a saída é a entrada" parece natural de implementar e destrói o
    original de alguém.
    """
    from PIL import Image

    if os.path.abspath(source_path) == os.path.abspath(output_path):
        raise ImageCompressionError(
            'output_is_source', 'A saída não pode ser o próprio arquivo de origem.')

    fmt = _resolve_format(source_path, settings.output_format)
    if fmt not in config.IMAGE_FORMATS:
        raise ImageCompressionError('unsupported_format', f'Formato não suportado: {fmt!r}')
    if settings.lossless and fmt not in config.IMAGE_FORMATS_LOSSLESS:
        raise ImageCompressionError(
            'lossless_unsupported', f'{fmt} não tem compressão sem perda.')

    try:
        with Image.open(source_path) as origem:
            origem.load()
            largura_inicial, altura_inicial = origem.size
            trabalho = _resize(origem, settings)
            trabalho = _prepare_mode(trabalho, fmt)
            exif, icc = _metadata_to_keep(origem, settings.metadata_policy)

            opcoes = _encode_options(fmt, settings)
            if exif is not None:
                opcoes['exif'] = exif
            if icc is not None:
                opcoes['icc_profile'] = icc

            os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
            trabalho.save(output_path, format=fmt.upper(), **opcoes)
            largura_final, altura_final = trabalho.size
    except ImageCompressionError:
        raise
    except OSError as error:
        raise ImageCompressionError('unreadable', 'Não foi possível ler ou gravar a imagem.') from error

    return {
        'output_format': fmt,
        'quality': settings.quality,
        'lossless': settings.lossless,
        'metadata_policy': settings.metadata_policy,
        'source_size': (largura_inicial, altura_inicial),
        'output_size': (largura_final, altura_final),
    }


def _resolve_format(source_path: str, requested: str) -> str:
    """`keep` significa o formato da origem — resolvido aqui, uma vez, em vez de
    cada chamador reimplementar o mapeamento de extensão."""
    if requested and requested != 'keep':
        return requested.lower()
    extensao = os.path.splitext(source_path)[1].lstrip('.').lower()
    return 'jpeg' if extensao in ('jpg', 'jpeg') else (extensao or 'png')


def _resize(img, settings: ImageSettings):
    alvo = _target_size(img.size, settings)
    if alvo is None or alvo == img.size:
        return img
    from PIL import Image

    # LANCZOS ao reduzir: é o filtro que preserva detalhe sem serrilhar, e
    # reduzir é o caso desta tela — aumentar aqui seria upscale sem modelo, que
    # é a outra tela.
    return img.resize(alvo, Image.Resampling.LANCZOS)


def _target_size(atual: tuple[int, int], settings: ImageSettings) -> tuple[int, int] | None:
    largura, altura = atual

    caixa = _preset_box(settings.resolution)
    if caixa is not None:
        # O preset é um teto pelo lado maior, e não uma caixa fixa: aplicar
        # 1920×1080 literalmente a um retrato o deitaria. O que a pessoa pede ao
        # escolher "1080p" é "não passe disso", nos dois sentidos.
        limite_maior, limite_menor = max(caixa), min(caixa)
        atual_maior, atual_menor = max(atual), min(atual)
        escala = min(limite_maior / atual_maior, limite_menor / atual_menor, 1.0)
        if escala >= 1.0:
            return atual
        return (max(1, round(largura * escala)), max(1, round(altura * escala)))

    if settings.percent:
        fator = settings.percent / 100
        alvo = (max(1, round(largura * fator)), max(1, round(altura * fator)))
    elif settings.width and settings.height:
        alvo = (int(settings.width), int(settings.height))
    elif settings.width:
        alvo = (int(settings.width), max(1, round(altura * settings.width / largura)))
    elif settings.height:
        alvo = (max(1, round(largura * settings.height / altura)), int(settings.height))
    else:
        return None

    if settings.preserve_aspect and settings.width and settings.height:
        # Cabe dentro da caixa pedida sem distorcer. Esticar a imagem para
        # preencher exatamente seria mudar o que ela mostra, não o seu tamanho.
        escala = min(alvo[0] / largura, alvo[1] / altura)
        alvo = (max(1, round(largura * escala)), max(1, round(altura * escala)))

    if settings.prevent_upscale and (alvo[0] > largura or alvo[1] > altura):
        return atual
    return alvo


def _preset_box(nome: str | None) -> tuple[int, int] | None:
    """A caixa de um degrau nomeado, ou `None` quando não há degrau escolhido.

    Um nome desconhecido devolve `None` em vez de levantar: a validação já
    aconteceu na rota (FR-064), e levantar aqui trocaria uma recusa clara por uma
    falha no meio do processamento.
    """
    if not nome or nome == 'original':
        return None
    return config.RESOLUTION_PRESETS.get(nome)


def _prepare_mode(img, fmt: str):
    """JPEG e BMP não têm canal alfa. Converter é escolha; deixar o Pillow
    levantar no meio da gravação, não."""
    if fmt in ('jpeg', 'bmp') and img.mode in ('RGBA', 'LA', 'P', 'PA'):
        fundo = img.convert('RGBA')
        from PIL import Image

        # Compõe sobre branco em vez de descartar o alfa: descartar deixa halos
        # pretos nas bordas transparentes, que é o defeito clássico.
        plano = Image.new('RGB', fundo.size, (255, 255, 255))
        plano.paste(fundo, mask=fundo.split()[-1])
        return plano
    if fmt == 'png' and img.mode == 'CMYK':
        return img.convert('RGB')
    return img


def _encode_options(fmt: str, settings: ImageSettings) -> dict[str, Any]:
    """As opções que **este** formato entende, e nenhuma outra.

    FR-029: a troca de formato muda quais controles existem. Passar `quality`
    para PNG não é erro do Pillow — é ignorado —, e um controle ignorado em
    silêncio é pior que um ausente.
    """
    if fmt == 'png':
        explicito = settings.png_compress_level is not None
        nivel = (settings.png_compress_level if explicito
                 else _quality_to_png_level(settings.quality))
        opcoes: dict[str, Any] = {'compress_level': max(0, min(9, int(nivel)))}
        if not explicito:
            # `optimize=True` do Pillow **força nível 9** e descarta o
            # `compress_level` passado. Com um nível explícito isso significa
            # ignorar em silêncio a escolha da pessoa — o defeito que este
            # arquivo condena duas funções acima, e que um teste pegou aqui.
            # Sem nível explícito não há escolha a respeitar, e otimizar é o
            # melhor padrão.
            opcoes['optimize'] = True
        return opcoes

    if fmt == 'jpeg':
        opcoes: dict[str, Any] = {'quality': settings.quality, 'optimize': True}
        if settings.progressive is not None:
            opcoes['progressive'] = bool(settings.progressive)
        if settings.chroma_subsampling is not None:
            # '4:4:4' → 0, '4:2:2' → 1, '4:2:0' → 2, na convenção do Pillow.
            mapa = {'4:4:4': 0, '4:2:2': 1, '4:2:0': 2}
            if settings.chroma_subsampling not in mapa:
                raise ImageCompressionError(
                    'invalid_settings',
                    f'Subamostragem desconhecida: {settings.chroma_subsampling!r}')
            opcoes['subsampling'] = mapa[settings.chroma_subsampling]
        return opcoes

    if fmt == 'webp':
        opcoes = {'quality': settings.quality, 'lossless': settings.lossless}
        if settings.effort is not None:
            opcoes['method'] = max(0, min(6, int(settings.effort)))
        return opcoes

    if fmt == 'avif':
        opcoes = {'quality': settings.quality}
        if settings.speed is not None:
            opcoes['speed'] = max(0, min(10, int(settings.speed)))
        return opcoes

    if fmt == 'tiff':
        # TIFF sem compressão é maior que o original; não é compressão, é
        # conversão. Deflate é sem perda e é o que faz o formato caber aqui.
        return {'compression': 'tiff_deflate'}

    return {}


def _quality_to_png_level(quality: int) -> int:
    """No PNG a fidelidade é dada e o que varia é esforço. Qualidade baixa pede
    arquivo menor, que é mais esforço de compressão."""
    return max(0, min(9, round(9 - (quality / 100) * 9)))


# ------------------------------- políticas ------------------------------- #

def _metadata_to_keep(img, policy: str) -> tuple[bytes | None, bytes | None]:
    """O EXIF e o ICC que sobrevivem a esta política.

    `essential_only` é o padrão porque é a única combinação que atende às duas
    metades do FR-028: privacidade **sem degradar a imagem**. Remover orientação
    gira a foto; remover o perfil de cor muda as cores. Remover GPS e
    comentários não muda pixel nenhum e é o que ninguém quer publicar junto.
    """
    if policy not in METADATA_POLICIES:
        raise ImageCompressionError('invalid_settings', f'Política desconhecida: {policy!r}')

    icc = img.info.get('icc_profile')
    bruto = img.info.get('exif')

    if policy == 'preserve_all':
        return bruto, icc
    if policy == 'strip_all':
        return None, None
    if policy == 'strip_icc':
        return bruto, None
    if policy == 'strip_exif':
        return None, icc

    exif = img.getexif()
    if not exif:
        return None, icc

    # **Remover do EXIF existente, não reconstruir um novo.** Algumas tags não
    # guardam valor e sim um ponteiro para um IFD aninhado — GPS é a principal.
    # Copiá-las com `novo[tag] = valor` grava o deslocamento como se fosse dado,
    # e o arquivo sai com um ponteiro para lugar nenhum. Foi o que a primeira
    # versão fez, e o teste de `strip_comments` a pegou: a estrutura toda
    # quebrava ao preservar uma tag que nem estava em questão.
    descartar = _tags_to_drop(exif, policy)
    for tag in descartar:
        if tag in exif:
            del exif[tag]

    if not list(exif.items()):
        return None, icc
    return exif.tobytes(), icc


def _tags_to_drop(exif, policy: str) -> set[int]:
    presentes = set(exif.keys())
    if policy == 'essential_only':
        return presentes - _EXIF_ESSENTIAL
    if policy == 'strip_gps':
        return {_EXIF_GPS_IFD}
    if policy == 'strip_comments':
        return set(_EXIF_COMMENT_TAGS)
    return set()
