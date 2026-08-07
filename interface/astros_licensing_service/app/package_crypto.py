"""Package encryption for Fase 4 — pacote temporário de execução. Two layers:

1. Content encryption: the package bytes (the orchestration logic) are
   encrypted ONCE per build with a random content key (AES-256-GCM), and the
   ciphertext is signed with the service's Ed25519 key (service_identity.py).
   The ciphertext is the same for every installation — expensive to produce,
   cheap to serve, safe to cache.
2. Key wrapping: the 32-byte content key is envelope-encrypted PER
   INSTALLATION at request time, via X25519 ECDH with that installation's
   public key + HKDF + AES-GCM. Only that installation's private key can
   unwrap it (install_identity.py's decrypt_envelope on the client side) —
   this is what "vinculado à instalação" actually means cryptographically,
   not just an access-control check.
"""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.service_identity import get_signing_key

_HKDF_INFO = b'astros-upscale-package-key-wrap'


def build_package(source_bytes: bytes) -> dict:
    """Encrypts + signs once. Returns everything needed to serve this package
    to any number of installations (the content key is NOT included — it's
    only ever wrapped per-installation by wrap_content_key_for_install)."""
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
    # Best-effort — see protected_loader.py's matching comment on the client
    # side: dropping the reference is what CPython actually offers here, not
    # a guaranteed wipe of the underlying memory.
    del content_key, derived_key
    ephemeral_public_bytes = ephemeral_private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return {
        'ephemeral_public_key_b64': base64.b64encode(ephemeral_public_bytes).decode('ascii'),
        'nonce_b64': base64.b64encode(nonce).decode('ascii'),
        'wrapped_key_b64': base64.b64encode(wrapped).decode('ascii'),
    }
