"""Timeline thumbnail sprites for the video editor (FR-007a).

Justified as its own module under Princípio XI by conditions (a) and (c): it is
exercised directly by test_video_thumbnails.py without going through routes,
and it isolates an FFmpeg invocation the rest of the domain does not make.

Princípio XV governs everything here. A sprite is a derived artefact: it is
written to storage the API owns — never beside the source file — it is never
presented as the result of an operation, and it stops being used the moment the
source's content key changes.
"""
from __future__ import annotations

import os
import shutil
from typing import NamedTuple

from app.config import settings
from app.media_handles import HandleError
from eterzion_upscale.media import run_ffmpeg

# Small enough that a strip of them is cheap to decode and to keep in memory,
# large enough to recognise a scene. Height follows from the source's aspect
# ratio; only the width is fixed.
THUMBNAIL_WIDTH = 160

# Roughly this many thumbnails across the strip, whatever the duration. A fixed
# interval would produce four frames for a ten-second clip and nine thousand for
# a three-hour one.
TARGET_THUMBNAIL_COUNT = 40

# Bounds on the interval, so a very short clip does not ask FFmpeg for a frame
# every few milliseconds and a very long one still gets a usable strip.
_MIN_INTERVAL_SECONDS = 0.2
_MAX_INTERVAL_SECONDS = 60.0


class Sprite(NamedTuple):
    path: str
    count: int
    interval_seconds: float
    thumbnail_width: int
    thumbnail_height: int


def interval_for(duration_seconds: float) -> float:
    """Spacing that yields roughly TARGET_THUMBNAIL_COUNT frames, bounded."""
    if duration_seconds <= 0:
        return _MIN_INTERVAL_SECONDS
    raw = duration_seconds / TARGET_THUMBNAIL_COUNT
    return max(_MIN_INTERVAL_SECONDS, min(raw, _MAX_INTERVAL_SECONDS))


def _cache_dir() -> str:
    # Storage the API owns (Princípio XV), never next to the source file.
    return os.path.join(settings.outputs_dir, 'thumbnails')


def _sprite_path(handle_id: str, content_key: str) -> str:
    # The content key is IN the filename rather than compared alongside it. A
    # changed source therefore addresses a different file, so a stale sprite can
    # never be served by mistake — the failure mode FR-017 exists to prevent
    # becomes impossible rather than merely checked for.
    return os.path.join(_cache_dir(), f'{handle_id}_{content_key[:16]}.jpg')


def build(input_path: str, handle_id: str, content_key: str, duration_seconds: float,
          source_width: int, source_height: int, *, interval_seconds: float | None = None) -> Sprite:
    """Build (or reuse) the sprite for a source. One horizontal row of frames.

    Reuses an existing file when the content key already matches, which is the
    point of putting the key in the name.
    """
    if not source_width or not source_height:
        raise HandleError('unreadable', 'Dimensões do vídeo desconhecidas.')

    interval = interval_seconds or interval_for(duration_seconds)
    count = max(1, min(TARGET_THUMBNAIL_COUNT, int(duration_seconds / interval) or 1))
    height = max(2, int(round(THUMBNAIL_WIDTH * source_height / source_width)) // 2 * 2)
    path = _sprite_path(handle_id, content_key)

    if os.path.isfile(path):
        return Sprite(path, count, interval, THUMBNAIL_WIDTH, height)

    os.makedirs(_cache_dir(), exist_ok=True)
    # fps=1/interval samples one frame per interval; tile lays them in a single
    # row. Both numbers are computed here from probed metadata — nothing in this
    # graph comes from a request (Princípio XIII).
    run_ffmpeg(lambda f: f.input(input_path).output(
        path,
        {'vf': f'fps=1/{interval:.6f},scale={THUMBNAIL_WIDTH}:{height},tile={count}x1',
         'frames:v': '1', 'q:v': '4'},
    ))
    if not os.path.isfile(path):
        raise HandleError('unreadable', 'Não foi possível gerar as miniaturas.')
    return Sprite(path, count, interval, THUMBNAIL_WIDTH, height)


def discard_stale(handle_id: str, current_content_key: str) -> int:
    """Remove sprites for this handle whose content key is not the current one.

    Princípio XV: derived artefacts are invalidated, not merely bypassed.
    Leaving them on disk would grow the cache without bound every time someone
    re-exports over their source.
    """
    directory = _cache_dir()
    if not os.path.isdir(directory):
        return 0
    keep = os.path.basename(_sprite_path(handle_id, current_content_key))
    removed = 0
    for name in os.listdir(directory):
        if name.startswith(f'{handle_id}_') and name != keep:
            try:
                os.remove(os.path.join(directory, name))
                removed += 1
            except OSError:
                # A file another process still has open is not worth failing a
                # request over; it will be caught by the next pass.
                pass
    return removed


def clear_all() -> None:
    """Drop the whole cache. For tests and for application shutdown."""
    shutil.rmtree(_cache_dir(), ignore_errors=True)
