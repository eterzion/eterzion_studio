"""Compressão de áudio: MP3, AAC/M4A, OGG, Opus, WAV e FLAC.

Duas regras carregam este módulo, e as duas são sobre **não fingir controle**.

**Formato sem perda não tem bitrate a escolher** (FR-033). FLAC e WAV comprimem
pelo conteúdo; um bitrate ali não é ignorado com elegância — é ignorado. Um
controle que aceita um valor e não faz nada com ele é pior que a sua ausência,
porque a pessoa move o slider, vê o arquivo sair do mesmo tamanho, e conclui que
o produto está quebrado. A ausência do controle é uma afirmação verdadeira.

**`original` não reamostra** (FR-034). Reamostrar é uma conversão com perda, e
fazê-la quando ninguém pediu é alterar a mídia por conta própria. O valor
`original` tem que produzir uma invocação **sem** `-ar`, e não com `-ar` no valor
que se leu — porque ler errado, ou ler de um arquivo que não declara, viraria uma
reamostragem silenciosa.

Como no vídeo, a invocação é estruturada (Princípio XIII) e nenhum nome de
encoder atravessa a fronteira: quem chama pede `opus` e recebe uma recusa sobre
`opus` (Princípio V).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

from eterzion_upscale.media import Cancelado, ffprobe_json, run_ffmpeg

from . import capabilities, config


class AudioCompressionError(RuntimeError):
    """`reason` é chave, nunca frase — quem exibe traduz (Princípio XIV)."""

    def __init__(self, reason: str, message: str, detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.reason = reason
        self.detail = detail or {}


@dataclass
class AudioSettings:
    output_format: str | None = None
    codec: str | None = None
    # 0–100 na interface. Vira bitrate para formatos com perda e é ignorado —
    # explicitamente, não por acidente — nos sem perda.
    quality: int = 70
    bitrate_bps: int | None = None
    bitrate_mode: str | None = None   # 'cbr' | 'vbr'
    sample_rate: int | str | None = None  # inteiro, ou 'original'
    channels: int | str | None = None     # inteiro, ou 'original'

    @classmethod
    def from_dict(cls, dados: dict[str, Any]) -> 'AudioSettings':
        conhecidos = {campo for campo in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in dados.items() if k in conhecidos})


def is_lossless(codec: str) -> bool:
    return codec in config.AUDIO_CODECS_LOSSLESS


def lossless_format(output_format: str) -> bool:
    """Verdadeiro quando **todo** codec que o formato aceita é sem perda.

    OGG aceita Vorbis e Opus, os dois com perda; WAV e FLAC não aceitam nenhum
    com perda. A pergunta que a interface faz é sobre o formato, e é aqui que ela
    é respondida em vez de numa lista paralela que sairia de sincronia.
    """
    codecs = config.AUDIO_FORMATS.get(output_format, ())
    return bool(codecs) and all(is_lossless(c) for c in codecs)


def compress(source_path: str, output_path: str, settings: AudioSettings, *,
             on_progress: Callable[[int], None] | None = None,
             on_stage: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Comprime, e devolve o que de fato aplicou.

    **Nunca escreve sobre a origem** (Princípio XV).
    """
    if os.path.abspath(source_path) == os.path.abspath(output_path):
        raise AudioCompressionError(
            'source_would_be_overwritten', 'A saída não pode ser o arquivo de origem.')

    origem = _probe(source_path)
    formato = settings.output_format or _format_from_extension(output_path)
    codec = _resolve_codec(formato, settings)
    encoder = capabilities.audio_codec_encoder(codec)
    if encoder is None:
        raise AudioCompressionError(
            'encoder_unavailable', 'Este computador não consegue produzir este codec.',
            {'codec': codec})

    opcoes: dict[str, Any] = {'c:a': encoder, 'vn': None}
    opcoes.update(_rate_options(codec, settings))
    opcoes.update(_channel_options(settings))
    opcoes.update(_sample_rate_options(settings))

    if on_stage:
        on_stage('Comprimindo')

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
    _run(source_path, output_path, opcoes, origem.get('duration_seconds'), on_progress)

    return {
        'output_format': formato,
        'codec': codec,
        'lossless': is_lossless(codec),
        'options': {k: v for k, v in opcoes.items() if k not in ('c:a', 'vn')},
    }


# ------------------------------- opções ------------------------------- #

