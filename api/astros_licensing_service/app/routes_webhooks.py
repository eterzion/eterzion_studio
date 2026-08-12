from fastapi import APIRouter, Header, HTTPException, Request

from app.config import settings
from app.licensing import create_license_from_payment
from app.payments import mercadopago_provider, stripe_provider

router = APIRouter()


@router.post('/stripe')
async def stripe_webhook(request: Request, stripe_signature: str = Header(default='')):
    payload = await request.body()
    event = stripe_provider.verify_and_parse(payload, stripe_signature, settings.stripe_webhook_secret)
    if event is None:
        # Deliberately generic — never reveal *why* verification failed to the caller.
        raise HTTPException(400, 'Assinatura inválida.')
    license_ = create_license_from_payment(event)
    return {'ok': True, 'license_id': license_.id}


@router.post('/mercadopago')
async def mercadopago_webhook(
    request: Request,
    x_signature: str = Header(default=''),
    x_request_id: str = Header(default=''),
):
    body = await request.json()
    data_id = str((body.get('data') or {}).get('id') or request.query_params.get('data.id') or '')
    if not data_id or not mercadopago_provider.verify_signature(data_id, x_request_id, x_signature, settings.mercadopago_webhook_secret):
        raise HTTPException(400, 'Assinatura inválida.')
    # Mercado Pago's webhook body only ever carries the payment id — status/email
    # require this follow-up call to their API (see mercadopago_provider docstring).
    details = mercadopago_provider.fetch_payment_details(data_id, settings.mercadopago_access_token)
    if details is None:
        raise HTTPException(502, 'Não foi possível confirmar o pagamento junto ao Mercado Pago.')
    event = mercadopago_provider.to_payment_event(details)
    if event is None:
        return {'ok': True, 'ignored': True}  # not an approved payment, nothing to do
    license_ = create_license_from_payment(event)
    return {'ok': True, 'license_id': license_.id}
