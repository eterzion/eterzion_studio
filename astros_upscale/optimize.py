"""File-size optimization (recompression) for images, videos and audio.

Unlike the upscale pipeline, this keeps resolution/duration unchanged and only
re-encodes for a smaller file size, in the same format as the input. Quality
is a single 0-100 knob (higher = larger file, closer to the original), mapped
differently per media type below.
"""
from __future__ import annotations

import os

import cv2

from .utils.image_io import ImageOpenError, imread
from .utils.video_io import has_ffmpeg

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.mov', '.avi', '.webm')
AUDIO_LOSSY_EXTENSIONS = ('.mp3', '.m4a', '.aac', '.ogg', '.opus')
AUDIO_LOSSLESS_EXTENSIONS = ('.flac',)


class UnsupportedFormatError(ValueError):
    """Raised when the input/output extension has no optimization path."""


def _run_ffmpeg(args_builder) -> None:
    from ffmpeg import FFmpeg, FFmpegError
    try:
        args_builder(FFmpeg().option('y')).execute()
    except (FFmpegError, OSError) as error:
        raise RuntimeError(f'Falha ao otimizar com ffmpeg: {error}') from error


def optimize_image(input_path: str, output_path: str, quality: int = 82) -> None:
    """Recompress an image: jpg/webp use ``quality`` (lossy); png is always max lossless compression."""
    ext = os.path.splitext(output_path)[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        raise UnsupportedFormatError(f'Otimização de imagem não suporta {ext!r}; use jpg, png ou webp.')
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
    _run_ffmpeg(lambda f: f.input(input_path).output(
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
        _run_ffmpeg(lambda f: f.input(input_path).output(output_path, {'compression_level': 12}))
    elif ext in AUDIO_LOSSY_EXTENSIONS:
        bitrate = _quality_to_audio_bitrate_kbps(quality)
        _run_ffmpeg(lambda f: f.input(input_path).output(output_path, {'b:a': f'{bitrate}k'}))
    else:
        raise UnsupportedFormatError(
            f'Otimização de áudio não suporta {ext!r} (sem compressão) — use mp3, m4a, ogg, opus ou flac.')


def optimize_file(input_path: str, output_path: str, quality: int = 80, codec: str = 'libx264') -> None:
    """Dispatch to the right optimizer based on the (matching) input/output extension."""
    in_ext = os.path.splitext(input_path)[1].lower()
    out_ext = os.path.splitext(output_path)[1].lower()
    if in_ext != out_ext:
        raise UnsupportedFormatError(
            f'A extensão de saída ({out_ext!r}) deve ser igual à de entrada ({in_ext!r}) — '
            'a otimização mantém o formato original.')
    if in_ext in IMAGE_EXTENSIONS:
        optimize_image(input_path, output_path, quality=quality)
    elif in_ext in VIDEO_EXTENSIONS:
        optimize_video(input_path, output_path, quality=quality, codec=codec)
    elif in_ext in AUDIO_LOSSY_EXTENSIONS or in_ext in AUDIO_LOSSLESS_EXTENSIONS:
        optimize_audio(input_path, output_path, quality=quality)
    else:
        raise UnsupportedFormatError(f'Extensão não suportada para otimização: {in_ext!r}')
