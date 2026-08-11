"""Central FFmpeg access point — the single place every media domain (video, audio,
compression, conversion) shells out to FFmpeg from, replacing three previously
independent implementations (astros_upscale.utils.video_io, astros_upscale.audio,
astros_upscale.optimize each had their own inline/`_run_ffmpeg` pattern).

Licence note: this module deliberately does NOT fail at import time when the
resolved ffmpeg binary is a GPL build (`--enable-gpl`/`--enable-nonfree`) — the
developer's local ffmpeg is irrelevant to the Constitution's LGPL requirement,
which is about what gets *bundled in the shipped installer*. A GPL dev machine
must not block `pytest` or local development. `is_lgpl_build()` below is the
real check, and it's enforced at packaging time (tasks.md T072), not at import.
"""
from __future__ import annotations

from .probe import ffprobe_json, probe_streams
from .temporal import TileGrid, apply_atadenoise, apply_deflicker, compute_tile_grid
from .transcode import GPL_ENCODERS, has_ffmpeg, is_lgpl_build, run_ffmpeg

__all__ = [
    'has_ffmpeg', 'is_lgpl_build', 'run_ffmpeg', 'GPL_ENCODERS', 'probe_streams', 'ffprobe_json',
    'TileGrid', 'compute_tile_grid', 'apply_atadenoise', 'apply_deflicker',
]
