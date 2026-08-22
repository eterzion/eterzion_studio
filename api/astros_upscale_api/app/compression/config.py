"""Toda tabela, limite e preset da Central de Compressão — e nenhum deles em
outro lugar.

FR-012 e a §66 da solicitação pedem isso, mas a razão é mais concreta que a
regra: um piso de bitrate escrito dentro do estimador e outro dentro da
validação divergem no dia em que só um dos dois é ajustado, e a divergência não
falha — ela produz um número levemente errado que ninguém questiona.

**Duas perguntas diferentes vivem aqui e não devem ser confundidas** (Decisão 6
de research.md):

- *É legal?* — o que um container aceita é propriedade do formato. É esta tabela.
- *Esta máquina consegue?* — é sonda funcional, e mora em `capabilities.py`.

Uma combinação só chega à interface quando passa nas duas.
"""
from __future__ import annotations

from typing import Any, NamedTuple

# ------------------------------- vídeo ------------------------------- #

# Nome público do codec → encoders que o produzem, em ordem de preferência.
#
# O nome público é o que a interface mostra no modo Avançado e o que a API
# aceita; os encoders são detalhe interno que a sonda resolve. Essa separação é
# o que permite trocar `libsvtav1` por outro encoder de AV1 sem que a interface,
# os presets salvos ou o histórico saibam disso.
#
# `libx264` e `libx265` NÃO aparecem em lugar nenhum desta tabela. São GPL, a
# constituição proíbe empacotá-los, e a condição 5 da exceção do Princípio V é
# explícita: licenciamento não vira escolha do usuário. H.264 e H.265 saem de
# encoder de hardware ou não saem.
VIDEO_CODEC_ENCODERS: dict[str, tuple[str, ...]] = {
    'h264': ('h264_nvenc', 'h264_qsv', 'h264_amf'),
    'h265': ('hevc_nvenc', 'hevc_qsv', 'hevc_amf'),
    'vp9': ('libvpx-vp9',),
    'av1': ('libsvtav1', 'libaom-av1'),
}

# Codecs cuja única fonte é hardware. A interface usa isto para explicar por que
# uma opção está indisponível **sem nomear encoder** (Princípio V).
VIDEO_CODECS_REQUIRING_HARDWARE = frozenset({'h264', 'h265'})

AUDIO_CODEC_ENCODERS: dict[str, tuple[str, ...]] = {
    'aac': ('aac',),
    'mp3': ('libmp3lame',),
    'opus': ('libopus',),
    'vorbis': ('libvorbis',),
    'flac': ('flac',),
    'pcm': ('pcm_s16le',),
}

AUDIO_CODECS_LOSSLESS = frozenset({'flac', 'pcm'})


class ContainerSpec(NamedTuple):
    """O que um container aceita — propriedade do formato, não da máquina."""
    video_codecs: tuple[str, ...]
    audio_codecs: tuple[str, ...]


# A matriz declarada. Deliberadamente conservadora: VP9 e Opus em MP4 existem no
# papel, e quase nenhum player de fato os toca. Oferecer uma combinação que o
# arquivo resultante não reproduz em lugar nenhum é pior do que não oferecê-la.
VIDEO_CONTAINERS: dict[str, ContainerSpec] = {
    'mp4': ContainerSpec(video_codecs=('h264', 'h265', 'av1'), audio_codecs=('aac', 'mp3')),
    'webm': ContainerSpec(video_codecs=('vp9', 'av1'), audio_codecs=('opus', 'vorbis')),
    'mkv': ContainerSpec(video_codecs=('h264', 'h265', 'vp9', 'av1'),
                         audio_codecs=('aac', 'mp3', 'opus', 'vorbis', 'flac')),
}

# ------------------------------- imagem ------------------------------- #

IMAGE_FORMATS: tuple[str, ...] = ('png', 'jpeg', 'webp', 'avif', 'tiff', 'bmp')

# Quais aceitam compressão sem perda. FR-026 exige desabilitar o controle onde
# não se aplica, com o motivo — e não apresentá-lo inerte.
IMAGE_FORMATS_LOSSLESS = frozenset({'png', 'webp', 'tiff', 'bmp'})
IMAGE_FORMATS_LOSSY = frozenset({'jpeg', 'webp', 'avif'})

# ------------------------------- áudio ------------------------------- #

AUDIO_FORMATS: dict[str, tuple[str, ...]] = {
    'mp3': ('mp3',),
    'm4a': ('aac',),
    'aac': ('aac',),
    'ogg': ('vorbis', 'opus'),
    'opus': ('opus',),
    'wav': ('pcm',),
    'flac': ('flac',),
}

AUDIO_BITRATE_PRESETS_KBPS: tuple[int, ...] = (64, 96, 128, 160, 192, 256, 320)
AUDIO_SAMPLE_RATES_HZ: tuple[int, ...] = (22050, 32000, 44100, 48000, 96000)

# ------------------------------- animação ------------------------------- #

ANIMATION_FORMATS: tuple[str, ...] = ('gif', 'webp', 'mp4', 'webm')

# `paletteuse` é o filtro que a sonda precisa confirmar, e ele tem DUAS entradas.
# Sondá-lo como filtro de entrada única dá falso negativo — registrado na
# Decisão 2 de research.md, depois de a primeira sondagem desta feature reprovar
# um filtro que funciona.
ANIMATION_REQUIRED_FILTERS: tuple[str, ...] = ('palettegen', 'paletteuse')

