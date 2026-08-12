"""T040/T042 — real, end-to-end coverage of VideoUpscaler.process(): a genuine
ffmpeg-built input video, run through the real `realesr-animevideo` model
(already downloaded to models/), verified via real ffprobe afterwards that
fps, duration, audio channels and aspect ratio all survive the round trip.
No mocking of the model, the video I/O, or the ffprobe verification."""
from __future__ import annotations

import subprocess

import pytest

from app.config import settings
from app.core.video_upscaler import VideoUpscaler
from astros_upscale.media_engine.probe import ffprobe_json
from astros_upscale.utils.video_io import has_ffmpeg

pytestmark = pytest.mark.skipif(not has_ffmpeg(), reason='requires a real ffmpeg binary on PATH')


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(['ffmpeg', '-y', *args], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def _build_input_video(path: str, duration: float = 1.0, fps: int = 12) -> None:
    """Small, real, decodable video with a real audio track — cheap enough
    (12 fps, 1s, 64x48) to run through the real model in a unit test."""
    _run_ffmpeg([
        '-f', 'lavfi', '-i', f'color=c=blue:s=64x48:r={fps}:d={duration}',
        '-f', 'lavfi', '-i', f'sine=frequency=440:d={duration}',
        '-c:v', 'mpeg4', '-c:a', 'aac', '-shortest', path,
    ])


@pytest.fixture(scope='module')
def upscaled_video(tmp_path_factory):
    """Runs the real model once (module-scoped — model load + inference on a
    12-frame clip is the expensive part) and hands every test the same
    already-produced output + its real ffprobe data."""
    tmp_path = tmp_path_factory.mktemp('video_upscaler')
    input_path = str(tmp_path / 'input.mp4')
    output_path = str(tmp_path / 'output.mp4')
    _build_input_video(input_path)

    upscaler = VideoUpscaler('realesr-animevideo', settings.models_dir, device='cpu', half=False)
    result = upscaler.process(input_path, scale=2, output_path=output_path)

    return {
        'input_path': input_path, 'output_path': output_path, 'result': result,
        'input_probe': ffprobe_json(input_path), 'output_probe': ffprobe_json(output_path),
    }


def _video_stream(probe: dict) -> dict:
    return next(s for s in probe['streams'] if s['codec_type'] == 'video')


def _audio_stream(probe: dict) -> dict | None:
    return next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)


class TestVideoUpscalerPreservesRealMetadata:
    def test_output_file_exists_and_is_decodable(self, upscaled_video):
        import os

        assert os.path.isfile(upscaled_video['output_path'])
        assert os.path.getsize(upscaled_video['output_path']) > 0

    def test_resolution_scales_by_the_requested_factor(self, upscaled_video):
        in_v = _video_stream(upscaled_video['input_probe'])
        out_v = _video_stream(upscaled_video['output_probe'])
        assert out_v['width'] == in_v['width'] * 2
        assert out_v['height'] == in_v['height'] * 2

    def test_aspect_ratio_is_preserved(self, upscaled_video):
        in_v = _video_stream(upscaled_video['input_probe'])
        out_v = _video_stream(upscaled_video['output_probe'])
        in_ratio = in_v['width'] / in_v['height']
        out_ratio = out_v['width'] / out_v['height']
        assert out_ratio == pytest.approx(in_ratio, rel=0.05)

    def test_fps_is_preserved(self, upscaled_video):
        in_v = _video_stream(upscaled_video['input_probe'])
        out_v = _video_stream(upscaled_video['output_probe'])

        def _fps(stream):
            num, den = stream['r_frame_rate'].split('/')
            return float(num) / float(den)

        assert _fps(out_v) == pytest.approx(_fps(in_v), rel=0.05)

    def test_duration_is_preserved(self, upscaled_video):
        in_duration = float(upscaled_video['input_probe']['format']['duration'])
        out_duration = float(upscaled_video['output_probe']['format']['duration'])
        assert out_duration == pytest.approx(in_duration, abs=0.2)

    def test_audio_track_is_preserved(self, upscaled_video):
        in_a = _audio_stream(upscaled_video['input_probe'])
        out_a = _audio_stream(upscaled_video['output_probe'])
        assert in_a is not None
        assert out_a is not None
        assert out_a['channels'] == in_a['channels']

    def test_result_reports_correct_source_and_output_sizes(self, upscaled_video):
        in_v = _video_stream(upscaled_video['input_probe'])
        result = upscaled_video['result']
        assert result['source_size'] == (in_v['width'], in_v['height'])
        assert result['output_size'] == (in_v['width'] * 2, in_v['height'] * 2)


def test_video_without_audio_produces_a_silent_but_valid_output(tmp_path):
    input_path = str(tmp_path / 'silent.mp4')
    output_path = str(tmp_path / 'silent_out.mp4')
    _run_ffmpeg(['-f', 'lavfi', '-i', 'color=c=red:s=64x48:r=8:d=1', '-c:v', 'mpeg4', '-an', input_path])

    upscaler = VideoUpscaler('realesr-animevideo', settings.models_dir, device='cpu', half=False)
    result = upscaler.process(input_path, scale=2, output_path=output_path)

    import os
    assert os.path.isfile(output_path)
    out_probe = ffprobe_json(output_path)
    assert _audio_stream(out_probe) is None
    assert result['output_size'] == (128, 96)
