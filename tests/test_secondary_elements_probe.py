"""T047 — real ffprobe-backed detection of secondary elements a video-enhance
job would silently drop (extra audio tracks, subtitles, chapters), FR-081 to
FR-086. Every fixture here is a real file built with real ffmpeg, not a
mocked ffprobe response."""
import subprocess

import pytest

from astros_upscale.media_engine.probe import detect_secondary_elements
from astros_upscale.utils.video_io import has_ffmpeg

pytestmark = pytest.mark.skipif(not has_ffmpeg(), reason='requires a real ffmpeg binary on PATH')


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(['ffmpeg', '-y', *args], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def _simple_video_with_audio(path: str, duration: float = 1.0) -> None:
    _run_ffmpeg([
        '-f', 'lavfi', '-i', f'color=c=blue:s=64x48:d={duration}',
        '-f', 'lavfi', '-i', f'sine=frequency=440:d={duration}',
        '-c:v', 'mpeg4', '-c:a', 'aac', '-shortest', path,
    ])


def test_single_audio_track_no_subtitles_no_chapters_has_no_losses(tmp_path):
    path = str(tmp_path / 'simple.mp4')
    _simple_video_with_audio(path)
    info = detect_secondary_elements(path)
    assert info['has_losses'] is False
    assert info['losses'] == []
    assert info['audio_stream_count'] == 1


def test_video_with_no_audio_at_all_has_no_losses(tmp_path):
    path = str(tmp_path / 'silent.mp4')
    _run_ffmpeg(['-f', 'lavfi', '-i', 'color=c=red:s=64x48:d=1', '-c:v', 'mpeg4', '-an', path])
    info = detect_secondary_elements(path)
    assert info['has_losses'] is False
    assert info['audio_stream_count'] == 0


def test_two_audio_tracks_flagged_as_a_loss(tmp_path):
    path = str(tmp_path / 'dual_audio.mp4')
    _run_ffmpeg([
        '-f', 'lavfi', '-i', 'color=c=blue:s=64x48:d=1',
        '-f', 'lavfi', '-i', 'sine=frequency=440:d=1',
        '-f', 'lavfi', '-i', 'sine=frequency=880:d=1',
        '-map', '0:v', '-map', '1:a', '-map', '2:a',
        '-c:v', 'mpeg4', '-c:a', 'aac', '-shortest', path,
    ])
    info = detect_secondary_elements(path)
    assert info['has_losses'] is True
    assert 'extra_audio_tracks' in info['losses']
    assert info['audio_stream_count'] == 2


def test_subtitle_track_flagged_as_a_loss(tmp_path):
    srt_path = tmp_path / 'subs.srt'
    srt_path.write_text('1\n00:00:00,000 --> 00:00:01,000\nOlá\n', encoding='utf-8')
    video_path = str(tmp_path / 'plain.mp4')
    _simple_video_with_audio(video_path)

    out_path = str(tmp_path / 'with_subs.mkv')
    _run_ffmpeg([
        '-i', video_path, '-i', str(srt_path),
        '-map', '0:v', '-map', '0:a', '-map', '1:s',
        '-c:v', 'copy', '-c:a', 'copy', '-c:s', 'srt', out_path,
    ])
    info = detect_secondary_elements(out_path)
    assert info['has_losses'] is True
    assert 'subtitles' in info['losses']
    assert info['subtitle_stream_count'] == 1


def test_chapters_flagged_as_a_loss(tmp_path):
    metadata_path = tmp_path / 'chapters.ffmetadata'
    metadata_path.write_text(
        ';FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=500\ntitle=Início\n', encoding='utf-8')
    video_path = str(tmp_path / 'plain2.mp4')
    _simple_video_with_audio(video_path)

    out_path = str(tmp_path / 'with_chapters.mp4')
    _run_ffmpeg([
        '-f', 'ffmetadata', '-i', str(metadata_path), '-i', video_path,
        '-map_metadata', '0', '-map_chapters', '0',
        '-c', 'copy', out_path,
    ])
    info = detect_secondary_elements(out_path)
    assert info['has_losses'] is True
    assert 'chapters' in info['losses']
