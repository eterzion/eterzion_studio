"""Compressão de vídeo: o que a pessoa pediu, traduzido em argumentos estruturados.

**Nenhuma string de comando é montada aqui** (Princípio XIII). Cada opção é uma
chave num dicionário que a biblioteca converte em `argv`, e todo número passa por
um validador antes de virar valor. A diferença não é estética: um caminho com
espaço, um nome com aspas ou um valor vindo de um preset do usuário são, num
comando montado por concatenação, uma injeção esperando acontecer.

**Nenhum nome de encoder atravessa a fronteira desta camada.** Quem chama pede
`h264` e recebe uma recusa sobre `h264` quando a máquina não tem como produzi-lo
— `h264_nvenc` e `libsvtav1` existem só aqui dentro (Princípio V).

Sobre o que esta máquina consegue: a build LGPL que o produto distribui não traz
`libx264` nem `libx265`, porque as duas são GPL e incompatíveis com o
licenciamento do aplicativo. H.264 e H.265 portanto só saem de um encoder de
**hardware**, e onde não houver um, os dois são recusados antes de qualquer
processamento em vez de falharem no meio da barra de progresso.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

from eterzion_upscale.media import Cancelado, ffprobe_json, run_ffmpeg

from . import capabilities, config

# O quantizador não se chama do mesmo jeito em todo encoder, e mandar `crf` para
# um encoder de hardware é um argumento desconhecido — o FFmpeg aceita, ignora, e
# entrega um arquivo com a qualidade padrão que ninguém pediu. Silencioso, que é
# o pior tipo.
_QUANTIZER_OPTION: dict[str, str] = {
    'h264_nvenc': 'cq',
    'hevc_nvenc': 'cq',
    'h264_qsv': 'global_quality',
    'hevc_qsv': 'global_quality',
    'h264_amf': 'qp_i',
    'hevc_amf': 'qp_i',
    'libvpx-vp9': 'crf',
    'libsvtav1': 'crf',
    'libaom-av1': 'crf',
}

# Faixa útil de cada codec. Fora dela o número deixa de significar o que a
# interface promete: 0 em VP9 é sem perda, e 63 é irreconhecível.
_QUANTIZER_RANGE: dict[str, tuple[int, int]] = {
    'h264': (0, 51),
    'h265': (0, 51),
    'vp9': (0, 63),
    'av1': (0, 63),
}

_SPEED_PRESETS = ('slow', 'medium', 'fast')

# `-preset` também não é universal: os encoders de hardware usam vocabulário
# próprio, e o AV1 do SVT usa um número. Traduzir aqui é o que permite à
# interface oferecer três palavras — devagar, médio, rápido — em vez de expor a
# tabela de cada encoder.
_SPEED_BY_ENCODER: dict[str, dict[str, Any]] = {
    'libsvtav1': {'slow': {'preset': 4}, 'medium': {'preset': 8}, 'fast': {'preset': 10}},
    'libaom-av1': {'slow': {'cpu-used': 2}, 'medium': {'cpu-used': 5}, 'fast': {'cpu-used': 8}},
    'libvpx-vp9': {'slow': {'cpu-used': 1}, 'medium': {'cpu-used': 3}, 'fast': {'cpu-used': 5}},
    'h264_nvenc': {'slow': {'preset': 'p6'}, 'medium': {'preset': 'p4'}, 'fast': {'preset': 'p2'}},
    'hevc_nvenc': {'slow': {'preset': 'p6'}, 'medium': {'preset': 'p4'}, 'fast': {'preset': 'p2'}},
    'h264_qsv': {'slow': {'preset': 'slower'}, 'medium': {'preset': 'medium'},
                 'fast': {'preset': 'veryfast'}},
    'hevc_qsv': {'slow': {'preset': 'slower'}, 'medium': {'preset': 'medium'},
                 'fast': {'preset': 'veryfast'}},
    'h264_amf': {'slow': {'quality': 'quality'}, 'medium': {'quality': 'balanced'},
                 'fast': {'quality': 'speed'}},
    'hevc_amf': {'slow': {'quality': 'quality'}, 'medium': {'quality': 'balanced'},
                 'fast': {'quality': 'speed'}},
}

# Encoders que são de hardware. Serve para responder "esta máquina tem
# aceleração?" sem que a resposta cite marca (§41/§42).
_HARDWARE_SUFFIXES = ('_nvenc', '_qsv', '_amf', '_videotoolbox', '_vaapi')


class VideoCompressionError(RuntimeError):
    """`reason` é chave, nunca frase — quem exibe traduz (Princípio XIV)."""

    def __init__(self, reason: str, message: str, detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.reason = reason
        self.detail = detail or {}


@dataclass
class VideoSettings:
    container: str | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    # 0–100 na interface, convertido para o quantizador do codec. A pessoa pensa
    # em "qualidade", não em "quantizador invertido cuja escala muda por codec".
    quality: int = 70
    crf: int | None = None
    rate_mode: str | None = None          # 'quality' | 'bitrate'
    video_bitrate_bps: int | None = None
    max_bitrate_bps: int | None = None
    width: int | None = None
    height: int | None = None
    resolution: str | None = None
    fps: float | None = None
    encoding_preset: str | None = None    # slow | medium | fast
    encoder_preference: str | None = None  # auto | cpu | gpu
    # Áudio contido no vídeo (FR-031).
    audio_mode: str = 'keep'              # keep | recompress | remove
    audio_bitrate_bps: int | None = None
    sample_rate: int | None = None
    channels: int | None = None

    @classmethod
    def from_dict(cls, dados: dict[str, Any]) -> 'VideoSettings':
        conhecidos = {campo for campo in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in dados.items() if k in conhecidos})


def compress(source_path: str, output_path: str, settings: VideoSettings, *,
             on_progress: Callable[[int], None] | None = None,
             on_stage: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Comprime, e devolve o que de fato aplicou.

    **Nunca escreve sobre a origem** (Princípio XV). A verificação é aqui, e não
    confiada ao chamador: um caminho de saída que resolve para a entrada é o caso
    em que "a saída é a entrada" parece natural de implementar e destrói o
    original de alguém.
    """
    if os.path.abspath(source_path) == os.path.abspath(output_path):
        raise VideoCompressionError(
            'source_would_be_overwritten', 'A saída não pode ser o arquivo de origem.')

    origem = _probe(source_path)
    container = settings.container or _container_from_extension(output_path)
    codec = _resolve_codec(container, settings)
    encoder = capabilities.video_codec_encoder(codec)
    if encoder is None:
        # Nomeia o codec, nunca o encoder: a pessoa escolheu "H.264", e é sobre
        # H.264 que a recusa fala.
        raise VideoCompressionError(
            'encoder_unavailable', 'Este computador não consegue produzir este codec.',
            {'codec': codec})

    opcoes: dict[str, Any] = {'c:v': encoder}
    opcoes.update(_pixel_format_options(origem))
    opcoes.update(_rate_options(codec, encoder, settings))
    opcoes.update(_speed_options(encoder, settings.encoding_preset))
    opcoes.update(_audio_options(container, settings, origem))

    filtros = _filters(settings, origem)
    if filtros:
        opcoes['vf'] = ','.join(filtros)
    if settings.fps:
        opcoes['r'] = _numero(settings.fps, 'fps', 1, 480)

    if on_stage:
        on_stage('Comprimindo')

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
    _run(source_path, output_path, opcoes, origem.get('duration_seconds'), on_progress)

    return {
        'container': container,
        'video_codec': codec,
        'audio_codec': _audio_codec_applied(container, settings, origem),
        'options': {k: v for k, v in opcoes.items() if k not in ('c:v',)},
    }


