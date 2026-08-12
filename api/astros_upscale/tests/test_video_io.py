import json
import subprocess

import numpy as np
import pytest

from astros_upscale.processing import resolve_model
from astros_upscale.media import ImageOpenError, imread
from astros_upscale.media import VideoOpenError, VideoReader, VideoWriter, copy_audio, has_ffmpeg


def _write_toy_video(path, frames=5, width=32, height=24, fps=10.0):
    writer = VideoWriter(str(path), fps=fps, width=width, height=height)
    rng = np.random.default_rng(0)
    for _ in range(frames):
        writer.write(rng.integers(0, 255, (height, width, 3), dtype=np.uint8))
    writer.close()
    return str(path)


def _probe_streams(path):
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', path], capture_output=True, text=True)
    return [s['codec_type'] for s in json.loads(result.stdout)['streams']]


def test_video_roundtrip(tmp_path):
    path = _write_toy_video(tmp_path / 'toy.mp4', frames=5, width=32, height=24, fps=10.0)
    reader = VideoReader(path)
    assert (reader.width, reader.height) == (32, 24)
    assert reader.fps == pytest.approx(10.0)
    assert len(reader) == 5
    frames = list(reader)
    reader.close()
    assert len(frames) == 5
    assert frames[0].shape == (24, 32, 3)


def test_video_reader_nonexistent(tmp_path):
    with pytest.raises(ValueError):
        VideoReader(str(tmp_path / 'nao_existe.mp4'))


def test_video_reader_corrupted(tmp_path):
    bad = tmp_path / 'corrompido.mp4'
    bad.write_bytes(b'isto nao e um video' * 100)
    with pytest.raises(VideoOpenError):
        VideoReader(str(bad))


def test_imread_nonexistent(tmp_path):
    with pytest.raises(ImageOpenError):
        imread(str(tmp_path / 'nao_existe.png'))


def test_resolve_model_invalid():
    with pytest.raises(ValueError, match='Modelo desconhecido'):
        resolve_model('modelo-que-nao-existe')


@pytest.mark.skipif(not has_ffmpeg(), reason='ffmpeg binary not available')
def test_copy_audio_preserves_audio_track(tmp_path):
    from ffmpeg import FFmpeg

    upscaled = _write_toy_video(tmp_path / 'upscaled.mp4')
    silent_source = _write_toy_video(tmp_path / 'source_silent.mp4')

    # build a source video WITH an audio track (sine wave)
    source_with_audio = str(tmp_path / 'source_audio.mp4')
    (FFmpeg().option('y')
     .input(silent_source)
     .input('sine=frequency=440:duration=1', f='lavfi')
     .output(source_with_audio, {'c:v': 'copy', 'c:a': 'aac'}, shortest=None)
     .execute())
    assert 'audio' in _probe_streams(source_with_audio)

    output = str(tmp_path / 'final.mp4')
    assert copy_audio(source_with_audio, upscaled, output) is True
    streams = _probe_streams(output)
    assert 'video' in streams and 'audio' in streams


@pytest.mark.skipif(not has_ffmpeg(), reason='ffmpeg binary not available')
def test_copy_audio_source_without_audio(tmp_path):
    # a source with no audio track must still succeed (video-only output)
    upscaled = _write_toy_video(tmp_path / 'upscaled.mp4')
    silent_source = _write_toy_video(tmp_path / 'source_silent.mp4')
    output = str(tmp_path / 'final.mp4')
    assert copy_audio(silent_source, upscaled, output) is True
    assert _probe_streams(output) == ['video']


def test_copy_audio_invalid_input(tmp_path):
    # a corrupted "upscaled" file must fail gracefully (False), never raise
    bad = tmp_path / 'bad.mp4'
    bad.write_bytes(b'nao e video')
    ok = copy_audio(str(bad), str(bad), str(tmp_path / 'out.mp4'))
    assert ok is False
