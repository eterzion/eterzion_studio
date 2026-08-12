"""Core licensing logic — license creation from a payment event, activation
with a per-license seat limit (not per-image/job, per docs/processing-
protection-architecture.md §0.2), and revocation. No usage metering anywhere
in this module by design.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from app.config import settings
from app.db import get_conn
from app.payments.base import PaymentEvent


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
