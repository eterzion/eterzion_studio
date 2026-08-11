"""Real ffprobe wrapper — used for stream inspection (secondary-elements detection,
duration/fps/channel verification) across video, audio and image domains.
"""
from __future__ import annotations

import json
import shutil
import subprocess


class ProbeError(RuntimeError):
    """Raised when ffprobe is unavailable or the file can't be probed."""


def ffprobe_json(path: str) -> dict:
    """Runs `ffprobe -show_format -show_streams -show_chapters -of json` and
    returns the parsed result. Real subprocess call, no parsing of a
    synthetic/mocked shape."""
    ffprobe_bin = shutil.which('ffprobe')
    if not ffprobe_bin:
        raise ProbeError('ffprobe não encontrado no sistema.')
    try:
        result = subprocess.run(
            [ffprobe_bin, '-v', 'error', '-show_format', '-show_streams', '-show_chapters', '-of', 'json', path],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProbeError(f'Falha ao executar ffprobe em {path!r}: {error}') from error
    if result.returncode != 0:
        raise ProbeError(f'ffprobe falhou em {path!r}: {result.stderr.strip()}')
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ProbeError(f'Saída inválida do ffprobe para {path!r}: {error}') from error


def probe_streams(path: str) -> dict:
    """Summarizes a probed file into what callers actually need: counts of video/
    audio/subtitle streams and whether chapters are present — the exact signals
    the secondary-elements confirmation flow (FR-081) needs, without every caller
    re-parsing the raw ffprobe JSON shape."""
    data = ffprobe_json(path)
    streams = data.get('streams', [])
    video_streams = [s for s in streams if s.get('codec_type') == 'video']
    audio_streams = [s for s in streams if s.get('codec_type') == 'audio']
    subtitle_streams = [s for s in streams if s.get('codec_type') == 'subtitle']
    chapters = data.get('chapters', [])
    return {
        'video_stream_count': len(video_streams),
        'audio_stream_count': len(audio_streams),
        'subtitle_stream_count': len(subtitle_streams),
        'has_chapters': len(chapters) > 0,
        'duration_seconds': float(data.get('format', {}).get('duration', 0.0) or 0.0),
    }


# T047, FR-081 to FR-086: the video-enhance pipeline (VideoReader/VideoWriter,
# astros_upscale.utils.video_io) only ever carries one video stream and one
# audio stream through — anything beyond that (extra audio tracks, subtitles,
# chapters) is silently lost unless the person explicitly confirms first.
def detect_secondary_elements(path: str) -> dict:
    """Real, ffprobe-backed answer to "will processing this file lose
    anything the person didn't ask to lose". `has_losses=False` when the
    file has at most one audio stream and no subtitles/chapters — FR-085:
    files with nothing to lose never trigger a confirmation prompt."""
    info = probe_streams(path)
    losses = []
    if info['audio_stream_count'] > 1:
        losses.append('extra_audio_tracks')
    if info['subtitle_stream_count'] > 0:
        losses.append('subtitles')
    if info['has_chapters']:
        losses.append('chapters')
    return {**info, 'has_losses': bool(losses), 'losses': losses}
