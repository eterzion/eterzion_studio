"""Unit tests for app.licensing — the core license/activation logic, tested
directly against the module (no HTTP layer) so failures point straight at the
business rule that broke."""
from __future__ import annotations

import pytest

from app import licensing


class TestCreateLicenseFromPayment:
    def test_creates_active_license_with_correct_fields(self, make_payment_event):
        event = make_payment_event(email='alice@example.com', provider='stripe', reference='txn_1')
        lic = licensing.create_license_from_payment(event)
        assert lic.email == 'alice@example.com'
        assert lic.status == 'active'
        assert lic.payment_provider == 'stripe'
        assert lic.payment_reference == 'txn_1'
        assert lic.id.startswith('lic_')

    def test_default_activation_limit_applied_when_not_specified(self, make_payment_event):
        from app.config import settings

        event = make_payment_event()
        lic = licensing.create_license_from_payment(event)
        assert lic.activation_limit == settings.default_activation_limit

    def test_explicit_activation_limit_overrides_default(self, make_payment_event):
        event = make_payment_event()
        lic = licensing.create_license_from_payment(event, activation_limit=7)
        assert lic.activation_limit == 7

    def test_idempotent_on_payment_reference(self, make_payment_event):
        """A webhook retried by the provider must not mint a second license
        for the same purchase — this is the documented contract, not
        incidental behavior."""
        event = make_payment_event(reference='txn_shared')
        first = licensing.create_license_from_payment(event)
        second = licensing.create_license_from_payment(event)
        assert first.id == second.id

    def test_idempotent_retry_does_not_duplicate_row(self, make_payment_event):
        from app.database import get_conn

        event = make_payment_event(reference='txn_dedup')
        licensing.create_license_from_payment(event)
        licensing.create_license_from_payment(event)
        with get_conn() as conn:
            count = conn.execute(
                'SELECT COUNT(*) AS n FROM licenses WHERE payment_reference = ?', ('txn_dedup',)
            ).fetchone()['n']
        assert count == 1

    def test_different_references_create_different_licenses(self, make_payment_event):
        first = licensing.create_license_from_payment(make_payment_event(reference='txn_a'))
        second = licensing.create_license_from_payment(make_payment_event(reference='txn_b'))
        assert first.id != second.id


