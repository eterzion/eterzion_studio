"""License gate for POST /jobs* (T016/T035, FR-051/FR-056 to FR-061): blocks
job creation when this installation is known to be blocked/not activated,
and applies the real offline-tolerance window (offline_tolerance.py +
license_cache.py) when astros_licensing_service can't be reached at all —
FR-061: a communication failure MUST NOT be treated as an invalid licence
while the tolerance window is still open.

`settings.licensing_service_url` empty means no license infra is configured
at all — that alone still blocks (T037) unless `settings.dev_allow_unlicensed`
is explicitly true (default for local dev/pytest), so a build that turns that
flag off can never end up unenforced just because the URL was left unset.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.config import settings
from app.core import license_cache, offline_tolerance

# Statuses a license row (interface/astros_licensing_service/app/licensing.py)
# can carry. Only 'active' passes the gate — anything else (suspended,
# refunded, revoked, ...) is a real reason to block, per FR-060.
_ACTIVE_STATUS = 'active'


@dataclass
class GateResult:
    allowed: bool
    state: str  # LicenseState-ish, see app.models.schemas.LicenseState
    message: str | None = None
    installations_used: int | None = None
    installations_limit: int | None = None
    offline_days_remaining: int | None = None


def _http_get(url: str, timeout: float = 5.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 - fixed, config-provided base_url
        return json.loads(resp.read().decode('utf-8'))


def _offline_fallback(message: str) -> GateResult:
    """FR-061: unreachable service, not an invalid license — fall back to the
    real 30-day/23-day window computed from the last time we DID reach it
    (license_cache.py), never a blanket 'allow'."""
    days = license_cache.days_since_last_success()
    state, remaining = offline_tolerance.compute_offline_state(days)
    if state == 'blocked':
        return GateResult(
            allowed=False, state='blocked',
            message='Não foi possível confirmar sua licença e o período de uso offline expirou. '
                    'Conecte-se à internet para continuar.')
    return GateResult(allowed=True, state=state, message=message, offline_days_remaining=remaining)


def check_gate() -> GateResult:
    """Real check when a licensing service is configured. When it isn't,
    T037: the permissive fallback requires the EXPLICIT dev_allow_unlicensed
    flag (default True for local dev/pytest) — an empty licensing_service_url
    alone is never enough to silently disable enforcement in a build that set
    that flag to false."""
    if not settings.licensing_service_url:
        if settings.dev_allow_unlicensed:
            return GateResult(allowed=True, state='not_configured')
        return GateResult(
            allowed=False, state='not_activated',
            message='Nenhum serviço de licenciamento configurado. Ative sua licença para continuar.')

    from app.core.install_identity import ensure_identity

    identity = ensure_identity()
    url = f'{settings.licensing_service_url}/activations/{identity.install_id}/status'
    try:
        body = _http_get(url)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return GateResult(
                allowed=False, state='not_activated',
                message='Este produto ainda não foi ativado. Ative sua licença para continuar.')
        # Any other HTTP error from the service itself (5xx, etc.) is a real
        # reachability problem from the caller's point of view — same offline
        # fallback as a network-level failure below.
        return _offline_fallback('Não foi possível confirmar o estado da licença agora.')
    except (urllib.error.URLError, TimeoutError, OSError):
        return _offline_fallback('Não foi possível confirmar o estado da licença agora.')

    # Reaching the service at all — regardless of what it says — is a real
    # revalidation (FR-056): resets the offline clock license_cache.py tracks.
    license_cache.record_successful_check()

    if body.get('status') == _ACTIVE_STATUS:
        return GateResult(
            allowed=True, state='active',
            installations_used=body.get('installations_used'), installations_limit=body.get('installations_limit'),
        )
    return GateResult(
        allowed=False, state='blocked',
        message='Sua licença não está mais ativa. Verifique o status da sua assinatura.')
