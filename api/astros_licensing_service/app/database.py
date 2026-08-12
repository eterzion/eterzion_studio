"""SQLite persistence — deliberately simple (stdlib sqlite3, no ORM) to match
the rest of this codebase's style. If this service ever needs to scale beyond
a single instance, swap this module for a real database; nothing above this
layer (licensing.py, routes) would need to change.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS licenses (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    status TEXT NOT NULL,                  -- active | revoked | refunded
    activation_limit INTEGER NOT NULL,
    payment_provider TEXT NOT NULL,
    payment_reference TEXT NOT NULL UNIQUE,  -- idempotency: one license per transaction
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS installations (
    install_id TEXT PRIMARY KEY,
    license_id TEXT NOT NULL REFERENCES licenses(id),
    signing_public_key_b64 TEXT NOT NULL,     -- Ed25519 — verifica requisições da instalação
    encryption_public_key_b64 TEXT NOT NULL,  -- X25519 — envelopa a chave de conteúdo de pacotes (Fase 4)
    activated_at TEXT NOT NULL,
    last_seen_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_installations_license ON installations(license_id);

CREATE TABLE IF NOT EXISTS authorizations (
    id TEXT PRIMARY KEY,
    install_id TEXT NOT NULL,
    model TEXT NOT NULL,
    version TEXT NOT NULL,
    operation TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    max_uses INTEGER NOT NULL,
    uses_consumed INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_authorizations_install ON authorizations(install_id);

-- Fase 4 — pacote temporário de execução. content_key_b64 never leaves this
-- table: it's only ever served wrapped per-installation (package_crypto.py).
CREATE TABLE IF NOT EXISTS packages (
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    ciphertext_b64 TEXT NOT NULL,
    nonce_b64 TEXT NOT NULL,
    signature_b64 TEXT NOT NULL,
    content_key_b64 TEXT NOT NULL,
    built_at TEXT NOT NULL,
    PRIMARY KEY (name, version)
);
"""


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(settings.database_path), exist_ok=True)
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
