from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# astros_upscale (the core package, imported by app.core.upscaler) lives three
# levels above this service, same layout app/config.py itself relies on.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest


@pytest.fixture(autouse=True)
def isolated_identity_dir(tmp_path, monkeypatch):
    """install_identity.py reads %LOCALAPPDATA%/%APPDATA% directly (it's a
    real per-machine path, not something app.config exposes) — point it at a
    temp dir per test and clear the in-process identity cache so no test sees
    another test's generated keys."""
    from app.core import install_identity

    def _fake_identity_dir():
        path = tmp_path / 'identity'
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    monkeypatch.setattr(install_identity, '_identity_dir', _fake_identity_dir)
    monkeypatch.setattr(install_identity, '_cached', None)
    yield
    monkeypatch.setattr(install_identity, '_cached', None)


@pytest.fixture(autouse=True)
def isolated_job_store(monkeypatch, tmp_path):
    """job_manager.jobs is plain module-level state shared across the whole
    process — without this, tests would see each other's jobs. Harmless
    (just resets an unrelated dict) for tests that never touch job_manager."""
    from app.config import settings
    from app.core import job_manager

    monkeypatch.setattr(job_manager, 'jobs', {})
    monkeypatch.setattr(job_manager, '_processing_job_id', None)
    monkeypatch.setattr(settings, 'outputs_dir', str(tmp_path / 'outputs'))
    yield


class FakeSupervisor:
    """Drop-in replacement for WorkerSupervisor — same .process()/.terminate()
    surface job_manager actually calls, but returns/raises whatever the test
    configures instead of running a real subprocess."""

    def __init__(self):
        self.terminated = False
        self.process_calls: list[dict] = []
        self._result = {'source_size': (100, 100), 'output_size': (200, 200)}
        self._error: Exception | None = None
        self._progress_events: list[int] = []
        self._stage_events: list[str] = []
        # A real, decodable PNG — export_job() re-decodes the master file
        # (Upscaler.export -> imread) regardless of target format, so a
        # placeholder byte string would fail there just like a genuinely
        # corrupted output file would.
        import cv2
        import numpy as np

        ok, encoded = cv2.imencode('.png', np.zeros((4, 4, 3), dtype=np.uint8))
        assert ok
        self._write_master_bytes: bytes | None = encoded.tobytes()

    def configure_result(self, source_size, output_size):
        self._result = {'source_size': source_size, 'output_size': output_size}

    def configure_error(self, error: Exception):
        self._error = error

    def process(self, *, job_id, input_path, master_path, model, models_dir, device, scale,
                custom_size, denoise, on_progress=None, on_stage=None, protected=None,
                sharpen=0, face_recovery=False, face_recovery_strength=80, denoise_filter_strength=0,
                media_type='image', operation='enhance', half=True, stabilize=False,
                tile_threshold=None, tile_size=None):
        import os

        self.process_calls.append({
            'job_id': job_id, 'input_path': input_path, 'master_path': master_path, 'model': model,
            'device': device, 'scale': scale, 'custom_size': custom_size, 'denoise': denoise,
            'sharpen': sharpen, 'face_recovery': face_recovery, 'denoise_filter_strength': denoise_filter_strength,
            'media_type': media_type, 'operation': operation, 'half': half, 'stabilize': stabilize,
        })
        for pct in self._progress_events:
            if on_progress:
                on_progress(pct)
        for stage in self._stage_events:
            if on_stage:
                on_stage(stage)
        if self._error is not None:
            raise self._error
        if self._write_master_bytes is not None:
            os.makedirs(os.path.dirname(master_path), exist_ok=True)
            with open(master_path, 'wb') as fh:
                fh.write(self._write_master_bytes)
        return self._result

    def terminate(self):
        self.terminated = True


@pytest.fixture
def fake_supervisor(monkeypatch):
    from app.core import worker_supervisor

    fake = FakeSupervisor()
    monkeypatch.setattr(worker_supervisor, '_supervisor', fake)
    monkeypatch.setattr(worker_supervisor, 'get_supervisor', lambda: fake)
    return fake


@pytest.fixture
def real_input_file(tmp_path):
    path = tmp_path / 'input.png'
    path.write_bytes(b'\x89PNG\r\n\x1a\nfake-but-present')
    return str(path)


@pytest.fixture
def default_job_params():
    """Factory fixture — call it to get a params dict shaped like what
    routes_jobs.py's _build_job_params() actually produces: intent only
    (scale/profile/device/adjustments), never a model identifier (FR-011)."""

    def _make(**overrides):
        params = {
            'scale': '4x', 'profile': 'fast', 'device': 'auto', 'custom_size': None,
            'adjustments': {
                'denoise': 50, 'deblur': 0, 'detail_recovery': 0, 'face_correction': False,
                'face_recovery_strength': 80, 'denoise_filter_enabled': False, 'denoise_filter_strength': 0,
            },
        }
        params.update(overrides)
        return params

    return _make
