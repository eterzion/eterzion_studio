from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_prefix='ASTROS_')

    port: int = 8765
    # 'null' covers the packaged Electron app (loaded via file://, which sends Origin: null).
    cors_origins: list[str] = ['http://localhost:5173', 'app://.', 'null']
    # APP_DIR = <repo>/api/astros_upscale_api/app -> repo root is 3 levels up.
    # /models stays at the true git repo root (data, not application source),
    # unlike component_manager.py's _REPO_ROOT which points at api/ instead.
    models_dir: str = str((APP_DIR.parent.parent.parent / 'models').resolve())
    uploads_dir: str = str((APP_DIR / 'storage' / 'uploads').resolve())
    outputs_dir: str = str((APP_DIR / 'storage' / 'outputs').resolve())
    max_upload_mb: int = 200
    api_key: str | None = None  # required only when hosted remotely

    # Fase 4 — pacote temporário de execução. licensing_service_url points at
    # the separate service in api/astros_licensing_service. Empty =
    # protected loading disabled, isolated_worker.py falls back to the plain
    # static import — orthogonal to whether a job was ALLOWED to be created
    # at all (that's license_gate.py's job, governed by dev_allow_unlicensed
    # below), this only picks which already-authorized code runs it.
    licensing_service_url: str = ''
    # Pin the service's real signing public key here at build time in
    # production — fetching it live from /public-key (the fallback when this
    # is empty) is trust-on-first-use, fine for local dev, not for a shipped
    # build (see routes_packages' docstring on the service side).
    licensing_service_public_key_b64: str = ''
    # T037: an empty licensing_service_url alone must never silently mean
    # "no enforcement" in a shipped build — that would ship for free by
    # omission. This is the explicit override that makes the permissive dev/
    # test behavior an opt-in, auditable decision (ASTROS_DEV_ALLOW_UNLICENSED
    # env var) instead of an implicit side effect of an unset URL. Defaults
    # to True so local dev/pytest keep working without extra setup; a real
    # packaging/production config MUST set this to false explicitly alongside
    # a real licensing_service_url.
    dev_allow_unlicensed: bool = True


settings = Settings()
