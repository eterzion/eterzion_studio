"""HTTP-layer tests for routes_files.py — GET /jobs/{id}/download."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_files
from app.core import job_manager


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes_files.router)
    return TestClient(app)


class TestDownloadJobOutput:
    def test_returns_404_for_unknown_job(self, client):
        res = client.get('/jobs/job_ghost/download')
        assert res.status_code == 404

    def test_returns_409_for_a_job_not_yet_done(self, client, real_input_file, default_job_params):
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())
        res = client.get(f'/jobs/{job_id}/download')
        assert res.status_code == 409

    def test_returns_410_when_output_file_no_longer_exists_on_disk(self, client, real_input_file, default_job_params, tmp_path):
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())
        job_manager.jobs[job_id]['status'] = 'done'
        job_manager.jobs[job_id]['output_path'] = str(tmp_path / 'gone.png')  # never created
        res = client.get(f'/jobs/{job_id}/download')
        assert res.status_code == 410

    def test_downloads_the_real_output_file(self, client, real_input_file, default_job_params, tmp_path):
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())
        output_path = tmp_path / 'result.png'
        output_path.write_bytes(b'real-output-bytes')
        job_manager.jobs[job_id]['status'] = 'done'
        job_manager.jobs[job_id]['output_path'] = str(output_path)

        res = client.get(f'/jobs/{job_id}/download')
        assert res.status_code == 200
        assert res.content == b'real-output-bytes'
        assert 'result.png' in res.headers.get('content-disposition', '')
