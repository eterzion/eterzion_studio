"""Per-installation cryptographic identity, DPAPI-backed secret storage, private
scratch directories, self-integrity verification, and the protected package
loader (licensing-service client). Consolidates what were `protected_loader.py`,
`secure_tempdir.py`, `integrity.py`, `dpapi.py` and `install_identity.py`
(Constitution Princípio XI) — none of these mechanisms is weakened by the move.
"""
from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import types
import urllib.error
import urllib.request
import uuid
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path

from eterzion_upscale import __version__
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

# ------------------------------- dpapi ------------------------------- #
#
# Thin ctypes wrapper around Windows DPAPI (crypt32.dll's CryptProtectData /
# CryptUnprotectData) — no pywin32 dependency needed for this.
#
# DPAPI ties the encrypted blob to the current Windows user profile: only the
# same user account on the same machine can decrypt it (no password/key of ours
# to manage or leak). Used below (install identity) to keep the installation's
# private key unreadable at rest without ever sending it anywhere — see
# docs/processing-protection-architecture.md, Fase 2.

if sys.platform == 'win32':
    _crypt32 = ctypes.windll.crypt32
    _kernel32 = ctypes.windll.kernel32

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

    _crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB), wintypes.LPCWSTR, ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_DATA_BLOB),
    ]
    _crypt32.CryptProtectData.restype = wintypes.BOOL
    _crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_DATA_BLOB),
    ]
    _crypt32.CryptUnprotectData.restype = wintypes.BOOL
    _kernel32.LocalFree.argtypes = [ctypes.c_void_p]

    _CRYPTPROTECT_UI_FORBIDDEN = 0x1

    def _to_blob(data: bytes) -> tuple[_DATA_BLOB, ctypes.Array]:
        buf = ctypes.create_string_buffer(data, len(data))
        blob = _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
        return blob, buf  # caller must keep buf alive for the call's duration

    def _from_blob(blob: _DATA_BLOB) -> bytes:
        try:
            return ctypes.string_at(blob.pbData, blob.cbData)
        finally:
            _kernel32.LocalFree(blob.pbData)

    def dpapi_protect(data: bytes, entropy: bytes | None = None) -> bytes:
        """Encrypts data for the current Windows user only."""
        blob_in, buf_in = _to_blob(data)
        blob_out = _DATA_BLOB()
        entropy_blob = entropy_buf = None
        entropy_ptr = None
        if entropy is not None:
            entropy_blob, entropy_buf = _to_blob(entropy)
            entropy_ptr = ctypes.byref(entropy_blob)
        ok = _crypt32.CryptProtectData(
            ctypes.byref(blob_in), None, entropy_ptr, None, None,
            _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out),
        )
        if not ok:
            raise OSError(f'CryptProtectData falhou: {ctypes.get_last_error()}')
        return _from_blob(blob_out)

    def dpapi_unprotect(data: bytes, entropy: bytes | None = None) -> bytes:
        """Decrypts data previously encrypted by dpapi_protect() under the same user."""
        blob_in, buf_in = _to_blob(data)
        blob_out = _DATA_BLOB()
        entropy_blob = entropy_buf = None
        entropy_ptr = None
        if entropy is not None:
            entropy_blob, entropy_buf = _to_blob(entropy)
            entropy_ptr = ctypes.byref(entropy_blob)
        ok = _crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, entropy_ptr, None, None,
            _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out),
        )
        if not ok:
            raise OSError(f'CryptUnprotectData falhou: {ctypes.get_last_error()}')
        return _from_blob(blob_out)

else:
    def dpapi_protect(data: bytes, entropy: bytes | None = None) -> bytes:  # noqa: ARG001
        raise NotImplementedError('DPAPI só existe no Windows.')

    def dpapi_unprotect(data: bytes, entropy: bytes | None = None) -> bytes:  # noqa: ARG001
        raise NotImplementedError('DPAPI só existe no Windows.')


