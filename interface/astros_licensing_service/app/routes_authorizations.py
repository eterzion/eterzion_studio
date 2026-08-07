from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import authorizations
from app.licensing import LicenseNotActive

router = APIRouter()


class AuthorizeRequest(BaseModel):
    install_id: str
    model: str
    version: str
    operation: str = 'process'


@router.post('')
def authorize(body: AuthorizeRequest):
    try:
        result = authorizations.issue_authorization(body.install_id, body.model, body.version, body.operation)
    except LicenseNotActive as error:
        raise HTTPException(403, str(error)) from error
    except authorizations.VersionRejected as error:
        raise HTTPException(409, str(error)) from error
    except authorizations.AuthorizationError as error:
        raise HTTPException(404, str(error)) from error
    return result


@router.post('/{authorization_id}/redeem')
def redeem(authorization_id: str):
    if not authorizations.redeem_authorization(authorization_id):
        raise HTTPException(409, 'Autorização inválida, expirada ou já utilizada.')
    return {'ok': True}
