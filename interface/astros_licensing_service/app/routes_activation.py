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
