"""HTTP-layer integration tests for routes_jobs.py — the real request/response
contract (status codes, validation, path/query params), on top of the same
job_manager state machine test_job_manager.py already covers at the function
level. Mounts just this router (not app.main) so the API startup sequence
(worker supervisor lifecycle, secure_tempdir cleanup) never runs — this
module's own job_manager state is isolated the same way either way."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_jobs


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes_jobs.router, prefix='/jobs')
    return TestClient(app)


def _local_body(input_path, **media_request_overrides):
    media_request = {
        'media_type': 'image', 'operation': 'enhance', 'content_type_override': 'photo',
        'scale': '4x', 'input_path': input_path,
    }
    media_request.update(media_request_overrides)
    return {'media_request': media_request}


class TestCreateJobLocal:
    def test_creates_a_job_for_an_existing_file(self, client, real_input_file):
        res = client.post('/jobs/local', json=_local_body(real_input_file))
        assert res.status_code == 200
        assert res.json()['id'].startswith('job_')

    def test_returns_404_for_a_missing_file(self, client, tmp_path):
        missing = str(tmp_path / 'does-not-exist.png')
        res = client.post('/jobs/local', json=_local_body(missing))
        assert res.status_code == 404

    def test_accepts_a_profile_and_scale(self, client, real_input_file):
        res = client.post('/jobs/local', json=_local_body(real_input_file, scale='2x', profile='quality'))
        job_id = res.json()['id']
        job = client.get(f'/jobs/{job_id}').json()
        assert job['params']['scale'] == '2x'
        assert job['params']['profile'] == 'quality'

    def test_rejects_malformed_body(self, client):
        res = client.post('/jobs/local', json={})  # missing required media_request
        assert res.status_code == 422

    def test_rejects_a_model_field_inside_media_request(self, client, real_input_file):
        """FR-011 — extra='forbid' on MediaRequest makes this a hard 422, not a
        silently-ignored extra key."""
        body = _local_body(real_input_file)
        body['media_request']['model'] = 'realesrgan-x4'
        res = client.post('/jobs/local', json=body)
        assert res.status_code == 422

    def test_rejects_a_content_type_with_no_approved_implementation(self, client, real_input_file, monkeypatch):
        """FR-098 — every one of today's 6 content types now has an approved
        implementation (T024/T045/T046/T055); this exercises the refusal path
        via a temporarily unapproved registry entry so the guarantee ("refused
        before the Job is created, not fail later mid-queue") stays covered."""
        from app.core import profile_resolver

        monkeypatch.setitem(
            profile_resolver._CONTENT_TYPE_IMPLEMENTATIONS, 'music',
            profile_resolver._ContentTypeImplementation(engine_ref=None))
        res = client.post('/jobs/local', json=_local_body(
            real_input_file, media_type='audio', operation='enhance', content_type_override='music'))
        assert res.status_code == 422

    def test_uses_explicit_content_type_override_without_decoding_the_image(self, client, real_input_file):
        """real_input_file is deliberately not a decodable image (see conftest.py)
        — an explicit override must skip detection entirely, not attempt it."""
        res = client.post('/jobs/local', json=_local_body(real_input_file, content_type_override='anime_image'))
        assert res.status_code == 200
        job_id = res.json()['id']
        assert client.get(f'/jobs/{job_id}').json()['content_type_detected'] == 'anime_image'


class TestDetectContentType:
    def test_detects_a_real_photo(self, client, tmp_path):
        import cv2
        import numpy as np

        img = np.random.randint(0, 255, (32, 32, 3), dtype=np.uint8)  # photo-like noise, not flat anime shading
        path = tmp_path / 'photo.png'
        cv2.imwrite(str(path), img)

        res = client.post('/jobs/detect-content-type', json={'input_path': str(path), 'media_type': 'image'})
        assert res.status_code == 200
        assert res.json()['content_type'] in ('photo', 'anime_image')

    def test_returns_404_for_a_missing_file(self, client, tmp_path):
        res = client.post('/jobs/detect-content-type', json={
            'input_path': str(tmp_path / 'nope.png'), 'media_type': 'image',
        })
        assert res.status_code == 404

    def test_returns_422_for_an_undecodable_file(self, client, real_input_file):
        res = client.post('/jobs/detect-content-type', json={'input_path': real_input_file, 'media_type': 'image'})
        assert res.status_code == 422

    def test_returns_422_for_non_image_media_types(self, client, tmp_path):
        path = tmp_path / 'clip.mp4'
        path.write_bytes(b'not a real video, just needs to exist')
        res = client.post('/jobs/detect-content-type', json={'input_path': str(path), 'media_type': 'video'})
        assert res.status_code == 422


class TestGetJob:
    def test_returns_the_job(self, client, real_input_file):
        job_id = client.post('/jobs/local', json=_local_body(real_input_file)).json()['id']
        res = client.get(f'/jobs/{job_id}')
        assert res.status_code == 200
        assert res.json()['id'] == job_id
        assert res.json()['status'] == 'pending'

    def test_returns_404_for_unknown_job(self, client):
        res = client.get('/jobs/job_ghost')
        assert res.status_code == 404

    def test_response_excludes_internal_fields(self, client, real_input_file):
        """input_path and queue_order are server-internal bookkeeping — the
        public view (_public_view in routes_jobs.py) must strip them, not
        leak local filesystem paths to the client response body."""
        job_id = client.post('/jobs/local', json=_local_body(real_input_file)).json()['id']
        body = client.get(f'/jobs/{job_id}').json()
        assert 'input_path' not in body
        assert 'queue_order' not in body


class TestListJobs:
    def test_lists_all_created_jobs(self, client, real_input_file):
        client.post('/jobs/local', json=_local_body(real_input_file))
        client.post('/jobs/local', json=_local_body(real_input_file))
        res = client.get('/jobs')
        assert res.status_code == 200
        assert len(res.json()['jobs']) == 2


class TestDeleteJob:
    def test_cancels_an_existing_job(self, client, real_input_file):
        job_id = client.post('/jobs/local', json=_local_body(real_input_file)).json()['id']
        res = client.delete(f'/jobs/{job_id}')
        assert res.status_code == 200
        assert client.get(f'/jobs/{job_id}').json()['status'] == 'cancelled'

    def test_returns_404_for_unknown_job(self, client):
        res = client.delete('/jobs/job_ghost')
        assert res.status_code == 404


class TestUpdateJobParams:
    def test_updates_params_of_a_pending_job(self, client, real_input_file):
        job_id = client.post('/jobs/local', json=_local_body(real_input_file)).json()['id']
        res = client.patch(f'/jobs/{job_id}/params', json={'scale': '2x'})
        assert res.status_code == 200
        assert res.json()['params']['scale'] == '2x'

    def test_returns_409_for_unknown_job(self, client):
        res = client.patch('/jobs/job_ghost/params', json={'scale': '2x'})
        assert res.status_code == 409

    def test_returns_409_once_job_has_left_pending(self, client, real_input_file):
        job_id = client.post('/jobs/local', json=_local_body(real_input_file)).json()['id']
        client.delete(f'/jobs/{job_id}')  # -> cancelled, no longer pending
        res = client.patch(f'/jobs/{job_id}/params', json={'scale': '2x'})
        assert res.status_code == 409

    def test_rejects_a_model_field(self, client, real_input_file):
        """FR-011 — the PATCH escape hatch must not let a model identifier
        back in after LocalJobRequest already blocked it at creation."""
        job_id = client.post('/jobs/local', json=_local_body(real_input_file)).json()['id']
        res = client.patch(f'/jobs/{job_id}/params', json={'model': 'realesrgan-x4'})
        assert res.status_code == 422


class TestProcessJob:
    def test_enqueues_a_pending_job(self, client, real_input_file):
        job_id = client.post('/jobs/local', json=_local_body(real_input_file)).json()['id']
        res = client.post(f'/jobs/{job_id}/process')
        assert res.status_code == 200
        assert res.json() == {'ok': True}
        assert client.get(f'/jobs/{job_id}').json()['status'] == 'queued'

    def test_returns_409_for_unknown_job(self, client):
        res = client.post('/jobs/job_ghost/process')
        assert res.status_code == 409

    def test_returns_409_for_a_job_already_processed(self, client, real_input_file):
        job_id = client.post('/jobs/local', json=_local_body(real_input_file)).json()['id']
        client.post(f'/jobs/{job_id}/process')
        res = client.post(f'/jobs/{job_id}/process')  # already queued, not pending anymore
        assert res.status_code == 409


class TestExportJobRoute:
    def test_returns_404_for_unknown_job(self, client, tmp_path):
        res = client.post('/jobs/job_ghost/export', json={
            'format': 'png', 'quality': 90, 'output_dir': str(tmp_path), 'conflict': 'rename',
        })
        assert res.status_code == 404

    def test_returns_409_for_a_job_not_yet_done(self, client, real_input_file, tmp_path):
        job_id = client.post('/jobs/local', json=_local_body(real_input_file)).json()['id']
        res = client.post(f'/jobs/{job_id}/export', json={
            'format': 'png', 'quality': 90, 'output_dir': str(tmp_path), 'conflict': 'rename',
        })
        assert res.status_code == 409

    def test_exports_a_done_job_and_renames_on_conflict(self, client, real_input_file, tmp_path, fake_supervisor):
        from app.core import job_manager

        fake_supervisor.configure_result((10, 10), (20, 20))
        job_id = client.post('/jobs/local', json=_local_body(real_input_file)).json()['id']
        job_manager.jobs[job_id]['status'] = 'queued'
        import asyncio

        asyncio.run(job_manager._process_job(job_id))
        assert job_manager.get_job(job_id)['status'] == 'done'

        out_dir = tmp_path / 'out'
        out_dir.mkdir()
        existing = out_dir / f'{job_id}_upscaled.png'
        existing.write_bytes(b'pre-existing file')  # forces the 'rename' branch

        res = client.post(f'/jobs/{job_id}/export', json={
            'format': 'png', 'quality': 90, 'output_dir': str(out_dir),
            'filename': f'{job_id}_upscaled.png', 'conflict': 'rename',
        })
        assert res.status_code == 200
        output_path = res.json()['output_path']
        assert output_path != str(existing)  # renamed, did not overwrite
        assert existing.read_bytes() == b'pre-existing file'  # original untouched


class TestLicenseGate:
    """T016: POST /jobs* must refuse before creating/enqueueing a job when the
    license gate says no — real gate function, only its network call is faked
    (via GateResult, monkeypatched at the module level check_gate() reads)."""

    def test_create_job_local_is_blocked_when_gate_refuses(self, client, real_input_file, monkeypatch):
        from app.core import license_gate

        monkeypatch.setattr(
            license_gate, 'check_gate',
            lambda: license_gate.GateResult(allowed=False, state='blocked', message='Licença bloqueada.'))
        res = client.post('/jobs/local', json=_local_body(real_input_file))
        assert res.status_code == 403
        assert res.json()['detail']['error_category'] == 'license_invalid'

    def test_create_job_local_proceeds_when_gate_allows(self, client, real_input_file, monkeypatch):
        from app.core import license_gate

        monkeypatch.setattr(
            license_gate, 'check_gate', lambda: license_gate.GateResult(allowed=True, state='active'))
        res = client.post('/jobs/local', json=_local_body(real_input_file))
        assert res.status_code == 200

    def test_process_job_is_blocked_when_gate_refuses(self, client, real_input_file, monkeypatch):
        from app.core import license_gate

        job_id = client.post('/jobs/local', json=_local_body(real_input_file)).json()['id']
        monkeypatch.setattr(
            license_gate, 'check_gate',
            lambda: license_gate.GateResult(allowed=False, state='not_activated', message='Não ativado.'))
        res = client.post(f'/jobs/{job_id}/process')
        assert res.status_code == 403
