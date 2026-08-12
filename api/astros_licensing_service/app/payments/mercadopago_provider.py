"""Mercado Pago webhook verification, per their documented `x-signature`
scheme: HMAC-SHA256 over the manifest string
    "id:{data.id};request-id:{x-request-id};ts:{ts};"
(data.id lowercased when alphanumeric, per their docs), header format
`x-signature: ts=<ts>,v1=<hex hmac>`.

verify_signature() is fully tested in this session against self-generated
signatures using this exact scheme. fetch_payment_details() calls Mercado
Pago's real API to resolve a payment id into status/payer email/amount — that
part needs a live `ASTROS_LICENSING_MERCADOPAGO_ACCESS_TOKEN` to exercise; the
webhook only ever carries a payment id, never the payer's email itself, so
this follow-up call is required by Mercado Pago's own design, not a choice
made here.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import urllib.error
import urllib.request

from app.payments.base import PaymentEvent

PROVIDER = 'mercadopago'


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
        provider=PROVIDER, reference=reference, email=email,
        amount=details.get('transaction_amount'), currency=details.get('currency_id'),
    )
