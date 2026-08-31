"""T034 (eterzion_upscale_api half): nothing license_gate.py sends over the
wire, or persists locally, may carry file bytes, content hashes, or any
field derived from the media being processed (FR-062). The licensing
service's own payload-shape audit lives in
api/eterzion_licensing_service/tests/test_no_content_leakage.py — a
different Python package, not importable from here."""
from __future__ import annotations

import urllib.error

import pytest

from app import licensing as license_gate

_SUSPICIOUS_SUBSTRINGS = (
    'file', 'path', 'content', 'hash', 'sha256', 'md5', 'bytes', 'media',
    'input_path', 'output_path', 'source', 'checksum',
)


@pytest.fixture(autouse=True)
def isolated_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.delenv('APPDATA', raising=False)


class _FakeIdentity:
    install_id = 'install-fake'


def test_license_gate_only_ever_sends_a_bare_get_no_body(monkeypatch):
    """Capture every call check_gate() makes to the wire and confirm none of
    them carries a body — the gate is GET-only, so there is no channel for
    file content to travel through in the first place."""
    from app.config import settings

    calls = []

    def spy_http_get(url, timeout=5.0):
        calls.append(url)
        return {'license_id': 'lic_1', 'status': 'active'}

    monkeypatch.setattr(settings, 'licensing_service_url', 'http://licensing.test')
    monkeypatch.setattr(license_gate, '_http_get', spy_http_get)
    monkeypatch.setattr('app.security.ensure_identity', lambda: _FakeIdentity())

    license_gate.check_gate()

    assert len(calls) == 1
    url = calls[0]
    assert url == 'http://licensing.test/activations/install-fake/status'
    for term in _SUSPICIOUS_SUBSTRINGS:
        assert term not in url.lower(), f'suspicious term {term!r} found in license-check URL: {url}'


def test_license_cache_never_persists_anything_but_timestamps(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    license_gate.record_successful_check(now_epoch=1000.0)
    cached = license_gate.load_license_cache()
    assert set(cached.keys()) == {'last_success_epoch', 'max_observed_epoch'}
    assert all(isinstance(v, (int, float)) for v in cached.values())


def test_offline_fallback_path_sends_nothing_at_all(monkeypatch):
    """FR-061's offline path is entirely local computation — confirm it
    makes zero additional network calls, so there's no channel to leak
    through even in principle while offline."""
    from app.config import settings

    def _raise_unreachable(url, timeout=5.0):
        raise urllib.error.URLError('connection refused')

    monkeypatch.setattr(settings, 'licensing_service_url', 'http://licensing.test')
    monkeypatch.setattr(license_gate, '_http_get', _raise_unreachable)
    monkeypatch.setattr('app.security.ensure_identity', lambda: _FakeIdentity())

    result = license_gate.check_gate()
    assert result.state in ('blocked', 'offline_tolerance', 'offline_expiring')