def dpapi_is_available() -> bool:
    return sys.platform == 'win32'


# ------------------------------- secure tempdir ------------------------------- #
#
# Private scratch directories for the isolated worker (Fase 1 — isolamento de
# processo). Each directory gets a random, unguessable name and, on Windows, an
# ACL restricted to the current user only (inheritance stripped, no group/Everyone
# grant). Not a substitute for real sandboxing (Job Objects/AppContainer are a
# Fase 5/6 concern) — this only keeps casual/other-user access off artifacts that
# briefly touch disk.

_ROOT_DIRNAME = 'eterzion-studio-worker'


def _base_root() -> str:
    """%LOCALAPPDATA%\\Temp on Windows (per-user already), a generic temp dir
    elsewhere — always under a private, user-owned parent, never a shared
    system-wide temp root."""
    base = os.environ.get('LOCALAPPDATA') or os.environ.get('TEMP') or os.environ.get('TMP')
    if not base:
        import tempfile
        base = tempfile.gettempdir()
    root = os.path.join(base, _ROOT_DIRNAME)
    os.makedirs(root, exist_ok=True)
    return root


def restrict_to_current_user(path: str) -> None:
    """Strip inherited permissions and grant full control only to the current
    user. Best-effort: a failure here shouldn't crash the caller, it just means
    the directory keeps default (less restrictive) permissions. Shared by every
    private, per-user directory this module creates."""
    if sys.platform != 'win32':
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass
        return
    username = os.environ.get('USERNAME')
    domain = os.environ.get('USERDOMAIN')
    account = f'{domain}\\{username}' if domain and username else username
    if not account:
        return
    try:
        subprocess.run(
            ['icacls', path, '/inheritance:r', '/grant:r', f'{account}:(OI)(CI)F'],
            capture_output=True, timeout=10, check=False, shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def create_private_dir() -> str:
    """Creates and returns a fresh, randomly-named, ACL-restricted directory."""
    root = _base_root()
    name = uuid.uuid4().hex
    path = os.path.join(root, name)
    os.makedirs(path, exist_ok=False)
    restrict_to_current_user(path)
    return path


def remove_dir(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)


def cleanup_stale(max_age_seconds: int = 24 * 60 * 60) -> int:
    """Removes leftover directories from crashed/killed previous runs. Meant to
    run once at API startup. Returns how many were removed."""
    root = _base_root()
    removed = 0
    now = time.time()
    try:
        entries = os.listdir(root)
    except OSError:
        return 0
    for name in entries:
        path = os.path.join(root, name)
        try:
            age = now - os.path.getmtime(path)
        except OSError:
            continue
        if age >= max_age_seconds or _is_locked_stale(path):
            remove_dir(path)
            removed += 1
    return removed


def _is_locked_stale(path: str) -> bool:
    """A leftover directory containing a pidfile whose process no longer exists
    is stale regardless of age — it's a crash residue, not a live job."""
    pidfile = os.path.join(path, 'worker.pid')
    if not os.path.isfile(pidfile):
        return False
    try:
        with open(pidfile, encoding='utf-8') as fh:
            pid = int(fh.read().strip())
    except (OSError, ValueError):
        return True
    return not _pid_alive(pid)


def _pid_alive(pid: int) -> bool:
    if sys.platform != 'win32':
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    try:
        result = subprocess.run(
            ['tasklist', '/FI', f'PID eq {pid}'], capture_output=True, timeout=5, text=True, check=False,
        )
        return str(pid) in result.stdout
    except (OSError, subprocess.SubprocessError):
        return True  # unknown -> assume alive, don't delete a possibly-live job's dir


# ------------------------------- install identity ------------------------------- #
#
# Per-installation cryptographic identity (Fase 2 — identidade criptográfica
# por instalação, docs/processing-protection-architecture.md).
#
# Generated once, on first run. Two keypairs, both never leaving the machine as
# private material:
# - Ed25519 (signing) — proves "this specific installation" made a request
#   (e.g. an activation or authorization request).
# - X25519 (key exchange) — lets the licensing service (Fase 3) envelope-encrypt
#   a package's content key specifically for this installation (Fase 4): only
#   this installation's private key can unwrap it, so a package copied to
#   another machine is useless there. Ed25519 alone can't do this — a signing
#   key doesn't double as an encryption key.
#
# At rest, both private keys are protected by Windows DPAPI (tied to the current
# Windows user profile), never written to disk in the clear. TPM-backed
# protection, where available, is a Fase 6 enhancement layered on top of this,
# not a prerequisite for it.

# ---------------------------------------------------------------------------
# ATENÇÃO — os identificadores abaixo NÃO são o nome do produto.
#
# O produto passou a se chamar Eterzion Studio, e estas quatro cadeias
# continuaram "astros-upscale"/"AstrosUpscale" de propósito:
#
# - `_DIRNAME` é a pasta onde o `identity.json` desta instalação já está
#   gravado. Renomear órfã a identidade de toda máquina instalada.
# - `_HKDF_INFO` é separação de domínio na derivação da chave que abre os
#   pacotes, e o **mesmo valor** vive em
#   `eterzion_licensing_service/app/packages.py`, num serviço já implantado. As
#   duas pontas têm de bater.
# - `astros-upscale-install-signing` e `-install-encryption` são a entropia do
#   DPAPI. Mudá-las torna indecifrável todo `identity.json` já escrito — cada
#   máquina perde a identidade e precisa reativar.
#
# Trocá-las é uma migração de protocolo com as duas pontas coordenadas, não uma
# renomeação. Se um dia isso for feito, tem de vir com caminho de migração.
# ---------------------------------------------------------------------------
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
        for this installation's X25519 public key (see the licensing service's
        packages module). Only this installation's private key can do this —
        the whole point of Fase 4's "vinculado à instalação"."""
        eph_pub = X25519PublicKey.from_public_bytes(base64.b64decode(ephemeral_public_key_b64))
        shared = self._encryption_key.exchange(eph_pub)
        derived_key = HKDF(algorithm=SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(shared)
        del shared  # best-effort — see load_protected_module() below for the caveat on what this actually buys
        nonce = base64.b64decode(nonce_b64)
        wrapped = base64.b64decode(wrapped_key_b64)
        try:
            return AESGCM(derived_key).decrypt(nonce, wrapped, None)
        finally:
            del derived_key


def verify_signature(public_key_bytes: bytes, data: bytes, signature: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(signature, data)
        return True
    except InvalidSignature:
        return False


def _protect(raw: bytes, entropy: bytes) -> bytes:
    if dpapi_is_available():
        return dpapi_protect(raw, entropy=entropy)
    return raw  # non-Windows fallback (dev only) — weaker than DPAPI, documented as such


def _unprotect(blob: bytes, entropy: bytes) -> bytes:
    if dpapi_is_available():
        return dpapi_unprotect(blob, entropy=entropy)
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
        'protected_with': 'dpapi' if dpapi_is_available() else 'none',
    }
    identity_dir = _identity_dir()
    restrict_to_current_user(identity_dir)
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


_cached_identity: InstallIdentity | None = None


def ensure_identity() -> InstallIdentity:
    """Idempotent: loads the existing installation identity, or generates one
    on first run. Safe to call on every API startup."""
    global _cached_identity
    if _cached_identity is not None:
        return _cached_identity
    identity = _load_existing() or _generate_and_persist()
    _cached_identity = identity
    return identity


# ------------------------------- protected package loader ------------------------------- #
#
# Client of the licensing service's package endpoint (Fase 4). Fetches the
# encrypted orchestration-logic package, verifies its signature, unwraps the
# content key for this installation, decrypts, and executes the result in
# memory — never written to disk. Opt-in: only used when
# settings.licensing_service_url is set (no license infra deployed by default
# today — see jobs.py for the fallback to a plain static import when this is
# empty).

# The DPAPI-backed identity this whole scheme relies on (InstallIdentity above)
# is Windows-only today — refuse protected loading elsewhere rather than fail
# confusingly deeper in the flow. Update this if/when another platform is
# actually supported end to end, not preemptively.
_SUPPORTED_PLATFORMS = ('win32',)


class ProtectedLoadError(Exception):
    """Falha ao falar com o serviço de licenciamento.

    `status` guarda o código HTTP quando o serviço RESPONDEU. Ele existe para
    separar "a licença não existe" (404, decisão do serviço) de "não deu para
    falar com o serviço" (timeout, DNS, 5xx). Sem isso, quem trata o erro só
    tem a mensagem, e um ID digitado errado chegava ao usuário como falha de
    infraestrutura pedindo para checar a conexão de internet.

    `None` quando não houve resposta alguma.
    """

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class UnsupportedRuntime(ProtectedLoadError):
    pass


_HTTP_HEADERS = {
    'Accept': 'application/json',
    'User-Agent': f'EterzionStudio/{__version__}',
}


def _http_get(url: str) -> dict:
    req = urllib.request.Request(url, headers=_HTTP_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _http_post(url: str, body: dict) -> dict:
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={**_HTTP_HEADERS, 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        detail = error.read().decode('utf-8', errors='replace')
        raise ProtectedLoadError(f'{url} -> HTTP {error.code}: {detail}', error.code) from error


def installation_status(base_url: str, install_id: str) -> dict:
    """T036 — the same GET .../status endpoint the licensing check uses, exposed
    here for the license route's release flow, which needs the license_id
    tied to this installation (check_gate()'s GateResult doesn't carry it)."""
    return _http_get(f'{base_url}/activations/{install_id}/status')


def activate(base_url: str, license_id: str, identity: InstallIdentity) -> dict:
    return _http_post(f'{base_url}/activations', {
        'license_id': license_id,
        'install_id': identity.install_id,
        'signing_public_key_b64': identity.signing_public_key_b64,
        'encryption_public_key_b64': identity.encryption_public_key_b64,
    })


def release(base_url: str, license_id: str, install_id: str) -> dict:
    """T036 — releases this installation's seat (FR-054)."""
    req = urllib.request.Request(
        f'{base_url}/activations/{install_id}?license_id={license_id}',
        headers={**_HTTP_HEADERS, 'Content-Type': 'application/json'}, method='DELETE',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        detail = error.read().decode('utf-8', errors='replace')
        raise ProtectedLoadError(f'{base_url} -> HTTP {error.code}: {detail}', error.code) from error


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

    module = types.ModuleType(f'eterzion_upscale_protected.{package_name}.{pkg["version"]}')
    code = compile(source_bytes, f'<protected:{package_name}:{pkg["version"]}>', 'exec')
    del source_bytes
    exec(code, module.__dict__)  # noqa: S102 - executes verified, decrypted-in-memory code, never written to disk
    return module


# ------------------------------- self-integrity check ------------------------------- #
#
# Self-integrity check for the isolated worker's own shipped code (Fase 5 —
# proteção em runtime e anti-adulteração). The package signature (Fase 4)
# protects content fetched at runtime from the licensing service; it says
# nothing about whether the FILES ALREADY ON DISK — this module, jobs.py's IPC
# handling, this file's own identity code — have been tampered with locally
# before the worker even starts. This closes that gap for the files that matter
# most: anything that decides what to trust or how to load it.
#
# The manifest (integrity_manifest.json) pins expected SHA-256 hashes. Run this
# module directly to (re)generate it after an intentional code change — same
# idea as a lockfile, not something meant to auto-update silently.
#
# Honest limits, stated plainly rather than glossed over:
# - This only checks files on disk at worker startup. It can't detect in-memory
#   patching after the process is already running (a debugger attached to a
#   live process bypasses this entirely, as it does most local anti-tamper
#   measures — see the architecture doc's "Regra de arquitetura").
# - This module checking itself is a well-known weak point of any local
#   self-verification scheme: a sufficiently capable attacker can edit this
#   file to make verify() always return True. Including this file in its own
#   manifest (below) doesn't eliminate that, but it does mean a naive
#   edit-the-target-file tamper attempt gets caught, which is most of the real
#   threat this defends against. A hard guarantee here would require OS-level
#   code signing of a real compiled executable, which is the same "native
#   compilation" gap already noted as future work in Fase 4.

_APP_DIR = Path(__file__).resolve().parent
_MANIFEST_PATH = _APP_DIR / 'integrity_manifest.json'

# The files that decide what this process trusts or executes. After the
# Constitution Princípio XI consolidation these are the three domain modules
# that used to be the 17 separate app/core/ files this manifest originally
# pinned (upscaler.py, video_upscaler.py, audio_processor.py, capacity.py,
# component_manager.py -> processing.py; job_manager.py, worker_supervisor.py,
# isolated_worker.py -> jobs.py; protected_loader.py, install_identity.py,
# secure_tempdir.py, dpapi.py, integrity.py -> security.py, this file).
PROTECTED_FILES = (
    'processing.py',
    'jobs.py',
    'security.py',
)


def _hash_file(path: Path) -> str:
    """Hash the file's CONTENT, with line endings normalised first.

    Hashing raw bytes made the manifest depend on how git happened to
    materialise the file rather than on what the file says. With
    core.autocrlf=true -- the Windows default -- the repository stores LF and
    the working copy gets CRLF, so a manifest generated on one checkout fails
    to verify on another, and a fresh clone can refuse to start the worker
    with nobody having touched a line of code. That is a false positive on a
    check whose whole job is to be trusted, and a false positive here is not
    a warning: the worker fails closed and every job dies at startup.

    Normalising costs nothing in what this defends against. The threat is
    someone editing code to change what it does; swapping CRLF for LF changes
    no behaviour, and any real tamper still lands on different content.
    """
    normalised = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(normalised).hexdigest()


def compute_hashes() -> dict[str, str]:
    return {name: _hash_file(_APP_DIR / name) for name in PROTECTED_FILES if (_APP_DIR / name).is_file()}


def generate_manifest() -> dict[str, str]:
    hashes = compute_hashes()
    _MANIFEST_PATH.write_text(json.dumps(hashes, indent=2, sort_keys=True), encoding='utf-8')
    return hashes


def _load_manifest() -> dict[str, str] | None:
    if not _MANIFEST_PATH.is_file():
        return None
    try:
        return json.loads(_MANIFEST_PATH.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None


def verify_integrity() -> tuple[bool, list[str]]:
    """Returns (ok, problems). problems lists which files are missing,
    modified, or unexpectedly present relative to the pinned manifest."""
    manifest = _load_manifest()
    if manifest is None:
        return False, ['integrity_manifest.json ausente ou ilegível']
    current = compute_hashes()
    problems: list[str] = []
    for name, expected_hash in manifest.items():
        actual_hash = current.get(name)
        if actual_hash is None:
            problems.append(f'{name}: ausente')
        elif actual_hash != expected_hash:
            problems.append(f'{name}: hash não confere (modificado)')
    for name in current:
        if name not in manifest:
            problems.append(f'{name}: presente mas não está no manifesto')
    return not problems, problems


if __name__ == '__main__':
    if '--verify' in sys.argv:
        ok, problems = verify_integrity()
        if ok:
            print('OK — todos os arquivos protegidos conferem com o manifesto.')
            sys.exit(0)
        print('FALHA de integridade:', file=sys.stderr)
        for problem in problems:
            print(f'  - {problem}', file=sys.stderr)
        sys.exit(1)
    hashes = generate_manifest()
    print(f'Manifesto gerado em {_MANIFEST_PATH} com {len(hashes)} arquivo(s).')
