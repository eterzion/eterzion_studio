from pathlib import Path
from typing import NamedTuple

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_prefix='ASTROS_')

    # The packaged default. Development uses 8050, passed in as ASTROS_PORT by
    # the Electron main process (see interface/electron.vite.config.ts). The two
    # differ so a dev run and a packaged build can be open at once.
    port: int = 8051
    # An explicit list, not a wildcard: this API answers on loopback and any
    # page in a browser could otherwise call it. 'null' covers the packaged
    # Electron app, which loads via file:// and sends Origin: null. 8055 is the
    # renderer's dev server — a rejected origin here surfaces as a dead backend
    # rather than as a CORS problem, which is a slow thing to diagnose.
    cors_origins: list[str] = [
        'http://localhost:8055',
        'app://.',
        'null',
    ]
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


# ------------------------------- video editing ------------------------------- #
#
# T001/T002 (specs/007-video-editor-player). Two tables, deliberately separate
# because they answer different questions and are wrong in different ways.


class VideoCeilings(NamedTuple):
    """Constitution Princípio VII: an operation whose cost scales with input size
    MUST declare explicit maximums and refuse work above them BEFORE starting,
    naming the limiting factor.

    These do NOT replace processing.check_capacity(), and MUST NOT be read as
    doing so. check_capacity() asks "can this machine cope", adaptively, from
    detected hardware — that is Princípio VII's other half (FR-035: never a
    fixed ceiling independent of what the hardware reports). These ask "is this
    job reasonable at all". A video has to pass both; neither answers the
    other's question.
    """
    max_duration_seconds: float
    max_width: int
    max_height: int
    max_frame_rate: float
    max_frame_count: int
    max_size_bytes: int


# Re-encoding every frame through a filter graph. Cost scales with pixels × frames.
VIDEO_EDIT_CEILINGS = VideoCeilings(
    max_duration_seconds=2 * 60 * 60,
    max_width=3840,
    max_height=2160,
    max_frame_rate=120.0,
    max_frame_count=500_000,
    max_size_bytes=32 * 1024 ** 3,
)

# Trim/remux without re-encoding: frames are copied, not filtered, so the same
# machine tolerates roughly twice as much before the operation stops being
# reasonable. Looser is correct here, not generous.
VIDEO_REMUX_CEILINGS = VideoCeilings(
    max_duration_seconds=4 * 60 * 60,
    max_width=7680,
    max_height=4320,
    max_frame_rate=240.0,
    max_frame_count=1_000_000,
    max_size_bytes=64 * 1024 ** 3,
)


class ContainerSpec(NamedTuple):
    """Video encoders in preference order, plus the audio encoders permitted
    alongside them. Order is the fallback chain when the preferred one is not
    present at runtime — 'permitted' is not 'present' (Princípio XIII)."""
    video_encoders: tuple[str, ...]
    audio_encoders: tuple[str, ...]


# Constitution, Licensing and Distribution Constraints: libx264 and libx265 are
# GPL and MUST NOT be bundled. Their absence from this table is the whole point
# of the table, not an omission — H.264/H.265 output comes from hardware
# encoders only. Combined with the API accepting `container` + `profile` and no
# codec field at all (contracts/api.md), there is no request shape that can ask
# for a GPL encoder.
VIDEO_CONTAINER_ALLOWLIST: dict[str, ContainerSpec] = {
    'mp4': ContainerSpec(
        video_encoders=('h264_nvenc', 'h264_qsv', 'h264_amf'),
        audio_encoders=('aac',),
    ),
    'mov': ContainerSpec(
        video_encoders=('h264_nvenc', 'h264_qsv', 'h264_amf'),
        audio_encoders=('aac',),
    ),
    'mkv': ContainerSpec(
        video_encoders=('h264_nvenc', 'h264_qsv', 'h264_amf', 'libvpx-vp9'),
        audio_encoders=('libopus', 'flac'),
    ),
    'webm': ContainerSpec(
        video_encoders=('libvpx-vp9', 'libaom-av1'),
        audio_encoders=('libopus',),
    ),
}

