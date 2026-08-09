"""HTTP-layer tests for routes_models.py — GET /models. Reads the real
MODELS registry from astros_upscale.core (no mocking of the registry itself,
that's the actual source of truth the desktop app depends on) but points
settings.models_dir at an empty temp dir so 'downloaded' status is
deterministic regardless of what's cached on the machine running the test."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_models
from app.config import settings


@pytest.fixture(autouse=True)
def empty_models_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'models_dir', str(tmp_path / 'models'))


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes_models.router, prefix='/models')
    return TestClient(app)


class TestListModels:
    def test_returns_the_full_real_registry(self, client):
        from astros_upscale.core import MODELS

        res = client.get('/models')
        assert res.status_code == 200
        body = res.json()
        assert len(body['models']) == len(MODELS)
        names = {m['name'] for m in body['models']}
        assert names == set(MODELS.keys())

    def test_models_are_sorted_by_name(self, client):
        res = client.get('/models')
        names = [m['name'] for m in res.json()['models']]
        assert names == sorted(names)

    def test_each_model_has_the_expected_fields(self, client):
        res = client.get('/models')
        model = res.json()['models'][0]
        assert set(model.keys()) == {
            'name', 'category', 'scale', 'description', 'architecture', 'file_count', 'downloaded', 'size_bytes',
        }

    def test_nothing_downloaded_reports_false_and_null_size(self, client):
        """models_dir is empty (fixture) — every model must honestly report
        as not downloaded, never a stale/cached True."""
        res = client.get('/models')
        for model in res.json()['models']:
            assert model['downloaded'] is False
            assert model['size_bytes'] is None

    def test_a_downloaded_model_reports_its_real_file_size(self, client, tmp_path, monkeypatch):
        from astros_upscale.core import MODELS
        from urllib.parse import urlparse
        import os

        name, info = next(iter(sorted(MODELS.items())))
        models_dir = tmp_path / 'models2'
        models_dir.mkdir()
        monkeypatch.setattr(settings, 'models_dir', str(models_dir))
        for url in info['urls']:
            filename = os.path.basename(urlparse(url).path)
            (models_dir / filename).write_bytes(b'x' * 1234)

        res = client.get('/models')
        model = next(m for m in res.json()['models'] if m['name'] == name)
        assert model['downloaded'] is True
        assert model['size_bytes'] == 1234 * len(info['urls'])

    def test_default_models_are_real_registry_entries(self, client):
        from astros_upscale.core import MODELS

        body = client.get('/models').json()
        assert body['default_image_model'] in MODELS
        assert body['default_video_model'] in MODELS

    def test_devices_list_is_present(self, client):
        body = client.get('/models').json()
        assert 'auto' in body['devices']
        assert 'cpu' in body['devices']
