"""FFmpeg invocation — the one place `FFmpeg().execute()` gets called from for
video/audio/image transcoding, compression and conversion. See package docstring
for why the LGPL check here is a warning, not an import-time failure.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess

logger = logging.getLogger(__name__)

# Software encoders that are GPL, not LGPL — must never ship in a bundled build
# without a separately negotiated commercial licence (Constitution, Licensing and
# Distribution Constraints). Hardware encoders (h264_nvenc, hevc_qsv, etc.) and
# AV1 encoders (libsvtav1, librav1e) are not in this set — they're LGPL-safe.
GPL_ENCODERS = frozenset({'libx264', 'libx264rgb', 'libx265', 'libxvid'})

_warned_this_process = False


def _bundled_ffmpeg_path() -> str | None:
    """Path to the ffmpeg binary electron-builder packages alongside the app.

    The Electron main process (interface/src/main/apiProcess.ts)
    sets ASTROS_FFMPEG_DIR to the extraResources 'ffmpeg' folder when a bundled
    LGPL build exists for the current platform (see electron-builder.yml and
    docs/models/MODEL_LICENSES.md §5). Unset in dev or on platforms without one
    (currently macOS), in which case callers fall back to PATH.
    """
    bundled_dir = os.environ.get('ASTROS_FFMPEG_DIR')
    if not bundled_dir:
        return None
    binary_name = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
    bundled_path = os.path.join(bundled_dir, binary_name)
    return bundled_path if os.path.isfile(bundled_path) else None


def ffmpeg_path() -> str | None:
    """Return the ffmpeg binary to use: the bundled build if present, else PATH."""
    return _bundled_ffmpeg_path() or shutil.which('ffmpeg')


def has_ffmpeg() -> bool:
    return ffmpeg_path() is not None


def is_lgpl_build() -> bool | None:
    """Returns True/False when determinable, or None when no ffmpeg binary
    (bundled or on PATH) is found. Real check against `ffmpeg -version`'s
    configuration line — not a guess."""
    ffmpeg_bin = ffmpeg_path()
    if not ffmpeg_bin:
        return None
    try:
        result = subprocess.run([ffmpeg_bin, '-version'], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    config_line = next((line for line in result.stdout.splitlines() if line.startswith('configuration:')), '')
    return '--enable-gpl' not in config_line and '--enable-nonfree' not in config_line


def _warn_once_if_gpl_build() -> None:
    global _warned_this_process
    if _warned_this_process:
        return
    _warned_this_process = True
    lgpl = is_lgpl_build()
    if lgpl is False:
        logger.warning(
            'The ffmpeg on PATH reports --enable-gpl/--enable-nonfree. Fine for local '
            'development; MUST be replaced with an LGPL build before packaging a '
            'distributable installer (see docs/models/MODEL_LICENSES.md §5).'
        )


def run_ffmpeg(args_builder) -> None:
    """Runs one FFmpeg invocation built by `args_builder(FFmpeg().option('y'))`.
    Consolidates what were three near-identical `_run_ffmpeg` helpers in
    utils/video_io.py, audio.py and optimize.py into the one real place.
    Uses the bundled ffmpeg binary (T072) when packaged, falling back to PATH."""
    from ffmpeg import FFmpeg, FFmpegError

    _warn_once_if_gpl_build()
    executable = ffmpeg_path() or 'ffmpeg'
    try:
        args_builder(FFmpeg(executable=executable).option('y')).execute()
    except (FFmpegError, OSError) as error:
        raise RuntimeError(f'Falha ao processar com ffmpeg: {error}') from error
