"""Real capacity estimation derived from hardware.py's HardwareCapability
(T061/T062, FR-031 to FR-035, FR-076 to FR-080) — every figure below is
computed from the machine's actually-available memory, never a fixed
constant independent of it (FR-035).

Two things live here:
1. `compute_tile_params()` — replaces the old fixed `_TILE_THRESHOLD=1600`/
   `_TILE_SIZE=512` constants in upscaler.py/video_upscaler.py: more free
   memory -> larger tiles (fewer seams, faster); less -> smaller tiles.
2. `check_capacity()` — the pre-flight gate FR-076/FR-077/FR-079 require:
   image/video always "fits" (tiling makes arbitrarily large inputs
   processable, just slower) unless the machine genuinely cannot hold even
   the smallest usable tile; the estimated-duration figure (FR-078) is an
   explicitly labelled order-of-magnitude estimate, not a benchmarked
   guarantee — this codebase has no per-machine benchmark harness to derive
   real throughput numbers from.
"""
from __future__ import annotations

from dataclasses import dataclass

from astros_upscale.hardware import HardwareCapability

# Conservative bytes-per-megapixel budget for one tile's fp32 activations
# (a handful of conv layers, no tiling) — deliberately generous so a real
# OOM stays rare, not a measured per-model figure.
_BYTES_PER_MEGAPIXEL_FP32 = 350 * 1024 * 1024
_MIN_TILE_SIZE = 192
_MAX_TILE_SIZE = 1024
# Below this, not even one _MIN_TILE_SIZE tile's worth of memory is free —
# genuinely nothing can proceed (FR-079).
_MIN_VIABLE_MEMORY_MB = 64

# Order-of-magnitude throughput assumptions (FR-078: "an estimate", not a
# benchmarked guarantee) — GPU figures assume a mid-range consumer card,
# CPU figures assume the tiled fp32 fallback. Deliberately conservative:
# better to over-warn about a long job than under-warn.
_GPU_PIXELS_PER_SECOND = 2_000_000
_CPU_PIXELS_PER_SECOND = 150_000
_AUDIO_REALTIME_FACTOR_GPU = 8.0
_AUDIO_REALTIME_FACTOR_CPU = 1.5


@dataclass
class CapacityCheck:
    fits: bool
    estimated_duration: float | None
    limiting_resource: str | None


def _available_memory_mb(hardware: HardwareCapability) -> tuple[int, str]:
    """FR-080 — always the currently AVAILABLE figure, never total. Prefers
    VRAM when a GPU is present and its VRAM is actually queryable; CPU/RAM
    is the real fallback otherwise (FR-033)."""
    if hardware.gpu_present and hardware.vram_available_mb is not None:
        return hardware.vram_available_mb, 'vram'
    return hardware.ram_available_mb, 'ram'


def compute_tile_params(hardware: HardwareCapability) -> tuple[int, int]:
    """Returns (tile_threshold, tile_size) — images/frames at or under
    tile_threshold px on the long side skip tiling entirely."""
    available_mb, _ = _available_memory_mb(hardware)
    megapixels_that_fit = max(available_mb, 1) / (_BYTES_PER_MEGAPIXEL_FP32 / (1024 * 1024))
    tile_side = int((max(megapixels_that_fit, 0.01) * 1_000_000) ** 0.5)
    tile_size = max(_MIN_TILE_SIZE, min(_MAX_TILE_SIZE, tile_side))
    tile_threshold = tile_size * 3  # a handful of tiles' worth before tiling is worth it at all
    return tile_threshold, tile_size


def estimate_duration_seconds(
        hardware: HardwareCapability, media_type: str,
        pixel_count: int | None, duration_seconds: float | None) -> float | None:
    if media_type in ('image', 'video') and pixel_count:
        rate = _GPU_PIXELS_PER_SECOND if hardware.gpu_present else _CPU_PIXELS_PER_SECOND
        return pixel_count / rate
    if media_type == 'audio' and duration_seconds:
        factor = _AUDIO_REALTIME_FACTOR_GPU if hardware.gpu_present else _AUDIO_REALTIME_FACTOR_CPU
        return duration_seconds / factor
    return None


def check_capacity(
        hardware: HardwareCapability, media_type: str,
        width: int | None = None, height: int | None = None,
        duration_seconds: float | None = None) -> CapacityCheck:
    """FR-076/FR-077/FR-079 — image/video refuses only when the machine
    can't even hold the smallest usable tile (tiling handles everything
    above that, just more slowly); audio has no tiling equivalent, so it
    refuses on the same bare memory floor. Never a fixed byte/pixel/second
    ceiling independent of what `hardware` actually reports (FR-035)."""
    available_mb, limiting = _available_memory_mb(hardware)
    pixel_count = (width * height) if (width and height) else None
    estimated = estimate_duration_seconds(hardware, media_type, pixel_count, duration_seconds)

    if available_mb < _MIN_VIABLE_MEMORY_MB:
        return CapacityCheck(fits=False, estimated_duration=None, limiting_resource=limiting)
    return CapacityCheck(fits=True, estimated_duration=estimated, limiting_resource=None)