# ------------------------------- execução ------------------------------- #

def _run(source_path: str, output_path: str, opcoes: dict[str, Any],
         duracao: float | None, on_progress: Callable[[int], None] | None) -> None:
    """Executa, transformando o progresso real do FFmpeg em percentual (FR-051).

    O percentual vem da **posição de tempo que o FFmpeg reporta**, não de um
    relógio. A diferença aparece exatamente quando importa: num trecho pesado a
    codificação desacelera, e uma barra movida por relógio continuaria subindo no
    mesmo ritmo — chegaria a 100% com o arquivo pela metade, e depois ficaria
    parada ali. Uma barra que mente é pior que nenhuma barra.
    """
    def construir(f):
        chamada = f.input(source_path).output(output_path, opcoes)
        if on_progress and duracao and duracao > 0:
            @chamada.on('progress')
            def _(progresso) -> None:  # pragma: no cover - vem da thread da lib
                segundos = progresso.time.total_seconds()
                # Limitado a 99: 100% é do encerramento, e uma barra cheia com o
                # arquivo ainda sendo finalizado é a mesma mentira invertida.
                on_progress(max(0, min(99, int(segundos / duracao * 100))))
        return chamada

    try:
        run_ffmpeg(construir)
    except Cancelado:
        # Cancelar nao e' falhar: nem 'encoding_failed', nem log de erro.
        raise
    except RuntimeError as error:
        raise VideoCompressionError('encoding_failed', str(error)) from error


