"""Unit tests for app.authorizations — short-lived signed processing
authorizations, their anti-rollback check, and atomic anti-replay redemption."""
from __future__ import annotations

import base64
import time

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app import authorizations, licensing
from app.db import get_conn
from app.service_identity import get_public_key_b64


def _activate(license_factory, install_keys, activation_limit=5):
    lic = license_factory(activation_limit=activation_limit)
    install_id = 'install-auth-test'
    licensing.activate_installation(lic.id, install_id, **install_keys())
    return lic, install_id


class TestIssueAuthorization:
    def test_issues_a_signed_authorization_for_an_active_installation(self, license_factory, install_keys):
        _lic, install_id = _activate(license_factory, install_keys)
        result = authorizations.issue_authorization(install_id, 'realesrgan-x4', '1.0.0', 'process')
        assert result['authorization']['install_id'] == install_id
        assert result['authorization']['model'] == 'realesrgan-x4'
        assert result['authorization']['max_uses'] == 1
        assert 'signature_b64' in result

    def test_signature_verifies_against_the_services_public_key(self, license_factory, install_keys):
        _lic, install_id = _activate(license_factory, install_keys)
        result = authorizations.issue_authorization(install_id, 'realesrgan-x4', '1.0.0', 'process')

        payload_bytes = authorizations._canonical_payload(result['authorization'])
        signature = base64.b64decode(result['signature_b64'])
        pubkey = Ed25519PublicKey.from_public_bytes(base64.b64decode(get_public_key_b64()))
        pubkey.verify(signature, payload_bytes)  # raises InvalidSignature on failure

    def test_signature_rejects_tampered_payload(self, license_factory, install_keys):
        _lic, install_id = _activate(license_factory, install_keys)
        result = authorizations.issue_authorization(install_id, 'realesrgan-x4', '1.0.0', 'process')

        tampered = dict(result['authorization'])
        tampered['model'] = 'a-different-model'
        payload_bytes = authorizations._canonical_payload(tampered)
        signature = base64.b64decode(result['signature_b64'])
        pubkey = Ed25519PublicKey.from_public_bytes(base64.b64decode(get_public_key_b64()))
        with pytest.raises(InvalidSignature):
            pubkey.verify(signature, payload_bytes)

    def test_raises_when_installation_never_activated(self):
        with pytest.raises(authorizations.AuthorizationError):
            authorizations.issue_authorization('install-never-activated', 'realesrgan-x4', '1.0.0', 'process')

    def test_raises_when_license_not_active(self, license_factory, install_keys):
        lic, install_id = _activate(license_factory, install_keys)
        licensing.set_license_status(lic.id, 'suspended')
        with pytest.raises(licensing.LicenseNotActive):
            authorizations.issue_authorization(install_id, 'realesrgan-x4', '1.0.0', 'process')

    def test_persists_a_row_with_zero_uses_consumed(self, license_factory, install_keys):
        _lic, install_id = _activate(license_factory, install_keys)
        result = authorizations.issue_authorization(install_id, 'realesrgan-x4', '1.0.0', 'process')
        stored = authorizations.get_authorization(result['authorization']['id'])
        assert stored is not None
        assert stored['uses_consumed'] == 0
        assert stored['max_uses'] == 1

    def test_anti_rollback_rejects_outdated_version_for_process_operation(self, license_factory, install_keys):
        from app.packages import save_package

        _lic, install_id = _activate(license_factory, install_keys)
        save_package('orchestration-logic', '2.0.0', {
            'ciphertext_b64': 'x', 'nonce_b64': 'x', 'signature_b64': 'x', 'content_key_b64': 'x',
        })
        with pytest.raises(authorizations.VersionRejected):
            authorizations.issue_authorization(install_id, 'realesrgan-x4', '1.0.0', 'process')

    def test_anti_rollback_allows_the_current_version(self, license_factory, install_keys):
        from app.packages import save_package

        _lic, install_id = _activate(license_factory, install_keys)
        save_package('orchestration-logic', '2.0.0', {
            'ciphertext_b64': 'x', 'nonce_b64': 'x', 'signature_b64': 'x', 'content_key_b64': 'x',
        })
        result = authorizations.issue_authorization(install_id, 'realesrgan-x4', '2.0.0', 'process')
        assert result['authorization']['version'] == '2.0.0'

    def test_anti_rollback_does_not_apply_to_non_process_operations(self, license_factory, install_keys):
        from app.packages import save_package

        _lic, install_id = _activate(license_factory, install_keys)
        save_package('orchestration-logic', '2.0.0', {
            'ciphertext_b64': 'x', 'nonce_b64': 'x', 'signature_b64': 'x', 'content_key_b64': 'x',
        })
        result = authorizations.issue_authorization(install_id, 'realesrgan-x4', '1.0.0', 'other-op')
        assert result['authorization']['version'] == '1.0.0'


