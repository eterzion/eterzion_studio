from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_prefix='ASTROS_')

    port: int = 8765
    # 'null' covers the packaged Electron app (loaded via file://, which sends Origin: null).
    cors_origins: list[str] = ['http://localhost:5173', 'app://.', 'null']
    # APP_DIR = <repo>/api/astros_upscale_api/app -> repo root is 3 levels up.
    # /models stays at the true git repo root (data, not application source),
    # unlike app.processing's _REPO_ROOT (component management) which points
    # at api/ instead.
    models_dir: str = str((APP_DIR.parent.parent.parent / 'models').resolve())
    uploads_dir: str = str((APP_DIR / 'storage' / 'uploads').resolve())
    outputs_dir: str = str((APP_DIR / 'storage' / 'outputs').resolve())
    max_upload_mb: int = 200
    api_key: str | None = None  # required only when hosted remotely

    # Fase 4 — pacote temporário de execução. licensing_service_url points at
    # the separate service in api/astros_licensing_service. Empty =
    # protected loading disabled, app.jobs's isolated worker falls back to the
    # plain static import — orthogonal to whether a job was ALLOWED to be
    # created at all (that's app.licensing's check_gate() job, governed by
    # dev_allow_unlicensed below), this only picks which already-authorized
    # code runs it.
    licensing_service_url: str = ''
    # Pin the service's real signing public key here at build time in
    # production — fetching it live from /public-key (the fallback when this
    # is empty) is trust-on-first-use, fine for local dev, not for a shipped
    # build (see the licensing service's packages module docstring).
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

    # Path to the audio-worker's own interpreter (a separate venv with
    # audio_worker_requirements.txt installed — the SonicMaster pins are
    # deliberately incompatible with this process's own torch, per
    # specs/006-audio-engine-masterizacao/research.md Decisão 4). Empty =
    # AI music restoration unavailable, ai_provider.is_available() returns
    # False and app.audio_engine falls back to DSP-only (FR-020).
    audio_worker_python: str = ''
    # SonicMaster's model.safetensors (~3.29 GB), downloaded on demand — not
    # committed, not fetched at build time. Default lives next to /models
    # (the same true repo-root data directory image/video checkpoints use).
    audio_worker_checkpoint: str = str(
        (APP_DIR.parent.parent.parent / 'models' / 'sonicmaster' / 'model.safetensors').resolve())
    # Stable Audio Open's VAE is a gated HF repo (research.md — required at
    # inference time, not optional). Read here — via `.env` or the plain
    # (unprefixed) HF_TOKEN env var — and passed explicitly in the IPC
    # message to the audio-worker (app.audio_engine.ai_provider), rather than
    # relying on subprocess environment inheritance: that path repeatedly
    # failed to carry a Windows user-level env var across terminal restarts
    # during real operator testing.
    hf_token: str = Field(default='', validation_alias='HF_TOKEN')


settings = Settings()
