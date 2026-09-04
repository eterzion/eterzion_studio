"""File-size optimization (recompression) and format conversion for images,
videos and audio (FR-025 to FR-030).

Compression keeps resolution/duration/structure unchanged and only re-encodes
for a smaller file size; conversion changes the container/codec to a
different format within the SAME media type. Both always go through real
transcoding tools (OpenCV/ffmpeg) — never an AI model (FR-029, Constitution
"No AI Without Benefit"). Quality is a single 0-100 knob (higher = larger
file, closer to the original), mapped differently per media type below.
"""
from __future__ import annotations

import os

import cv2

from .media import (ImageOpenError, encoder_works, even, first_available_audio_encoder,
                    first_available_encoder, has_ffmpeg, imread, run_ffmpeg)

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.avif')
_CV2_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')  # what OpenCV itself can decode/encode
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.mov', '.avi', '.webm')
AUDIO_LOSSY_EXTENSIONS = ('.mp3', '.m4a', '.aac', '.ogg', '.opus')
AUDIO_LOSSLESS_EXTENSIONS = ('.flac',)

# Video/audio encoders permitted per container, in preference order. Every one
# is LGPL-safe: the Constitution's Licensing and Distribution Constraints forbid
# bundling a GPL encoder, and `libx264` — this module's default until
# docs/technical-debt/gpl-encoder-default.md was closed — is GPL.
#
# Deliberately NOT imported from eterzion_upscale_api.app.config's
# VIDEO_CONTAINER_ALLOWLIST, which lists the same encoders for the video-editor
# path: the dependency runs the other way (the API imports this package, never
# the reverse). Five short tuples repeated beats an inverted import.
_CONTAINER_VIDEO_ENCODERS: dict[str, tuple[str, ...]] = {
    '.mp4': ('h264_nvenc', 'h264_qsv', 'h264_amf'),
    '.mov': ('h264_nvenc', 'h264_qsv', 'h264_amf'),
    '.avi': ('h264_nvenc', 'h264_qsv', 'h264_amf'),
    '.mkv': ('h264_nvenc', 'h264_qsv', 'h264_amf', 'libvpx-vp9'),
    '.webm': ('libvpx-vp9', 'libaom-av1'),
}

_CONTAINER_AUDIO_ENCODERS: dict[str, tuple[str, ...]] = {
    '.mp4': ('aac',),
    '.mov': ('aac',),
    '.avi': ('aac',),
    '.mkv': ('libopus', 'flac'),
    '.webm': ('libopus',),
}

# Every video encoder above takes a quantizer where lower means better quality,
# but each spells it differently. `_quality_to_crf` still decides the number;
# this only decides its name, so no new quality judgement enters here.
_QUANTIZER_OPTION: dict[str, str] = {
    'h264_nvenc': 'cq',
    'h264_qsv': 'global_quality',
    'h264_amf': 'qp_i',
    'libvpx-vp9': 'crf',
    'libaom-av1': 'crf',
}


class UnsupportedFormatError(ValueError):
    """Raised when the input/output extension has no optimization path."""


class EncoderUnavailableError(RuntimeError):
    """Raised when no permitted encoder for the requested container actually
    works on this machine — refused before transcoding starts, never partway
    through (Princípio XIII).

    Messages never name an encoder: they surface to the client through the job
    error field, and Princípio V keeps encoder names off that wire.
    """


def _quality_to_avif_crf(quality: int) -> int:
    quality = max(0, min(100, quality))
    return round(15 + (100 - quality) * 0.35)  # 100 -> crf 15 (quase sem perda), 0 -> crf 50


def _convert_image_via_ffmpeg(input_path: str, output_path: str, quality: int,
                              resize: tuple[int, int] | None = None) -> None:
    """AVIF isn't a format OpenCV's stock build can decode or encode — real
    transcoding via ffmpeg's AV1 still-picture encoder (libaom-av1, LGPL-safe
    per media.GPL_ENCODERS) covers both directions."""
    if not has_ffmpeg():
        raise RuntimeError('ffmpeg não encontrado no sistema; instale-o para converter de/para AVIF.')
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
    out_ext = os.path.splitext(output_path)[1].lower()
    params = {}
    if out_ext == '.avif':
        params = {'c:v': 'libaom-av1', 'crf': _quality_to_avif_crf(quality), 'still-picture': '1'}
    if resize is not None:
        params['vf'] = f'scale={resize[0]}:{resize[1]}'
    run_ffmpeg(lambda f: f.input(input_path).output(output_path, params))


