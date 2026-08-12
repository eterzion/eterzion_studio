"""T060 — HTTP-layer coverage of the capacity pre-flight gate (T062,
FR-076/FR-077/FR-079): a request whose size exceeds the (real, injected)
computed capacity is rejected before job_manager.create_job() ever runs,
with the limiting resource named in the response. detect_hardware() itself
is monkeypatched (this test controls the machine's capacity, not what's
literally plugged into this CI box) — everything downstream (capacity.py's
real math, the real HTTP route logic) runs unmocked."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_jobs
from astros_upscale.hardware import HardwareCapability


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


def _starved_hardware() -> HardwareCapability:
    return HardwareCapability(
        cpu_cores=2, ram_total_mb=2048, ram_available_mb=8,
        gpu_present=False, gpu_vendor='unknown', vram_total_mb=None, vram_available_mb=None,
    )


def _roomy_hardware() -> HardwareCapability:
    return HardwareCapability(
        cpu_cores=16, ram_total_mb=65536, ram_available_mb=32768,
        gpu_present=True, gpu_vendor='nvidia', vram_total_mb=24576, vram_available_mb=20480,
    )


class TestCapacityGateOnJobCreation:
    def test_a_request_on_a_starved_machine_is_rejected_before_the_job_exists(
            self, client, real_input_file, monkeypatch):
        from astros_upscale import hardware as hardware_module

        monkeypatch.setattr(hardware_module, 'detect_hardware', _starved_hardware)
        res = client.post('/jobs/local', json=_local_body(real_input_file))
        assert res.status_code == 422
        detail = res.json()['detail']
        assert detail['error_category'] == 'hardware_insufficient'
        assert detail['limiting_resource'] == 'ram'
        # never created — a 422 here must mean job_manager never saw this request
        assert client.get('/jobs').json()['jobs'] == []

    def test_a_request_on_a_capable_machine_proceeds_and_reports_an_estimate(
            self, client, tmp_path, monkeypatch):
        import cv2
        import numpy as np

        from astros_upscale import hardware as hardware_module

        decodable_path = str(tmp_path / 'real.png')
        cv2.imwrite(decodable_path, np.zeros((64, 64, 3), dtype=np.uint8))

        monkeypatch.setattr(hardware_module, 'detect_hardware', _roomy_hardware)
        res = client.post('/jobs/local', json=_local_body(decodable_path))
        assert res.status_code == 200
        body = res.json()
        assert body['id'].startswith('job_')
        assert body['estimated_duration'] is not None
        assert body['estimated_duration'] > 0

        job = client.get(f"/jobs/{body['id']}").json()
        assert job['capacity_check']['fits'] is True
        assert job['capacity_check']['estimated_duration'] == pytest.approx(body['estimated_duration'])

    def test_compress_never_runs_a_capacity_check(self, client, real_input_file, monkeypatch):
        """FR-076 to FR-079 are about the AI-model memory footprint —
        compress/convert never load a model (Constitution "No AI Without
        Benefit"), so this must proceed even on a starved machine."""
        from astros_upscale import hardware as hardware_module

        monkeypatch.setattr(hardware_module, 'detect_hardware', _starved_hardware)
        res = client.post('/jobs/local', json=_local_body(
            real_input_file, operation='compress', scale=None, content_type_override=None))
        assert res.status_code == 200
        assert res.json()['estimated_duration'] is None