def _probe(path: str) -> dict[str, Any]:
    try:
        dados = ffprobe_json(path)
    except Exception as error:  # noqa: BLE001
        raise VideoCompressionError('unreadable', 'Não foi possível ler o vídeo.') from error

    streams = dados.get('streams', [])
    video = next((s for s in streams if s.get('codec_type') == 'video'), None)
    audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    if video is None:
        raise VideoCompressionError('unreadable', 'O arquivo não tem trilha de vídeo.')

    duracao = dados.get('format', {}).get('duration')
    return {
        'width': int(video.get('width') or 0) or None,
        'height': int(video.get('height') or 0) or None,
        'duration_seconds': float(duracao) if duracao else None,
        'has_audio': audio is not None,
        'audio_codec': audio.get('codec_name') if audio else None,
        'pix_fmt': video.get('pix_fmt'),
    }


# ------------------------------- escolhas ------------------------------- #

def _container_from_extension(output_path: str) -> str:
    extensao = os.path.splitext(output_path)[1].lstrip('.').lower()
    if extensao in config.VIDEO_CONTAINERS:
        return extensao
    raise VideoCompressionError(
        'invalid_settings', f'Container desconhecido para a extensão {extensao!r}.')


def _resolve_codec(container: str, settings: VideoSettings) -> str:
    """O codec pedido, ou o melhor que este container e esta máquina permitem.

    Resolver em vez de exigir escolha é o que faz o modo Básico existir: quem
    nunca abriu o Avançado não escolheu codec nenhum, e o produto ainda assim
    precisa produzir o melhor arquivo possível aqui (FR-039).
    """
    spec = config.VIDEO_CONTAINERS.get(container)
    if spec is None:
        raise VideoCompressionError('invalid_settings', f'Container desconhecido: {container!r}')

    pedido = settings.video_codec
    if pedido and pedido != 'auto':
        if pedido not in spec.video_codecs:
            raise VideoCompressionError(
                'incompatible_combination', f'{container} não aceita este codec de vídeo.',
                {'container': container, 'codec': pedido})
        return pedido

    # A ordem é a do container, que já lista do mais desejável ao menos. O
    # primeiro que esta máquina consegue produzir ganha.
    for candidato in spec.video_codecs:
        if capabilities.video_codec_encoder(candidato) is not None:
            return candidato
    raise VideoCompressionError(
        'encoder_unavailable', 'Este computador não consegue produzir nenhum codec deste formato.',
        {'container': container})


# Formatos de pixel que nenhum encoder de vídeo comum aceita: paletizados (o de
# um GIF) e com canal alfa. Deixá-los passar não degrada nada — faz o FFmpeg
# recusar antes de escrever o primeiro quadro, com "Invalid argument", que não
# diz nada sobre a origem ser um GIF.
_PIXEL_FORMATS_NEEDING_CONVERSION = frozenset({
    'pal8', 'bgra', 'rgba', 'argb', 'abgr', 'ya8', 'gray8a',
    'yuva420p', 'yuva422p', 'yuva444p',
})


def _pixel_format_options(origem: dict[str, Any]) -> dict[str, Any]:
    """Converte para `yuv420p` **só** quando a origem tem paleta ou alfa.

    Forçar `yuv420p` sempre seria mais simples e destruiria informação: uma
    origem 10 bits (`yuv420p10le`) seria rebaixada para 8 sem ninguém pedir, e a
    perda apareceria como banding em gradientes — o tipo de degradação que se
    atribui à compressão e não à conversão.
    """
    pix_fmt = origem.get('pix_fmt')
    if pix_fmt and pix_fmt in _PIXEL_FORMATS_NEEDING_CONVERSION:
        return {'pix_fmt': 'yuv420p'}
    return {}


