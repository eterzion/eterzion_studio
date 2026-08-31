"""T068/T069 (specs/007-video-editor-player) — refusals through the route.

test_video_edits.py already covers check_ceilings() directly. What this adds is
the property SC-005 actually measures and that a unit test cannot see: the
refusal arrives BEFORE anything is created. A ceiling that rejects correctly but
only after ffmpeg has started is still the failure FR-025 forbids.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import media_handles, video_edits
from app.main import app

FIXTURES = Path(__file__).resolve().parent / 'fixtures'


@pytest.fixture
def client():
    media_handles.clear()
    with TestClient(app) as test_client:
        yield test_client
    media_handles.clear()


@pytest.fixture
def handle_id(client):
    source = FIXTURES / 'curto.mp4'
    if not source.exists():
        pytest.skip('fixtures ausentes — rode tests/fixtures/make_video_fixtures.py')
    response = client.post('/media/handles', json={'path': str(source)})
    assert response.status_code == 201
    return response.json()['handle_id']


def _request(handle_id, **overrides):
    body = {'handle_id': handle_id, 'edits': {}, 'container': 'webm', 'profile': 'fast'}
    body.update(overrides)
    return body


class TestRefusalArrivesBeforeWork:
    """SC-005: 'nenhuma operação termina em falha por exaustão' rests on nothing
    starting at all."""

    def test_an_exceeded_ceiling_never_reaches_ffmpeg(self, client, handle_id):
        # If the refusal came late, run_ffmpeg would have been called. Patching
        # it is what turns "refused" into "refused before starting".
        with patch('eterzion_upscale.media.run_ffmpeg') as run_ffmpeg:
            with patch.object(video_edits, 'check_ceilings',
                              side_effect=video_edits.CeilingExceeded('duration', 7200, 9840)):
                response = client.post('/video/edit-jobs', json=_request(handle_id))

        assert response.status_code == 422
        detail = response.json()['detail']
        assert detail['reason'] == 'ceiling_exceeded'
        assert detail['limiting_factor'] == 'duration'
        run_ffmpeg.assert_not_called()

    def test_a_missing_encoder_never_reaches_ffmpeg(self, client, handle_id):
        with patch('eterzion_upscale.media.run_ffmpeg') as run_ffmpeg:
            with patch.object(video_edits, 'resolve_encoder',
                              side_effect=video_edits.EncoderUnavailable('webm')):
                response = client.post('/video/edit-jobs', json=_request(handle_id))

        assert response.status_code == 422
        assert response.json()['detail']['reason'] == 'encoder_unavailable'
        run_ffmpeg.assert_not_called()

    def test_insufficient_disk_never_reaches_ffmpeg(self, client, handle_id):
        with patch('eterzion_upscale.media.run_ffmpeg') as run_ffmpeg:
            with patch.object(video_edits, 'check_disk_space',
                              side_effect=video_edits.InsufficientDisk(1_000_000, 10)):
                response = client.post('/video/edit-jobs', json=_request(handle_id))

        assert response.status_code == 422
        assert response.json()['detail']['reason'] == 'disk_full'
        run_ffmpeg.assert_not_called()


class TestRefusalNamesTheFactor:
    """FR-025. A generic 'too big' tells a person nothing about what to change."""

    @pytest.mark.parametrize(
        'factor', ['duration', 'width', 'height', 'frame_rate', 'frame_count', 'size_bytes']
    )
    def test_every_factor_reaches_the_client_by_name(self, client, handle_id, factor):
        with patch.object(video_edits, 'check_ceilings',
                          side_effect=video_edits.CeilingExceeded(factor, 1, 2)):
            response = client.post('/video/edit-jobs', json=_request(handle_id))
        assert response.json()['detail']['limiting_factor'] == factor


class TestSourceChanged:
    def test_a_changed_source_is_refused(self, client, tmp_path):
        original = FIXTURES / 'curto.mp4'
        if not original.exists():
            pytest.skip('fixtures ausentes')
        working = tmp_path / 'origem.mp4'
        working.write_bytes(original.read_bytes())

        handle = client.post('/media/handles', json={'path': str(working)}).json()['handle_id']
        working.write_bytes((FIXTURES / 'sem_audio.mp4').read_bytes())

        response = client.post('/video/edit-jobs', json=_request(handle))
        assert response.status_code == 409
        assert response.json()['detail']['reason'] == 'source_changed'


class TestDiskSpace:
    def test_a_destination_with_room_is_allowed(self, tmp_path):
        video_edits.check_disk_space(str(tmp_path / 'saida.webm'), 1024)

    def test_an_unreadable_destination_does_not_refuse_on_a_guess(self):
        """Refusing because the destination could not be measured would turn an
        unrelated problem into a capacity error."""
        video_edits.check_disk_space('\x00://caminho/invalido/saida.webm', 1024)
