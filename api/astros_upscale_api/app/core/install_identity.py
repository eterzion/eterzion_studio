"""Per-installation cryptographic identity (Fase 2 — identidade criptográfica
por instalação, docs/processing-protection-architecture.md).

Generated once, on first run. Two keypairs, both never leaving the machine as
private material:
- Ed25519 (signing) — proves "this specific installation" made a request
  (e.g. an activation or authorization request).
- X25519 (key exchange) — lets the licensing service (Fase 3) envelope-encrypt
  a package's content key specifically for this installation (Fase 4): only
  this installation's private key can unwrap it, so a package copied to
  another machine is useless there. Ed25519 alone can't do this — a signing
  key doesn't double as an encryption key.

At rest, both private keys are protected by Windows DPAPI (tied to the current
Windows user profile), never written to disk in the clear. TPM-backed
protection, where available, is a Fase 6 enhancement layered on top of this,
not a prerequisite for it.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
from cryptography.hazmat.primitives.hashes import SHA256

from app.core import dpapi, secure_tempdir

_DIRNAME = 'AstrosUpscale'
_IDENTITY_FILENAME = 'identity.json'
_HKDF_INFO = b'astros-upscale-package-key-wrap'


def _identity_dir() -> str:
    base = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA')
    if not base:
        base = str(Path.home())
    path = os.path.join(base, _DIRNAME, 'identity')
    os.makedirs(path, exist_ok=True)
    return path


def _identity_path() -> str:
    return os.path.join(_identity_dir(), _IDENTITY_FILENAME)


@dataclass
class InstallIdentity:
    install_id: str
    signing_public_key_bytes: bytes = field(repr=False)
    encryption_public_key_bytes: bytes = field(repr=False)
    _signing_key: Ed25519PrivateKey = field(repr=False)
    _encryption_key: X25519PrivateKey = field(repr=False)

    @property
    def signing_public_key_b64(self) -> str:
        return base64.b64encode(self.signing_public_key_bytes).decode('ascii')

    @property
    def encryption_public_key_b64(self) -> str:
        return base64.b64encode(self.encryption_public_key_bytes).decode('ascii')

    def sign(self, data: bytes) -> bytes:
        """Proves this installation produced `data` (e.g. an activation request
        payload). The private key never leaves this process's memory."""
        return self._signing_key.sign(data)

    def decrypt_envelope(self, ephemeral_public_key_b64: str, nonce_b64: str, wrapped_key_b64: str) -> bytes:
        """Unwraps a content key the licensing service encrypted specifically
        for this installation's X25519 public key (see package_crypto.py on
        the service side). Only this installation's private key can do this —
        the whole point of Fase 4's "vinculado à instalação"."""
        eph_pub = X25519PublicKey.from_public_bytes(base64.b64decode(ephemeral_public_key_b64))
        shared = self._encryption_key.exchange(eph_pub)
        derived_key = HKDF(algorithm=SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(shared)
        del shared  # best-effort — see protected_loader.py for the caveat on what this actually buys
        nonce = base64.b64decode(nonce_b64)
        wrapped = base64.b64decode(wrapped_key_b64)
        try:
            return AESGCM(derived_key).decrypt(nonce, wrapped, None)
        finally:
            del derived_key


def verify(public_key_bytes: bytes, data: bytes, signature: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(signature, data)
        return True
    except InvalidSignature:
        return False


def _protect(raw: bytes, entropy: bytes) -> bytes:
    if dpapi.is_available():
        return dpapi.protect(raw, entropy=entropy)
    return raw  # non-Windows fallback (dev only) — weaker than DPAPI, documented as such


def _unprotect(blob: bytes, entropy: bytes) -> bytes:
    if dpapi.is_available():
        return dpapi.unprotect(blob, entropy=entropy)
    return blob


def _generate_and_persist() -> InstallIdentity:
    signing_key = Ed25519PrivateKey.generate()
    encryption_key = X25519PrivateKey.generate()
    raw_signing_priv = signing_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    raw_encryption_priv = encryption_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    raw_signing_pub = signing_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    raw_encryption_pub = encryption_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    install_id = uuid.uuid4().hex

    payload = {
        'install_id': install_id,
        'signing_public_key_b64': base64.b64encode(raw_signing_pub).decode('ascii'),
        'signing_private_key_protected_b64': base64.b64encode(
            _protect(raw_signing_priv, b'astros-upscale-install-signing')).decode('ascii'),
        'encryption_public_key_b64': base64.b64encode(raw_encryption_pub).decode('ascii'),
        'encryption_private_key_protected_b64': base64.b64encode(
            _protect(raw_encryption_priv, b'astros-upscale-install-encryption')).decode('ascii'),
        'protected_with': 'dpapi' if dpapi.is_available() else 'none',
    }
    identity_dir = _identity_dir()
    secure_tempdir.restrict_to_current_user(identity_dir)
    path = _identity_path()
    tmp_path = path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh)
    os.replace(tmp_path, path)  # atomic on both Windows and POSIX
    if sys.platform != 'win32':
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    return InstallIdentity(
        install_id=install_id, signing_public_key_bytes=raw_signing_pub, encryption_public_key_bytes=raw_encryption_pub,
        _signing_key=signing_key, _encryption_key=encryption_key,
    )


def _load_existing() -> InstallIdentity | None:
    path = _identity_path()
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding='utf-8') as fh:
            payload = json.load(fh)
        raw_signing_priv = _unprotect(
            base64.b64decode(payload['signing_private_key_protected_b64']), b'astros-upscale-install-signing')
        raw_encryption_priv = _unprotect(
            base64.b64decode(payload['encryption_private_key_protected_b64']), b'astros-upscale-install-encryption')
        signing_key = Ed25519PrivateKey.from_private_bytes(raw_signing_priv)
        encryption_key = X25519PrivateKey.from_private_bytes(raw_encryption_priv)
        raw_signing_pub = base64.b64decode(payload['signing_public_key_b64'])
        raw_encryption_pub = base64.b64decode(payload['encryption_public_key_b64'])
        return InstallIdentity(
            install_id=payload['install_id'], signing_public_key_bytes=raw_signing_pub,
            encryption_public_key_bytes=raw_encryption_pub, _signing_key=signing_key, _encryption_key=encryption_key,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        # Corrupted, from a different user profile (DPAPI can't decrypt it), or
        # otherwise unreadable — treat as absent rather than crash the API.
        return None


_cached: InstallIdentity | None = None


def ensure_identity() -> InstallIdentity:
    """Idempotent: loads the existing installation identity, or generates one
    on first run. Safe to call on every API startup."""
    global _cached
    if _cached is not None:
        return _cached
    identity = _load_existing() or _generate_and_persist()
    _cached = identity
    return identity
