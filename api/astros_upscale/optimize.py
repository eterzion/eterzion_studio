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

from .media import ImageOpenError, has_ffmpeg, imread, run_ffmpeg

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.avif')
_CV2_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')  # what OpenCV itself can decode/encode
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.mov', '.avi', '.webm')
AUDIO_LOSSY_EXTENSIONS = ('.mp3', '.m4a', '.aac', '.ogg', '.opus')
AUDIO_LOSSLESS_EXTENSIONS = ('.flac',)


class UnsupportedFormatError(ValueError):
    """Raised when the input/output extension has no optimization path."""


def _quality_to_avif_crf(quality: int) -> int:
    quality = max(0, min(100, quality))
    return round(15 + (100 - quality) * 0.35)  # 100 -> crf 15 (quase sem perda), 0 -> crf 50


def _convert_image_via_ffmpeg(input_path: str, output_path: str, quality: int) -> None:
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
    run_ffmpeg(lambda f: f.input(input_path).output(output_path, params))


def optimize_image(input_path: str, output_path: str, quality: int = 82) -> None:
    """Recompresses or converts an image: jpg/webp use ``quality`` (lossy); png is
    always max lossless compression; avif (either side) goes through ffmpeg since
    OpenCV can't read/write it."""
    ext = os.path.splitext(output_path)[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        raise UnsupportedFormatError(f'Otimização de imagem não suporta {ext!r}; use jpg, png, webp ou avif.')
    in_ext = os.path.splitext(input_path)[1].lower()
    if ext == '.avif' or in_ext not in _CV2_IMAGE_EXTENSIONS:
        _convert_image_via_ffmpeg(input_path, output_path, quality)
        return
    img = imread(input_path)
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


def optimize_video(input_path: str, output_path: str, quality: int = 75, codec: str = 'libx264') -> None:
    """Re-encode a video with a smaller bitrate target (CRF), keeping resolution/fps; audio is copied as-is."""
    if not has_ffmpeg():
        raise RuntimeError('ffmpeg não encontrado no sistema; instale-o para otimizar vídeos.')
    crf = _quality_to_crf(quality)
    run_ffmpeg(lambda f: f.input(input_path).output(
        output_path, {'c:v': codec, 'crf': crf, 'preset': 'medium', 'c:a': 'copy'}))


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


def optimize_file(input_path: str, output_path: str, quality: int = 80, codec: str = 'libx264') -> None:
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
        optimize_image(input_path, output_path, quality=quality)
    elif in_category == 'vídeo':
        optimize_video(input_path, output_path, quality=quality, codec=codec)
    else:
        optimize_audio(input_path, output_path, quality=quality)
