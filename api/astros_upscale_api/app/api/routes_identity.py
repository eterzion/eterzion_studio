"""Read-only view of this installation's cryptographic identity (Fase 2). Never
exposes the private key — only what a future activation flow (Fase 3) would
need to send to a remote licensing service: the install id and the public key.
"""
from fastapi import APIRouter

from app.core.install_identity import ensure_identity

router = APIRouter()


@router.get('')
def get_identity():
    identity = ensure_identity()
    return {
        'install_id': identity.install_id,
        'signing_public_key_b64': identity.signing_public_key_b64,
        'encryption_public_key_b64': identity.encryption_public_key_b64,
    }
