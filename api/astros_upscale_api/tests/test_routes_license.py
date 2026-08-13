"""T036 — HTTP-layer tests for the license facade routes. Network calls to
astros_licensing_service are stubbed at the same seam license_gate.py's own
tests use (license_gate._http_get / protected_loader's HTTP helpers), so the
real routing/branching logic runs end to end."""
from __future__ import annotations

import urllib.error

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import license_router


@pytest.fixture(autouse=True)
def isolated_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.delenv('APPDATA', raising=False)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(license_router, prefix='/license')
    return TestClient(app)


class _FakeIdentity:
    install_id = 'install-fake'
    signing_public_key_b64 = 'c2lnbmluZy1rZXk='
    encryption_public_key_b64 = 'ZW5jcnlwdGlvbi1rZXk='


def _configure(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, 'licensing_service_url', 'http://licensing.test')
    monkeypatch.setattr('app.security.ensure_identity', lambda: _FakeIdentity())


class TestGetStatus:
    def test_reports_not_configured_when_no_service_configured(self, client, monkeypatch):
        # 'not_configured' (not 'not_activated') is the correct distinct state here:
        # this is the dev/local default (empty licensing_service_url +
        # ASTROS_DEV_ALLOW_UNLICENSED), where check_gate() already allows job
        # creation — the frontend must not treat this the same as a real
        # never-activated installation and hard-block the whole app shell.
        from app.config import settings

        monkeypatch.setattr(settings, 'licensing_service_url', '')
        res = client.get('/license/status')
        assert res.status_code == 200
        assert res.json()['state'] == 'not_configured'

    def test_reports_active_with_seat_counts(self, client, monkeypatch):
        _configure(monkeypatch)
        from app import licensing as license_gate

        monkeypatch.setattr(license_gate, '_http_get', lambda url, timeout=5.0: {
            'license_id': 'lic_1', 'status': 'active', 'installations_used': 1, 'installations_limit': 2,
        })
        res = client.get('/license/status')
        assert res.status_code == 200
        body = res.json()
        assert body['state'] == 'active'
        assert body['installations_used'] == 1
        assert body['installations_limit'] == 2

    def test_reports_not_activated_for_a_never_activated_installation(self, client, monkeypatch):
        _configure(monkeypatch)
        from app import licensing as license_gate

        def _raise_404(url, timeout=5.0):
            raise urllib.error.HTTPError(url, 404, 'not found', hdrs=None, fp=None)

        monkeypatch.setattr(license_gate, '_http_get', _raise_404)
        res = client.get('/license/status')
        assert res.json()['state'] == 'not_activated'


class TestActivate:
    def test_returns_409_when_no_service_configured(self, client, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, 'licensing_service_url', '')
        res = client.post('/license/activate', json={'license_id': 'lic_1'})
        assert res.status_code == 409

    def test_activates_and_records_a_successful_check(self, client, monkeypatch):
        _configure(monkeypatch)
        from app import licensing as license_cache
        from app import security as protected_loader

        monkeypatch.setattr(protected_loader, '_http_post', lambda url, body: {'ok': True})
        assert license_cache.days_since_last_success() is None

        res = client.post('/license/activate', json={'license_id': 'lic_1'})
        assert res.status_code == 200
        assert license_cache.days_since_last_success() == pytest.approx(0.0, abs=0.1)

    def test_surfaces_a_clear_error_when_the_service_rejects_activation(self, client, monkeypatch):
        _configure(monkeypatch)
        from app import security as protected_loader

        def _raise(url, body):
            raise protected_loader.ProtectedLoadError('licença inválida')

        monkeypatch.setattr(protected_loader, '_http_post', _raise)
        res = client.post('/license/activate', json={'license_id': 'lic_1'})
        assert res.status_code == 502


class TestRelease:
    def test_returns_409_when_not_activated(self, client, monkeypatch):
        _configure(monkeypatch)
        from app import licensing as license_gate

        def _raise_404(url, timeout=5.0):
            raise urllib.error.HTTPError(url, 404, 'not found', hdrs=None, fp=None)

        monkeypatch.setattr(license_gate, '_http_get', _raise_404)
        res = client.post('/license/release')
        assert res.status_code == 409

    def test_releases_a_real_activated_installation(self, client, monkeypatch):
        _configure(monkeypatch)
        from app import licensing as license_gate
        from app import security as protected_loader

        monkeypatch.setattr(
            license_gate, '_http_get',
            lambda url, timeout=5.0: {'license_id': 'lic_1', 'status': 'active'})
        monkeypatch.setattr(
            protected_loader, '_http_get',
            lambda url: {'license_id': 'lic_1', 'status': 'active'})
        released = {}

        def _fake_release(base_url, license_id, install_id):
            released['license_id'] = license_id
            released['install_id'] = install_id
            return {'ok': True}

        monkeypatch.setattr(protected_loader, 'release', _fake_release)
        res = client.post('/license/release')
        assert res.status_code == 200
        assert released == {'license_id': 'lic_1', 'install_id': 'install-fake'}
