"""Payment provider webhook verification and normalization. Consolidates what
were `payments/base.py`, `payments/stripe_provider.py` and
`payments/mercadopago_provider.py` (Constitution Princípio XI) — preserves the
`PaymentProvider`-shaped contract (`PaymentEvent`), `StripeProvider`,
`MercadoPagoProvider` exactly.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

# ------------------------------- common event shape ------------------------------- #
#
# Common shape every payment provider adapter normalizes into — the rest of
# the service (licensing.py) only ever sees this, never a provider-specific
# payload. Swapping/adding a provider means writing one more section here, not
# touching licensing logic.


@dataclass
class PaymentEvent:
    provider: str
    reference: str  # provider's transaction/session id — used for idempotency
    email: str
    amount: int | None  # smallest currency unit (cents), when the provider reports it
    currency: str | None


# ------------------------------- Stripe ------------------------------- #
#
# Stripe webhook verification — implements Stripe's documented signature
# scheme (HMAC-SHA256 over "{timestamp}.{raw body}", header `Stripe-Signature:
# t=...,v1=...`) directly, no `stripe` SDK dependency. Verified in this session
# against self-generated signatures using the exact same algorithm Stripe's
# webhooks use; NOT yet exercised against a live Stripe account — plug in the
# real `ASTROS_LICENSING_STRIPE_WEBHOOK_SECRET` (from the Stripe dashboard) to
# go live, the verification code itself doesn't change.

STRIPE_PROVIDER = 'stripe'


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
        provider=STRIPE_PROVIDER, reference=session_id, email=email,
        amount=obj.get('amount_total'), currency=obj.get('currency'),
    )


# ------------------------------- Mercado Pago ------------------------------- #
#
# Mercado Pago webhook verification, per their documented `x-signature`
# scheme: HMAC-SHA256 over the manifest string
#     "id:{data.id};request-id:{x-request-id};ts:{ts};"
# (data.id lowercased when alphanumeric, per their docs), header format
# `x-signature: ts=<ts>,v1=<hex hmac>`.
#
# verify_signature() is fully tested in this session against self-generated
# signatures using this exact scheme. fetch_payment_details() calls Mercado
# Pago's real API to resolve a payment id into status/payer email/amount — that
# part needs a live `ASTROS_LICENSING_MERCADOPAGO_ACCESS_TOKEN` to exercise; the
# webhook only ever carries a payment id, never the payer's email itself, so
# this follow-up call is required by Mercado Pago's own design, not a choice
# made here.

MERCADOPAGO_PROVIDER = 'mercadopago'


def _parse_signature_header(header: str) -> tuple[str, str] | None:
    parts: dict[str, str] = {}
    for item in header.split(','):
        if '=' not in item:
            continue
        key, _, value = item.partition('=')
        parts[key.strip()] = value.strip()
    ts = parts.get('ts')
    v1 = parts.get('v1')
    if not ts or not v1:
        return None
    return ts, v1


def verify_signature(data_id: str, request_id: str, signature_header: str, webhook_secret: str) -> bool:
    if not webhook_secret or not signature_header:
        return False
    parsed = _parse_signature_header(signature_header)
    if parsed is None:
        return False
    ts, v1 = parsed
    normalized_id = data_id.lower() if data_id.isalnum() else data_id
    manifest = f'id:{normalized_id};request-id:{request_id};ts:{ts};'
    expected = hmac.new(webhook_secret.encode('utf-8'), manifest.encode('utf-8'), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


def fetch_payment_details(payment_id: str, access_token: str, timeout: float = 10.0) -> dict | None:
    """GET /v1/payments/{id} — requires a real access token. Not exercised
    against the live API in this session (no credentials available here)."""
    req = urllib.request.Request(
        f'https://api.mercadopago.com/v1/payments/{payment_id}',
        headers={'Authorization': f'Bearer {access_token}'},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, json.JSONDecodeError):
        return None


def to_payment_event(details: dict) -> PaymentEvent | None:
    if details.get('status') != 'approved':
        return None
    email = (details.get('payer') or {}).get('email')
    reference = str(details.get('id') or '')
    if not email or not reference:
        return None
    return PaymentEvent(
        provider=MERCADOPAGO_PROVIDER, reference=reference, email=email,
        amount=details.get('transaction_amount'), currency=details.get('currency_id'),
    )
