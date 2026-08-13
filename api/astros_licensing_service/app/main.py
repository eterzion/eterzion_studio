from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.licensing import get_public_key_b64
from app.routes import activation_router, authorizations_router, packages_router, webhooks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title='Astros Upscale — Licensing Service', lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(webhooks_router, prefix='/webhooks', tags=['webhooks'])
app.include_router(activation_router, prefix='/activations', tags=['activations'])
app.include_router(authorizations_router, prefix='/authorizations', tags=['authorizations'])
app.include_router(packages_router, prefix='/packages', tags=['packages'])


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/public-key')
def public_key():
    """The service's signing public key — a real client should pin this at
    build time rather than fetch it over the wire (fetching it live is only
    convenient for local development/testing, not for production trust)."""
    return {'public_key_b64': get_public_key_b64()}
