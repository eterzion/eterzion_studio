"""HTTP-layer tests for routes_identity.py — GET /identity. The real security
property that matters here: the endpoint must NEVER expose private key
material, only the install id and public keys."""
from __future__ import annotations

import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_identity


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes_identity.router, prefix='/identity')
    return TestClient(app)


class TestGetIdentity:
    def test_returns_install_id_and_public_keys(self, client):
        res = client.get('/identity')
        assert res.status_code == 200
        body = res.json()
        assert body['install_id']
        assert len(base64.b64decode(body['signing_public_key_b64'])) == 32
        assert len(base64.b64decode(body['encryption_public_key_b64'])) == 32

    def test_never_exposes_private_key_material(self, client):
        body = client.get('/identity').json()
        assert set(body.keys()) == {'install_id', 'signing_public_key_b64', 'encryption_public_key_b64'}
        assert 'signing_private_key_protected_b64' not in body
        assert 'encryption_private_key_protected_b64' not in body
        assert 'private' not in str(body).lower()

    def test_is_idempotent_across_requests(self, client):
        first = client.get('/identity').json()
        second = client.get('/identity').json()
        assert first == second
