"""Runtime settings for the Eterzion Studio licensing service."""

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_prefix='ETERZION_LICENSING_',
    )

    port: int = Field(
        8766,
        validation_alias=AliasChoices('ETERZION_LICENSING_PORT', 'ASTROS_LICENSING_PORT'),
    )
    database_path: str = Field(
        str((APP_DIR.parent / 'storage' / 'licensing.db').resolve()),
        validation_alias=AliasChoices(
            'ETERZION_LICENSING_DATABASE_PATH',
            'ASTROS_LICENSING_DATABASE_PATH',
        ),
    )
    identity_dir: str = Field(
        str((APP_DIR.parent / 'storage' / 'identity').resolve()),
        validation_alias=AliasChoices(
            'ETERZION_LICENSING_IDENTITY_DIR',
            'ASTROS_LICENSING_IDENTITY_DIR',
        ),
    )

    # Electron uses app://. in production; Vite uses localhost in development.
    cors_origins: list[str] = ['http://localhost:5173', 'app://.', 'null']

    default_activation_limit: int = 2
    authorization_ttl_seconds: int = 300

    # Provider integrations stay disabled until their secrets are configured.
    stripe_webhook_secret: str = Field(
        '',
        validation_alias=AliasChoices(
            'ETERZION_LICENSING_STRIPE_WEBHOOK_SECRET',
            'ASTROS_LICENSING_STRIPE_WEBHOOK_SECRET',
        ),
    )
    mercadopago_webhook_secret: str = Field(
        '',
        validation_alias=AliasChoices(
            'ETERZION_LICENSING_MERCADOPAGO_WEBHOOK_SECRET',
            'ASTROS_LICENSING_MERCADOPAGO_WEBHOOK_SECRET',
        ),
    )
    mercadopago_access_token: str = Field(
        '',
        validation_alias=AliasChoices(
            'ETERZION_LICENSING_MERCADOPAGO_ACCESS_TOKEN',
            'ASTROS_LICENSING_MERCADOPAGO_ACCESS_TOKEN',
        ),
    )


settings = Settings()
