"""T059 — real coverage of capacity.py's hardware-derived computations
(FR-031 to FR-035): injected HardwareCapability values (never mocking the
math itself) prove low-RAM/no-GPU yields a strictly smaller computed
capacity than high-RAM/GPU, for both tiling and the duration estimate.
"""
from __future__ import annotations

from app.processing import check_capacity, compute_tile_params, estimate_duration_seconds
from eterzion_upscale.processing import HardwareCapability


def _hardware(**overrides) -> HardwareCapability:
    base = dict(
        cpu_cores=4, ram_total_mb=8192, ram_available_mb=4096,
        gpu_present=False, gpu_vendor='unknown', vram_total_mb=None, vram_available_mb=None,
    )
    base.update(overrides)
    return HardwareCapability(**base)


LOW_END = _hardware(ram_total_mb=4096, ram_available_mb=256, gpu_present=False)
HIGH_END = _hardware(
    ram_total_mb=65536, ram_available_mb=32768,
    gpu_present=True, gpu_vendor='nvidia', vram_total_mb=24576, vram_available_mb=20480,
)


class TestComputeTileParams:
    def test_low_end_hardware_gets_a_smaller_tile_than_high_end(self):
        _, low_tile_size = compute_tile_params(LOW_END)
        _, high_tile_size = compute_tile_params(HIGH_END)
        assert low_tile_size < high_tile_size

    def test_tile_size_is_never_below_the_floor(self):
        starved = _hardware(ram_available_mb=1)
        _, tile_size = compute_tile_params(starved)
        assert tile_size >= 192

    def test_tile_size_is_never_above_the_ceiling(self):
        _, tile_size = compute_tile_params(HIGH_END)
        assert tile_size <= 1024

    def test_result_is_deterministic_for_the_same_input(self):
        assert compute_tile_params(LOW_END) == compute_tile_params(LOW_END)


class TestEstimateDurationSeconds:
    def test_gpu_estimate_is_faster_than_cpu_for_the_same_image_size(self):
        pixel_count = 4000 * 3000
        gpu_seconds = estimate_duration_seconds(HIGH_END, 'image', pixel_count, None)
        cpu_seconds = estimate_duration_seconds(LOW_END, 'image', pixel_count, None)
        assert gpu_seconds < cpu_seconds

    def test_larger_image_takes_longer_than_smaller_on_the_same_hardware(self):
        small = estimate_duration_seconds(LOW_END, 'image', 1000 * 1000, None)
        large = estimate_duration_seconds(LOW_END, 'image', 8000 * 8000, None)
        assert large > small

    def test_audio_uses_duration_not_pixel_count(self):
        seconds = estimate_duration_seconds(LOW_END, 'audio', None, 120.0)
        assert seconds is not None and seconds > 0

    def test_returns_none_without_enough_information(self):
        assert estimate_duration_seconds(LOW_END, 'image', None, None) is None


class TestCheckCapacity:
    def test_a_starved_machine_does_not_fit(self):
        starved = _hardware(ram_available_mb=8, gpu_present=False)
        result = check_capacity(starved, 'image', width=1000, height=1000)
        assert result.fits is False
        assert result.limiting_resource == 'ram'

    def test_a_starved_gpu_machine_names_vram_as_the_limiting_resource(self):
        starved = _hardware(gpu_present=True, gpu_vendor='nvidia', vram_total_mb=2048, vram_available_mb=8)
        result = check_capacity(starved, 'image', width=1000, height=1000)
        assert result.fits is False
        assert result.limiting_resource == 'vram'

    def test_normal_hardware_fits_and_reports_an_estimate(self):
        result = check_capacity(HIGH_END, 'image', width=4000, height=3000)
        assert result.fits is True
        assert result.limiting_resource is None
        assert result.estimated_duration is not None and result.estimated_duration > 0

    def test_low_end_hardware_reports_a_longer_estimate_than_high_end_for_the_same_input(self):
        low = check_capacity(LOW_END, 'image', width=4000, height=3000)
        high = check_capacity(HIGH_END, 'image', width=4000, height=3000)
        assert low.fits is True and high.fits is True
        assert low.estimated_duration > high.estimated_duration
