"""T070 — HTTP-layer tests for routes_components.py — GET /components,
GET /components/{id}/details, install/update/delete. Real component_manager.py
underneath (no mocking of the registry itself); settings.models_dir points at
an empty temp dir so install_state is deterministic regardless of what's
cached on the machine running the test."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_components
from app.config import settings


@pytest.fixture(autouse=True)
def empty_models_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'models_dir', str(tmp_path / 'models'))


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes_components.router, prefix='/components')
    return TestClient(app)


class TestListComponents:
    def test_returns_the_six_content_type_components(self, client):
        from app.core.component_manager import CAPABILITY_LABELS

        res = client.get('/components')
        assert res.status_code == 200
        body = res.json()
        assert {c['id'] for c in body} == set(CAPABILITY_LABELS)

    def test_never_exposes_technical_name_in_the_list_response(self, client):
        """FR-009/FR-063 — the list-level Component schema has no
        technical_name/version/provenance/license fields at all."""
        res = client.get('/components')
        for component in res.json():
            assert set(component.keys()) == {'id', 'capability_label', 'size_mb', 'install_state', 'update_available'}

    def test_nothing_downloaded_reports_not_installed(self, client):
        res = client.get('/components')
        image_video = [c for c in res.json() if c['id'] in ('photo', 'anime_image', 'real_video', 'anime_video')]
        assert image_video
        for c in image_video:
            assert c['install_state'] == 'not_installed'
            assert c['size_mb'] == 0


class TestComponentDetails:
    def test_details_expose_technical_fields(self, client):
        res = client.get('/components/photo/details')
        assert res.status_code == 200
        body = res.json()
        assert body['technical_name'] == 'nomos-webphoto'
        assert body['license']

    def test_returns_404_for_unknown_component(self, client):
        res = client.get('/components/not-real/details')
        assert res.status_code == 404


class TestInstallUpdateDelete:
    def test_install_speech_returns_422_with_actionable_message(self, client):
        res = client.post('/components/speech/install')
        assert res.status_code == 422
        assert 'pip install' in res.json()['detail']

    def test_delete_music_returns_422(self, client):
        res = client.delete('/components/music')
        assert res.status_code == 422

    def test_install_unknown_component_returns_404(self, client):
        res = client.post('/components/not-real/install')
        assert res.status_code == 404

    @pytest.mark.slow
    def test_real_install_then_delete_a_small_model(self, client):
        install_res = client.post('/components/anime_image/install')
        assert install_res.status_code == 200
        assert install_res.json()['install_state'] == 'installed'

        delete_res = client.delete('/components/anime_image')
        assert delete_res.status_code == 200
        assert delete_res.json()['install_state'] == 'not_installed'