def optimize_image(input_path: str, output_path: str, quality: int = 82,
                   resize: tuple[int, int] | None = None) -> None:
    """Recompresses or converts an image: jpg/webp use ``quality`` (lossy); png is
    always max lossless compression; avif (either side) goes through ffmpeg since
    OpenCV can't read/write it. ``resize`` scales the output to exactly (w, h) —
    a plain resample, never the upscaling model."""
    ext = os.path.splitext(output_path)[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        raise UnsupportedFormatError(f'Otimização de imagem não suporta {ext!r}; use jpg, png, webp ou avif.')
    in_ext = os.path.splitext(input_path)[1].lower()
    if ext == '.avif' or in_ext not in _CV2_IMAGE_EXTENSIONS:
        _convert_image_via_ffmpeg(input_path, output_path, quality, resize=resize)
        return
    img = imread(input_path)
    if resize is not None:
        # INTER_AREA is the right filter for shrinking (the common case here);
        # it degenerates badly when enlarging, so switch for that direction.
        target_w, target_h = resize
        shrinking = target_w * target_h < img.shape[1] * img.shape[0]
        img = cv2.resize(img, (target_w, target_h),
                         interpolation=cv2.INTER_AREA if shrinking else cv2.INTER_CUBIC)
    if ext in ('.jpg', '.jpeg'):
        params = [cv2.IMWRITE_JPEG_QUALITY, int(quality)]
    elif ext == '.webp':
        params = [cv2.IMWRITE_WEBP_QUALITY, int(quality)]
    else:  # .png: lossless regardless of quality — always maximum compression
        params = [cv2.IMWRITE_PNG_COMPRESSION, 9]
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
    ok, buffer = cv2.imencode(ext, img, params)
    if not ok:
        raise ImageOpenError(f'Falha ao codificar imagem otimizada: {output_path}')
    buffer.tofile(output_path)


def _quality_to_crf(quality: int) -> int:
    quality = max(0, min(100, quality))
    return round(18 + (100 - quality) * 0.22)  # 100 -> crf 18 (quase sem perda), 0 -> crf 40 (bem compacto)


def _resolve_video_encoder(output_path: str, codec: str | None) -> str:
    """The video encoder for this output, confirmed to actually encode a frame
    here — permitted is not present (Princípio XIII).

    A caller may still name one, but it goes through the same functional probe.
    `encoder_works()` refuses every GPL encoder unconditionally, so no argument
    can bring `libx264` back through this door.
    """
    if codec is not None:
        if not encoder_works(codec):
            raise EncoderUnavailableError(
                'O encoder pedido não pode ser usado aqui — indisponível nesta máquina, '
                'ou proibido numa build distribuível.')
        return codec
    ext = os.path.splitext(output_path)[1].lower()
    candidates = _CONTAINER_VIDEO_ENCODERS.get(ext)
    if not candidates:
        raise UnsupportedFormatError(
            f'Otimização de vídeo não suporta {ext!r}; use mp4, mkv, mov, avi ou webm.')
    encoder = first_available_encoder(candidates)
    if encoder is None:
        raise EncoderUnavailableError(
            f'Nenhum encoder permitido para {ext.lstrip(".")} funciona nesta máquina; '
            'escolha outro formato de saída.')
    return encoder


def _video_quality_options(encoder: str, quality: int) -> dict:
    q = _quality_to_crf(quality)
    if encoder in ('libvpx-vp9', 'libaom-av1'):
        # These two only treat `crf` as a real quality target when the bitrate
        # target is explicitly zero; without it they run in constrained-quality
        # mode, where the same number means something else entirely.
        return {'crf': q, 'b:v': '0'}
    return {_QUANTIZER_OPTION[encoder]: q}


def _audio_options(input_path: str, output_path: str) -> dict:
    """Copying the source track is right for compression (same container) and
    wrong for conversion: AAC does not go into WebM, and Opus does not go into
    MP4. Same extension in and out means the track is already legal where it is
    going; a different one means it has to be re-encoded."""
    out_ext = os.path.splitext(output_path)[1].lower()
    if os.path.splitext(input_path)[1].lower() == out_ext:
        return {'c:a': 'copy'}
    encoder = first_available_audio_encoder(_CONTAINER_AUDIO_ENCODERS.get(out_ext, ()))
    if encoder is None:
        raise EncoderUnavailableError(
            f'Nenhum encoder de áudio permitido para {out_ext.lstrip(".")} funciona nesta '
            'máquina; escolha outro formato de saída.')
    return {'c:a': encoder}


def optimize_video(input_path: str, output_path: str, quality: int = 75, codec: str | None = None,
                   resize: tuple[int, int] | None = None) -> None:
    """Re-encode a video with a smaller bitrate target, keeping fps; audio is
    copied when the container does not change. ``resize`` scales the frames to
    exactly (w, h) — ffmpeg's own scaler, never the upscaling model.

    ``codec=None`` means "resolve one that works here from the output
    container". It used to default to ``libx264``, which is GPL and must never
    reach a shipped build — see docs/technical-debt/gpl-encoder-default.md.
    """
    if not has_ffmpeg():
        raise RuntimeError('ffmpeg não encontrado no sistema; instale-o para otimizar vídeos.')
    encoder = _resolve_video_encoder(output_path, codec)
    options = {'c:v': encoder, **_video_quality_options(encoder, quality),
               **_audio_options(input_path, output_path)}
    if resize is not None:
        # Encoders reject odd dimensions for common yuv420p pixel formats, so
        # round to even rather than failing deep inside ffmpeg.
        target_w, target_h = (even(resize[0]), even(resize[1]))
        options['vf'] = f'scale={target_w}:{target_h}'
    run_ffmpeg(lambda f: f.input(input_path).output(output_path, options))


def _quality_to_audio_bitrate_kbps(quality: int) -> int:
    quality = max(0, min(100, quality))
    return round(64 + quality / 100 * 256)  # 0 -> 64kbps, 100 -> 320kbps


def optimize_audio(input_path: str, output_path: str, quality: int = 75) -> None:
    """Recompress an audio file: lossy formats get a bitrate target, FLAC gets max compression."""
    if not has_ffmpeg():
        raise RuntimeError('ffmpeg não encontrado no sistema; instale-o para otimizar áudio.')
    ext = os.path.splitext(output_path)[1].lower()
    if ext in AUDIO_LOSSLESS_EXTENSIONS:
        run_ffmpeg(lambda f: f.input(input_path).output(output_path, {'compression_level': 12}))
    elif ext in AUDIO_LOSSY_EXTENSIONS:
        bitrate = _quality_to_audio_bitrate_kbps(quality)
        run_ffmpeg(lambda f: f.input(input_path).output(output_path, {'b:a': f'{bitrate}k'}))
    else:
        raise UnsupportedFormatError(
            f'Otimização de áudio não suporta {ext!r} (sem compressão) — use mp3, m4a, ogg, opus ou flac.')


def _media_category(ext: str) -> str | None:
    if ext in IMAGE_EXTENSIONS:
        return 'imagem'
    if ext in VIDEO_EXTENSIONS:
        return 'vídeo'
    if ext in AUDIO_LOSSY_EXTENSIONS or ext in AUDIO_LOSSLESS_EXTENSIONS:
        return 'áudio'
    return None


def optimize_file(input_path: str, output_path: str, quality: int = 80, codec: str | None = None,
                  resize: tuple[int, int] | None = None) -> None:
    """Dispatches to the right optimizer/converter based on the input/output
    extensions. Same extension -> compress (FR-025 to FR-027); different
    extension within the same media type -> convert (FR-028); different media
    type entirely -> refused outright with a clear reason (FR-030) — this
    function never silently guesses."""
    in_ext = os.path.splitext(input_path)[1].lower()
    out_ext = os.path.splitext(output_path)[1].lower()
    in_category = _media_category(in_ext)
    out_category = _media_category(out_ext)
    if in_category is None:
        raise UnsupportedFormatError(f'Extensão de entrada não suportada: {in_ext!r}')
    if out_category is None:
        raise UnsupportedFormatError(f'Extensão de saída não suportada: {out_ext!r}')
    if in_category != out_category:
        raise UnsupportedFormatError(
            f'Não é possível converter {in_category} para {out_category} — '
            'a conversão só é permitida dentro do mesmo tipo de mídia (FR-030).')

    if in_category == 'imagem':
        optimize_image(input_path, output_path, quality=quality, resize=resize)
    elif in_category == 'vídeo':
        optimize_video(input_path, output_path, quality=quality, codec=codec, resize=resize)
    else:
        # Audio has no spatial dimensions — `resize` is meaningless here, and
        # silently accepting it would suggest otherwise.
        optimize_audio(input_path, output_path, quality=quality)
