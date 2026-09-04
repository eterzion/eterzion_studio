"""O que esta máquina consegue de fato produzir.

`config.py` responde "é legal?". Este módulo responde "esta máquina consegue?",
e a interface só oferece o que passa nas duas — Princípio XIII: uma entrada de
allowlist significa *permitido*, não *presente*.

Isso não é zelo abstrato. Nesta máquina de desenvolvimento os três encoders
H.264 de hardware estão compilados no binário e **falham ao codificar um único
quadro** (driver NVENC velho, sem sessão MFX, `amfrt64.dll` ausente). Uma
verificação por listagem ofereceria MP4 e deixaria toda exportação morrer no
meio. Por isso tudo aqui passa por sonda funcional.

**Nenhum nome de encoder sai deste módulo.** O que sai é o nome público do
codec e uma *chave* de motivo. Princípio V, condição 3 da exceção da v4.0.0.
"""
from __future__ import annotations

import functools
from typing import Any

from eterzion_upscale.media import audio_encoder_works, encoder_works, filter_works

from . import config


def _entry(value: str, available: bool, reason: str | None,
           requires_hardware: bool = False) -> dict[str, Any]:
    return {
        'value': value,
        'available': available,
        'unavailable_reason': None if available else reason,
        'requires_hardware': requires_hardware,
    }


# ------------------------------- vídeo ------------------------------- #

def video_codec_encoder(codec: str) -> str | None:
    """O encoder que produzirá este codec aqui, ou None.

    Interno: o chamador de fora recebe o nome público do codec e nunca este
    valor. É a fronteira que mantém `h264_nvenc` fora da API.
    """
    candidatos = config.VIDEO_CODEC_ENCODERS.get(codec, ())
    return next((c for c in candidatos if encoder_works(c)), None)


def audio_codec_encoder(codec: str) -> str | None:
    candidatos = config.AUDIO_CODEC_ENCODERS.get(codec, ())
    return next((c for c in candidatos if audio_encoder_works(c)), None)


def video_codecs() -> list[dict[str, Any]]:
    resultado = []
    for codec in config.VIDEO_CODEC_ENCODERS:
        precisa_hw = codec in config.VIDEO_CODECS_REQUIRING_HARDWARE
        usavel = video_codec_encoder(codec) is not None
        # Motivos distintos porque a pessoa pode agir sobre um e não sobre o
        # outro: um encoder de hardware ausente é uma questão de máquina, e
        # dizer só "indisponível" esconderia isso.
        motivo = 'requires_hardware_encoder' if precisa_hw else 'no_encoder_available'
        resultado.append(_entry(codec, usavel, motivo, precisa_hw))
    return resultado


def audio_codecs() -> list[dict[str, Any]]:
    return [_entry(c, audio_codec_encoder(c) is not None, 'no_encoder_available')
            for c in config.AUDIO_CODEC_ENCODERS]


def video_containers() -> list[dict[str, Any]]:
    """Um container é utilizável quando ao menos um codec de vídeo E um de áudio
    seus funcionam aqui.

    Sem áudio utilizável o container não serve: todo vídeo que a Central produz
    ou carrega uma trilha ou a remove por escolha explícita, e "não pude
    codificar o áudio" no meio da exportação é a falha tardia que o
    Princípio XIII proíbe.
    """
    resultado = []
    for nome, spec in config.VIDEO_CONTAINERS.items():
        tem_video = any(video_codec_encoder(c) for c in spec.video_codecs)
        tem_audio = any(audio_codec_encoder(c) for c in spec.audio_codecs)
        usavel = tem_video and tem_audio
        precisa_hw = all(c in config.VIDEO_CODECS_REQUIRING_HARDWARE for c in spec.video_codecs)
        resultado.append(_entry(nome, usavel, 'no_encoder_available', precisa_hw))
    return resultado


def compatibility() -> dict[str, dict[str, list[str]]]:
    """Container → codecs que são **ao mesmo tempo** permitidos e presentes.

    É o que torna FR-046 possível sem que a interface precise conhecer as duas
    perguntas: ela recebe só o que sobrou.
    """
    return {
        nome: {
            'video': [c for c in spec.video_codecs if video_codec_encoder(c)],
            'audio': [c for c in spec.audio_codecs if audio_codec_encoder(c)],
        }
        for nome, spec in config.VIDEO_CONTAINERS.items()
    }


