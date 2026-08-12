"""Real tests for the license gate (T016/T035) — network calls are stubbed at
license_gate._http_get (the one seam that actually talks to the wire), not
the whole module, so the real branching logic (including the real offline-
tolerance fallback, license_cache.py + offline_tolerance.py) still runs."""
import urllib.error

import pytest

from app.core import license_cache, license_gate


@pytest.fixture(autouse=True)
def isolated_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.delenv('APPDATA', raising=False)


class _FakeIdentity:
    install_id = 'install-fake'


def _configure(monkeypatch, http_get):
    from app.config import settings

    monkeypatch.setattr(settings, 'licensing_service_url', 'http://licensing.test')
    monkeypatch.setattr(license_gate, '_http_get', http_get)
    monkeypatch.setattr('app.core.install_identity.ensure_identity', lambda: _FakeIdentity())


def test_gate_allows_when_no_licensing_service_configured(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, 'licensing_service_url', '')
    monkeypatch.setattr(settings, 'dev_allow_unlicensed', True)
    result = license_gate.check_gate()
    assert result.allowed is True
    assert result.state == 'not_configured'


def test_gate_blocks_when_unconfigured_and_dev_override_is_off(monkeypatch):
    """T037: an empty licensing_service_url alone must never silently mean
    'no enforcement' — only the explicit dev_allow_unlicensed flag can."""
    from app.config import settings

    monkeypatch.setattr(settings, 'licensing_service_url', '')
    monkeypatch.setattr(settings, 'dev_allow_unlicensed', False)
    result = license_gate.check_gate()
    assert result.allowed is False
    assert result.state == 'not_activated'
    assert result.message


def test_gate_allows_when_installation_status_is_active(monkeypatch):
    _configure(monkeypatch, lambda url, timeout=5.0: {
        'license_id': 'lic_1', 'status': 'active', 'installations_used': 1, 'installations_limit': 2,
    })
    result = license_gate.check_gate()
    assert result.allowed is True
    assert result.state == 'active'
    assert result.installations_used == 1
    assert result.installations_limit == 2


def test_gate_reaching_the_service_records_a_successful_check(monkeypatch):
    """FR-056 — a successful reach, even to learn the license isn't active,
    is still a real revalidation for offline-tolerance purposes."""
    _configure(monkeypatch, lambda url, timeout=5.0: {'license_id': 'lic_1', 'status': 'active'})
    assert license_cache.days_since_last_success() is None
    license_gate.check_gate()
    assert license_cache.days_since_last_success() == pytest.approx(0.0, abs=0.1)


def test_gate_blocks_when_installation_status_is_not_active(monkeypatch):
    _configure(monkeypatch, lambda url, timeout=5.0: {'license_id': 'lic_1', 'status': 'revoked'})
    result = license_gate.check_gate()
    assert result.allowed is False
    assert result.state == 'blocked'
    assert result.message


def test_gate_blocks_when_installation_was_never_activated(monkeypatch):
    def _raise_404(url, timeout=5.0):
        raise urllib.error.HTTPError(url, 404, 'not found', hdrs=None, fp=None)

    _configure(monkeypatch, _raise_404)
    result = license_gate.check_gate()
    assert result.allowed is False
    assert result.state == 'not_activated'


class TestOfflineFallback:
    """FR-061: an unreachable service must fall back to the real
    offline-tolerance window, never a blanket allow or a blanket block."""

    def _raise_unreachable(self, url, timeout=5.0):
        raise urllib.error.URLError('connection refused')

    def test_never_successfully_validated_before_is_blocked_not_allowed(self, monkeypatch):
        """The old behavior blanket-allowed any network failure — that's
        wrong for an installation that has never once proven it's licensed."""
        _configure(monkeypatch, self._raise_unreachable)
        result = license_gate.check_gate()
        assert result.allowed is False
        assert result.state == 'blocked'

    def test_recently_validated_then_unreachable_is_allowed_within_tolerance(self, monkeypatch):
        license_cache.record_successful_check()
        _configure(monkeypatch, self._raise_unreachable)
        result = license_gate.check_gate()
        assert result.allowed is True
        assert result.state == 'offline_tolerance'
        assert result.offline_days_remaining == 30

    def test_validated_23_days_ago_then_unreachable_warns(self, monkeypatch):
        license_cache.record_successful_check(now_epoch=0.0)
        _configure(monkeypatch, self._raise_unreachable)
        monkeypatch.setattr('time.time', lambda: 23 * 86400.0)
        result = license_gate.check_gate()
        assert result.allowed is True
        assert result.state == 'offline_expiring'

    def test_validated_31_days_ago_then_unreachable_is_blocked(self, monkeypatch):
        license_cache.record_successful_check(now_epoch=0.0)
        _configure(monkeypatch, self._raise_unreachable)
        monkeypatch.setattr('time.time', lambda: 31 * 86400.0)
        result = license_gate.check_gate()
        assert result.allowed is False
        assert result.state == 'blocked'

    def test_a_5xx_from_the_service_itself_uses_the_same_offline_fallback(self, monkeypatch):
        def _raise_500(url, timeout=5.0):
            raise urllib.error.HTTPError(url, 500, 'server error', hdrs=None, fp=None)

        license_cache.record_successful_check()
        _configure(monkeypatch, _raise_500)
        result = license_gate.check_gate()
        assert result.allowed is True
        assert result.state == 'offline_tolerance'
