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
    cors_origins: list[str] = Field(
        ['http://localhost:5173', 'app://.', 'null'],
        validation_alias=AliasChoices(
            'ETERZION_LICENSING_CORS_ORIGINS',
            'ASTROS_LICENSING_CORS_ORIGINS',
        ),
    )

    default_activation_limit: int = Field(
        2,
        validation_alias=AliasChoices(
            'ETERZION_LICENSING_DEFAULT_ACTIVATION_LIMIT',
            'ASTROS_LICENSING_DEFAULT_ACTIVATION_LIMIT',
        ),
    )
    authorization_ttl_seconds: int = Field(
        300,
        validation_alias=AliasChoices(
            'ETERZION_LICENSING_AUTHORIZATION_TTL_SECONDS',
            'ASTROS_LICENSING_AUTHORIZATION_TTL_SECONDS',
        ),
    )

    # Downloads do Studio pelo R2 (app/downloads.py). A chave precisa ser
    # identica ao segredo STUDIO_SIGNING_KEY do Worker de cdn.eterzion.com, e
    # EXCLUSIVA do Studio -- nao a do catalogo. Vazia = rota desligada (503).
    studio_cdn_signing_key: str = Field(
        '', validation_alias=AliasChoices('ETERZION_LICENSING_STUDIO_CDN_SIGNING_KEY'),
    )
    studio_cdn_base: str = Field(
        'https://cdn.eterzion.com/studio',
        validation_alias=AliasChoices('ETERZION_LICENSING_STUDIO_CDN_BASE'),
    )
    # Seis horas cobre o maior download (instalador ~360 MB numa conexao lenta)
    # com folga; o app renova antes de vencer.
    studio_cdn_token_ttl_seconds: int = Field(
        21600, validation_alias=AliasChoices('ETERZION_LICENSING_STUDIO_CDN_TOKEN_TTL_SECONDS'),
    )
    studio_cdn_token_align_seconds: int = Field(
        3600, validation_alias=AliasChoices('ETERZION_LICENSING_STUDIO_CDN_TOKEN_ALIGN_SECONDS'),
    )

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
