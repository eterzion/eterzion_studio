"""Compressão de GIF e animação, pela cadeia do próprio FFmpeg (Decisão 2).

Um GIF não tem "qualidade" no sentido em que um JPEG tem: ele guarda uma paleta
de até 256 cores e índices para ela. Comprimir um GIF é escolher **quais** cores
ficam e como aproximar as que saíram — e é por isso que a cadeia canônica tem
duas passadas: `palettegen` olha a animação inteira para decidir a paleta, e
`paletteuse` reescreve os quadros contra ela. Uma passada só produziria uma
paleta por quadro e uma animação que cintila.

**Armadilha registrada na pesquisa, e a razão de este módulo usar
`filter_complex`:** `paletteuse` e `split` têm múltiplas entradas ou saídas e não
funcionam num `-vf` simples. A primeira sondagem da pesquisa os reprovou como
"ausentes" por sondá-los com a aridade errada, e uma sonda assim teria desligado
a compressão de GIF inteira numa máquina onde ela funciona.

Como no vídeo e no áudio, nenhum nome de encoder atravessa a fronteira
(Princípio V) e todo número passa por validador (Princípio XIII).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

from eterzion_upscale.media import Cancelado, encoder_works, ffprobe_json, filter_works, run_ffmpeg

from . import config

# Dithering: como aproximar uma cor que a paleta não tem.
#
# `bayer` é o padrão por medida, não por gosto: produz um padrão regular que
# comprime bem, e GIF é um formato onde ruído aleatório custa bytes caros.
# `none` é o que dá arquivos menores e degraus visíveis em gradientes;
# `floyd_steinberg` é o mais bonito e o maior.
DITHER_MODES = ('bayer', 'none', 'floyd_steinberg', 'sierra2_4a')
DEFAULT_DITHER = 'bayer'

# Um GIF de um quadro é uma **imagem** (FR-007). O caso de borda está registrado
# porque tratá-lo como animação ofereceria controles de FPS e de otimização de
# quadros para um arquivo com um quadro só.
_ANIMATION_MIN_FRAMES = 2


class AnimationCompressionError(RuntimeError):
    """`reason` é chave, nunca frase — quem exibe traduz (Princípio XIV)."""

    def __init__(self, reason: str, message: str, detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.reason = reason
        self.detail = detail or {}


@dataclass
class AnimationSettings:
    output_format: str | None = None
    quality: int = 70
    max_colors: int | str | None = None   # 2–256, ou 'auto'
    dither: str | None = None
    fps: float | str | None = None        # número, ou 'original'
    width: int | None = None
    height: int | None = None
    resolution: str | None = None
    # Reaproveitar as áreas que não mudam entre quadros. Ligado por padrão: é
    # ganho sem custo visual, e desligá-lo só faz sentido para diagnosticar.
    optimize_frames: bool = True

    @classmethod
    def from_dict(cls, dados: dict[str, Any]) -> 'AnimationSettings':
        conhecidos = {campo for campo in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in dados.items() if k in conhecidos})


def frame_count(path: str) -> int | None:
    """Quantos quadros o arquivo tem, quando a sondagem consegue dizer.

    `None` e não `0`: um arquivo cuja contagem não foi obtida não é um arquivo
    de zero quadros, e confundir os dois classificaria uma animação ilegível
    como imagem (FR-010).
    """
    try:
        dados = ffprobe_json(path)
    except Exception:  # noqa: BLE001
        return None
    for stream in dados.get('streams', []):
        if stream.get('codec_type') != 'video':
            continue
        for campo in ('nb_frames', 'nb_read_frames'):
            valor = stream.get(campo)
            if valor not in (None, '', 'N/A'):
                try:
                    return int(valor)
                except (TypeError, ValueError):
                    continue
    return None


def is_animated(path: str) -> bool:
    """Verdadeiro só quando há mais de um quadro **e** isso foi verificado.

    Uma contagem que a sondagem não obteve devolve `False`: classificar como
    imagem é o lado recuperável do erro — a imagem é comprimida sem os controles
    de animação — enquanto o contrário ofereceria FPS e otimização de quadros
    para um arquivo de um quadro só.
    """
    quadros = frame_count(path)
    return quadros is not None and quadros >= _ANIMATION_MIN_FRAMES


def compress(source_path: str, output_path: str, settings: AnimationSettings, *,
             on_progress: Callable[[int], None] | None = None,
             on_stage: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Comprime, e devolve o que de fato aplicou.

    **Nunca escreve sobre a origem** (Princípio XV).
    """
    if os.path.abspath(source_path) == os.path.abspath(output_path):
        raise AnimationCompressionError(
            'source_would_be_overwritten', 'A saída não pode ser o arquivo de origem.')

    formato = settings.output_format or _format_from_extension(output_path)
    if formato not in config.ANIMATION_FORMATS:
        raise AnimationCompressionError(
            'invalid_settings', f'Formato de animação desconhecido: {formato!r}')

    origem = _probe(source_path)

    if on_stage:
        on_stage('Comprimindo')

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)

    if formato == 'gif':
        aplicado = _compress_gif(source_path, output_path, settings, origem, on_progress)
    elif formato == 'webp':
        aplicado = _compress_webp(source_path, output_path, settings, origem, on_progress)
    else:
        # GIF → MP4/WebM: sai do domínio da paleta e entra no de vídeo, e é o
        # módulo de vídeo que sabe fazê-lo. Reimplementar aqui seria uma segunda
        # verdade sobre containers e codecs.
        aplicado = _compress_as_video(source_path, output_path, formato, settings,
                                      on_progress, on_stage)

    return {'output_format': formato, **aplicado}


