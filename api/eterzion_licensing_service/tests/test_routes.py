"""Integration tests — exercise the real FastAPI routes end-to-end (HTTP layer
+ business logic + SQLite), not the underlying functions directly. This is
where authorization/status-code contracts and request validation live."""
from __future__ import annotations

import hashlib
import hmac
import json
import time

SECRET = 'whsec_route_test'


class TestHealthAndPublicKey:
    def test_health(self, client):
        res = client.get('/health')
        assert res.status_code == 200
        assert res.json() == {'status': 'ok'}

    def test_public_key_is_valid_base64_ed25519_key(self, client):
        import base64

        res = client.get('/public-key')
        assert res.status_code == 200
        raw = base64.b64decode(res.json()['public_key_b64'])
        assert len(raw) == 32  # Ed25519 public keys are always 32 bytes


class TestActivationRoute:
    def test_activate_succeeds_for_a_valid_license(self, client, license_factory, install_keys):
        lic = license_factory(activation_limit=2)
        res = client.post('/activations', json={
            'license_id': lic.id, 'install_id': 'install-1', **install_keys(),
        })
        assert res.status_code == 200
        assert res.json() == {'ok': True}

    def test_activate_returns_404_for_unknown_license(self, client, install_keys):
        res = client.post('/activations', json={
            'license_id': 'lic_ghost', 'install_id': 'install-1', **install_keys(),
        })
        assert res.status_code == 404

    def test_activate_returns_403_for_inactive_license(self, client, license_factory, install_keys):
        from app import licensing

        lic = license_factory()
        licensing.set_license_status(lic.id, 'revoked')
        res = client.post('/activations', json={
            'license_id': lic.id, 'install_id': 'install-1', **install_keys(),
        })
        assert res.status_code == 403

    def test_activate_returns_409_when_device_limit_reached(self, client, license_factory, install_keys):
        lic = license_factory(activation_limit=1)
        client.post('/activations', json={'license_id': lic.id, 'install_id': 'install-1', **install_keys()})
        res = client.post('/activations', json={'license_id': lic.id, 'install_id': 'install-2', **install_keys()})
        assert res.status_code == 409

    def test_activate_rejects_malformed_body(self, client):
        res = client.post('/activations', json={'license_id': 'lic_x'})  # missing required fields
        assert res.status_code == 422

    def test_release_succeeds_for_an_active_installation(self, client, license_factory, install_keys):
        lic = license_factory()
        client.post('/activations', json={'license_id': lic.id, 'install_id': 'install-1', **install_keys()})
        res = client.delete('/activations/install-1', params={'license_id': lic.id})
        assert res.status_code == 200

    def test_release_returns_404_for_unknown_installation(self, client, license_factory):
        lic = license_factory()
        res = client.delete('/activations/install-ghost', params={'license_id': lic.id})
        assert res.status_code == 404

    def test_status_returns_the_license_status_for_an_activated_installation(self, client, license_factory, install_keys):
        lic = license_factory(activation_limit=2)
        client.post('/activations', json={'license_id': lic.id, 'install_id': 'install-1', **install_keys()})
        res = client.get('/activations/install-1/status')
        assert res.status_code == 200
        assert res.json() == {
            'license_id': lic.id, 'status': 'active', 'installations_used': 1, 'installations_limit': 2,
        }

    def test_status_call_touches_last_seen_at(self, client, license_factory, install_keys):
        """T035/FR-056 — reaching the status route at all is a revalidation."""
        from app import licensing

        lic = license_factory()
        client.post('/activations', json={'license_id': lic.id, 'install_id': 'install-1', **install_keys()})
        with licensing.get_conn() as conn:
            conn.execute(
                'UPDATE installations SET last_seen_at = ? WHERE install_id = ?',
                ('2020-01-01T00:00:00Z', 'install-1'),
            )
        assert licensing.get_installation('install-1')['last_seen_at'] == '2020-01-01T00:00:00Z'

        client.get('/activations/install-1/status')
        assert licensing.get_installation('install-1')['last_seen_at'] != '2020-01-01T00:00:00Z'

    def test_status_reflects_a_revoked_license(self, client, license_factory, install_keys):
        from app import licensing

        lic = license_factory()
        client.post('/activations', json={'license_id': lic.id, 'install_id': 'install-1', **install_keys()})
        licensing.set_license_status(lic.id, 'revoked')
        res = client.get('/activations/install-1/status')
        assert res.status_code == 200
        assert res.json()['status'] == 'revoked'

    def test_status_returns_404_for_a_never_activated_installation(self, client):
        res = client.get('/activations/install-never-activated/status')
        assert res.status_code == 404


