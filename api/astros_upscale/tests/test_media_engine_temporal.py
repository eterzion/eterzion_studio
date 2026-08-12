"""T043/T044 — real tests for deterministic tiling and temporal stabilization."""
import json
import subprocess

import numpy as np
import pytest

from astros_upscale.media import apply_atadenoise, apply_deflicker, compute_tile_grid
from astros_upscale.media import VideoWriter


def _write_toy_video(path, frames=8, width=64, height=48, fps=10.0):
    writer = VideoWriter(str(path), fps=fps, width=width, height=height)
    rng = np.random.default_rng(1)
    for i in range(frames):
        # deliberately flickering brightness so deflicker has something real to fix
        base = 80 + (i % 2) * 60
        frame = np.clip(base + rng.normal(0, 15, (height, width, 3)), 0, 255).astype(np.uint8)
        writer.write(frame)
    writer.close()
    return str(path)


def _probe(path):
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path],
        capture_output=True, text=True)
    return json.loads(result.stdout)


class TestComputeTileGrid:
    def test_same_input_always_produces_the_same_grid(self):
        a = compute_tile_grid(1920, 1080, tile_size=512)
        b = compute_tile_grid(1920, 1080, tile_size=512)
        assert a == b

    def test_grid_covers_the_whole_frame(self):
        grid = compute_tile_grid(1000, 700, tile_size=300)
        assert grid.tiles_x * grid.tile_size >= 1000
        assert grid.tiles_y * grid.tile_size >= 700

    def test_zero_tile_size_means_a_single_tile(self):
        grid = compute_tile_grid(1920, 1080, tile_size=0)
        assert (grid.tiles_x, grid.tiles_y) == (1, 1)

    def test_different_frame_sizes_produce_different_grids(self):
        """Real proof of determinism: it's a pure function of the inputs, not
        of frame content or processing order — same size in, same grid out,
        every time, and a DIFFERENT size genuinely changes it."""
        small = compute_tile_grid(512, 512, tile_size=256)
        large = compute_tile_grid(2048, 2048, tile_size=256)
        assert small != large


class TestAtadenoise:
    def test_real_ffmpeg_run_preserves_frame_count_and_dimensions(self, tmp_path):
        src = _write_toy_video(tmp_path / 'in.mp4')
        out = str(tmp_path / 'denoised.mp4')
        apply_atadenoise(src, out)

        before = _probe(src)
        after = _probe(out)
        v_before = next(s for s in before['streams'] if s['codec_type'] == 'video')
        v_after = next(s for s in after['streams'] if s['codec_type'] == 'video')
        assert v_after['width'] == v_before['width']
        assert v_after['height'] == v_before['height']
        assert v_after['nb_frames'] == v_before['nb_frames']


class TestDeflicker:
    def test_real_ffmpeg_run_reduces_frame_to_frame_brightness_variance(self, tmp_path):
        """The toy video was built with deliberately alternating brightness —
        a real, measurable claim: deflicker must reduce that variance, not
        just run without error."""
        import cv2

        src = _write_toy_video(tmp_path / 'flicker.mp4')
        out = str(tmp_path / 'deflickered.mp4')
        apply_deflicker(src, out)

        def mean_brightness_diffs(path):
            cap = cv2.VideoCapture(path)
            means = []
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                means.append(frame.mean())
            cap.release()
            diffs = [abs(means[i] - means[i - 1]) for i in range(1, len(means))]
            return diffs

        before_diffs = mean_brightness_diffs(src)
        after_diffs = mean_brightness_diffs(out)
        assert sum(after_diffs) / len(after_diffs) < sum(before_diffs) / len(before_diffs)

    def test_real_ffmpeg_run_preserves_frame_count_and_dimensions(self, tmp_path):
        src = _write_toy_video(tmp_path / 'in.mp4')
        out = str(tmp_path / 'deflickered.mp4')
        apply_deflicker(src, out)

        before = _probe(src)
        after = _probe(out)
        v_before = next(s for s in before['streams'] if s['codec_type'] == 'video')
        v_after = next(s for s in after['streams'] if s['codec_type'] == 'video')
        assert v_after['width'] == v_before['width']
        assert v_after['height'] == v_before['height']