def _rate_options(codec: str, settings: AudioSettings) -> dict[str, Any]:
    """Bitrate — e **nada** quando o codec é sem perda (FR-033).

    Não é uma omissão por conveniência: mandar `-b:a` para o FLAC produz um
    argumento que o encoder aceita e descarta, e o arquivo sai do tamanho que o
    conteúdo determina. O controle teria existido para nada, e a pessoa teria
    passado por ele acreditando ter escolhido algo.
    """
    if is_lossless(codec):
        return {}

    bits = settings.bitrate_bps or _bitrate_for(settings.quality)
    bits = _numero(bits, 'bitrate_bps', config.AUDIO_BITRATE_FLOOR_BPS, 2_000_000)
    opcoes: dict[str, Any] = {'b:a': bits}

    if settings.bitrate_mode == 'vbr' and codec == 'mp3':
        # O LAME expressa VBR por qualidade, e `-b:a` junto vira taxa alvo. Os
        # dois convivem, e é por isso que este ramo existe em vez de trocar um
        # pelo outro.
        opcoes['q:a'] = _mp3_vbr_quality(settings.quality)
        opcoes.pop('b:a')
    return opcoes


def _bitrate_for(qualidade: int) -> int:
    """Qualidade 0–100 mapeada nos degraus que as pessoas de fato usam.

    Interpolar linearmente entre 32 e 320 kbps produziria valores como 187 kbps,
    que nenhum player exibe de forma reconhecível e nenhuma pessoa pediria. Os
    degraus são a escala real do domínio.
    """
    degraus = config.AUDIO_BITRATE_PRESETS_KBPS
    qualidade = max(0, min(100, int(qualidade)))
    indice = round(qualidade / 100 * (len(degraus) - 1))
    return degraus[indice] * 1000


def _mp3_vbr_quality(qualidade: int) -> int:
    """`-q:a` do LAME vai de 0 (melhor) a 9 (pior) — invertido em relação à
    qualidade que a pessoa move."""
    return max(0, min(9, round((100 - max(0, min(100, int(qualidade)))) / 100 * 9)))


def _sample_rate_options(settings: AudioSettings) -> dict[str, Any]:
    """`original` produz invocação **sem** `-ar` (FR-034).

    A alternativa — ler a taxa da origem e passá-la de volta — parece
    equivalente e não é: quando a sondagem falha ou o arquivo não declara, o que
    sairia é um valor adivinhado, e o áudio seria reamostrado sem ninguém ter
    pedido. Reamostrar é conversão com perda.
    """
    taxa = settings.sample_rate
    if taxa in (None, 'original', ''):
        return {}
    valor = _numero(taxa, 'sample_rate', 8000, 192_000)
    if valor not in config.AUDIO_SAMPLE_RATES_HZ:
        raise AudioCompressionError(
            'invalid_settings', f'Sample rate não suportado: {valor}',
            {'supported': list(config.AUDIO_SAMPLE_RATES_HZ)})
    return {'ar': valor}


def _channel_options(settings: AudioSettings) -> dict[str, Any]:
    canais = settings.channels
    if canais in (None, 'original', ''):
        return {}
    return {'ac': _numero(canais, 'channels', 1, 8)}


def _format_from_extension(output_path: str) -> str:
    extensao = os.path.splitext(output_path)[1].lstrip('.').lower()
    if extensao in config.AUDIO_FORMATS:
        return extensao
    raise AudioCompressionError(
        'invalid_settings', f'Formato desconhecido para a extensão {extensao!r}.')


def _resolve_codec(formato: str, settings: AudioSettings) -> str:
    aceitos = config.AUDIO_FORMATS.get(formato)
    if not aceitos:
        raise AudioCompressionError('invalid_settings', f'Formato desconhecido: {formato!r}')

    pedido = settings.codec
    if pedido and pedido != 'auto':
        if pedido not in aceitos:
            raise AudioCompressionError(
                'incompatible_combination', f'{formato} não aceita este codec.',
                {'format': formato, 'codec': pedido})
        return pedido

    for candidato in aceitos:
        if capabilities.audio_codec_encoder(candidato) is not None:
            return candidato
    raise AudioCompressionError(
        'encoder_unavailable', 'Este computador não consegue produzir este formato.',
        {'format': formato})


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
        raise AudioCompressionError('encoding_failed', str(error)) from error


def _probe(path: str) -> dict[str, Any]:
    try:
        dados = ffprobe_json(path)
    except Exception as error:  # noqa: BLE001
        raise AudioCompressionError('unreadable', 'Não foi possível ler o áudio.') from error

    streams = dados.get('streams', [])
    audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    if audio is None:
        raise AudioCompressionError('unreadable', 'O arquivo não tem trilha de áudio.')

    duracao = dados.get('format', {}).get('duration')
    return {
        'duration_seconds': float(duracao) if duracao else None,
        'codec': audio.get('codec_name'),
        'sample_rate': int(audio['sample_rate']) if audio.get('sample_rate') else None,
        'channels': audio.get('channels'),
    }


def _numero(valor: Any, campo: str, minimo: float, maximo: float) -> int:
    try:
        numero = int(round(float(valor)))
    except (TypeError, ValueError) as error:
        raise AudioCompressionError(
            'invalid_settings', f'{campo} não é um número: {valor!r}') from error
    if not minimo <= numero <= maximo:
        raise AudioCompressionError(
            'invalid_settings', f'{campo} fora da faixa {minimo}–{maximo}: {numero}')
    return numero
