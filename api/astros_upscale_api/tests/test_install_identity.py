"""Tests for the .exe's own cryptographic identity — install_identity.py.
This is the client-side half of the trust chain: the licensing service only
ever sees the public keys generated here, and only this process can produce a
valid signature or unwrap an envelope for this specific installation."""
from __future__ import annotations

import base64
import json

import pytest

from app import security as install_identity


class TestEnsureIdentity:
    def test_generates_an_identity_on_first_call(self):
        identity = install_identity.ensure_identity()
        assert identity.install_id
        assert len(base64.b64decode(identity.signing_public_key_b64)) == 32
        assert len(base64.b64decode(identity.encryption_public_key_b64)) == 32

    def test_is_idempotent_within_the_same_process(self):
        first = install_identity.ensure_identity()
        second = install_identity.ensure_identity()
        assert first.install_id == second.install_id
        assert first.signing_public_key_b64 == second.signing_public_key_b64

    def test_persists_across_a_fresh_process_cache(self):
        """Simulates the API restarting: clear the in-memory cache (but keep
        the on-disk file) and confirm the *same* identity — not a new one —
        is loaded back, matching ensure_identity()'s documented contract."""
        first = install_identity.ensure_identity()
        install_identity._cached_identity = None
        second = install_identity.ensure_identity()
        assert first.install_id == second.install_id
        assert first.signing_public_key_b64 == second.signing_public_key_b64

    def test_writes_only_public_material_and_protected_private_material(self):
        identity = install_identity.ensure_identity()
        path = install_identity._identity_path()
        with open(path, encoding='utf-8') as fh:
            payload = json.load(fh)
        assert payload['install_id'] == identity.install_id
        assert payload['signing_public_key_b64'] == identity.signing_public_key_b64
        # the raw private key must never appear verbatim in the persisted file
        raw_priv_b64_fragment = base64.b64encode(b'\x00' * 32).decode('ascii')[:10]
        assert raw_priv_b64_fragment not in json.dumps(payload)
        assert 'signing_private_key_protected_b64' in payload
        assert 'encryption_private_key_protected_b64' in payload

    def test_install_id_is_unique_per_fresh_identity_dir(self, tmp_path, monkeypatch):
        first = install_identity.ensure_identity()

        another_dir = tmp_path / 'other-identity'
        another_dir.mkdir()
        monkeypatch.setattr(install_identity, '_identity_dir', lambda: str(another_dir))
        install_identity._cached_identity = None
        second = install_identity.ensure_identity()

        assert first.install_id != second.install_id


class TestSignAndVerify:
    def test_a_signature_verifies_against_its_own_public_key(self):
        identity = install_identity.ensure_identity()
        signature = identity.sign(b'a request payload')
        pubkey_bytes = base64.b64decode(identity.signing_public_key_b64)
        assert install_identity.verify_signature(pubkey_bytes, b'a request payload', signature) is True

    def test_verify_rejects_a_tampered_payload(self):
        identity = install_identity.ensure_identity()
        signature = identity.sign(b'original payload')
        pubkey_bytes = base64.b64decode(identity.signing_public_key_b64)
        assert install_identity.verify_signature(pubkey_bytes, b'tampered payload', signature) is False

    def test_verify_rejects_a_signature_from_a_different_identity(self, tmp_path, monkeypatch):
        identity_a = install_identity.ensure_identity()
        signature = identity_a.sign(b'shared payload')

        other_dir = tmp_path / 'identity-b'
        other_dir.mkdir()
        monkeypatch.setattr(install_identity, '_identity_dir', lambda: str(other_dir))
        install_identity._cached_identity = None
        identity_b = install_identity.ensure_identity()

        pubkey_b_bytes = base64.b64decode(identity_b.signing_public_key_b64)
        assert install_identity.verify_signature(pubkey_b_bytes, b'shared payload', signature) is False

    def test_verify_rejects_malformed_signature_bytes_without_raising(self):
        identity = install_identity.ensure_identity()
        pubkey_bytes = base64.b64decode(identity.signing_public_key_b64)
        assert install_identity.verify_signature(pubkey_bytes, b'payload', b'not-a-real-signature') is False


class TestEnvelopeDecryption:
    def test_decrypts_an_envelope_wrapped_for_this_installations_public_key(self):
        """Mirrors what package_crypto.py on the licensing-service side does:
        X25519 ECDH + HKDF-SHA256 + AES-GCM, wrapping a content key
        specifically for one installation's encryption public key."""
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.hashes import SHA256
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        import os

        identity = install_identity.ensure_identity()
        install_pub = X25519PublicKey.from_public_bytes(base64.b64decode(identity.encryption_public_key_b64))

        ephemeral = X25519PrivateKey.generate()
        shared = ephemeral.exchange(install_pub)
        derived_key = HKDF(algorithm=SHA256(), length=32, salt=None, info=install_identity._HKDF_INFO).derive(shared)
        nonce = os.urandom(12)
        content_key = b'a-32-byte-content-key-material!'
        wrapped = AESGCM(derived_key).encrypt(nonce, content_key, None)

        eph_pub_b64 = base64.b64encode(
            ephemeral.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        ).decode('ascii')
        decrypted = identity.decrypt_envelope(eph_pub_b64, base64.b64encode(nonce).decode('ascii'), base64.b64encode(wrapped).decode('ascii'))
        assert decrypted == content_key

    def test_rejects_a_wrapped_key_encrypted_for_a_different_installation(self, tmp_path, monkeypatch):
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.hashes import SHA256
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        from cryptography.exceptions import InvalidTag
        import os

        install_identity.ensure_identity()  # identity A, unused directly — just occupies the "real" install

        other_dir = tmp_path / 'identity-victim'
        other_dir.mkdir()
        monkeypatch.setattr(install_identity, '_identity_dir', lambda: str(other_dir))
        install_identity._cached_identity = None
        victim = install_identity.ensure_identity()

        # Wrap for an unrelated third keypair, not the victim's.
        attacker_target = X25519PrivateKey.generate()
        ephemeral = X25519PrivateKey.generate()
        shared = ephemeral.exchange(attacker_target.public_key())
        derived_key = HKDF(algorithm=SHA256(), length=32, salt=None, info=install_identity._HKDF_INFO).derive(shared)
        nonce = os.urandom(12)
        wrapped = AESGCM(derived_key).encrypt(nonce, b'secret-content-key', None)
        eph_pub_b64 = base64.b64encode(
            ephemeral.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        ).decode('ascii')

        with pytest.raises(InvalidTag):
            victim.decrypt_envelope(eph_pub_b64, base64.b64encode(nonce).decode('ascii'), base64.b64encode(wrapped).decode('ascii'))


class TestCorruptedOrMissingIdentity:
    def test_missing_file_returns_none_from_load_existing(self):
        assert install_identity._load_existing() is None

    def test_corrupted_json_is_treated_as_absent_not_a_crash(self):
        path = install_identity._identity_path()
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('{not valid json')
        assert install_identity._load_existing() is None

    def test_ensure_identity_regenerates_after_corruption(self):
        original = install_identity.ensure_identity()
        install_identity._cached_identity = None

        path = install_identity._identity_path()
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('{"garbage": true}')

        recovered = install_identity.ensure_identity()
        assert recovered.install_id != original.install_id  # a fresh identity was minted, not a crash
