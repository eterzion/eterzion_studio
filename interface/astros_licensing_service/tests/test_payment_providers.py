"""Unit tests for the webhook HMAC verification schemes — this is the only
thing standing between the licensing service and someone POSTing a forged
"payment succeeded" event to mint themselves a free license. Pure functions,
no network calls."""
from __future__ import annotations

import hashlib
import hmac
import json
import time

from app.payments import mercadopago_provider, stripe_provider

SECRET = 'whsec_test_secret'


def _stripe_signed(payload: bytes, secret: str = SECRET, ts: int | None = None) -> str:
    ts = ts if ts is not None else int(time.time())
    signed_payload = f'{ts}.'.encode('utf-8') + payload
    sig = hmac.new(secret.encode('utf-8'), signed_payload, hashlib.sha256).hexdigest()
    return f't={ts},v1={sig}'


def _stripe_payload(**overrides) -> bytes:
    body = {
        'type': 'checkout.session.completed',
        'data': {
            'object': {
                'id': 'cs_test_123',
                'payment_status': 'paid',
                'customer_details': {'email': 'buyer@example.com'},
                'amount_total': 1999,
                'currency': 'usd',
            }
        },
    }
    body['data']['object'].update(overrides)
    return json.dumps(body).encode('utf-8')


class TestStripeVerification:
    def test_accepts_a_correctly_signed_payload(self):
        payload = _stripe_payload()
        header = _stripe_signed(payload)
        event = stripe_provider.verify_and_parse(payload, header, SECRET)
        assert event is not None
        assert event.reference == 'cs_test_123'
        assert event.email == 'buyer@example.com'
        assert event.amount == 1999

    def test_rejects_wrong_secret(self):
        payload = _stripe_payload()
        header = _stripe_signed(payload, secret='a-different-secret')
        assert stripe_provider.verify_and_parse(payload, header, SECRET) is None

    def test_rejects_tampered_payload(self):
        """Same signature, different body — must fail, not just log a warning."""
        payload = _stripe_payload()
        header = _stripe_signed(payload)
        tampered = _stripe_payload(amount_total=1)
        assert stripe_provider.verify_and_parse(tampered, header, SECRET) is None

    def test_rejects_missing_header(self):
        assert stripe_provider.verify_and_parse(_stripe_payload(), '', SECRET) is None

    def test_rejects_empty_webhook_secret(self):
        """A misconfigured (empty) secret must fail closed, not treat every
        request as trusted."""
        payload = _stripe_payload()
        header = _stripe_signed(payload)
        assert stripe_provider.verify_and_parse(payload, header, '') is None

    def test_rejects_stale_timestamp_replay(self):
        """A captured, correctly-signed webhook replayed an hour later must be
        rejected — the timestamp tolerance window is the only defense here."""
        payload = _stripe_payload()
        old_ts = int(time.time()) - 3600
        header = _stripe_signed(payload, ts=old_ts)
        assert stripe_provider.verify_and_parse(payload, header, SECRET) is None

    def test_rejects_malformed_header(self):
        payload = _stripe_payload()
        assert stripe_provider.verify_and_parse(payload, 'not-a-valid-header', SECRET) is None

    def test_ignores_non_checkout_event_types(self):
        body = json.dumps({'type': 'invoice.paid', 'data': {'object': {}}}).encode('utf-8')
        header = _stripe_signed(body)
        assert stripe_provider.verify_and_parse(body, header, SECRET) is None

    def test_ignores_unpaid_session(self):
        payload = _stripe_payload(payment_status='unpaid')
        header = _stripe_signed(payload)
        assert stripe_provider.verify_and_parse(payload, header, SECRET) is None

    def test_rejects_missing_email(self):
        body = {
            'type': 'checkout.session.completed',
            'data': {'object': {'id': 'cs_1', 'payment_status': 'paid'}},
        }
        payload = json.dumps(body).encode('utf-8')
        header = _stripe_signed(payload)
        assert stripe_provider.verify_and_parse(payload, header, SECRET) is None


def _mp_signed(data_id: str, request_id: str, secret: str = SECRET, ts: str | None = None) -> str:
    ts = ts or str(int(time.time()))
    normalized = data_id.lower() if data_id.isalnum() else data_id
    manifest = f'id:{normalized};request-id:{request_id};ts:{ts};'
    v1 = hmac.new(secret.encode('utf-8'), manifest.encode('utf-8'), hashlib.sha256).hexdigest()
    return f'ts={ts},v1={v1}'


class TestMercadoPagoVerification:
    def test_accepts_a_correctly_signed_payload(self):
        header = _mp_signed('12345', 'req-1')
        assert mercadopago_provider.verify_signature('12345', 'req-1', header, SECRET) is True

    def test_rejects_wrong_secret(self):
        header = _mp_signed('12345', 'req-1', secret='a-different-secret')
        assert mercadopago_provider.verify_signature('12345', 'req-1', header, SECRET) is False

    def test_rejects_tampered_data_id(self):
        header = _mp_signed('12345', 'req-1')
        assert mercadopago_provider.verify_signature('99999', 'req-1', header, SECRET) is False

    def test_rejects_tampered_request_id(self):
        header = _mp_signed('12345', 'req-1')
        assert mercadopago_provider.verify_signature('12345', 'req-DIFFERENT', header, SECRET) is False

    def test_rejects_missing_header(self):
        assert mercadopago_provider.verify_signature('12345', 'req-1', '', SECRET) is False

    def test_rejects_empty_secret(self):
        header = _mp_signed('12345', 'req-1')
        assert mercadopago_provider.verify_signature('12345', 'req-1', header, '') is False

    def test_rejects_malformed_header(self):
        assert mercadopago_provider.verify_signature('12345', 'req-1', 'garbage', SECRET) is False

    def test_to_payment_event_accepts_approved_payment(self):
        event = mercadopago_provider.to_payment_event({
            'status': 'approved', 'id': 555, 'payer': {'email': 'buyer@example.com'},
            'transaction_amount': 49.9, 'currency_id': 'BRL',
        })
        assert event is not None
        assert event.reference == '555'
        assert event.email == 'buyer@example.com'

    def test_to_payment_event_ignores_non_approved_status(self):
        event = mercadopago_provider.to_payment_event({
            'status': 'pending', 'id': 555, 'payer': {'email': 'buyer@example.com'},
        })
        assert event is None

    def test_to_payment_event_rejects_missing_email(self):
        event = mercadopago_provider.to_payment_event({'status': 'approved', 'id': 555, 'payer': {}})
        assert event is None
