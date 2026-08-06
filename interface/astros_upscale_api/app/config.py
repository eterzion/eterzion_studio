from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_prefix='ASTROS_')

    port: int = 8765
    # 'null' covers the packaged Electron app (loaded via file://, which sends Origin: null).
    cors_origins: list[str] = ['http://localhost:5173', 'app://.', 'null']
    # APP_DIR = <repo>/interface/astros_upscale_api/app -> repo root is 3 levels up
    models_dir: str = str((APP_DIR.parent.parent.parent / 'models').resolve())
    uploads_dir: str = str((APP_DIR / 'storage' / 'uploads').resolve())
    outputs_dir: str = str((APP_DIR / 'storage' / 'outputs').resolve())
    max_upload_mb: int = 200
    api_key: str | None = None  # required only when hosted remotely


settings = Settings()
