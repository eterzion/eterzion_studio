from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

JobStatusValue = Literal['pending', 'pending_confirmation', 'queued', 'processing', 'done', 'error', 'cancelled']
ErrorCategory = Literal[
    'out_of_memory', 'corrupted_input', 'model_failure', 'disk_full',
    'hardware_insufficient', 'license_invalid',
]
ConflictMode = Literal['overwrite', 'rename', 'ask']

# --- Unified Media Processing (data-model.md / contracts/api.md) ---
MediaType = Literal['image', 'video', 'audio']
Operation = Literal['enhance', 'compress', 'convert']
Profile = Literal['fast', 'balanced', 'quality']
ContentType = Literal['photo', 'anime_image', 'real_video', 'anime_video', 'speech', 'music']
InstallState = Literal['not_installed', 'installing', 'installed', 'update_available']
LicenseState = Literal[
    'active', 'offline_tolerance', 'offline_expiring', 'blocked', 'not_activated', 'not_configured'
]
LicenseStatusValue = Literal['approved', 'approved_conditional']
# specs/006-audio-engine-masterizacao — audio_mode is additive: None/'enhance'
# preserves today's single-pass music/speech pipeline exactly (contracts/README.md
# Decisão 2). Only 'auto_master'/'restore'/'restore_master' route through
# app.audio_engine.mastering.MasteringEngine.
AudioMode = Literal['enhance', 'auto_master', 'restore', 'restore_master']
QualityVerdictOutcome = Literal['accepted', 'reduced', 'rejected']


class CustomSize(BaseModel):
    width: int
    height: int


class Adjustments(BaseModel):
    denoise: int = Field(default=50, ge=0, le=100)
    deblur: int = Field(default=0, ge=0, le=100)
    detail_recovery: int = Field(default=0, ge=0, le=100)
    face_correction: bool = False
    face_recovery_strength: int = Field(default=80, ge=0, le=100)
    denoise_filter_enabled: bool = False
    denoise_filter_strength: int = Field(default=45, ge=0, le=100)


class OutputTarget(BaseModel):
    """Where/how the result is written — format, directory, name, conflict policy."""
    format: str
    directory: str | None = None
    filename: str | None = None
    conflict: ConflictMode = 'rename'


class MediaRequest(BaseModel):
    """The processing-intent contract (contracts/api.md `POST /jobs`, data-model.md
    MediaRequest). `extra='forbid'` is what makes FR-011 real: a `model`/`engine`/
    `checkpoint_id` field (or any other unknown field) is a 422 validation error,
    never a silently-ignored extra key — the API only ever accepts intent, the
    implementation is resolved internally by profile_resolver.py."""
    model_config = ConfigDict(extra='forbid')

    media_type: MediaType
    operation: Operation
    scale: Literal['2x', '4x'] | None = None
    profile: Profile | None = None
    content_type_override: ContentType | None = None
    input_path: str
    output_target: OutputTarget | None = None
    secondary_elements_ack: bool = False
    device: str = 'auto'
    custom_size: CustomSize | None = None
    quality: int | None = Field(default=None, ge=0, le=100)  # compress/convert only (FR-027)
    # audio_mode/ai_strength: music-only (content_type='music'), both optional —
    # omitted or 'enhance' means "exactly today's behaviour", byte for byte
    # (specs/006-audio-engine-masterizacao contracts/README.md).
    audio_mode: AudioMode | None = None
    ai_strength: int | None = Field(default=None, ge=0, le=100)


class LocalJobRequest(BaseModel):
    """Body for POST /jobs/local — the same local-desktop convenience as
    ExportRequest.output_dir, but for input: skips the multipart upload and points
    the job straight at a file already on disk (API and client on the same machine).
    `media_request.input_path` IS the path — there is no separate top-level field."""
    media_request: MediaRequest
    adjustments: Adjustments = Adjustments()


class ExportRequest(BaseModel):
    """Body for POST /jobs/{id}/export. Only re-encodes the already-upscaled master
    result (see job_manager._process_job) — never re-runs the model, so switching
    format/quality/destination after a job is done is always fast."""
    format: Literal['png', 'jpg', 'jpeg', 'tiff', 'webp'] = 'png'
    quality: int = Field(default=90, ge=1, le=100)
    output_dir: str | None = None  # None = same folder as the original input
    filename: str | None = None  # None = "{name}_upscaled_{scale}x.{ext}"
    conflict: ConflictMode = 'rename'


class SizeMeta(BaseModel):
    # width/height are None for audio and for any compress/convert result —
    # those operations don't produce a pixel-dimensioned output (FR-025/FR-028).
    width: int | None = None
    height: int | None = None
    size_bytes: int | None = None


class CapacityCheck(BaseModel):
    fits: bool
    estimated_duration: float | None = None
    limiting_resource: str | None = None


class AudioAnalysisSummary(BaseModel):
    """Resumo público de audio_engine.analyzer.AudioAnalysisReport
    (contracts/README.md) — só os campos úteis para uma UI de métricas, não
    o relatório interno completo (Princípio V — sem detalhe técnico por
    padrão)."""
    integrated_lufs: float
    true_peak_db: float
    dynamic_range_db: float
    clipping_ratio: float


class QualityVerdictSummary(BaseModel):
    outcome: QualityVerdictOutcome
    reasons: list[str] = []


class JobStatus(BaseModel):
    id: str
    status: JobStatusValue
    media_type: MediaType = 'image'
    operation: Operation = 'enhance'
    content_type_detected: ContentType | None = None
    progress: int = 0
    stage: str | None = None
    eta_seconds: int | None = None
    queue_position: int | None = None
    input_file: str
    output_path: str | None = None
    error: str | None = None
    error_category: ErrorCategory | None = None
    capacity_check: CapacityCheck | None = None
    created_at: str
    processing_started_at: str | None = None
    processing_ended_at: str | None = None
    source_meta: SizeMeta | None = None
    output_meta: SizeMeta | None = None
    # Present only when audio_mode != 'enhance' was used — absent (not null)
    # for every image/video/speech job and for the default music pipeline,
    # so their response payload is byte-for-byte unchanged (contracts/README.md).
    audio_analysis: AudioAnalysisSummary | None = None
    quality_verdict: QualityVerdictSummary | None = None


class ModelInfo(BaseModel):
    name: str
    category: str
    scale: int
    description: str


class Component(BaseModel):
    """`GET /components` — capability-first listing, never a technical name
    (FR-063/FR-064). No selection affordance: only install/update/remove."""
    id: str
    capability_label: str
    size_mb: int
    install_state: InstallState
    update_available: bool = False


class ComponentDetails(Component):
    """`GET /components/{id}/details` — the one opt-in place technical detail is
    ever shown (FR-065/FR-066)."""
    technical_name: str
    version: str
    provenance: str
    license: str


class DetectContentTypeRequest(BaseModel):
    """Body for POST /content-type/detect — lets the UI show a correct default
    on the editable content-type indicator (FR-096) before a Job exists."""
    input_path: str
    media_type: MediaType


class LicenseStatusResponse(BaseModel):
    state: LicenseState
    installations_used: int
    installations_limit: int
    offline_days_remaining: int | None = None
