"""Short-lived, signed processing authorizations (§3 Fase 3 / §4.2 do
documento de arquitetura). Checked against an installation's license status at
issuance time — not metered per job, just gatekeeping (§0.2). Anti-replay is
enforced by uses_consumed vs max_uses, checked atomically at redeem time.
"""
from __future__ import annotations

import json
import time
import uuid

from app.db import get_conn
from app.licensing import LicenseNotActive, installation_license
from app.packages import latest_version
from app.service_identity import get_signing_key

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
    import base64
    return {'authorization': payload, 'signature_b64': base64.b64encode(signature).decode('ascii')}


def get_authorization(auth_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute('SELECT * FROM authorizations WHERE id = ?', (auth_id,)).fetchone()
    return dict(row) if row is not None else None


def redeem_for_install(auth_id: str, install_id: str) -> dict | None:
    """Same atomic consume as redeem_authorization(), plus an ownership check
    (an authorization issued for one installation can't be redeemed by
    another) — used by routes_packages.py so lookup+ownership+consume happens
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
