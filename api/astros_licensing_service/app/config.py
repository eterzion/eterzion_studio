"""Settings for the licensing service (Fase 3 — docs/processing-protection-architecture.md).

Deliberately a separate service from astros_upscale_api — it owns its own
database of licenses/installations/transactions and its own signing key. It
must never share a process or a secret with the local desktop API; the local
API only ever sees this service's public key and HTTPS responses.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_prefix='ASTROS_LICENSING_')

    port: int = 8766
    database_path: str = str((APP_DIR.parent / 'storage' / 'licensing.db').resolve())
    identity_dir: str = str((APP_DIR.parent / 'storage' / 'identity').resolve())

    # The desktop app's renderer (Electron/Chromium, a real browser context) calls
    # /activations and /authorizations directly — needs CORS. 'app://.' covers the
    # packaged app (file:// origin normalizes to 'null' in some Electron configs,
    # covered too); 5173 is the Vite dev server, matching astros_upscale_api's own
    # cors_origins in api/astros_upscale_api/app/config.py.
    cors_origins: list[str] = ['http://localhost:5173', 'app://.', 'null']

    default_activation_limit: int = 2
    authorization_ttl_seconds: int = 300  # curto prazo, conforme a especificação

    # Real secrets in production — set via env vars (ASTROS_LICENSING_STRIPE_WEBHOOK_SECRET
    # etc.), never committed. Empty string = provider disabled (webhook rejected outright).
    stripe_webhook_secret: str = ''
    mercadopago_webhook_secret: str = ''  # validates the webhook signature only
    mercadopago_access_token: str = ''  # separate credential, used for the follow-up API call


settings = Settings()