def hardware() -> dict[str, Any]:
    """Se há aceleração de vídeo utilizável, sem prometer marca.

    §41 e §42 pedem informar o encoder ativo. A condição 3 da exceção permite
    isso no modo Avançado — mas esta rota serve os dois modos, então responde a
    existência e não a identidade.
    """
    disponivel = any(video_codec_encoder(c) for c in config.VIDEO_CODECS_REQUIRING_HARDWARE)
    return {
        'available': disponivel,
        'reason': None if disponivel else 'no_working_hardware_encoder',
    }


# ------------------------------- imagem ------------------------------- #

@functools.lru_cache(maxsize=16)
def pillow_format_works(fmt: str) -> bool:
    """Se o **Pillow** grava este formato aqui.

    Sondar o OpenCV seria sondar a biblioteca errada: a Decisão 1 leva a imagem
    da Central para o Pillow, e foi assim que este defeito apareceu — a primeira
    versão usava `image_format_works` (OpenCV) e reprovava AVIF, que o Pillow
    grava nativamente. Uma sonda que não interroga quem faz o trabalho responde
    sobre outra coisa.

    Grava uma imagem 4×4 de verdade num buffer, porque uma tabela de formatos
    registrados diz o que a biblioteca conhece, não o que esta instalação
    consegue codificar — WebP e AVIF dependem de bibliotecas nativas que podem
    faltar.
    """
    import io

    from PIL import Image

    try:
        Image.new('RGB', (4, 4)).save(io.BytesIO(), format=fmt.upper())
    except Exception:  # noqa: BLE001 — qualquer falha significa "não grava"
        return False
    return True


def image_formats() -> list[dict[str, Any]]:
    return [_entry(f, pillow_format_works(f), 'unsupported_build')
            for f in config.IMAGE_FORMATS]


# ------------------------------- áudio ------------------------------- #

def audio_formats() -> list[dict[str, Any]]:
    """Um formato de áudio serve quando algum dos codecs que ele aceita funciona."""
    return [_entry(fmt, any(audio_codec_encoder(c) for c in codecs), 'no_encoder_available')
            for fmt, codecs in config.AUDIO_FORMATS.items()]


# ------------------------------- animação ------------------------------- #

def animation_formats() -> list[dict[str, Any]]:
    """GIF depende dos filtros de paleta, não só do encoder.

    Um build com o encoder `gif` mas sem `palettegen` produziria GIFs de 256
    cores escolhidas por aproximação — pior que os de hoje, e sem aviso.
    """
    paleta_ok = all(filter_works(f) for f in config.ANIMATION_REQUIRED_FILTERS)
    resultado = []
    for fmt in config.ANIMATION_FORMATS:
        if fmt == 'gif':
            usavel = paleta_ok and encoder_works('gif')
            motivo = 'unsupported_build'
        elif fmt == 'webp':
            usavel = encoder_works('libwebp_anim')
            motivo = 'unsupported_build'
        else:
            container = next((e for e in video_containers() if e['value'] == fmt), None)
            usavel = bool(container and container['available'])
            motivo = 'no_encoder_available'
        resultado.append(_entry(fmt, usavel, motivo))
    return resultado


# ------------------------------- fachada ------------------------------- #

def snapshot() -> dict[str, Any]:
    """Tudo que `GET /compression/capabilities` responde, numa chamada.

    As sondas são cacheadas por processo, então repetir a pergunta custa quase
    nada depois da primeira — e a primeira paga ~120 ms por encoder, o que é
    barato contra uma exportação que morreria minutos depois.
    """
    return {
        'image': {'formats': image_formats()},
        'video': {
            'containers': video_containers(),
            'video_codecs': video_codecs(),
            'audio_codecs': audio_codecs(),
            'compatibility': compatibility(),
            'hardware': hardware(),
        },
        'audio': {'formats': audio_formats(), 'codecs': audio_codecs()},
        'animation': {'formats': animation_formats()},
    }
