"""T041/T048 — HTTP-layer coverage for the secondary-elements confirmation
flow (FR-081 to FR-086): POST /jobs/local must land a video-enhance job in
pending_confirmation (not enqueue-able) when the probe finds extras the
pipeline would silently drop, and skip the prompt entirely when nothing is
lost. Real ffmpeg-built videos, real ffprobe detection — no mocking of the
logic under test."""
from __future__ import annotations

import subprocess

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_jobs
from astros_upscale.utils.video_io import has_ffmpeg

pytestmark = pytest.mark.skipif(not has_ffmpeg(), reason='requires a real ffmpeg binary on PATH')


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes_jobs.router, prefix='/jobs')
    return TestClient(app)


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(['ffmpeg', '-y', *args], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def _simple_video(path: str) -> None:
    _run_ffmpeg([
        '-f', 'lavfi', '-i', 'color=c=blue:s=64x48:d=1',
        '-f', 'lavfi', '-i', 'sine=frequency=440:d=1',
        '-c:v', 'mpeg4', '-c:a', 'aac', '-shortest', path,
    ])


def _dual_audio_video(path: str) -> None:
    _run_ffmpeg([
        '-f', 'lavfi', '-i', 'color=c=blue:s=64x48:d=1',
        '-f', 'lavfi', '-i', 'sine=frequency=440:d=1',
        '-f', 'lavfi', '-i', 'sine=frequency=880:d=1',
        '-map', '0:v', '-map', '1:a', '-map', '2:a',
        '-c:v', 'mpeg4', '-c:a', 'aac', '-shortest', path,
    ])


def _video_body(input_path, **overrides):
    media_request = {
        'media_type': 'video', 'operation': 'enhance', 'content_type_override': 'real_video',
        'scale': '2x', 'input_path': input_path,
    }
    media_request.update(overrides)
    return {'media_request': media_request}


class TestSecondaryElementsOnJobCreation:
    def test_video_with_nothing_to_lose_goes_straight_to_pending(self, client, tmp_path):
        path = str(tmp_path / 'simple.mp4')
        _simple_video(path)
        res = client.post('/jobs/local', json=_video_body(path))
        assert res.status_code == 200
        job = client.get(f"/jobs/{res.json()['id']}").json()
        assert job['status'] == 'pending'

    def test_video_with_extra_audio_lands_in_pending_confirmation(self, client, tmp_path):
        path = str(tmp_path / 'dual_audio.mp4')
        _dual_audio_video(path)
        res = client.post('/jobs/local', json=_video_body(path))
        assert res.status_code == 200
        job = client.get(f"/jobs/{res.json()['id']}").json()
        assert job['status'] == 'pending_confirmation'
        assert job['secondary_elements']['has_losses'] is True
        assert 'extra_audio_tracks' in job['secondary_elements']['losses']

    def test_ack_upfront_skips_pending_confirmation(self, client, tmp_path):
        path = str(tmp_path / 'dual_audio2.mp4')
        _dual_audio_video(path)
        res = client.post('/jobs/local', json=_video_body(path, secondary_elements_ack=True))
        job = client.get(f"/jobs/{res.json()['id']}").json()
        assert job['status'] == 'pending'

    def test_pending_confirmation_job_cannot_be_processed(self, client, tmp_path):
        path = str(tmp_path / 'dual_audio3.mp4')
        _dual_audio_video(path)
        job_id = client.post('/jobs/local', json=_video_body(path)).json()['id']
        res = client.post(f'/jobs/{job_id}/process')
        assert res.status_code == 409

    def test_non_video_operations_never_probe_for_losses(self, client, real_input_file):
        """image/enhance never calls detect_secondary_elements — confirmed by
        it not raising even though real_input_file isn't ffprobe-readable."""
        media_request = {
            'media_type': 'image', 'operation': 'enhance', 'content_type_override': 'photo',
            'scale': '4x', 'input_path': real_input_file,
        }
        res = client.post('/jobs/local', json={'media_request': media_request})
        assert res.status_code == 200
        job = client.get(f"/jobs/{res.json()['id']}").json()
        assert job['status'] == 'pending'


class TestConfirmSecondaryElements:
    def test_confirming_moves_job_to_pending_and_allows_processing(self, client, tmp_path):
        path = str(tmp_path / 'dual_audio4.mp4')
        _dual_audio_video(path)
        job_id = client.post('/jobs/local', json=_video_body(path)).json()['id']
        assert client.get(f'/jobs/{job_id}').json()['status'] == 'pending_confirmation'

        res = client.post(f'/jobs/{job_id}/confirm-secondary-elements')
        assert res.status_code == 200
        assert res.json()['status'] == 'pending'

        res = client.post(f'/jobs/{job_id}/process')
        assert res.status_code == 200

    def test_returns_404_for_unknown_job(self, client):
        res = client.post('/jobs/job_ghost/confirm-secondary-elements')
        assert res.status_code == 404

    def test_returns_404_for_a_job_not_awaiting_confirmation(self, client, tmp_path):
        path = str(tmp_path / 'simple2.mp4')
        _simple_video(path)
        job_id = client.post('/jobs/local', json=_video_body(path)).json()['id']  # nothing to lose -> pending
        res = client.post(f'/jobs/{job_id}/confirm-secondary-elements')
        assert res.status_code == 404
