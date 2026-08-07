"""Stripe webhook verification — implements Stripe's documented signature
scheme (HMAC-SHA256 over "{timestamp}.{raw body}", header `Stripe-Signature:
t=...,v1=...`) directly, no `stripe` SDK dependency. Verified in this session
against self-generated signatures using the exact same algorithm Stripe's
webhooks use; NOT yet exercised against a live Stripe account — plug in the
real `ASTROS_LICENSING_STRIPE_WEBHOOK_SECRET` (from the Stripe dashboard) to
go live, the verification code itself doesn't change.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time

from app.payments.base import PaymentEvent

PROVIDER = 'stripe'


def verify_and_parse(payload: bytes, signature_header: str, webhook_secret: str, tolerance_seconds: int = 300) -> PaymentEvent | None:
    if not webhook_secret or not signature_header:
        return None
    parts: dict[str, str] = {}
    for item in signature_header.split(','):
        if '=' not in item:
            continue
        key, _, value = item.partition('=')
        parts[key.strip()] = value.strip()
    timestamp = parts.get('t')
    signature = parts.get('v1')
    if not timestamp or not signature:
        return None
    try:
        ts = int(timestamp)
    except ValueError:
        return None
    if abs(time.time() - ts) > tolerance_seconds:
        return None

    signed_payload = f'{timestamp}.'.encode('utf-8') + payload
    expected = hmac.new(webhook_secret.encode('utf-8'), signed_payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None

    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if event.get('type') != 'checkout.session.completed':
        return None
    obj = event.get('data', {}).get('object', {})
    if obj.get('payment_status') != 'paid':
        return None
    email = (obj.get('customer_details') or {}).get('email') or obj.get('customer_email')
    session_id = obj.get('id')
    if not email or not session_id:
        return None
    return PaymentEvent(
        provider=PROVIDER, reference=session_id, email=email,
        amount=obj.get('amount_total'), currency=obj.get('currency'),
    )