def _rate_options(codec: str, encoder: str, settings: VideoSettings) -> dict[str, Any]:
    if settings.rate_mode == 'bitrate' or settings.video_bitrate_bps:
        opcoes: dict[str, Any] = {
            'b:v': _numero(settings.video_bitrate_bps or 0, 'video_bitrate_bps', 1000, 500_000_000)
        }
        if settings.max_bitrate_bps:
            opcoes['maxrate'] = _numero(settings.max_bitrate_bps, 'max_bitrate_bps',
                                        1000, 500_000_000)
            # Sem `bufsize` o `maxrate` não tem efeito prático — é o par que
            # define o teto, e mandar um sem o outro é pedir um limite que não
            # limita.
            opcoes['bufsize'] = opcoes['maxrate'] * 2
        return opcoes

    opcao = _QUANTIZER_OPTION.get(encoder)
    if opcao is None:
        # Sem quantizador conhecido, cair num bitrate derivado seria inventar um
        # número. Melhor deixar o encoder no seu padrão do que fingir controle.
        return {}
    return {opcao: _quantizer_for(codec, settings)}


def _quantizer_for(codec: str, settings: VideoSettings) -> int:
    minimo, maximo = _QUANTIZER_RANGE.get(codec, (0, 51))
    if settings.crf is not None:
        return _numero(settings.crf, 'crf', minimo, maximo)
    # Qualidade 0–100 → quantizador invertido. Não é linear de propósito: a faixa
    # que as pessoas usam de verdade fica entre 60 e 90, e esticá-la sobre o
    # intervalo inteiro deixaria metade do slider em território inútil.
    qualidade = _numero(settings.quality, 'quality', 0, 100)
    fracao = 1 - (qualidade / 100)
    return int(round(minimo + fracao * (maximo - minimo)))


def _speed_options(encoder: str, preset: str | None) -> dict[str, Any]:
    if not preset or preset == 'auto':
        return {}
    if preset not in _SPEED_PRESETS:
        raise VideoCompressionError('invalid_settings', f'Preset de velocidade inválido: {preset!r}')
    return dict(_SPEED_BY_ENCODER.get(encoder, {}).get(preset, {}))


def _filters(settings: VideoSettings, origem: dict[str, Any]) -> list[str]:
    alvo = _target_size(settings, origem)
    if alvo is None:
        return []
    largura, altura = alvo
    # Dimensões pares: yuv420p subamostra croma pela metade nos dois eixos, e um
    # lado ímpar faz o encoder recusar o quadro.
    return [f'scale={_par(largura)}:{_par(altura)}']


def _target_size(settings: VideoSettings, origem: dict[str, Any]) -> tuple[int, int] | None:
    largura, altura = origem.get('width'), origem.get('height')
    if not largura or not altura:
        return None

    if settings.resolution and settings.resolution != 'original':
        caixa = config.RESOLUTION_PRESETS.get(settings.resolution)
        if caixa is None:
            raise VideoCompressionError(
                'invalid_settings', f'Resolução desconhecida: {settings.resolution!r}')
        # Teto pelo lado maior, como na imagem: um vídeo em pé pedido em "1080p"
        # não deve ser deitado.
        escala = min(max(caixa) / max(largura, altura), min(caixa) / min(largura, altura), 1.0)
        if escala >= 1.0:
            return None
        return (round(largura * escala), round(altura * escala))

    if settings.width and settings.height:
        return (_numero(settings.width, 'width', 16, 16384),
                _numero(settings.height, 'height', 16, 16384))
    if settings.width:
        alvo = _numero(settings.width, 'width', 16, 16384)
        return (alvo, round(altura * alvo / largura))
    if settings.height:
        alvo = _numero(settings.height, 'height', 16, 16384)
        return (round(largura * alvo / altura), alvo)
    return None


# ------------------------------- áudio ------------------------------- #

