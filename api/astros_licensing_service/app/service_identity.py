"""The licensing service's own signing key — used to sign authorizations
issued to installations (§4.2 of the architecture doc). Separate from, and
never shared with, an installation's identity (astros_upscale_api's
install_identity.py) — this key belongs to the server, not to any one user's
machine.

This is a server-side secret, not a desktop-user secret, so it's protected
here by plain file permissions (chmod 600 / a best-effort Windows ACL
restriction), not DPAPI — DPAPI is scoped to a Windows user profile, which
doesn't map to how a server process runs. In a real deployment this file
should be backed by a proper secrets manager/KMS instead of bare disk storage;
this local implementation is a reasonable default for self-hosting on a single
box, not a substitute for one.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

from app.config import settings


def _restrict_to_owner(path: str) -> None:
    if sys.platform == 'win32':
        username = os.environ.get('USERNAME')
        domain = os.environ.get('USERDOMAIN')
        account = f'{domain}\\{username}' if domain and username else username
        if not account:
            return
        try:
            subprocess.run(
                ['icacls', path, '/inheritance:r', '/grant:r', f'{account}:F'],
                capture_output=True, timeout=10, check=False, shell=False,
            )
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def _key_path() -> str:
    os.makedirs(settings.identity_dir, exist_ok=True)
    return os.path.join(settings.identity_dir, 'service_signing_key.raw')


def _load_or_generate() -> Ed25519PrivateKey:
    path = _key_path()
    if os.path.isfile(path):
        raw = Path(path).read_bytes()
        return Ed25519PrivateKey.from_private_bytes(raw)
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    tmp = path + '.tmp'
    Path(tmp).write_bytes(raw)
    os.replace(tmp, path)
    _restrict_to_owner(path)
    return key


_cached: Ed25519PrivateKey | None = None


def get_signing_key() -> Ed25519PrivateKey:
    global _cached
    if _cached is None:
        _cached = _load_or_generate()
    return _cached


def get_public_key_b64() -> str:
    import base64
    raw = get_signing_key().public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(raw).decode('ascii')
