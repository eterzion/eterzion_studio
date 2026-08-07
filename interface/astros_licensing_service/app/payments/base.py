"""Common shape every payment provider adapter normalizes into — the rest of
the service (licensing.py) only ever sees this, never a provider-specific
payload. Swapping/adding a provider means writing one more module here, not
touching licensing logic.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PaymentEvent:
    provider: str
    reference: str  # provider's transaction/session id — used for idempotency
    email: str
    amount: int | None  # smallest currency unit (cents), when the provider reports it
    currency: str | None
