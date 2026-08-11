"""Video reading/writing built on OpenCV, with optional audio remux via python-ffmpeg.

The pipeline is: read frames with cv2.VideoCapture -> upscale frame by frame ->
write with cv2.VideoWriter -> if the ffmpeg binary is available, copy the
original audio track into the final file (driven by the python-ffmpeg library).
Without ffmpeg the video is still produced, only without audio.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Iterator

import cv2
import numpy as np

from ..media_engine import ffmpeg_path, has_ffmpeg, run_ffmpeg

logger = logging.getLogger(__name__)


class VideoOpenError(ValueError):
    """Raised when a video file cannot be opened for reading or writing."""


class VideoReader:
    """Iterate over the frames of a video file (BGR numpy arrays)."""

    def __init__(self, path: str) -> None:
        self.path = path
        if not os.path.isfile(path):
            raise VideoOpenError(f'Could not open video: {path} (file not found)')
        self.capture = cv2.VideoCapture(path)
        if not self.capture.isOpened():
            raise VideoOpenError(f'Could not open video: {path}')
        self.fps: float = self.capture.get(cv2.CAP_PROP_FPS) or 24.0
        self.width: int = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height: int = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.frame_count: int = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if self.width <= 0 or self.height <= 0:
            self.capture.release()
            raise VideoOpenError(f'Could not read video stream: {path} (invalid or corrupted file)')

    def __len__(self) -> int:
        return max(self.frame_count, 0)

    def __iter__(self) -> Iterator[np.ndarray]:
        return self

    def __next__(self) -> np.ndarray:
        ok, frame = self.capture.read()
        if not ok:
            raise StopIteration
        return frame

    def close(self) -> None:
        self.capture.release()


class VideoWriter:
    """Write BGR frames to a video file."""

    def __init__(self, path: str, fps: float, width: int, height: int, codec: str = 'mp4v') -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*codec)
        self.writer = cv2.VideoWriter(path, fourcc, fps, (width, height))
        if not self.writer.isOpened():
            raise VideoOpenError(f'Could not open video writer for: {path} (codec {codec})')
        self.path = path

    def write(self, frame: np.ndarray) -> None:
        self.writer.write(frame)

    def close(self) -> None:
        self.writer.release()


def even(n: int) -> int:
    """Round a dimension up to the nearest even number (some codecs require it)."""
    return n if n % 2 == 0 else n + 1


def extract_audio(video_path: str, output_wav_path: str) -> bool:
    """Extract the audio track of ``video_path`` into a PCM WAV file.

    Returns False (instead of raising) when ffmpeg is missing or the source has
    no audio track — the caller should treat that as "nothing to enhance".
    """
    if not has_ffmpeg():
        return False
    try:
        run_ffmpeg(lambda f: f.input(video_path).output(output_wav_path, {'vn': None, 'acodec': 'pcm_s16le'}))
    except RuntimeError:
        return False
    return os.path.isfile(output_wav_path) and os.path.getsize(output_wav_path) > 0


def mux_audio_file(video_path: str, audio_path: str, output_path: str) -> bool:
    """Mux an external audio file into a (silent) video, re-encoding audio to AAC."""
    if not has_ffmpeg():
        return False
    try:
        run_ffmpeg(lambda f: f.input(video_path).input(audio_path).output(
            output_path, {'c:v': 'copy', 'c:a': 'aac'}, map=['0:v:0', '1:a:0'], shortest=None))
    except RuntimeError as error:
        logger.warning('audio mux failed (%s)', error)
        if os.path.exists(output_path) and os.path.abspath(output_path) != os.path.abspath(video_path):
            os.remove(output_path)
        return False
    return True


def copy_audio(source_video: str, upscaled_video: str, output_path: str) -> bool:
    """Mux the audio track of ``source_video`` into ``upscaled_video``.

    The video stream is copied as-is (no re-encode); audio is encoded to AAC.
    Returns True on success. Falls back (returns False) when the ffmpeg binary
    is missing, the source has no audio, or the mux fails — the caller is
    expected to keep the audio-less file in that case.
    """
    if not has_ffmpeg():
        logger.info('ffmpeg binary not found (bundled or on PATH); skipping audio remux')
        return False
    try:
        run_ffmpeg(lambda f: f.input(upscaled_video).input(source_video).output(
            output_path, {'c:v': 'copy', 'c:a': 'aac'}, map=['0:v:0', '1:a:0?'], shortest=None))
    except RuntimeError as error:
        logger.warning('audio remux failed (%s); keeping video without audio', error)
        if os.path.exists(output_path) and os.path.abspath(output_path) != os.path.abspath(upscaled_video):
            os.remove(output_path)  # discard partial output
        return False
    return True
