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


class TestCreateJobLocal:
    def test_creates_a_job_for_an_existing_file(self, client, real_input_file):
        res = client.post('/jobs/local', json={'input_path': real_input_file, 'params': {}})
        assert res.status_code == 200
        assert res.json()['id'].startswith('job_')

    def test_returns_404_for_a_missing_file(self, client, tmp_path):
        missing = str(tmp_path / 'does-not-exist.png')
        res = client.post('/jobs/local', json={'input_path': missing, 'params': {}})
        assert res.status_code == 404

    def test_accepts_custom_params(self, client, real_input_file):
        res = client.post('/jobs/local', json={
            'input_path': real_input_file,
            'params': {'model': 'realesr-general', 'scale': 2, 'device': 'cpu'},
        })
        job_id = res.json()['id']
        job = client.get(f'/jobs/{job_id}').json()
        assert job['params']['model'] == 'realesr-general'
        assert job['params']['scale'] == 2

    def test_rejects_malformed_body(self, client):
        res = client.post('/jobs/local', json={})  # missing required input_path
        assert res.status_code == 422


class TestGetJob:
    def test_returns_the_job(self, client, real_input_file):
        job_id = client.post('/jobs/local', json={'input_path': real_input_file, 'params': {}}).json()['id']
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
        job_id = client.post('/jobs/local', json={'input_path': real_input_file, 'params': {}}).json()['id']
        body = client.get(f'/jobs/{job_id}').json()
        assert 'input_path' not in body
        assert 'queue_order' not in body


class TestListJobs:
    def test_lists_all_created_jobs(self, client, real_input_file):
        client.post('/jobs/local', json={'input_path': real_input_file, 'params': {}})
        client.post('/jobs/local', json={'input_path': real_input_file, 'params': {}})
        res = client.get('/jobs')
        assert res.status_code == 200
        assert len(res.json()['jobs']) == 2


class TestDeleteJob:
    def test_cancels_an_existing_job(self, client, real_input_file):
        job_id = client.post('/jobs/local', json={'input_path': real_input_file, 'params': {}}).json()['id']
        res = client.delete(f'/jobs/{job_id}')
        assert res.status_code == 200
        assert client.get(f'/jobs/{job_id}').json()['status'] == 'cancelled'

    def test_returns_404_for_unknown_job(self, client):
        res = client.delete('/jobs/job_ghost')
        assert res.status_code == 404


class TestUpdateJobParams:
    def test_updates_params_of_a_pending_job(self, client, real_input_file):
        job_id = client.post('/jobs/local', json={'input_path': real_input_file, 'params': {}}).json()['id']
        res = client.patch(f'/jobs/{job_id}/params', json={'scale': 2})
        assert res.status_code == 200
        assert res.json()['params']['scale'] == 2

    def test_returns_409_for_unknown_job(self, client):
        res = client.patch('/jobs/job_ghost/params', json={'scale': 2})
        assert res.status_code == 409

    def test_returns_409_once_job_has_left_pending(self, client, real_input_file):
        job_id = client.post('/jobs/local', json={'input_path': real_input_file, 'params': {}}).json()['id']
        client.delete(f'/jobs/{job_id}')  # -> cancelled, no longer pending
        res = client.patch(f'/jobs/{job_id}/params', json={'scale': 2})
        assert res.status_code == 409


class TestProcessJob:
    def test_enqueues_a_pending_job(self, client, real_input_file):
        job_id = client.post('/jobs/local', json={'input_path': real_input_file, 'params': {}}).json()['id']
        res = client.post(f'/jobs/{job_id}/process')
        assert res.status_code == 200
        assert res.json() == {'ok': True}
        assert client.get(f'/jobs/{job_id}').json()['status'] == 'queued'

    def test_returns_409_for_unknown_job(self, client):
        res = client.post('/jobs/job_ghost/process')
        assert res.status_code == 409

    def test_returns_409_for_a_job_already_processed(self, client, real_input_file):
        job_id = client.post('/jobs/local', json={'input_path': real_input_file, 'params': {}}).json()['id']
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
        job_id = client.post('/jobs/local', json={'input_path': real_input_file, 'params': {}}).json()['id']
        res = client.post(f'/jobs/{job_id}/export', json={
            'format': 'png', 'quality': 90, 'output_dir': str(tmp_path), 'conflict': 'rename',
        })
        assert res.status_code == 409

    def test_exports_a_done_job_and_renames_on_conflict(self, client, real_input_file, tmp_path, fake_supervisor):
        from app.core import job_manager

        fake_supervisor.configure_result((10, 10), (20, 20))
        job_id = client.post('/jobs/local', json={'input_path': real_input_file, 'params': {}}).json()['id']
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
