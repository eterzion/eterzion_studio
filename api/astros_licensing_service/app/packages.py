"""Storage for built packages (Fase 4). Building (encrypting the source once)
is a separate offline step — see tools/build_package.py — this module just
persists/retrieves the result."""
from __future__ import annotations

import time

from app.db import get_conn


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