# ------------------------------- GIF ------------------------------- #

def _compress_gif(source_path: str, output_path: str, settings: AnimationSettings,
                  origem: dict[str, Any],
                  on_progress: Callable[[int], None] | None) -> dict[str, Any]:
    """A cadeia de duas passadas, montada como `filter_complex` estruturado.

    A ordem dentro da cadeia importa e não é arbitrária: **fps e scale vêm antes
    do `split`**, para que a paleta seja gerada a partir dos quadros que de fato
    vão sair. Gerar a paleta sobre o material original e aplicá-la a quadros já
    reduzidos escolheria cores para uma imagem que não existe mais.
    """
    for filtro in config.ANIMATION_REQUIRED_FILTERS:
        if not filter_works(filtro):
            raise AnimationCompressionError(
                'unsupported_build', 'Esta instalação não consegue comprimir GIF.',
                {'filter': filtro})

    cores = _colors_for(settings)
    dither = _dither_for(settings)
    pre = _preprocess_chain(settings, origem)

    # `split` duplica o fluxo: um ramo gera a paleta, o outro é reescrito com
    # ela. É por isto que um `-vf` simples não serve.
    cadeia = (
        f'{pre}split[a][b];'
        f'[a]palettegen=max_colors={cores}[p];'
        f'[b][p]paletteuse=dither={dither}'
    )

    _run(source_path, output_path, {'filter_complex': cadeia, 'loop': 0},
         origem.get('duration_seconds'), on_progress)

    return {'max_colors': cores, 'dither': dither, 'filter_complex': cadeia}


def _compress_webp(source_path: str, output_path: str, settings: AnimationSettings,
                   origem: dict[str, Any],
                   on_progress: Callable[[int], None] | None) -> dict[str, Any]:
    """WebP animado — sem paleta, com qualidade de verdade.

    É por isso que ele costuma sair menor que o GIF equivalente com a mesma
    aparência: não está limitado a 256 cores, então não precisa gastar bytes
    aproximando as que faltam.
    """
    if not encoder_works('libwebp_anim'):
        raise AnimationCompressionError(
            'unsupported_build', 'Esta instalação não consegue gravar WebP animado.')

    pre = _preprocess_chain(settings, origem).rstrip(',')
    opcoes: dict[str, Any] = {
        'c:v': 'libwebp_anim',
        'quality': _numero(settings.quality, 'quality', 0, 100),
        'loop': 0,
        'an': None,
    }
    if pre:
        opcoes['vf'] = pre

    _run(source_path, output_path, opcoes, origem.get('duration_seconds'), on_progress)
    return {'quality': opcoes['quality']}


def _compress_as_video(source_path: str, output_path: str, formato: str,
                       settings: AnimationSettings,
                       on_progress: Callable[[int], None] | None,
                       on_stage: Callable[[str], None] | None) -> dict[str, Any]:
    from . import video

    try:
        return video.compress(
            source_path, output_path,
            video.VideoSettings(
                container=formato,
                quality=settings.quality,
                fps=None if settings.fps in (None, 'original') else settings.fps,
                resolution=settings.resolution,
                width=settings.width,
                height=settings.height,
                # Um GIF não tem áudio; pedir para removê-lo é dizer a verdade
                # em vez de deixar o container declarar uma trilha vazia.
                audio_mode='remove',
            ),
            on_progress=on_progress, on_stage=on_stage)
    except video.VideoCompressionError as error:
        raise AnimationCompressionError(error.reason, str(error), error.detail) from error


# ------------------------------- cadeia ------------------------------- #

def _preprocess_chain(settings: AnimationSettings, origem: dict[str, Any]) -> str:
    """FPS e escala, **antes** do split. Sempre termina com vírgula ou vazia."""
    partes: list[str] = []

    if settings.fps not in (None, 'original', ''):
        partes.append(f'fps={_numero(settings.fps, "fps", 1, 60)}')

    alvo = _target_size(settings, origem)
    if alvo is not None:
        largura, altura = alvo
        # `lanczos` ao reduzir: preserva detalhe sem serrilhar, e serrilhado é
        # especialmente caro num formato de paleta — cada borda dura vira cores
        # novas que a paleta precisa acomodar.
        partes.append(f'scale={largura}:{altura}:flags=lanczos')

    return ','.join(partes) + ',' if partes else ''


