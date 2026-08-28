"""T008 (specs/007-video-editor-player) — the identifier registry that lets every
other route stop accepting filesystem paths.

Constitution Princípio XIII, and specifically the four conditions its v3.0.0
bounded exception attaches to the one route that may accept a path. Three of
them are properties of this module and are tested here; the fourth (no other
route accepts a path) is a property of the route surface and is tested in
test_video_contract_surface.py.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app import media_handles


@pytest.fixture(autouse=True)
def clean_registry():
    media_handles.clear()
    yield
    media_handles.clear()


FIXTURES = Path(__file__).resolve().parent / 'fixtures'


@pytest.fixture
def video(tmp_path):
    """A real, ffprobe-readable video, copied so tests may modify it freely.

    An earlier version of this fixture wrote 4 KB of zeroes with an .mp4
    extension. register() rejected it — correctly — and the failure was the
    test's, not the module's. Princípio VIII: processing pipelines are tested
    against real behaviour, and 'a file ffprobe cannot read' exercises the
    rejection path, not the registration path this suite is about.
    """
    source = FIXTURES / 'curto.mp4'
    if not source.exists():
        pytest.skip('fixtures ausentes — rode tests/fixtures/make_video_fixtures.py')
    path = tmp_path / 'entrevista.mp4'
    path.write_bytes(source.read_bytes())
    return path


def test_register_returns_an_identifier(video):
    handle_id = media_handles.register(str(video))
    assert handle_id
    assert media_handles.resolve(handle_id) == str(video)


def test_identifier_is_not_a_reversible_encoding_of_the_path(video):
    """Fourth condition of the v3.0.0 exception. A base64 of the path would
    satisfy every other rule here and defeat the point of all of them."""
    handle_id = media_handles.register(str(video))
    import base64

    for encoding in ('utf-8', 'utf-16-le'):
        raw = str(video).encode(encoding)
        for variant in (base64.b64encode(raw), base64.b32encode(raw), base64.b16encode(raw)):
            assert variant.decode().rstrip('=').lower() not in handle_id.lower()
    assert video.name not in handle_id
    assert str(video.parent) not in handle_id


def test_two_registrations_of_the_same_file_do_not_collide(video):
    assert media_handles.register(str(video)) != media_handles.register(str(video))


def test_unknown_identifier_resolves_to_nothing():
    assert media_handles.resolve('vh_inexistente') is None


def test_register_refuses_a_missing_file(tmp_path):
    with pytest.raises(media_handles.HandleError):
        media_handles.register(str(tmp_path / 'nao_existe.mp4'))


def test_register_refuses_a_directory(tmp_path):
    with pytest.raises(media_handles.HandleError):
        media_handles.register(str(tmp_path))


def test_register_refuses_a_non_video_extension(tmp_path):
    path = tmp_path / 'documento.pdf'
    path.write_bytes(b'%PDF-1.4')
    with pytest.raises(media_handles.HandleError):
        media_handles.register(str(path))


def test_metadata_never_exposes_the_path(video):
    handle_id = media_handles.register(str(video))
    metadata = media_handles.describe(handle_id)
    # Second condition of the exception: the path is never returned. Checked
    # against every value in the payload, not against a field allowlist — a
    # future field would otherwise leak it silently.
    for value in metadata.values():
        assert str(video) != value
        assert str(video.parent) != value
    assert metadata['display_name'] == 'entrevista.mp4'


def test_content_change_is_detected(video):
    handle_id = media_handles.register(str(video))
    assert not media_handles.has_content_changed(handle_id)
    video.write_bytes(b'\x01' * 8192)
    assert media_handles.has_content_changed(handle_id)


def test_content_change_is_detected_for_a_same_size_rewrite(video):
    """Size alone would let a same-size overwrite pass as unchanged. FR-017
    depends on this not happening, so the content sample has to be doing real
    work — this rewrites bytes in place and keeps the length identical."""
    handle_id = media_handles.register(str(video))
    original = video.read_bytes()
    before = video.stat()

    mutated = bytearray(original)
    mutated[100:200] = bytes(100)
    video.write_bytes(bytes(mutated))
    # Restore size AND mtime, so neither of the two cheap signals can be what
    # detects this. Without it the test passes on the changed mtime alone and
    # proves nothing about the content sample it exists to exercise.
    os.utime(video, ns=(before.st_atime_ns, before.st_mtime_ns))

    after = video.stat()
    assert after.st_size == before.st_size
    assert after.st_mtime_ns == before.st_mtime_ns
    assert media_handles.has_content_changed(handle_id)


def test_deleted_file_counts_as_changed(video):
    handle_id = media_handles.register(str(video))
    video.unlink()
    assert media_handles.has_content_changed(handle_id)


@pytest.mark.parametrize(
    'raw, forbidden',
    [
        ('../../etc/passwd', '..'),
        ('..\\..\\windows\\system32', '..'),
        ('a/b/c.mp4', '/'),
        ('a\\b\\c.mp4', '\\'),
        ('nul.mp4', None),
        ('arquivo\x00oculto.mp4', '\x00'),
    ],
)
def test_sanitise_display_name_strips_path_construction(raw, forbidden):
    """Princípio XIII: "Filenames arriving from a client are treated as display
    text and MUST be sanitised before being used to construct any path"."""
    safe = media_handles.sanitise_display_name(raw)
    assert safe
    if forbidden:
        assert forbidden not in safe
    assert not safe.startswith('.')


def test_sanitise_display_name_keeps_ordinary_names():
    assert media_handles.sanitise_display_name('Entrevista Final.mp4') == 'Entrevista Final.mp4'


def test_sanitise_display_name_survives_an_empty_result():
    """'...' sanitises down to nothing; the function must still return a usable
    name rather than an empty string that a caller then joins into a path."""
    assert media_handles.sanitise_display_name('...')
    assert media_handles.sanitise_display_name('')
