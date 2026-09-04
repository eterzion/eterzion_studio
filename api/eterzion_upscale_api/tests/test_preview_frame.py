"""T041 (specs/007-video-editor-player) — the on-demand preview, through the
route.

test_video_edits.py already covers render_frame() directly. What this adds is
what the route promises on top of it: the source is untouched, no temporary file
survives, and a changed source is refused rather than previewed from stale
content.
"""
from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import media_handles
from app.config import settings
from app.main import app
from eterzion_upscale.media import has_ffmpeg

FIXTURES = Path(__file__).resolve().parent / 'fixtures'
needs_ffmpeg = pytest.mark.skipif(not has_ffmpeg(), reason='ffmpeg não encontrado')


@pytest.fixture
def client():
    media_handles.clear()
    with TestClient(app) as test_client:
        yield test_client
    media_handles.clear()


@pytest.fixture
def source(tmp_path):
    original = FIXTURES / 'curto.mp4'
    if not original.exists():
        pytest.skip('fixtures ausentes — rode tests/fixtures/make_video_fixtures.py')
    path = tmp_path / 'origem.mp4'
    path.write_bytes(original.read_bytes())
    return path


@pytest.fixture
def handle_id(client, source):
    return client.post('/media/handles', json={'path': str(source)}).json()['handle_id']


def _request(**overrides):
    body = {'time_seconds': 2.0, 'edits': {}}
    body.update(overrides)
    return body


@needs_ffmpeg
def test_returns_a_before_and_after_pair(client, handle_id):
    response = client.post(f'/media/handles/{handle_id}/preview-frame', json=_request())
    assert response.status_code == 200
    body = response.json()
    for key in ('before', 'after'):
        # Decodable PNG bytes, not just a non-empty string: a base64 of an empty
        # file would satisfy a length check and show nothing.
        raw = base64.b64decode(body[key])
        assert raw.startswith(b'\x89PNG'), f'{key} não é um PNG'


@needs_ffmpeg
def test_the_after_frame_differs_when_an_effect_is_active(client, handle_id):
    """The tier exists for effects the shader cannot reproduce. If before and
    after came back identical it would be decorative."""
    response = client.post(
        f'/media/handles/{handle_id}/preview-frame',
        json=_request(edits={'adjustments': {'brightness': 0.4}}),
    )
    body = response.json()
    assert body['before'] != body['after']


@needs_ffmpeg
def test_a_neutral_edit_set_is_allowed(client, handle_id):
    """Neutral is a legitimate request — it is what the before frame is."""
    assert client.post(f'/media/handles/{handle_id}/preview-frame', json=_request()).status_code == 200


@needs_ffmpeg
def test_leaves_the_source_untouched(client, handle_id, source):
    """FR-016: a preview is never the result of the operation, and never writes
    over what it previews."""
    before = source.read_bytes()
    client.post(f'/media/handles/{handle_id}/preview-frame',
                json=_request(edits={'effects': {'denoise_enabled': True, 'denoise_strength': 60}}))
    assert source.read_bytes() == before


@needs_ffmpeg
def test_no_temporary_file_survives(client, handle_id):
    """FR-022. One pair of frames per slider movement would accumulate fast, and
    a failure partway is the case that leaves them behind."""
    import glob
    import os
    import tempfile

    pattern = os.path.join(tempfile.gettempdir(), 'astros_preview_*')
    before = set(glob.glob(pattern))
    client.post(f'/media/handles/{handle_id}/preview-frame', json=_request())
    assert set(glob.glob(pattern)) == before, 'restou diretório temporário de preview'


@needs_ffmpeg
def test_the_preview_is_not_written_beside_the_source(client, handle_id, source):
    """Princípio XV: derived artefacts live in storage the API owns."""
    client.post(f'/media/handles/{handle_id}/preview-frame', json=_request())
    # Asserting on image files rather than on the directory being otherwise
    # empty: conftest's isolated_identity_dir fixture also lives in tmp_path, and
    # a test that failed on unrelated infrastructure would be read as a real
    # regression the first time someone hit it.
    images = [p for p in source.parent.iterdir()
              if p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp')]
    assert not images, f'preview escrito ao lado da origem: {images}'


def test_an_unknown_handle_is_refused(client):
    response = client.post('/media/handles/vh_inexistente/preview-frame', json=_request())
    assert response.status_code == 404


@needs_ffmpeg
def test_a_changed_source_is_refused_rather_than_previewed(client, handle_id, source):
    """Previewing from content that no longer exists would show the person a
    frame from a file they no longer have (FR-017)."""
    source.write_bytes((FIXTURES / 'sem_audio.mp4').read_bytes())
    response = client.post(f'/media/handles/{handle_id}/preview-frame', json=_request())
    assert response.status_code == 409
    assert response.json()['detail']['reason'] == 'source_changed'


def test_an_unknown_field_is_rejected(client, handle_id):
    """extra='forbid' on the request schema — a `codec` here would be as wrong
    as anywhere else."""
    response = client.post(f'/media/handles/{handle_id}/preview-frame',
                           json={'time_seconds': 1.0, 'edits': {}, 'codec': 'libx264'})
    assert response.status_code == 422
