from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import licensing

router = APIRouter()


class ActivateRequest(BaseModel):
    license_id: str
    install_id: str
    signing_public_key_b64: str
    encryption_public_key_b64: str


@router.post('')
def activate(body: ActivateRequest):
    try:
        licensing.activate_installation(
            body.license_id, body.install_id, body.signing_public_key_b64, body.encryption_public_key_b64
        )
    except licensing.LicenseNotActive as error:
        raise HTTPException(403, str(error)) from error
    except licensing.ActivationLimitReached as error:
        raise HTTPException(409, str(error)) from error
    except licensing.LicenseError as error:
        raise HTTPException(404, str(error)) from error
    return {'ok': True}


@router.delete('/{install_id}')
def release(install_id: str, license_id: str):
    if not licensing.release_installation(license_id, install_id):
        raise HTTPException(404, 'Ativação não encontrada.')
    return {'ok': True}


@router.get('/{install_id}/status')
def status(install_id: str):
    """The local API's license gate (T016) calls this before accepting a job:
    is this installation activated, and against a license that's currently
    active? Reaching this route AT ALL is itself a successful revalidation
    (FR-056) — it touches last_seen_at, resetting the offline-tolerance clock
    the local API falls back to when it *can't* reach this service."""
    license_ = licensing.installation_license(install_id)
    if license_ is None:
        raise HTTPException(404, 'Instalação não ativada.')
    licensing.touch_installation(install_id)
    installations_used = len(licensing.list_installations(license_.id))
    return {
        'license_id': license_.id,
        'status': license_.status,
        'installations_used': installations_used,
        'installations_limit': license_.activation_limit,
    }
