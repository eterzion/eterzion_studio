"""T036 — the local API's facade over astros_licensing_service (Constitution
Principle II: no reimplementation, delegate to the service). GET /status
reuses the same real check the T016 gate runs (license_gate.check_gate()) —
one source of truth for "is this installation allowed to work", not two
independently-drifting implementations.
"""
from __future__ import annotations

import urllib.error

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.core import install_identity, license_cache, protected_loader
from app.core.license_gate import check_gate
from app.core.protected_loader import ProtectedLoadError
from app.models.schemas import LicenseStatusResponse

router = APIRouter()


class ActivateRequest(BaseModel):
    license_id: str


@router.get('/status', response_model=LicenseStatusResponse)
def get_status() -> LicenseStatusResponse:
    result = check_gate()
    state = result.state if result.state != 'not_configured' else 'not_activated'
    return LicenseStatusResponse(
        state=state,
        installations_used=result.installations_used or 0,
        installations_limit=result.installations_limit or 0,
        offline_days_remaining=result.offline_days_remaining,
    )


@router.post('/activate')
def activate_license(payload: ActivateRequest) -> dict:
    if not settings.licensing_service_url:
        raise HTTPException(409, 'Nenhum serviço de licenciamento configurado.')
    identity = install_identity.ensure_identity()
    try:
        protected_loader.activate(settings.licensing_service_url, payload.license_id, identity)
    except ProtectedLoadError as error:
        raise HTTPException(502, f'Não foi possível ativar a licença: {error}') from error
    license_cache.record_successful_check()
    return {'ok': True}


@router.post('/release')
def release_license() -> dict:
    if not settings.licensing_service_url:
        raise HTTPException(409, 'Nenhum serviço de licenciamento configurado.')
    identity = install_identity.ensure_identity()
    status = check_gate()
    if status.state == 'not_activated':
        raise HTTPException(409, 'Esta instalação não está ativada.')
    # check_gate() doesn't carry license_id (only installations_used/limit) —
    # ask the service directly, the one place that actually knows it.
    try:
        body = protected_loader.installation_status(settings.licensing_service_url, identity.install_id)
        protected_loader.release(settings.licensing_service_url, body['license_id'], identity.install_id)
    except (ProtectedLoadError, urllib.error.HTTPError) as error:
        raise HTTPException(502, f'Não foi possível liberar a instalação: {error}') from error
    return {'ok': True}