def _target_size(settings: AnimationSettings,
                 origem: dict[str, Any]) -> tuple[int, int] | None:
    largura, altura = origem.get('width'), origem.get('height')
    if not largura or not altura:
        return None

    if settings.resolution and settings.resolution != 'original':
        caixa = config.RESOLUTION_PRESETS.get(settings.resolution)
        if caixa is None:
            raise AnimationCompressionError(
                'invalid_settings', f'Resolução desconhecida: {settings.resolution!r}')
        escala = min(max(caixa) / max(largura, altura),
                     min(caixa) / min(largura, altura), 1.0)
        if escala >= 1.0:
            return None
        return (max(2, round(largura * escala)), max(2, round(altura * escala)))

    if settings.width and settings.height:
        return (_numero(settings.width, 'width', 2, 16384),
                _numero(settings.height, 'height', 2, 16384))
    if settings.width:
        alvo = _numero(settings.width, 'width', 2, 16384)
        return (alvo, max(2, round(altura * alvo / largura)))
    if settings.height:
        alvo = _numero(settings.height, 'height', 2, 16384)
        return (max(2, round(largura * alvo / altura)), alvo)
    return None


def _colors_for(settings: AnimationSettings) -> int:
    """Cores da paleta — do controle, ou derivadas da qualidade.

    A escala não é linear: abaixo de 32 cores a degradação é abrupta e acima de
    128 o ganho de tamanho é pequeno. A faixa útil fica no meio, e é ela que o
    slider percorre.
    """
    minimo, maximo = config.ANIMATION_MAX_COLORS_RANGE
    if settings.max_colors not in (None, 'auto', ''):
        return _numero(settings.max_colors, 'max_colors', minimo, maximo)
    qualidade = _numero(settings.quality, 'quality', 0, 100)
    return max(minimo, min(maximo, int(round(16 + (qualidade / 100) * (256 - 16)))))


def _dither_for(settings: AnimationSettings) -> str:
    escolhido = settings.dither or DEFAULT_DITHER
    if escolhido not in DITHER_MODES:
        raise AnimationCompressionError(
            'invalid_settings', f'Modo de dithering desconhecido: {escolhido!r}',
            {'supported': list(DITHER_MODES)})
    return escolhido


# ------------------------------- execução ------------------------------- #

def _run(source_path: str, output_path: str, opcoes: dict[str, Any],
         duracao: float | None, on_progress: Callable[[int], None] | None) -> None:
    def construir(f):
        chamada = f.input(source_path).output(output_path, opcoes)
        if on_progress and duracao and duracao > 0:
            @chamada.on('progress')
            def _(progresso) -> None:  # pragma: no cover - vem da thread da lib
                segundos = progresso.time.total_seconds()
                on_progress(max(0, min(99, int(segundos / duracao * 100))))
        return chamada

    try:
        run_ffmpeg(construir)
    except Cancelado:
        # Cancelar nao e' falhar: nem 'encoding_failed', nem log de erro.
        raise
    except RuntimeError as error:
        raise AnimationCompressionError('encoding_failed', str(error)) from error


def _probe(path: str) -> dict[str, Any]:
    try:
        dados = ffprobe_json(path)
    except Exception as error:  # noqa: BLE001
        raise AnimationCompressionError(
            'unreadable', 'Não foi possível ler a animação.') from error

    video_stream = next((s for s in dados.get('streams', [])
                         if s.get('codec_type') == 'video'), None)
    if video_stream is None:
        raise AnimationCompressionError('unreadable', 'O arquivo não tem quadros.')

    duracao = dados.get('format', {}).get('duration')
    return {
        'width': int(video_stream['width']) if video_stream.get('width') else None,
        'height': int(video_stream['height']) if video_stream.get('height') else None,
        'duration_seconds': float(duracao) if duracao else None,
    }


def _format_from_extension(output_path: str) -> str:
    extensao = os.path.splitext(output_path)[1].lstrip('.').lower()
    if extensao in config.ANIMATION_FORMATS:
        return extensao
    raise AnimationCompressionError(
        'invalid_settings', f'Formato desconhecido para a extensão {extensao!r}.')


def _numero(valor: Any, campo: str, minimo: float, maximo: float) -> int:
    try:
        numero = int(round(float(valor)))
    except (TypeError, ValueError) as error:
        raise AnimationCompressionError(
            'invalid_settings', f'{campo} não é um número: {valor!r}') from error
    if not minimo <= numero <= maximo:
        raise AnimationCompressionError(
            'invalid_settings', f'{campo} fora da faixa {minimo}–{maximo}: {numero}')
    return numero
