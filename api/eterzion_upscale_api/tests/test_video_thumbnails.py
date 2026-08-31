"""T035 (specs/007-video-editor-player) — timeline thumbnail sprites.

Real FFmpeg (Princípio VIII). The invalidation test is the important one: it is
quickstart scenario 12, and it is the case that fails silently when a cache key
is a path.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app import video_thumbnails
from eterzion_upscale.media import content_key, has_ffmpeg

FIXTURES = Path(__file__).resolve().parent / 'fixtures'
needs_ffmpeg = pytest.mark.skipif(not has_ffmpeg(), reason='ffmpeg não encontrado')


@pytest.fixture(autouse=True)
def clean_cache():
    video_thumbnails.clear_all()
    yield
    video_thumbnails.clear_all()


@pytest.fixture
def source(tmp_path):
    original = FIXTURES / 'curto.mp4'
    if not original.exists():
        pytest.skip('fixtures ausentes — rode tests/fixtures/make_video_fixtures.py')
    path = tmp_path / 'origem.mp4'
    path.write_bytes(original.read_bytes())
    return path


def _build(path, handle_id='vh_test'):
    return video_thumbnails.build(
        str(path), handle_id, content_key(str(path)),
        duration_seconds=10.0, source_width=1920, source_height=1080,
    )


class TestInterval:
    def test_short_and_long_videos_both_get_a_usable_strip(self):
        # A fixed interval would give four frames for a ten-second clip and
        # nine thousand for a three-hour one.
        assert video_thumbnails.interval_for(10) >= video_thumbnails._MIN_INTERVAL_SECONDS
        assert video_thumbnails.interval_for(3 * 3600) <= video_thumbnails._MAX_INTERVAL_SECONDS

    def test_a_one_second_clip_does_not_ask_for_a_frame_every_millisecond(self):
        assert video_thumbnails.interval_for(1) >= video_thumbnails._MIN_INTERVAL_SECONDS

    def test_zero_duration_does_not_divide_by_zero(self):
        assert video_thumbnails.interval_for(0) > 0


@needs_ffmpeg
class TestBuild:
    def test_produces_a_sprite(self, source):
        sprite = _build(source)
        assert os.path.isfile(sprite.path)
        assert os.path.getsize(sprite.path) > 0
        assert sprite.count >= 1

    def test_writes_to_api_storage_not_beside_the_source(self, source):
        """Princípio XV: derived artefacts live in storage the API owns."""
        sprite = _build(source)
        assert Path(sprite.path).parent != source.parent
        assert not list(source.parent.glob('*.jpg'))

    def test_leaves_the_source_untouched(self, source):
        before = source.read_bytes()
        _build(source)
        assert source.read_bytes() == before

    def test_reuses_an_existing_sprite(self, source):
        first = _build(source)
        mtime = os.path.getmtime(first.path)
        second = _build(source)
        assert second.path == first.path
        assert os.path.getmtime(second.path) == mtime, 'regerou em vez de reaproveitar'

    def test_preserves_the_source_aspect_ratio(self, source):
        sprite = _build(source)
        # 1920x1080 at width 160 is 90 high, rounded to even.
        assert sprite.thumbnail_height == 90


@needs_ffmpeg
class TestInvalidation:
    """Quickstart scenario 12 — the case that passes silently when the cache key
    is a path."""

    def test_changed_content_addresses_a_different_sprite(self, source, tmp_path):
        first = _build(source)

        replacement = FIXTURES / 'sem_audio.mp4'
        source.write_bytes(replacement.read_bytes())
        second = _build(source)

        assert second.path != first.path, 'conteúdo mudou e a sprite antiga foi reaproveitada'

    def test_stale_sprites_are_removed_not_merely_bypassed(self, source):
        first = _build(source)
        source.write_bytes((FIXTURES / 'sem_audio.mp4').read_bytes())
        new_key = content_key(str(source))

        removed = video_thumbnails.discard_stale('vh_test', new_key)
        assert removed == 1
        assert not os.path.isfile(first.path)

    def test_discarding_keeps_the_current_sprite(self, source):
        sprite = _build(source)
        video_thumbnails.discard_stale('vh_test', content_key(str(source)))
        assert os.path.isfile(sprite.path)

    def test_discarding_does_not_touch_another_handle(self, source):
        mine = _build(source, handle_id='vh_mine')
        theirs = _build(source, handle_id='vh_theirs')
        video_thumbnails.discard_stale('vh_mine', 'chave_diferente')
        assert not os.path.isfile(mine.path)
        assert os.path.isfile(theirs.path)

    def test_discarding_an_empty_cache_is_harmless(self):
        video_thumbnails.clear_all()
        assert video_thumbnails.discard_stale('vh_test', 'qualquer') == 0