class TestAuthorizationRoute:
    def test_authorize_succeeds_for_an_activated_installation(self, client, license_factory, install_keys):
        lic = license_factory()
        client.post('/activations', json={'license_id': lic.id, 'install_id': 'install-1', **install_keys()})
        res = client.post('/authorizations', json={
            'install_id': 'install-1', 'model': 'realesrgan-x4', 'version': '1.0.0',
        })
        assert res.status_code == 200
        body = res.json()
        assert 'signature_b64' in body
        assert body['authorization']['install_id'] == 'install-1'

    def test_authorize_returns_404_for_unactivated_installation(self, client):
        res = client.post('/authorizations', json={
            'install_id': 'install-never-activated', 'model': 'm', 'version': 'v',
        })
        assert res.status_code == 404

    def test_authorize_returns_403_when_license_inactive(self, client, license_factory, install_keys):
        from app import licensing

        lic = license_factory()
        client.post('/activations', json={'license_id': lic.id, 'install_id': 'install-1', **install_keys()})
        licensing.set_license_status(lic.id, 'suspended')
        res = client.post('/authorizations', json={'install_id': 'install-1', 'model': 'm', 'version': 'v'})
        assert res.status_code == 403

    def test_redeem_succeeds_once_then_fails(self, client, license_factory, install_keys):
        lic = license_factory()
        client.post('/activations', json={'license_id': lic.id, 'install_id': 'install-1', **install_keys()})
        issued = client.post('/authorizations', json={'install_id': 'install-1', 'model': 'm', 'version': 'v'}).json()
        auth_id = issued['authorization']['id']

        first = client.post(f'/authorizations/{auth_id}/redeem')
        assert first.status_code == 200
        second = client.post(f'/authorizations/{auth_id}/redeem')
        assert second.status_code == 409

    def test_redeem_returns_409_for_unknown_authorization(self, client):
        res = client.post('/authorizations/auth_does_not_exist/redeem')
        assert res.status_code == 409


class TestStripeWebhookRoute:
    def _signed_headers(self, payload: bytes, secret: str) -> dict:
        ts = int(time.time())
        signed_payload = f'{ts}.'.encode('utf-8') + payload
        sig = hmac.new(secret.encode('utf-8'), signed_payload, hashlib.sha256).hexdigest()
        return {'stripe-signature': f't={ts},v1={sig}'}

    def _payload(self) -> bytes:
        body = {
            'type': 'checkout.session.completed',
            'data': {'object': {
                'id': 'cs_route_test', 'payment_status': 'paid',
                'customer_details': {'email': 'webhook-buyer@example.com'},
                'amount_total': 2999, 'currency': 'usd',
            }},
        }
        return json.dumps(body).encode('utf-8')

    def test_valid_webhook_creates_a_license(self, client, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, 'stripe_webhook_secret', SECRET)
        payload = self._payload()
        res = client.post('/webhooks/stripe', content=payload, headers=self._signed_headers(payload, SECRET))
        assert res.status_code == 200
        assert res.json()['ok'] is True

        from app import licensing

        lic = licensing.get_license(res.json()['license_id'])
        assert lic is not None
        assert lic.email == 'webhook-buyer@example.com'

    def test_forged_signature_is_rejected_and_creates_no_license(self, client, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, 'stripe_webhook_secret', SECRET)
        payload = self._payload()
        res = client.post(
            '/webhooks/stripe', content=payload,
            headers=self._signed_headers(payload, 'attacker-does-not-know-the-real-secret'),
        )
        assert res.status_code == 400

        from app.database import get_conn

        with get_conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM licenses WHERE payment_reference = 'cs_route_test'"
            ).fetchone()['n']
        assert count == 0

    def test_replayed_webhook_is_idempotent(self, client, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, 'stripe_webhook_secret', SECRET)
        payload = self._payload()
        headers = self._signed_headers(payload, SECRET)
        first = client.post('/webhooks/stripe', content=payload, headers=headers)
        second = client.post('/webhooks/stripe', content=payload, headers=headers)
        assert first.json()['license_id'] == second.json()['license_id']
