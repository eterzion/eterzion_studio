"""The service's own signing identity, core licensing logic (creation from a
payment event, activation with a per-license seat limit, revocation), and
short-lived signed processing authorizations. Consolidates what were
`licensing.py`, `authorizations.py` and `service_identity.py` (Constitution
Princípio XI) — activation, authorization, identity and license rules stay
logically distinct below, only the file boundary moved.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

from app.config import settings
from app.database import get_conn
from app.payments import PaymentEvent

# ------------------------------- service identity ------------------------------- #
#
# The licensing service's own signing key — used to sign authorizations
# issued to installations (§4.2 of the architecture doc). Separate from, and
# never shared with, an installation's identity (astros_upscale_api's
# app.security) — this key belongs to the server, not to any one user's
# machine.
#
# This is a server-side secret, not a desktop-user secret, so it's protected
# here by plain file permissions (chmod 600 / a best-effort Windows ACL
# restriction), not DPAPI — DPAPI is scoped to a Windows user profile, which
# doesn't map to how a server process runs. In a real deployment this file
# should be backed by a proper secrets manager/KMS instead of bare disk storage;
# this local implementation is a reasonable default for self-hosting on a single
# box, not a substitute for one.


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


_cached_signing_key: Ed25519PrivateKey | None = None


def get_signing_key() -> Ed25519PrivateKey:
    global _cached_signing_key
    if _cached_signing_key is None:
        _cached_signing_key = _load_or_generate()
    return _cached_signing_key


def get_public_key_b64() -> str:
    raw = get_signing_key().public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(raw).decode('ascii')


# ------------------------------- core licensing ------------------------------- #
#
# Core licensing logic — license creation from a payment event, activation
# with a per-license seat limit (not per-image/job, per docs/processing-
# protection-architecture.md §0.2), and revocation. No usage metering anywhere
# in this section by design.


def _now_iso() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


class LicenseError(Exception):
    pass


class ActivationLimitReached(LicenseError):
    pass


class LicenseNotActive(LicenseError):
    pass


@dataclass
class License:
    id: str
    email: str
    status: str
    activation_limit: int
    payment_provider: str
    payment_reference: str


def create_license_from_payment(event: PaymentEvent, activation_limit: int | None = None) -> License:
    """Idempotent on payment_reference — a webhook retried by the provider
    (Stripe/Mercado Pago both retry on non-2xx) must not mint a second license
    for the same purchase."""
    with get_conn() as conn:
        existing = conn.execute(
            'SELECT * FROM licenses WHERE payment_reference = ?', (event.reference,)
        ).fetchone()
        if existing:
            return License(
                id=existing['id'], email=existing['email'], status=existing['status'],
                activation_limit=existing['activation_limit'], payment_provider=existing['payment_provider'],
                payment_reference=existing['payment_reference'],
            )
        license_id = f'lic_{uuid.uuid4().hex[:12]}'
        limit = activation_limit if activation_limit is not None else settings.default_activation_limit
        now = _now_iso()
        conn.execute(
            'INSERT INTO licenses (id, email, status, activation_limit, payment_provider, payment_reference, created_at, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (license_id, event.email, 'active', limit, event.provider, event.reference, now, now),
        )
        return License(
            id=license_id, email=event.email, status='active', activation_limit=limit,
            payment_provider=event.provider, payment_reference=event.reference,
        )


def get_license(license_id: str) -> License | None:
    with get_conn() as conn:
        row = conn.execute('SELECT * FROM licenses WHERE id = ?', (license_id,)).fetchone()
    if row is None:
        return None
    return License(
        id=row['id'], email=row['email'], status=row['status'], activation_limit=row['activation_limit'],
        payment_provider=row['payment_provider'], payment_reference=row['payment_reference'],
    )


def set_license_status(license_id: str, status: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            'UPDATE licenses SET status = ?, updated_at = ? WHERE id = ?', (status, _now_iso(), license_id)
        )
        return cur.rowcount > 0


def activate_installation(license_id: str, install_id: str, signing_public_key_b64: str, encryption_public_key_b64: str) -> None:
    with get_conn() as conn:
        license_row = conn.execute('SELECT * FROM licenses WHERE id = ?', (license_id,)).fetchone()
        if license_row is None:
            raise LicenseError('Licença não encontrada.')
        if license_row['status'] != 'active':
            raise LicenseNotActive(f"Licença está '{license_row['status']}', não ativa.")

        existing = conn.execute(
            'SELECT license_id FROM installations WHERE install_id = ?', (install_id,)
        ).fetchone()
        if existing is not None and existing['license_id'] == license_id:
            conn.execute('UPDATE installations SET last_seen_at = ? WHERE install_id = ?', (_now_iso(), install_id))
            return

        count = conn.execute(
            'SELECT COUNT(*) AS n FROM installations WHERE license_id = ?', (license_id,)
        ).fetchone()['n']
        if count >= license_row['activation_limit']:
            raise ActivationLimitReached(
                f"Limite de {license_row['activation_limit']} instalação(ões) simultânea(s) já atingido para esta licença."
            )
        # install_id is the table's primary key — if this installation was
        # previously tied to a DIFFERENT license (e.g. an earlier license that
        # got revoked/refunded, or the user switched), re-activating under a
        # new license replaces that old association rather than erroring.
        # Found as a real bug during manual testing: INSERT alone hit a
        # UNIQUE/PRIMARY KEY violation here instead of migrating cleanly.
        now = _now_iso()
        conn.execute(
            'INSERT OR REPLACE INTO installations (install_id, license_id, signing_public_key_b64, encryption_public_key_b64, activated_at, last_seen_at) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (install_id, license_id, signing_public_key_b64, encryption_public_key_b64, now, now),
        )


def release_installation(license_id: str, install_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            'DELETE FROM installations WHERE install_id = ? AND license_id = ?', (install_id, license_id)
        )
        return cur.rowcount > 0


def touch_installation(install_id: str) -> bool:
    """Records a successful reachable check-in (T035/FR-056) — every time a
    client can reach this service at all, its offline clock resets. Called by
    GET /activations/{install_id}/status, which the local license gate (T016)
    already calls on every job creation."""
    with get_conn() as conn:
        cur = conn.execute(
            'UPDATE installations SET last_seen_at = ? WHERE install_id = ?', (_now_iso(), install_id)
        )
        return cur.rowcount > 0


def get_installation(install_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute('SELECT * FROM installations WHERE install_id = ?', (install_id,)).fetchone()
    return dict(row) if row is not None else None


def list_installations(license_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            'SELECT install_id, activated_at, last_seen_at FROM installations WHERE license_id = ?', (license_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def installation_license(install_id: str) -> License | None:
    """Looks up the (single) license an installation is currently activated
    against — used by issue_authorization() to check status without the
    caller having to already know the license id."""
    with get_conn() as conn:
        row = conn.execute(
            'SELECT l.* FROM licenses l JOIN installations i ON i.license_id = l.id WHERE i.install_id = ?',
            (install_id,),
        ).fetchone()
    if row is None:
        return None
    return License(
        id=row['id'], email=row['email'], status=row['status'], activation_limit=row['activation_limit'],
        payment_provider=row['payment_provider'], payment_reference=row['payment_reference'],
    )


# ------------------------------- authorizations ------------------------------- #
#
# Short-lived, signed processing authorizations (§3 Fase 3 / §4.2 do
# documento de arquitetura). Checked against an installation's license status at
# issuance time — not metered per job, just gatekeeping (§0.2). Anti-replay is
# enforced by uses_consumed vs max_uses, checked atomically at redeem time.

DEFAULT_TTL_SECONDS = 300

# The only package this service currently builds/serves (Fase 4). A real
# multi-package future would need a real model/operation -> package-name
# lookup instead of this constant; not worth building ahead of having a
# second package to route to.
_ORCHESTRATION_PACKAGE_NAME = 'orchestration-logic'


class AuthorizationError(Exception):
    pass


class VersionRejected(AuthorizationError):
    """Anti-rollback: refuses to authorize a version other than the current
    latest — otherwise a client could request an authorization for an old,
    still-validly-signed package build, sidestepping whatever a newer version
    fixed. Found and closed during this session's own testing, not a
    theoretical concern."""


def _now() -> float:
    return time.time()


def _iso(ts: float) -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(ts))


def _canonical_payload(auth: dict) -> bytes:
    return json.dumps(auth, sort_keys=True, separators=(',', ':')).encode('utf-8')


def issue_authorization(install_id: str, model: str, version: str, operation: str, ttl_seconds: int = DEFAULT_TTL_SECONDS, max_uses: int = 1) -> dict:
    from app.packages import latest_version

    license_ = installation_license(install_id)
    if license_ is None:
        raise AuthorizationError('Instalação não está ativada em nenhuma licença.')
    if license_.status != 'active':
        raise LicenseNotActive(f"Licença está '{license_.status}', não ativa.")

    if operation == 'process':
        current = latest_version(_ORCHESTRATION_PACKAGE_NAME)
        if current is not None and version != current:
            raise VersionRejected(
                f"Versão '{version}' desatualizada — a versão atual é '{current}'. Atualize o aplicativo."
            )

    auth_id = f'auth_{uuid.uuid4().hex}'
    issued_at = _now()
    expires_at = issued_at + ttl_seconds
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO authorizations (id, install_id, model, version, operation, issued_at, expires_at, max_uses) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (auth_id, install_id, model, version, operation, _iso(issued_at), _iso(expires_at), max_uses),
        )

    payload = {
        'id': auth_id, 'install_id': install_id, 'model': model, 'version': version,
        'operation': operation, 'issued_at': _iso(issued_at), 'expires_at': _iso(expires_at), 'max_uses': max_uses,
    }
    signature = get_signing_key().sign(_canonical_payload(payload))
    return {'authorization': payload, 'signature_b64': base64.b64encode(signature).decode('ascii')}


def get_authorization(auth_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute('SELECT * FROM authorizations WHERE id = ?', (auth_id,)).fetchone()
    return dict(row) if row is not None else None


def redeem_for_install(auth_id: str, install_id: str) -> dict | None:
    """Same atomic consume as redeem_authorization(), plus an ownership check
    (an authorization issued for one installation can't be redeemed by
    another) — used by the packages route so lookup+ownership+consume happens
    as a single transaction, not a check-then-act race."""
    with get_conn() as conn:
        row = conn.execute('SELECT * FROM authorizations WHERE id = ?', (auth_id,)).fetchone()
        if row is None or row['install_id'] != install_id:
            return None
        expires_at = time.strptime(row['expires_at'], '%Y-%m-%dT%H:%M:%SZ')
        if time.gmtime() > expires_at or row['uses_consumed'] >= row['max_uses']:
            return None
        cur = conn.execute(
            'UPDATE authorizations SET uses_consumed = uses_consumed + 1 WHERE id = ? AND uses_consumed < max_uses',
            (auth_id,),
        )
        if cur.rowcount == 0:
            return None
        return dict(row)


def redeem_authorization(auth_id: str) -> bool:
    """Atomically consumes one use. Returns False if the authorization is
    unknown, expired, or already at its use limit (replay)."""
    with get_conn() as conn:
        row = conn.execute('SELECT * FROM authorizations WHERE id = ?', (auth_id,)).fetchone()
        if row is None:
            return False
        expires_at = time.strptime(row['expires_at'], '%Y-%m-%dT%H:%M:%SZ')
        if time.gmtime() > expires_at:
            return False
        if row['uses_consumed'] >= row['max_uses']:
            return False
        cur = conn.execute(
            'UPDATE authorizations SET uses_consumed = uses_consumed + 1 '
            'WHERE id = ? AND uses_consumed < max_uses',
            (auth_id,),
        )
        return cur.rowcount > 0
