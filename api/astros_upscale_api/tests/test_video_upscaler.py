"""T040/T042 — real, end-to-end coverage of VideoUpscaler.process(): a genuine
ffmpeg-built input video, run through the real `realesr-animevideo` model
(already downloaded to models/), verified via real ffprobe afterwards that
fps, duration, audio channels and aspect ratio all survive the round trip.
No mocking of the model, the video I/O, or the ffprobe verification."""
from __future__ import annotations

import subprocess

import pytest

from app.config import settings
from app.processing import VideoUpscaler
from astros_upscale.media import ffprobe_json, has_ffmpeg
from astros_upscale.media import ffmpeg_path

pytestmark = pytest.mark.skipif(not has_ffmpeg(), reason='requires a real ffmpeg binary on PATH')


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run([ffmpeg_path() or ffmpeg_path() or 'ffmpeg', '-y', *args], capture_output=True, text=True, timeout=30)
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


class TestCustomSize:
    """The Vídeo screen's Customizado presets (1080p, 1440p, 4K...) send an exact
    output resolution instead of a multiplier. Runs the real model, like every
    other test in this file — nothing here is mocked."""

    @pytest.fixture(scope='class')
    @classmethod
    def sized_video(cls, tmp_path_factory):
        tmp_path = tmp_path_factory.mktemp('video_custom_size')
        input_path = str(tmp_path / 'input.mp4')
        output_path = str(tmp_path / 'output.mp4')
        _build_input_video(input_path)

        upscaler = VideoUpscaler('realesr-animevideo', settings.models_dir, device='cpu', half=False)
        # 64x48 source, deliberately not a whole multiple of either axis.
        result = upscaler.process(
            input_path, scale=2, output_path=output_path, custom_size=(200, 120)
        )
        return {'result': result, 'probe': ffprobe_json(output_path)}

    def test_lands_on_the_exact_requested_resolution(self, sized_video):
        stream = _video_stream(sized_video['probe'])
        assert (stream['width'], stream['height']) == (200, 120)

    def test_reports_the_custom_size_as_the_output_size(self, sized_video):
        assert sized_video['result']['output_size'] == (200, 120)

    def test_source_size_still_reports_the_real_input(self, sized_video):
        assert sized_video['result']['source_size'] == (64, 48)
