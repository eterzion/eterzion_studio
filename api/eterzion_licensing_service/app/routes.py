"""HTTP routes for the licensing service. Consolidates what were
`routes_activation.py`, `routes_authorizations.py`, `routes_packages.py` and
`routes_webhooks.py` (Constitution Princípio XI) — one router per resource,
kept as separate `APIRouter()` instances below so `app/main.py` mounts each
at exactly the same prefix as before; no path, method, schema, or status
code changes.
"""
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from app import licensing, packages, payments
from app.config import settings

# ------------------------------- /activations ------------------------------- #

activation_router = APIRouter()


class ActivateRequest(BaseModel):
    license_id: str
    install_id: str
    signing_public_key_b64: str
    encryption_public_key_b64: str


@activation_router.post('')
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


@activation_router.delete('/{install_id}')
def release(install_id: str, license_id: str):
    if not licensing.release_installation(license_id, install_id):
        raise HTTPException(404, 'Ativação não encontrada.')
    return {'ok': True}


@activation_router.get('/{install_id}/status')
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


# ------------------------------- /authorizations ------------------------------- #

authorizations_router = APIRouter()


class AuthorizeRequest(BaseModel):
    install_id: str
    model: str
    version: str
    operation: str = 'process'


@authorizations_router.post('')
def authorize(body: AuthorizeRequest):
    try:
        result = licensing.issue_authorization(body.install_id, body.model, body.version, body.operation)
    except licensing.LicenseNotActive as error:
        raise HTTPException(403, str(error)) from error
    except licensing.VersionRejected as error:
        raise HTTPException(409, str(error)) from error
    except licensing.AuthorizationError as error:
        raise HTTPException(404, str(error)) from error
    return result


@authorizations_router.post('/{authorization_id}/redeem')
def redeem(authorization_id: str):
    if not licensing.redeem_authorization(authorization_id):
        raise HTTPException(409, 'Autorização inválida, expirada ou já utilizada.')
    return {'ok': True}


# ------------------------------- /packages ------------------------------- #

packages_router = APIRouter()


@packages_router.get('/{name}/latest-version')
def get_latest_version(name: str):
    version = packages.latest_version(name)
    if version is None:
        raise HTTPException(404, f'Nenhuma versão de "{name}" foi construída ainda.')
    return {'name': name, 'version': version}


@packages_router.get('/{name}')
def get_package(name: str, install_id: str, authorization_id: str):
    auth = licensing.redeem_for_install(authorization_id, install_id)
    if auth is None:
        raise HTTPException(403, 'Autorização inválida, expirada, já utilizada, ou não pertence a esta instalação.')

    version = auth['version']
    built = packages.get_package(name, version)
    if built is None:
        raise HTTPException(404, f'Pacote "{name}" versão "{version}" não encontrado.')

    installation = licensing.get_installation(install_id)
    if installation is None:
        raise HTTPException(404, 'Instalação não encontrada.')

    wrap = packages.wrap_content_key_for_install(built['content_key_b64'], installation['encryption_public_key_b64'])
    return {
        'name': name,
        'version': version,
        'ciphertext_b64': built['ciphertext_b64'],
        'nonce_b64': built['nonce_b64'],
        'signature_b64': built['signature_b64'],
        'key_wrap': wrap,
    }


# ------------------------------- /webhooks ------------------------------- #

webhooks_router = APIRouter()


@webhooks_router.post('/stripe')
async def stripe_webhook(request: Request, stripe_signature: str = Header(default='')):
    payload = await request.body()
    event = payments.verify_and_parse(payload, stripe_signature, settings.stripe_webhook_secret)
    if event is None:
        # Deliberately generic — never reveal *why* verification failed to the caller.
        raise HTTPException(400, 'Assinatura inválida.')
    license_ = licensing.create_license_from_payment(event)
    return {'ok': True, 'license_id': license_.id}


@webhooks_router.post('/mercadopago')
async def mercadopago_webhook(
    request: Request,
    x_signature: str = Header(default=''),
    x_request_id: str = Header(default=''),
):
    body = await request.json()
    data_id = str((body.get('data') or {}).get('id') or request.query_params.get('data.id') or '')
    if not data_id or not payments.verify_signature(data_id, x_request_id, x_signature, settings.mercadopago_webhook_secret):
        raise HTTPException(400, 'Assinatura inválida.')
    # Mercado Pago's webhook body only ever carries the payment id — status/email
    # require this follow-up call to their API (see app.payments docstring).
    details = payments.fetch_payment_details(data_id, settings.mercadopago_access_token)
    if details is None:
        raise HTTPException(502, 'Não foi possível confirmar o pagamento junto ao Mercado Pago.')
    event = payments.to_payment_event(details)
    if event is None:
        return {'ok': True, 'ignored': True}  # not an approved payment, nothing to do
    license_ = licensing.create_license_from_payment(event)
    return {'ok': True, 'license_id': license_.id}
