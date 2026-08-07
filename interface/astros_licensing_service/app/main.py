from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import routes_activation, routes_authorizations, routes_packages, routes_webhooks
from app.config import settings
from app.db import init_db
from app.service_identity import get_public_key_b64

app = FastAPI(title='Astros Upscale — Licensing Service')

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(routes_webhooks.router, prefix='/webhooks', tags=['webhooks'])
app.include_router(routes_activation.router, prefix='/activations', tags=['activations'])
app.include_router(routes_authorizations.router, prefix='/authorizations', tags=['authorizations'])
app.include_router(routes_packages.router, prefix='/packages', tags=['packages'])


@app.on_event('startup')
async def on_startup():
    init_db()


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/public-key')
def public_key():
    """The service's signing public key — a real client should pin this at
    build time rather than fetch it over the wire (fetching it live is only
    convenient for local development/testing, not for production trust)."""
    return {'public_key_b64': get_public_key_b64()}
