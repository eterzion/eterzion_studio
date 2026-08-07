"""Client of the licensing service's package endpoint (Fase 4). Fetches the
encrypted orchestration-logic package, verifies its signature, unwraps the
content key for this installation, decrypts, and executes the result in
memory — never written to disk. Opt-in: only used when
settings.licensing_service_url is set (no license infra deployed by default
today — see worker_supervisor.py/isolated_worker.py for the fallback to a
plain static import when this is empty).
"""
from __future__ import annotations

import base64
import json
import sys
import types
import urllib.error
import urllib.request

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.install_identity import InstallIdentity

# The DPAPI-backed identity this whole scheme relies on (install_identity.py)
# is Windows-only today — refuse protected loading elsewhere rather than fail
# confusingly deeper in the flow. Update this if/when another platform is
# actually supported end to end, not preemptively.
_SUPPORTED_PLATFORMS = ('win32',)


class ProtectedLoadError(Exception):
    pass


class UnsupportedRuntime(ProtectedLoadError):
    pass


def _http_get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _http_post(url: str, body: dict) -> dict:
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        detail = error.read().decode('utf-8', errors='replace')
        raise ProtectedLoadError(f'{url} -> HTTP {error.code}: {detail}') from error


def activate(base_url: str, license_id: str, identity: InstallIdentity) -> dict:
    return _http_post(f'{base_url}/activations', {
        'license_id': license_id,
        'install_id': identity.install_id,
        'signing_public_key_b64': identity.signing_public_key_b64,
        'encryption_public_key_b64': identity.encryption_public_key_b64,
    })


def _trusted_public_key(base_url: str, pinned_b64: str) -> bytes:
    if pinned_b64:
        return base64.b64decode(pinned_b64)
    # Dev-only convenience — trust-on-first-use, not safe for a shipped build.
    return base64.b64decode(_http_get(f'{base_url}/public-key')['public_key_b64'])


def load_protected_module(
    base_url: str, trusted_pubkey_b64: str, identity: InstallIdentity,
    model: str, version: str = 'latest', operation: str = 'process', package_name: str = 'orchestration-logic',
) -> types.ModuleType:
    if sys.platform not in _SUPPORTED_PLATFORMS:
        raise UnsupportedRuntime(f'Carregamento protegido não suportado em "{sys.platform}".')

    if version == 'latest':
        version = _http_get(f'{base_url}/packages/{package_name}/latest-version')['version']

    auth_resp = _http_post(f'{base_url}/authorizations', {
        'install_id': identity.install_id, 'model': model, 'version': version, 'operation': operation,
    })
    auth_id = auth_resp['authorization']['id']

    pkg = _http_get(
        f'{base_url}/packages/{package_name}?install_id={identity.install_id}&authorization_id={auth_id}'
    )

    trusted_key = Ed25519PublicKey.from_public_bytes(_trusted_public_key(base_url, trusted_pubkey_b64))
    nonce = base64.b64decode(pkg['nonce_b64'])
    ciphertext = base64.b64decode(pkg['ciphertext_b64'])
    signature = base64.b64decode(pkg['signature_b64'])
    try:
        trusted_key.verify(signature, nonce + ciphertext)
    except InvalidSignature as error:
        raise ProtectedLoadError('Assinatura do pacote inválida — recusando executar.') from error

    content_key = identity.decrypt_envelope(**pkg['key_wrap'])
    source_bytes = AESGCM(content_key).decrypt(nonce, ciphertext, None)
    # Best-effort reduction of exposure window, not a real guarantee — Python's
    # `bytes` are immutable, so this can't zero the underlying memory the way
    # the architecture doc's "apagamento criptográfico" describes for on-disk
    # keys. Dropping the reference promptly is the most CPython actually
    # offers here; the interpreter, not this code, controls when that memory
    # is actually reclaimed.
    del content_key

    module = types.ModuleType(f'astros_upscale_protected.{package_name}.{pkg["version"]}')
    code = compile(source_bytes, f'<protected:{package_name}:{pkg["version"]}>', 'exec')
    del source_bytes
    exec(code, module.__dict__)  # noqa: S102 - executes verified, decrypted-in-memory code, never written to disk
    return module