class TestRedeemAuthorization:
    def test_redeems_a_valid_authorization(self, license_factory, install_keys):
        _lic, install_id = _activate(license_factory, install_keys)
        result = authorizations.issue_authorization(install_id, 'm', 'v', 'process')
        assert authorizations.redeem_authorization(result['authorization']['id']) is True

    def test_redeeming_twice_fails_the_second_time(self, license_factory, install_keys):
        """Anti-replay: max_uses=1 by default, enforced by an atomic
        UPDATE ... WHERE uses_consumed < max_uses, not a check-then-write."""
        _lic, install_id = _activate(license_factory, install_keys)
        result = authorizations.issue_authorization(install_id, 'm', 'v', 'process')
        auth_id = result['authorization']['id']
        assert authorizations.redeem_authorization(auth_id) is True
        assert authorizations.redeem_authorization(auth_id) is False

    def test_redeeming_unknown_id_fails(self):
        assert authorizations.redeem_authorization('auth_does_not_exist') is False

    def test_redeeming_expired_authorization_fails(self, license_factory, install_keys):
        _lic, install_id = _activate(license_factory, install_keys)
        result = authorizations.issue_authorization(install_id, 'm', 'v', 'process', ttl_seconds=-10)
        assert authorizations.redeem_authorization(result['authorization']['id']) is False

    def test_second_use_never_increments_beyond_max_uses(self, license_factory, install_keys):
        _lic, install_id = _activate(license_factory, install_keys)
        result = authorizations.issue_authorization(install_id, 'm', 'v', 'process')
        auth_id = result['authorization']['id']
        authorizations.redeem_authorization(auth_id)
        authorizations.redeem_authorization(auth_id)
        authorizations.redeem_authorization(auth_id)
        stored = authorizations.get_authorization(auth_id)
        assert stored['uses_consumed'] == 1


class TestRedeemForInstall:
    def test_succeeds_for_the_owning_installation(self, license_factory, install_keys):
        _lic, install_id = _activate(license_factory, install_keys)
        result = authorizations.issue_authorization(install_id, 'm', 'v', 'process')
        auth = authorizations.redeem_for_install(result['authorization']['id'], install_id)
        assert auth is not None
        assert auth['install_id'] == install_id

    def test_rejects_a_different_installation(self, license_factory, install_keys):
        """An authorization issued for one installation must not be
        redeemable by another, even with a guessed/leaked authorization id."""
        _lic, install_id = _activate(license_factory, install_keys)
        result = authorizations.issue_authorization(install_id, 'm', 'v', 'process')
        auth = authorizations.redeem_for_install(result['authorization']['id'], 'a-different-install')
        assert auth is None
        # and the use must not have been consumed by the failed attempt
        stored = authorizations.get_authorization(result['authorization']['id'])
        assert stored['uses_consumed'] == 0

    def test_rejects_expired_authorization(self, license_factory, install_keys):
        _lic, install_id = _activate(license_factory, install_keys)
        result = authorizations.issue_authorization(install_id, 'm', 'v', 'process', ttl_seconds=-10)
        assert authorizations.redeem_for_install(result['authorization']['id'], install_id) is None
