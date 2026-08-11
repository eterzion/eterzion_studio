"""Temporal stabilization and deterministic tiling for video upscaling
(T043/T044, FR-101/FR-102).

Deterministic tiling (FR-101): tile size/offset/overlap fixed for the whole
video — never varied per frame based on content, memory pressure, or
anything else. A tile grid that shifts frame-to-frame is a real source of
visible seams that "move" between frames (temporal flicker at tile
boundaries), which is worse than a fixed, occasionally-suboptimal tile size.

Temporal stabilization (FR-102): two real ffmpeg filters, both LGPL —
- `atadenoise` (pre-upscale): adaptive temporal averaging denoise across
  adjacent frames, so the model sees a less noisy, less frame-to-frame-erratic
  input than raw sensor/compression noise would give it.
- `deflicker` (post-upscale): corrects residual per-frame luminance variation
  after the model's own (necessarily per-frame, since the model itself has no
  temporal awareness) enhancement pass.

Never `hqdn3d` (GPL) for the same reason — Constitution "Licensing and
Distribution Constraints": a GPL filter in the filtergraph would GPL-license
the resulting ffmpeg invocation the same way a GPL codec does.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .transcode import run_ffmpeg


@dataclass(frozen=True)
class TileGrid:
    """A fixed tiling plan for one video — computed once from the frame size,
    reused unchanged for every single frame (FR-101). Never recomputed
    mid-video, regardless of what an individual frame's content looks like."""
    tile_size: int
    tile_pad: int
    tiles_x: int
    tiles_y: int


def compute_tile_grid(width: int, height: int, tile_size: int, tile_pad: int = 10) -> TileGrid:
    """Deterministic: the same (width, height, tile_size) always produces the
    exact same grid — no randomness, no content-adaptive resizing.
    `tile_size <= 0` means "no tiling" (one tile covering the whole frame)."""
    if tile_size <= 0:
        return TileGrid(tile_size=0, tile_pad=tile_pad, tiles_x=1, tiles_y=1)
    return TileGrid(
        tile_size=tile_size, tile_pad=tile_pad,
        tiles_x=math.ceil(width / tile_size), tiles_y=math.ceil(height / tile_size),
    )


def apply_atadenoise(input_path: str, output_path: str) -> None:
    """Pre-upscale temporal denoise — runs BEFORE the model sees any frame,
    on the original-resolution video. Audio is copied through untouched."""
    run_ffmpeg(lambda f: f.input(input_path).output(output_path, {'vf': 'atadenoise', 'c:a': 'copy'}))


def apply_deflicker(input_path: str, output_path: str) -> None:
    """Post-upscale flicker correction — runs on the already-upscaled frames.
    Audio is copied through untouched."""
    run_ffmpeg(lambda f: f.input(input_path).output(output_path, {'vf': 'deflicker', 'c:a': 'copy'}))
