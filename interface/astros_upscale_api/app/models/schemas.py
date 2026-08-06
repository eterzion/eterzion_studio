from typing import Literal

from pydantic import BaseModel, Field

JobStatusValue = Literal['pending', 'queued', 'processing', 'done', 'error', 'cancelled']
ErrorCategory = Literal['out_of_memory', 'corrupted_input', 'model_failure', 'disk_full']
ConflictMode = Literal['overwrite', 'rename', 'ask']


class CustomSize(BaseModel):
    width: int
    height: int


class Adjustments(BaseModel):
    denoise: int = Field(default=50, ge=0, le=100)
    deblur: int = Field(default=0, ge=0, le=100)
    detail_recovery: int = Field(default=0, ge=0, le=100)
    face_correction: bool = False


class JobParams(BaseModel):
    model: str = 'realesrgan-x4'
    device: str = 'auto'
    scale: int = 4
    custom_size: CustomSize | None = None
    adjustments: Adjustments = Adjustments()


class LocalJobRequest(BaseModel):
    """Body for POST /jobs/local — the same local-desktop convenience as
    ExportRequest.output_dir, but for input: skips the multipart upload and points
    the job straight at a file already on disk (API and client on the same machine)."""
    input_path: str
    params: JobParams = JobParams()


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
    width: int
    height: int
    size_bytes: int | None = None


class JobStatus(BaseModel):
    id: str
    status: JobStatusValue
    progress: int = 0
    stage: str | None = None
    eta_seconds: int | None = None
    queue_position: int | None = None
    input_file: str
    output_path: str | None = None
    error: str | None = None
    error_category: ErrorCategory | None = None
    created_at: str
    processing_started_at: str | None = None
    processing_ended_at: str | None = None
    source_meta: SizeMeta | None = None
    output_meta: SizeMeta | None = None


class ModelInfo(BaseModel):
    name: str
    category: str
    scale: int
    description: str
