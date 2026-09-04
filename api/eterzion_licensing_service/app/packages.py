"""Storage for built packages (Fase 4) and their per-installation encryption.
Consolidates what were `packages.py` and `package_crypto.py` (Constitution
Princípio XI) — the encryption/signing mechanisms are unchanged.
"""
from __future__ import annotations

import base64
import os
import time

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.database import get_conn

# ------------------------------- package storage ------------------------------- #
#
# Storage for built packages (Fase 4). Building (encrypting the source once)
# is a separate offline step — see tools/build_package.py — this section just
# persists/retrieves the result.


def _now_iso() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def save_package(name: str, version: str, built: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            'INSERT OR REPLACE INTO packages (name, version, ciphertext_b64, nonce_b64, signature_b64, content_key_b64, built_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (name, version, built['ciphertext_b64'], built['nonce_b64'], built['signature_b64'], built['content_key_b64'], _now_iso()),
        )


def get_package(name: str, version: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            'SELECT * FROM packages WHERE name = ? AND version = ?', (name, version)
        ).fetchone()
    return dict(row) if row is not None else None


def latest_version(name: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            'SELECT version FROM packages WHERE name = ? ORDER BY built_at DESC LIMIT 1', (name,)
        ).fetchone()
    return row['version'] if row is not None else None


# ------------------------------- package encryption ------------------------------- #
#
# Package encryption for Fase 4 — pacote temporário de execução. Two layers:
#
# 1. Content encryption: the package bytes (the orchestration logic) are
#    encrypted ONCE per build with a random content key (AES-256-GCM), and the
#    ciphertext is signed with the service's Ed25519 key (app.licensing's
#    service identity). The ciphertext is the same for every installation —
#    expensive to produce, cheap to serve, safe to cache.
# 2. Key wrapping: the 32-byte content key is envelope-encrypted PER
#    INSTALLATION at request time, via X25519 ECDH with that installation's
#    public key + HKDF + AES-GCM. Only that installation's private key can
#    unwrap it (the client's decrypt_envelope) — this is what "vinculado à
#    instalação" actually means cryptographically, not just an access-control
#    check.

# ATENÇÃO — não é o nome do produto. `_HKDF_INFO` é separação de domínio na
# derivação de chave, e o **mesmo valor** vive no cliente, em
# `eterzion_upscale_api/app/security.py`. O produto passou a se chamar Eterzion
# Studio; esta cadeia não acompanhou de propósito, porque as duas pontas têm de
# bater e este serviço já está implantado. Trocá-la é migração de protocolo
# coordenada, não renomeação.
_HKDF_INFO = b'astros-upscale-package-key-wrap'


def build_package(source_bytes: bytes) -> dict:
    """Encrypts + signs once. Returns everything needed to serve this package
    to any number of installations (the content key is NOT included — it's
    only ever wrapped per-installation by wrap_content_key_for_install)."""
    # Lazy import: app.licensing depends on app.packages (authorizations'
    # latest_version) at module load time — importing app.licensing back at
    # the top of this file would be a real circular import. Deferred here,
    # the only place in this module that needs it, breaks the cycle (see
    # research.md Decisão 3).
    from app.licensing import get_signing_key

    content_key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    ciphertext = AESGCM(content_key).encrypt(nonce, source_bytes, None)
    signature = get_signing_key().sign(nonce + ciphertext)
    return {
        'ciphertext_b64': base64.b64encode(ciphertext).decode('ascii'),
        'nonce_b64': base64.b64encode(nonce).decode('ascii'),
        'signature_b64': base64.b64encode(signature).decode('ascii'),
        'content_key_b64': base64.b64encode(content_key).decode('ascii'),  # kept server-side only, never served raw
    }


def wrap_content_key_for_install(content_key_b64: str, install_encryption_public_key_b64: str) -> dict:
    content_key = base64.b64decode(content_key_b64)
    install_pub = X25519PublicKey.from_public_bytes(base64.b64decode(install_encryption_public_key_b64))

    ephemeral_private = X25519PrivateKey.generate()
    shared = ephemeral_private.exchange(install_pub)
    derived_key = HKDF(algorithm=SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(shared)
    del shared

    nonce = os.urandom(12)
    wrapped = AESGCM(derived_key).encrypt(nonce, content_key, None)
    # Best-effort — see app.security's protected loader for the matching
    # comment on the client side: dropping the reference is what CPython
    # actually offers here, not a guaranteed wipe of the underlying memory.
    del content_key, derived_key
    ephemeral_public_bytes = ephemeral_private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return {
        'ephemeral_public_key_b64': base64.b64encode(ephemeral_public_bytes).decode('ascii'),
        'nonce_b64': base64.b64encode(nonce).decode('ascii'),
        'wrapped_key_b64': base64.b64encode(wrapped).decode('ascii'),
    }
