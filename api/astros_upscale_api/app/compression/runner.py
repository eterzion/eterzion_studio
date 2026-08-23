"""Executa um job de compressão: valida, comprime num temporário, publica.

A ordem não é arbitrária. **Validar antes de tudo** (FR-064) porque uma recusa
depois de a barra de progresso começar já custou o tempo da pessoa. **Comprimir
num temporário** porque uma interrupção no meio não pode deixar um arquivo
truncado com o nome do resultado. **Publicar por último** porque só aí existe
algo que valha o nome.
"""
from __future__ import annotations

import os
import shutil
import time
from typing import Any, Callable

from . import capabilities, config, image, video, workspace


class CompressionRefused(ValueError):
    """Recusa antes de processar. `reason` é chave, nunca frase."""

    def __init__(self, reason: str, message: str, detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.reason = reason
        self.detail = detail or {}


# Campos que só o modo Avançado pode enviar. A condição 2 da exceção do
# Princípio V (constituição v4.0.0) exige que o modo Básico nunca encontre
# vocabulário técnico — e verificar isso **no backend** é o que impede a
# condição de se perder no dia em que alguém mexer só na interface.
_ADVANCED_ONLY_FIELDS = frozenset({
    'video_codec', 'audio_codec', 'container', 'crf', 'rate_mode',
    'video_bitrate_bps', 'max_bitrate_bps', 'audio_bitrate_bps', 'cbr', 'encoding_preset',
    'encoder_preference', 'codec', 'bitrate_mode', 'sample_rate', 'channels',
    'png_compress_level', 'chroma_subsampling', 'progressive', 'effort', 'speed',
    'dither', 'max_colors',
})


def validate(media_kind: str, settings: dict[str, Any], *, advanced: bool) -> None:
    """Tudo que pode ser recusado, recusado agora (FR-064).

    Nenhuma destas verificações precisa tocar o arquivo, e é por isso que todas
    cabem antes de qualquer processamento.
    """
    if not advanced:
        tecnicos = sorted(set(settings) & _ADVANCED_ONLY_FIELDS)
        if tecnicos:
            # Não é tolerado em silêncio: tolerar seria a porta pela qual a
            # condição 2 deixa de valer, porque um cliente que manda codec no
            # modo Básico passaria a funcionar e viraria comportamento.
            raise CompressionRefused(
                'invalid_settings',
                'O modo Básico não aceita configurações técnicas.',
                {'fields': tecnicos})

    if media_kind == 'image':
        _validate_image(settings)
    elif media_kind in ('video', 'animation'):
        _validate_video(settings)
    elif media_kind == 'audio':
        _validate_audio(settings)
    else:
        raise CompressionRefused('invalid_settings', f'Tipo de mídia desconhecido: {media_kind!r}')


def _validate_image(settings: dict[str, Any]) -> None:
    fmt = settings.get('output_format')
    if fmt and fmt != 'keep':
        if fmt not in config.IMAGE_FORMATS:
            raise CompressionRefused('invalid_settings', f'Formato desconhecido: {fmt!r}')
        if not capabilities.pillow_format_works(fmt):
            raise CompressionRefused(
                'encoder_unavailable', 'Este computador não consegue gravar neste formato.',
                {'format': fmt})
        if settings.get('lossless') and fmt not in config.IMAGE_FORMATS_LOSSLESS:
            raise CompressionRefused(
                'invalid_settings', f'{fmt} não tem compressão sem perda.')
    _validate_quality(settings)
    _validate_dimensions(settings)


def _validate_video(settings: dict[str, Any]) -> None:
    container = settings.get('container')
    codec = settings.get('video_codec')
    audio = settings.get('audio_codec')

    if container and container not in config.VIDEO_CONTAINERS:
        raise CompressionRefused('invalid_settings', f'Container desconhecido: {container!r}')

    for nome, valor in (('video_codec', codec), ('audio_codec', audio)):
        if valor in (None, 'auto'):
            continue
        tabela = (config.VIDEO_CODEC_ENCODERS if nome == 'video_codec'
                  else config.AUDIO_CODEC_ENCODERS)
        if valor not in tabela:
            raise CompressionRefused('invalid_settings', f'Codec desconhecido: {valor!r}')
        resolvido = (capabilities.video_codec_encoder(valor) if nome == 'video_codec'
                     else capabilities.audio_codec_encoder(valor))
        if resolvido is None:
            # Nomeia o codec, nunca o encoder: a pessoa escolheu "H.264", e é
            # sobre H.264 que a recusa fala (Princípio V).
            raise CompressionRefused(
                'encoder_unavailable', 'Este computador não consegue produzir este codec.',
                {'codec': valor})

    if container:
        spec = config.VIDEO_CONTAINERS[container]
        if codec and codec != 'auto' and codec not in spec.video_codecs:
            raise CompressionRefused(
                'incompatible_combination',
                f'{container} não aceita este codec de vídeo.',
                {'container': container, 'codec': codec})
        if audio and audio != 'auto' and audio not in spec.audio_codecs:
            raise CompressionRefused(
                'incompatible_combination',
                f'{container} não aceita este codec de áudio.',
                {'container': container, 'codec': audio})

    _validate_quality(settings)
    _validate_dimensions(settings)


def _validate_audio(settings: dict[str, Any]) -> None:
    fmt = settings.get('output_format')
    if fmt and fmt not in config.AUDIO_FORMATS:
        raise CompressionRefused('invalid_settings', f'Formato desconhecido: {fmt!r}')
    taxa = settings.get('sample_rate')
    if taxa not in (None, 'original') and int(taxa) not in config.AUDIO_SAMPLE_RATES_HZ:
        raise CompressionRefused('invalid_settings', f'Sample rate não suportado: {taxa!r}')


def _validate_quality(settings: dict[str, Any]) -> None:
    qualidade = settings.get('quality')
    if qualidade is not None and not 0 <= int(qualidade) <= 100:
        raise CompressionRefused('invalid_settings', 'Qualidade fora de 0–100.')


def _validate_dimensions(settings: dict[str, Any]) -> None:
    resolucao = settings.get('resolution')
    if resolucao not in (None, 'original') and resolucao not in config.RESOLUTION_PRESETS:
        raise CompressionRefused('invalid_settings', f'Resolução desconhecida: {resolucao!r}')
    for campo in ('width', 'height'):
        valor = settings.get(campo)
        if valor is not None and int(valor) <= 0:
            raise CompressionRefused('invalid_settings', f'{campo} tem que ser positivo.')
    percentual = settings.get('percent')
    if percentual is not None and not 0 < float(percentual) <= 1000:
        raise CompressionRefused('invalid_settings', 'Percentual fora de 0–1000.')


def check_disk(source_path: str, output_dir: str) -> None:
    """Espaço para o resultado, verificado antes (FR-064).

    O tamanho da origem é o teto razoável: comprimir raramente cresce, e quando
    cresce é pouco. Exigir o dobro seria recusar trabalho que caberia.
    """
    try:
        necessario = os.path.getsize(source_path)
        livre = shutil.disk_usage(output_dir or os.path.dirname(source_path) or '.').free
    except OSError:
        return  # não medível não é o mesmo que insuficiente
    if livre < necessario:
        raise CompressionRefused(
            'insufficient_disk', 'Não há espaço em disco para o resultado.',
            {'required_bytes': necessario, 'free_bytes': livre})


def run(media_kind: str, source_path: str, output_path: str, settings: dict[str, Any],
        *, on_progress: Callable[[int], None] | None = None,
        on_stage: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Comprime, medindo o que de fato saiu.

    Os números do resultado são **medidos**, nunca a estimativa repetida: o
    FR-022 pede o real, e apresentar a previsão como resultado seria a mentira
    mais fácil de cometer aqui.
    """
    inicio = time.monotonic()
    original_bytes = os.path.getsize(source_path)

    # Uma barra de progresso nunca anda para trás. O vídeo reporta progresso
    # real e chega perto de 99; a imagem não reporta nada e salta de uma vez. Sem
    # esta trava, o marco fixo pós-compressão puxaria a barra do vídeo de 99 de
    # volta para 90 — e uma barra que recua é lida como "algo deu errado e está
    # refazendo".
    ultimo = 0

    def avancar(valor: int) -> None:
        nonlocal ultimo
        if on_progress and valor > ultimo:
            ultimo = valor
            on_progress(valor)

    if on_stage:
        on_stage('Comprimindo')

    with workspace.workspace() as trabalho:
        temporario = os.path.join(trabalho, 'saida' + os.path.splitext(output_path)[1])
        aplicado = _compress(media_kind, source_path, temporario, settings,
                             on_progress=avancar, on_stage=on_stage)

        avancar(90)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
        # `move` e não `copy`: o resultado atravessa o limite do temporário uma
        # vez só, e nada fica no meio do caminho.
        shutil.move(temporario, output_path)

    tamanho_final = os.path.getsize(output_path)
    avancar(100)

    return {
        'output_path': output_path,
        'original_bytes': original_bytes,
        'output_size_bytes': tamanho_final,
        'saving_bytes': original_bytes - tamanho_final,
        'reduction_ratio': (1 - tamanho_final / original_bytes) if original_bytes else None,
        # Campo, não cálculo do renderer: FR-023 exige dizer quando o resultado
        # ficou maior, e uma redução negativa apresentada como economia é o tipo
        # de defeito que passa por formatação.
        'grew': tamanho_final > original_bytes,
        'elapsed_seconds': round(time.monotonic() - inicio, 2),
        'applied': aplicado,
    }


def _compress(media_kind: str, source_path: str, output_path: str, settings: dict[str, Any],
              *, on_progress: Callable[[int], None] | None = None,
              on_stage: Callable[[str], None] | None = None) -> dict[str, Any]:
    if media_kind == 'image':
        return image.compress(source_path, output_path,
                              image.ImageSettings.from_dict(settings))
    if media_kind == 'video':
        try:
            return video.compress(source_path, output_path,
                                  video.VideoSettings.from_dict(settings),
                                  on_progress=on_progress, on_stage=on_stage)
        except video.VideoCompressionError as error:
            # Traduzida para a recusa da Central em vez de vazar um tipo da
            # camada de baixo: quem trata `CompressionRefused` já sabe o que
            # fazer com `reason`, e um segundo tipo de erro com a mesma forma
            # seria dois caminhos para a mesma coisa.
            raise CompressionRefused(error.reason, str(error), error.detail) from error
    # Áudio e animação chegam nas Fases 5 e 6. Levantar aqui é melhor que uma
    # implementação parcial que produza arquivo errado em silêncio.
    raise CompressionRefused(
        'unsupported_media', f'A compressão de {media_kind} ainda não está disponível.')