class TestGetLicense:
    def test_returns_none_for_unknown_id(self):
        assert licensing.get_license('lic_does_not_exist') is None

    def test_returns_license_for_known_id(self, license_factory):
        created = license_factory()
        fetched = licensing.get_license(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.email == created.email


class TestSetLicenseStatus:
    def test_updates_status(self, license_factory):
        lic = license_factory()
        assert licensing.set_license_status(lic.id, 'revoked') is True
        assert licensing.get_license(lic.id).status == 'revoked'

    def test_returns_false_for_unknown_license(self):
        assert licensing.set_license_status('lic_ghost', 'revoked') is False


class TestActivateInstallation:
    def test_succeeds_under_limit(self, license_factory, install_keys):
        lic = license_factory(activation_limit=2)
        keys = install_keys()
        licensing.activate_installation(lic.id, 'install-1', **keys)
        installed = licensing.get_installation('install-1')
        assert installed is not None
        assert installed['license_id'] == lic.id
        assert installed['signing_public_key_b64'] == keys['signing_public_key_b64']

    def test_raises_for_unknown_license(self, install_keys):
        with pytest.raises(licensing.LicenseError):
            licensing.activate_installation('lic_ghost', 'install-1', **install_keys())

    @pytest.mark.parametrize('status', ['revoked', 'refunded', 'suspended', 'pending'])
    def test_raises_when_license_not_active(self, license_factory, install_keys, status):
        lic = license_factory()
        licensing.set_license_status(lic.id, status)
        with pytest.raises(licensing.LicenseNotActive):
            licensing.activate_installation(lic.id, 'install-1', **install_keys())

    def test_raises_when_activation_limit_reached(self, license_factory, install_keys):
        lic = license_factory(activation_limit=2)
        licensing.activate_installation(lic.id, 'install-1', **install_keys())
        licensing.activate_installation(lic.id, 'install-2', **install_keys())
        with pytest.raises(licensing.ActivationLimitReached):
            licensing.activate_installation(lic.id, 'install-3', **install_keys())

    def test_third_install_does_not_get_persisted_after_limit_error(self, license_factory, install_keys):
        """The limit check must reject before any write — a failed activation
        must never leave a partial row behind."""
        lic = license_factory(activation_limit=1)
        licensing.activate_installation(lic.id, 'install-1', **install_keys())
        with pytest.raises(licensing.ActivationLimitReached):
            licensing.activate_installation(lic.id, 'install-2', **install_keys())
        assert licensing.get_installation('install-2') is None
        assert len(licensing.list_installations(lic.id)) == 1

    def test_reactivating_same_device_on_same_license_is_idempotent(self, license_factory, install_keys):
        """Re-running the desktop app's activation call (e.g. on every
        startup) for a device already tied to this license must not count
        against the seat limit a second time."""
        lic = license_factory(activation_limit=1)
        keys = install_keys()
        licensing.activate_installation(lic.id, 'install-1', **keys)
        licensing.activate_installation(lic.id, 'install-1', **keys)  # must not raise
        assert len(licensing.list_installations(lic.id)) == 1

    def test_reactivation_updates_last_seen_at(self, license_factory, install_keys, monkeypatch):
        lic = license_factory(activation_limit=1)
        keys = install_keys()
        licensing.activate_installation(lic.id, 'install-1', **keys)
        first_seen = licensing.get_installation('install-1')['last_seen_at']

        monkeypatch.setattr(licensing, '_now_iso', lambda: '2099-01-01T00:00:00Z')
        licensing.activate_installation(lic.id, 'install-1', **keys)
        second_seen = licensing.get_installation('install-1')['last_seen_at']
        assert second_seen == '2099-01-01T00:00:00Z'
        assert second_seen != first_seen

    def test_install_id_migrating_to_a_different_license_replaces_old_association(
        self, license_factory, install_keys
    ):
        """Regression test for a real bug found during manual testing this
        session: install_id is the installations table's PRIMARY KEY, so
        re-activating the same install under a *different* license (e.g. the
        user's earlier license was refunded and they bought a new one) used to
        hit a UNIQUE/PRIMARY KEY violation instead of migrating cleanly."""
        license_a = license_factory(activation_limit=5)
        license_b = license_factory(activation_limit=5)
        keys = install_keys()

        licensing.activate_installation(license_a.id, 'install-shared', **keys)
        licensing.activate_installation(license_b.id, 'install-shared', **keys)  # must not raise

        assert licensing.get_installation('install-shared')['license_id'] == license_b.id
        assert licensing.list_installations(license_a.id) == []
        assert len(licensing.list_installations(license_b.id)) == 1

    def test_migrating_installation_does_not_count_against_old_licenses_limit_check(
        self, license_factory, install_keys
    ):
        """After migrating away, the old license's seat should be free again
        for a genuinely new device."""
        license_a = license_factory(activation_limit=1)
        license_b = license_factory(activation_limit=5)
        keys = install_keys()

        licensing.activate_installation(license_a.id, 'install-shared', **keys)
        licensing.activate_installation(license_b.id, 'install-shared', **keys)

        # license_a should have 0 installs now, so a fresh device can take the freed seat
        licensing.activate_installation(license_a.id, 'install-new', **install_keys())
        assert len(licensing.list_installations(license_a.id)) == 1


class TestReleaseInstallation:
    def test_removes_installation(self, license_factory, install_keys):
        lic = license_factory()
        licensing.activate_installation(lic.id, 'install-1', **install_keys())
        assert licensing.release_installation(lic.id, 'install-1') is True
        assert licensing.get_installation('install-1') is None

    def test_returns_false_for_unknown_installation(self, license_factory):
        lic = license_factory()
        assert licensing.release_installation(lic.id, 'install-ghost') is False

    def test_returns_false_when_license_id_does_not_match(self, license_factory, install_keys):
        """A release request scoped to the wrong license must not delete
        someone else's installation row — this is the ownership check."""
        license_a = license_factory()
        license_b = license_factory()
        licensing.activate_installation(license_a.id, 'install-1', **install_keys())
        assert licensing.release_installation(license_b.id, 'install-1') is False
        assert licensing.get_installation('install-1') is not None

    def test_frees_seat_for_a_new_activation(self, license_factory, install_keys):
        lic = license_factory(activation_limit=1)
        licensing.activate_installation(lic.id, 'install-1', **install_keys())
        licensing.release_installation(lic.id, 'install-1')
        licensing.activate_installation(lic.id, 'install-2', **install_keys())  # must not raise
        assert len(licensing.list_installations(lic.id)) == 1


class TestInstallationLicense:
    def test_returns_the_license_an_install_is_activated_against(self, license_factory, install_keys):
        lic = license_factory()
        licensing.activate_installation(lic.id, 'install-1', **install_keys())
        found = licensing.installation_license('install-1')
        assert found is not None
        assert found.id == lic.id

    def test_returns_none_for_unactivated_install(self):
        assert licensing.installation_license('install-never-activated') is None