def _audio_options(container: str, settings: VideoSettings,
                   origem: dict[str, Any]) -> dict[str, Any]:
    """Manter, recomprimir ou remover (FR-031).

    **Manter é o padrão, e copiar é o que "manter" quer dizer**: recodificar uma
    trilha que ninguém pediu para mudar custa tempo e perde qualidade de graça.
    """
    if not origem.get('has_audio') or settings.audio_mode == 'remove':
        return {'an': None}

    if settings.audio_mode == 'keep':
        codec_origem = origem.get('audio_codec')
        spec = config.VIDEO_CONTAINERS[container]
        # Copiar só é possível quando o container aceita o que já está lá. Um
        # AAC dentro de WebM não existe, e mandar `copy` produziria um arquivo
        # que nada abre.
        if codec_origem and _codec_publico(codec_origem) in spec.audio_codecs:
            return {'c:a': 'copy'}

    codec = _audio_codec_applied(container, settings, origem)
    if codec is None:
        return {'an': None}
    encoder = capabilities.audio_codec_encoder(codec)
    if encoder is None:
        raise VideoCompressionError(
            'encoder_unavailable', 'Este computador não consegue produzir este codec de áudio.',
            {'codec': codec})

    opcoes: dict[str, Any] = {'c:a': encoder}
    if settings.audio_bitrate_bps and codec not in config.AUDIO_CODECS_LOSSLESS:
        opcoes['b:a'] = _numero(settings.audio_bitrate_bps, 'audio_bitrate_bps', 8000, 2_000_000)
    if settings.sample_rate:
        taxa = _numero(settings.sample_rate, 'sample_rate', 8000, 192_000)
        if taxa not in config.AUDIO_SAMPLE_RATES_HZ:
            raise VideoCompressionError('invalid_settings', f'Sample rate não suportado: {taxa}')
        opcoes['ar'] = taxa
    if settings.channels:
        opcoes['ac'] = _numero(settings.channels, 'channels', 1, 8)
    return opcoes


def _audio_codec_applied(container: str, settings: VideoSettings,
                         origem: dict[str, Any]) -> str | None:
    if not origem.get('has_audio') or settings.audio_mode == 'remove':
        return None
    spec = config.VIDEO_CONTAINERS[container]
    pedido = settings.audio_codec
    if pedido and pedido != 'auto':
        if pedido not in spec.audio_codecs:
            raise VideoCompressionError(
                'incompatible_combination', f'{container} não aceita este codec de áudio.',
                {'container': container, 'codec': pedido})
        return pedido
    for candidato in spec.audio_codecs:
        if capabilities.audio_codec_encoder(candidato) is not None:
            return candidato
    return None


def _codec_publico(nome_ffprobe: str) -> str:
    """O ffprobe chama H.265 de `hevc` e Vorbis de `vorbis`. Só o primeiro
    diverge do vocabulário público do produto."""
    return {'hevc': 'h265'}.get(nome_ffprobe, nome_ffprobe)


# ------------------------------- hardware ------------------------------- #

def encoder_is_hardware(encoder: str) -> bool:
    return encoder.endswith(_HARDWARE_SUFFIXES)


def resolve_encoder_preference(codec: str, preferencia: str | None) -> str | None:
    """Automático, CPU ou GPU, com queda para CPU (FR-047).

    **Qualidade e compatibilidade acima de velocidade** (FR-048), e é isto que o
    `auto` faz: prefere o encoder por software quando existe um, porque a um
    mesmo tamanho ele produz imagem melhor. O hardware entra quando é a única
    forma de produzir aquele codec — que é o caso de H.264 e H.265 nesta build —
    ou quando a pessoa pede.

    Pedir GPU numa máquina sem GPU utilizável **não é erro**: cai para CPU. O
    contrário — recusar o trabalho — trocaria um arquivo um pouco mais lento por
    nenhum arquivo.
    """
    candidatos = config.VIDEO_CODEC_ENCODERS.get(codec, ())
    disponiveis = [c for c in candidatos if capabilities.encoder_works(c)]
    if not disponiveis:
        return None

    software = [c for c in disponiveis if not encoder_is_hardware(c)]
    hardware = [c for c in disponiveis if encoder_is_hardware(c)]

    if preferencia == 'cpu':
        return (software or hardware)[0]
    if preferencia == 'gpu':
        return (hardware or software)[0]
    return (software or hardware)[0]


# ------------------------------- validação ------------------------------- #

def _numero(valor: Any, campo: str, minimo: float, maximo: float) -> int:
    """Todo número que vira argumento passa por aqui (Princípio XIII).

    Não é paranoia sobre injeção — a invocação já é estruturada. É sobre o que
    um valor fora de faixa faz depois: um `crf` de 200 ou um `fps` de 0 chegam
    ao FFmpeg, que falha no meio da codificação com uma mensagem sobre o seu
    próprio interior, e a pessoa recebe um erro que não fala do que ela fez.
    """
    try:
        numero = int(round(float(valor)))
    except (TypeError, ValueError) as error:
        raise VideoCompressionError(
            'invalid_settings', f'{campo} não é um número: {valor!r}') from error
    if not minimo <= numero <= maximo:
        raise VideoCompressionError(
            'invalid_settings', f'{campo} fora da faixa {minimo}–{maximo}: {numero}')
    return numero


def _par(valor: int) -> int:
    return valor if valor % 2 == 0 else valor - 1