ANIMATION_MAX_COLORS_RANGE = (2, 256)

# ------------------------------- resolução ------------------------------- #

RESOLUTION_PRESETS: dict[str, tuple[int, int] | None] = {
    'original': None,
    '4k': (3840, 2160),
    '1440p': (2560, 1440),
    '1080p': (1920, 1080),
    '720p': (1280, 720),
    '480p': (854, 480),
}

# ------------------------------- pisos ------------------------------- #

# Abaixo destes bitrates, o resultado deixa de ser utilizável — comprimir mais
# não é compressão, é destruição. FR-020 exige recusar o alvo antes de
# processar, e é este piso que torna a recusa uma medida em vez de um palpite.
#
# Valores em bits por segundo, por altura de vídeo. Derivados de bits por pixel
# por quadro na faixa em que os codecs modernos ainda preservam estrutura.
VIDEO_BITRATE_FLOOR_BPS: dict[int, int] = {
    2160: 2_500_000,
    1440: 1_200_000,
    1080: 600_000,
    720: 300_000,
    480: 150_000,
    0: 80_000,
}

AUDIO_BITRATE_FLOOR_BPS = 32_000

# Overhead de container, como fração do payload. Usado pela estimativa; medido
# grosseiramente e declarado como premissa na resposta, nunca escondido.
CONTAINER_OVERHEAD_RATIO: dict[str, float] = {
    'mp4': 0.02,
    'webm': 0.015,
    'mkv': 0.02,
}


def video_bitrate_floor(height: int) -> int:
    """O piso para esta altura — o degrau imediatamente abaixo dela.

    Interpolar entre degraus daria um número mais bonito e não mais verdadeiro:
    o piso é um julgamento sobre utilizabilidade, não uma curva contínua.
    """
    for limite in sorted(VIDEO_BITRATE_FLOOR_BPS, reverse=True):
        if height >= limite:
            return VIDEO_BITRATE_FLOOR_BPS[limite]
    return VIDEO_BITRATE_FLOOR_BPS[0]


# ------------------------------- presets ------------------------------- #

# Os seis presets internos, por tipo de mídia. Valores aqui e em nenhum outro
# lugar (FR-012): um preset "Balanceado" definido na interface e outro no
# backend divergem no dia em que só um é ajustado, e a divergência não falha —
# produz um resultado levemente diferente do prometido.
#
# O nome é chave de i18n, não texto: `compression.preset.<id>` (Princípio XIV).
BUILTIN_PRESETS: dict[str, dict[str, dict[str, Any]]] = {
    'image': {
        'max_quality': {'quality': 98, 'lossless': False},
        'high_quality': {'quality': 90, 'lossless': False},
        'balanced': {'quality': 80, 'lossless': False},
        'small_file': {'quality': 65, 'lossless': False},
        'max_compression': {'quality': 45, 'lossless': False},
    },
    'video': {
        'max_quality': {'crf': 18, 'encoding_preset': 'slow'},
        'high_quality': {'crf': 22, 'encoding_preset': 'medium'},
        'balanced': {'crf': 26, 'encoding_preset': 'medium'},
        'small_file': {'crf': 32, 'encoding_preset': 'fast'},
        'max_compression': {'crf': 38, 'encoding_preset': 'veryfast'},
    },
    'audio': {
        'max_quality': {'bitrate_bps': 320_000},
        'high_quality': {'bitrate_bps': 256_000},
        'balanced': {'bitrate_bps': 192_000},
        'small_file': {'bitrate_bps': 128_000},
        'max_compression': {'bitrate_bps': 96_000},
    },
    'animation': {
        'max_quality': {'max_colors': 256, 'dither': 'sierra2_4a'},
        'high_quality': {'max_colors': 192, 'dither': 'sierra2_4a'},
        'balanced': {'max_colors': 128, 'dither': 'bayer'},
        'small_file': {'max_colors': 64, 'dither': 'bayer'},
        'max_compression': {'max_colors': 32, 'dither': 'none'},
    },
}

# `custom` não está acima porque não tem valores: ele **é** o que a pessoa
# ajustou. Listá-lo com números seria um sexto preset disfarçado.
PRESET_IDS = ('max_quality', 'high_quality', 'balanced', 'small_file',
              'max_compression', 'custom')

DEFAULT_PRESET_ID = 'balanced'


# Presets de plataforma (§64). Guardam limite de tamanho, não configuração —
# o limite é o fato durável, e as configurações que o atingem dependem do
# arquivo. Um preset "Discord" com bitrate fixo estaria errado para metade dos
# vídeos; com o limite, o resolvedor de alvo acerta os dois casos.
PLATFORM_PRESETS: dict[str, dict[str, Any]] = {
    'discord': {'media_kinds': ('video', 'image', 'animation'),
                'target_bytes': 10 * 1000 * 1000},
    'whatsapp': {'media_kinds': ('video', 'image'), 'target_bytes': 16 * 1000 * 1000},
    'telegram': {'media_kinds': ('video', 'image', 'animation'),
                 'target_bytes': 50 * 1000 * 1000},
    'email': {'media_kinds': ('image', 'video', 'audio', 'animation'),
              'target_bytes': 20 * 1000 * 1000},
    'web': {'media_kinds': ('image', 'animation'), 'target_bytes': 500 * 1000},
}
