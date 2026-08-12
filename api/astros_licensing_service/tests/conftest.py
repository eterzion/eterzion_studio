"""Test isolation strategy: `app.config.settings` is a module-level singleton
(pydantic BaseSettings), but its fields are plain mutable attributes — so each
test points `settings.database_path` / `settings.identity_dir` at a fresh
temp directory and calls `db.init_db()` for a clean schema, instead of
depending on any shared file. No test depends on execution order or leaves
state for the next one.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app import licensing as service_identity
from app.config import settings
from app.database import init_db


@pytest.fixture(autouse=True)
def isolated_service_storage(tmp_path, monkeypatch):
    """Runs for every test: fresh SQLite DB + fresh signing-key directory,
    and clears service_identity's in-process key cache so a key generated
    for a previous test's identity_dir is never reused."""
    db_path = tmp_path / 'licensing.db'
    identity_dir = tmp_path / 'identity'
    monkeypatch.setattr(settings, 'database_path', str(db_path))
    monkeypatch.setattr(settings, 'identity_dir', str(identity_dir))
    monkeypatch.setattr(service_identity, '_cached_signing_key', None)
    init_db()
    yield
    monkeypatch.setattr(service_identity, '_cached_signing_key', None)


@pytest.fixture
def make_payment_event():
    from app.payments import PaymentEvent

    counter = {'n': 0}

    def _make(**overrides):
        counter['n'] += 1
        defaults = dict(
            provider='stripe',
            reference=f'txn_test_{counter["n"]}',
            email='buyer@example.com',
            amount=9990,
            currency='usd',
        )
        defaults.update(overrides)
        return PaymentEvent(**defaults)

    return _make


@pytest.fixture
def license_factory(make_payment_event):
    """Creates a real, active license through the same code path production
    webhooks use (create_license_from_payment) — no direct INSERTs that could
    drift from what the app actually does."""
    from app import licensing

    def _make(activation_limit: int | None = None, **payment_overrides):
        event = make_payment_event(**payment_overrides)
        return licensing.create_license_from_payment(event, activation_limit=activation_limit)

    return _make


@pytest.fixture
def install_keys():
    """A real Ed25519/X25519 keypair (a stand-in for what install_identity.py
    generates client-side) — used wherever a test needs to activate an
    installation with plausible-looking, real-format public keys."""
    import base64

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    def _make():
        signing = Ed25519PrivateKey.generate()
        encryption = X25519PrivateKey.generate()
        return {
            'signing_public_key_b64': base64.b64encode(
                signing.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
            ).decode('ascii'),
            'encryption_public_key_b64': base64.b64encode(
                encryption.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
            ).decode('ascii'),
        }

    return _make


@pytest.fixture
def client(isolated_service_storage):
    """FastAPI TestClient — used as a context manager so startup/shutdown
    events fire (in particular app.main's `init_db()` on startup), matching
    real process behavior instead of bypassing it. Explicitly depends on
    isolated_service_storage (rather than relying on autouse ordering) so the
    app always starts up against the test's temp DB/identity dir."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
