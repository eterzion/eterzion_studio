"""HTTP routes and the job-progress WebSocket. Consolidates what were
`api/routes_jobs.py`, `api/routes_files.py`, `api/routes_components.py`,
`api/routes_identity.py`, `api/routes_license.py`, `api/routes_preview.py`
and `api/ws_progress.py` (Constitution Princípio XI) — one router per
resource, kept as separate `APIRouter()` instances below so `app/main.py`
mounts each at exactly the same prefix as before; no path, method, schema,
status code or WebSocket behaviour changes.
"""
from __future__ import annotations

import asyncio
import base64
import os
import shutil
import tempfile
import urllib.error
from typing import get_args

import cv2
from fastapi import APIRouter, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import jobs, licensing, media_handles, processing, security, video_edits, video_thumbnails
from app.compression import capabilities as compression_capabilities
from app.compression import estimator as compression_estimator
from app.compression import presets as compression_presets
from app.compression import runner as compression_runner
from app.config import VIDEO_EDIT_CEILINGS, settings
from app.licensing import UnresolvableRequestError
from app.schemas import (Adjustments, Component, ComponentDetails, ContainerAvailability,
                         CompressionCapabilitiesResponse, CompressionEstimateRequest,
                         CompressionEstimateResponse, CompressionJobRequest,
                         CompressionMediaRequest, CompressionMediaResponse,
                         CompressionJobResponse, CompressionPreset,
                         CompressionPresetCreateRequest, CompressionPresetsResponse,
                         CompressionPresetUpdateRequest, DetectContentTypeRequest,
                         ExportFormat, ExportRequest,
                         ImageExportOptionsResponse, ImageFormatAvailability,
                         LicenseStatusResponse, LocalJobRequest, MediaHandleRequest,
                         MediaHandleResponse, MediaRequest, VideoCeilingsResponse,
                         VideoExportOptionsResponse, VideoExportRequest,
                         VideoPreviewFrameRequest)
from astros_upscale.media import image_format_works

# ------------------------------- /jobs ------------------------------- #

jobs_router = APIRouter()

_INTERNAL_FIELDS = ('input_path', 'queue_order')


def _enforce_license_gate() -> None:
    """FR-051/FR-060: every POST /jobs* route calls this before a job is
    created. `blocked`/`not_activated` refuse outright; every other state
    (including today's default, no license infra deployed) lets the request
    through — see app.licensing's check_gate()."""
    result = licensing.check_gate()
    if not result.allowed:
        raise HTTPException(403, {'error_category': 'license_invalid', 'message': result.message})


def _detect_image_content_type(input_path: str) -> str:
    from astros_upscale.processing import classify_image
    from astros_upscale.media import ImageOpenError, imread

    try:
        image = imread(input_path)
    except ImageOpenError as error:
        raise HTTPException(422, f'Não foi possível ler a imagem para detectar o tipo de conteúdo: {error}') from error
    return classify_image(image).content_type


# Bounds for the content-type probe: enough audio for the classifier to be
# confident, decoded straight to the rate/layout it works in.
_CLASSIFY_SECONDS = 30
_CLASSIFY_SAMPLE_RATE = 16000


def _detect_audio_content_type(input_path: str) -> str:
    """T056 — wires astros_upscale.processing's real VAD+harmonic/percussive
    classifier (T008) into the job-creation path, same shared function image
    detection already uses. Converts to WAV via ffmpeg first so any
    ffmpeg-readable input format (mp3/flac/a video file's audio track...)
    works, not just wav."""
    import tempfile

    import soundfile as sf

    from astros_upscale.processing import classify_audio
    from astros_upscale.media import run_ffmpeg

    tmp_wav = tempfile.mktemp(suffix='.wav')
    try:
        # Decode only the excerpt classify_audio() will actually look at, and at
        # the 16 kHz it resamples to anyway. Decoding a full-length track to a
        # ~50 MB WAV just to analyse a slice of it was a large part of why this
        # endpoint felt slow. Mono, since the classifier averages channels.
        run_ffmpeg(lambda f: f.input(input_path).output(tmp_wav, {
            'vn': None, 'acodec': 'pcm_s16le', 'ar': _CLASSIFY_SAMPLE_RATE, 'ac': 1,
            't': _CLASSIFY_SECONDS,
        }))
        samples, sample_rate = sf.read(tmp_wav)
    except Exception as error:  # noqa: BLE001 - any ffmpeg/soundfile failure means "can't detect"
        raise HTTPException(422, f'Não foi possível ler o áudio para detectar o tipo de conteúdo: {error}') from error
    finally:
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)
    return classify_audio(samples, sample_rate).content_type


def _detect_video_content_type(input_path: str) -> str:
    """Classify a video by looking at frames from it.

    There was no automatic detection here at all: the route refused with a 422
    and the Vídeo screen filled in 'real_video' as a fixed default, so an
    anime clip arrived labelled live action and got the model meant for
    photography. Nothing was misdetecting — nothing was detecting.

    Frames are sampled across the whole duration rather than from the start,
    because openings, title cards and fades are the least representative part
    of a video and the first seconds are usually exactly that. Each frame goes
    through the same classify_image() the Imagem screen uses, and the majority
    wins: a single frame of a stylised live-action shot, or one live-action
    still inside an animation, should not decide the whole file.

    A frame that classifies as pixel art counts towards animation. Video is
    never enlarged by repeating pixels here, so 'pixel_art' is not a video
    content type — but a frame that looks like it is certainly not live action.
    """
    import subprocess
    import tempfile

    import cv2

    from astros_upscale.media import ffmpeg_path, probe_streams
    from astros_upscale.processing import classify_image

    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        raise HTTPException(503, 'FFmpeg não está disponível para analisar o vídeo.')

    try:
        info = probe_streams(input_path)
        duration = float(info.get('duration_seconds') or 0)
    except Exception:
        duration = 0

    # Five frames spread over the middle 80%: enough to outvote one odd shot,
    # few enough that detection stays well under a second.
    if duration > 1:
        offsets = [duration * fraction for fraction in (0.1, 0.3, 0.5, 0.7, 0.9)]
    else:
        offsets = [0.0]

    votes: list[str] = []
    with tempfile.TemporaryDirectory() as workdir:
        for index, offset in enumerate(offsets):
            frame_path = os.path.join(workdir, f'f{index}.png')
            result = subprocess.run(
                [ffmpeg, '-v', 'error', '-ss', f'{offset:.3f}', '-i', input_path,
                 '-frames:v', '1', '-y', frame_path],
                capture_output=True, shell=False,
            )
            if result.returncode != 0 or not os.path.isfile(frame_path):
                continue
            frame = cv2.imread(frame_path, cv2.IMREAD_UNCHANGED)
            if frame is None:
                continue
            votes.append(classify_image(frame).content_type)

    if not votes:
        # Refusing beats guessing: the person picks, as they always could.
        raise HTTPException(
            422, 'Não foi possível analisar quadros deste vídeo; informe content_type_override.')

    drawn = sum(1 for vote in votes if vote in ('anime_image', 'pixel_art'))
    return 'anime_video' if drawn * 2 > len(votes) else 'real_video'


def _detect_content_type(media_type: str, input_path: str) -> str:
    """Real detection (T008/T056) — image and audio have a real classifier;
    video samples frames and reuses the image classifier. Shared by POST
    /content-type/detect (called by the UI before a Job exists, so its
    editable indicator, FR-096, shows a real default) and
    _resolve_content_type below (job creation)."""
    if media_type == 'image':
        return _detect_image_content_type(input_path)
    if media_type == 'audio':
        return _detect_audio_content_type(input_path)
    if media_type == 'video':
        return _detect_video_content_type(input_path)
    raise HTTPException(
        422, f"Detecção automática de tipo de conteúdo ainda não existe para media_type={media_type!r}; "
             "informe content_type_override.")


def _resolve_content_type(media_request: MediaRequest, input_path: str) -> str | None:
    """FR-096: the person's explicit correction always wins over detection.
    FR-005: only `enhance` cares about content_type at all — compress/convert
    resolve to a fixed ffmpeg/OpenCV path regardless of it (app.licensing's
    profile resolver mirrors this same rule), so this never runs detection,
    or requires an override, for those operations."""
    if media_request.operation != 'enhance':
        return media_request.content_type_override
    if media_request.content_type_override:
        return media_request.content_type_override
    return _detect_content_type(media_request.media_type, input_path)


@jobs_router.post('/detect-content-type')
def detect_content_type(payload: DetectContentTypeRequest):
    """Lets the UI populate its editable content-type indicator (FR-096) with
    a real default before a Job is created — no license gate needed, this
    reads the file but starts no processing."""
    if not os.path.isfile(payload.input_path):
        raise HTTPException(404, 'Arquivo não encontrado no caminho informado.')
    return {'content_type': _detect_content_type(payload.media_type, payload.input_path)}


def _validate_resolvable(media_request: MediaRequest, content_type: str) -> None:
    """FR-098: reject before the Job is even created when no approved
    implementation exists for this combination — never let it fail later,
    mid-queue, for a reason that was already knowable at request time."""
    # scale '1x' is the Imagem screen's Original mode: no model is resolved for
    # it at all (see jobs.blocking_run), so there is nothing here that could be
    # unresolvable — asking the resolver would reject a request that is valid.
    if media_request.scale == '1x':
        return
    try:
        licensing.resolve(licensing.MediaRequest(
            media_type=media_request.media_type, operation=media_request.operation,
            content_type=content_type, scale=media_request.scale, profile=media_request.profile,
        ))
    except UnresolvableRequestError as error:
        raise HTTPException(422, str(error)) from error


def _capacity_check_for(media_request: MediaRequest, input_path: str):
    """T062, FR-076/FR-077/FR-079: only `enhance` runs an AI model (the real
    memory-bound step) — compress/convert go through ffmpeg/OpenCV directly
    and have no comparable capacity constraint here, same reasoning
    tile_threshold/tile_size (T061) already uses. Returns None for those,
    meaning "no check needed", not "not computed"."""
    if media_request.operation != 'enhance':
        return None
    # Same reasoning for scale '1x' (the Imagem screen's Original mode): it runs
    # the filters, never the model, so it has no model-sized memory footprint to
    # check a machine against.
    if media_request.scale == '1x':
        return None
    from astros_upscale.processing import detect_hardware

    hardware = detect_hardware()
    width = height = None
    duration_seconds = None
    if media_request.media_type == 'image':
        import cv2 as _cv2

        image = _cv2.imread(input_path)
        if image is not None:
            height, width = image.shape[:2]
    elif media_request.media_type == 'video':
        from astros_upscale.media import ProbeError, probe_streams

        try:
            info = probe_streams(input_path)
            duration_seconds = info['duration_seconds']
        except ProbeError:
            pass
        import cv2 as _cv2

        cap = _cv2.VideoCapture(input_path)
        if cap.isOpened():
            width = int(cap.get(_cv2.CAP_PROP_FRAME_WIDTH)) or None
            height = int(cap.get(_cv2.CAP_PROP_FRAME_HEIGHT)) or None
        cap.release()
    elif media_request.media_type == 'audio':
        from astros_upscale.media import ProbeError, probe_streams

        try:
            duration_seconds = probe_streams(input_path)['duration_seconds']
        except ProbeError:
            pass

    return processing.check_capacity(
        hardware, media_request.media_type, width=width, height=height, duration_seconds=duration_seconds)


def _detect_secondary_elements(media_request: MediaRequest, input_path: str) -> dict | None:
    """FR-081/FR-085: only video-enhance jobs can lose extra audio tracks,
    subtitles or chapters (the video pipeline only carries one video + one
    audio stream through) — every other media_type/operation combination
    never has anything at stake, so this returns None (no prompt, ever) for
    them instead of probing a file that was never going to lose anything."""
    if media_request.media_type != 'video' or media_request.operation != 'enhance':
        return None
    from astros_upscale.media import ProbeError, detect_secondary_elements

    try:
        return detect_secondary_elements(input_path)
    except ProbeError as error:
        raise HTTPException(422, f'Não foi possível inspecionar o vídeo: {error}') from error


def _build_job_params(media_request: MediaRequest, adjustments: Adjustments) -> dict:
    """What jobs.py actually stores as `job['params']` — intent only
    (scale/profile/device/adjustments), never a model/engine identifier
    (FR-009/FR-011). The engine_ref app.licensing's profile resolver resolves
    at processing time (jobs._process_job) never lands here."""
    return {
        'scale': media_request.scale,
        'profile': media_request.profile,
        'device': media_request.device,
        'custom_size': media_request.custom_size.model_dump() if media_request.custom_size else None,
        'adjustments': adjustments.model_dump(),
        'quality': media_request.quality,
        'output_target': media_request.output_target.model_dump() if media_request.output_target else None,
        # specs/006-audio-engine-masterizacao — None/'enhance' (the default)
        # means jobs._process_job takes the exact same path as before this
        # feature existed; only audio_engine reads these two fields.
        'audio_mode': media_request.audio_mode,
        'ai_strength': media_request.ai_strength,
    }


@jobs_router.post('')
async def create_job(file: UploadFile, media_request: str = Form(...), adjustments: str = Form(default='{}')):
    _enforce_license_gate()
    media_req = MediaRequest.model_validate_json(media_request)
    adj = Adjustments.model_validate_json(adjustments)

    os.makedirs(settings.uploads_dir, exist_ok=True)
    dest_path = os.path.join(settings.uploads_dir, file.filename)
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f'Arquivo maior que o limite de {settings.max_upload_mb} MB.')
    with open(dest_path, 'wb') as fh:
        fh.write(content)

    content_type = _resolve_content_type(media_req, dest_path)
    _validate_resolvable(media_req, content_type)
    capacity_result = _capacity_check_for(media_req, dest_path)
    if capacity_result is not None and not capacity_result.fits:
        raise HTTPException(422, {
            'error_category': 'hardware_insufficient',
            'message': f'Este arquivo excede a capacidade desta máquina (recurso insuficiente: '
                       f'{capacity_result.limiting_resource}).',
            'limiting_resource': capacity_result.limiting_resource,
        })
    secondary_elements = _detect_secondary_elements(media_req, dest_path)
    job_id = jobs.create_job(
        dest_path, file.filename, _build_job_params(media_req, adj),
        media_type=media_req.media_type, operation=media_req.operation, content_type_detected=content_type,
        secondary_elements=secondary_elements, secondary_elements_ack=media_req.secondary_elements_ack,
    )
    if capacity_result is not None:
        jobs.set_capacity_check(job_id, True, capacity_result.estimated_duration, None)
    # T063/FR-078 — surfaced right in the creation response, so the client
    # can decide whether to proceed with a long job without a follow-up GET.
    return {'id': job_id, 'estimated_duration': capacity_result.estimated_duration if capacity_result else None}


@jobs_router.post('/local')
def create_job_local(payload: LocalJobRequest):
    """Same as POST /jobs, but for when the API and the client share a filesystem
    (the Electron desktop app): points the job straight at a path already on disk
    instead of uploading the file's bytes over HTTP."""
    _enforce_license_gate()
    input_path = payload.media_request.input_path
    if not os.path.isfile(input_path):
        raise HTTPException(404, 'Arquivo não encontrado no caminho informado.')
    filename = os.path.basename(input_path)
    content_type = _resolve_content_type(payload.media_request, input_path)
    _validate_resolvable(payload.media_request, content_type)
    capacity_result = _capacity_check_for(payload.media_request, input_path)
    if capacity_result is not None and not capacity_result.fits:
        raise HTTPException(422, {
            'error_category': 'hardware_insufficient',
            'message': f'Este arquivo excede a capacidade desta máquina (recurso insuficiente: '
                       f'{capacity_result.limiting_resource}).',
            'limiting_resource': capacity_result.limiting_resource,
        })
    secondary_elements = _detect_secondary_elements(payload.media_request, input_path)
    job_id = jobs.create_job(
        input_path, filename, _build_job_params(payload.media_request, payload.adjustments),
        media_type=payload.media_request.media_type, operation=payload.media_request.operation,
        content_type_detected=content_type,
        secondary_elements=secondary_elements, secondary_elements_ack=payload.media_request.secondary_elements_ack,
    )
    if capacity_result is not None:
        jobs.set_capacity_check(job_id, True, capacity_result.estimated_duration, None)
    return {'id': job_id, 'estimated_duration': capacity_result.estimated_duration if capacity_result else None}


@jobs_router.get('')
def list_jobs():
    return {'jobs': [_job_public_view(job) for job in jobs.list_jobs()]}


@jobs_router.get('/{job_id}')
def get_job(job_id: str):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(404, 'Job não encontrado.')
    return _job_public_view(job)


@jobs_router.delete('/{job_id}')
def delete_job(job_id: str):
    if not jobs.cancel_job(job_id):
        raise HTTPException(404, 'Job não encontrado.')
    return {'ok': True}


_FORBIDDEN_PARAM_KEYS = ('model', 'engine', 'checkpoint_id')


@jobs_router.patch('/{job_id}/params')
def update_job_params(job_id: str, params: dict):
    leaked = [key for key in params if key in _FORBIDDEN_PARAM_KEYS]
    if leaked:
        raise HTTPException(422, f'Campo(s) não permitido(s): {", ".join(leaked)} (FR-011).')
    if not jobs.update_params(job_id, params):
        raise HTTPException(409, 'Job não encontrado ou já iniciado.')
    return _job_public_view(jobs.get_job(job_id))


@jobs_router.post('/{job_id}/confirm-secondary-elements')
def confirm_secondary_elements(job_id: str):
    """FR-081/FR-085: moves a video-enhance job out of pending_confirmation
    once the person has seen and accepted what will be lost (extra audio
    tracks/subtitles/chapters). 404 covers both "no such job" and "job
    wasn't waiting on this in the first place" — jobs.py already treats those
    as the same real state (nothing to confirm)."""
    if not jobs.confirm_secondary_elements(job_id):
        raise HTTPException(404, 'Job não encontrado ou não está aguardando confirmação.')
    return _job_public_view(jobs.get_job(job_id))


@jobs_router.post('/{job_id}/process')
async def process_job(job_id: str):
    _enforce_license_gate()
    if not await jobs.enqueue(job_id):
        raise HTTPException(409, 'Job não encontrado ou já processado.')
    return {'ok': True}


def _is_same_file(candidate: str, source: str) -> bool:
    """Whether the export would land on the source file itself.

    os.path.samefile() answers this properly — it follows the two paths to the
    same inode/file id, so a symlink, a junction or a UNC alias for the same
    file is still recognised as the same file. It needs both to exist, and the
    output normally does not yet, so the textual comparison is the fallback
    rather than the answer.
    """
    try:
        if os.path.exists(candidate) and os.path.samefile(candidate, source):
            return True
    except OSError:
        pass
    return os.path.normcase(os.path.abspath(candidate)) == os.path.normcase(os.path.abspath(source))


def _suffixed(path: str) -> str:
    """`foto.png` -> `foto_upscaled.png`, the name a collision falls back to."""
    base, ext = os.path.splitext(path)
    return f'{base}_upscaled{ext}'


def _free_path(path: str) -> str:
    """First path in the `name`, `name (1)`, `name (2)`... series that is free."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 1
    while os.path.exists(f'{base} ({n}){ext}'):
        n += 1
    return f'{base} ({n}){ext}'


@jobs_router.post('/{job_id}/export')
def export_job(job_id: str, payload: ExportRequest):
    """Re-encodes a done job's already-upscaled result to the requested format,
    quality and destination. Never re-runs the model (see app.processing's
    Upscaler / app.jobs)."""
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(404, 'Job não encontrado.')
    if job['status'] != 'done':
        raise HTTPException(409, 'Job ainda não foi concluído.')

    ext = '.' + payload.format.lstrip('.')
    # The source's own name is the default. Adding "_upscaled" to everything
    # made every export announce the tool instead of naming the picture, and
    # people ended up renaming files by hand afterwards. The suffix is what a
    # collision costs, not what every file is called.
    name = payload.filename or os.path.splitext(job['input_file'])[0] + ext
    if not name.lower().endswith(ext):
        name = os.path.splitext(name)[0] + ext
    output_dir = payload.output_dir or os.path.dirname(job['input_path']) or settings.outputs_dir
    output_path = os.path.join(output_dir, name)

    # Princípio XV: "Output never lands on the input." Now that the default
    # name is the source's name and the default directory is the source's
    # directory, the two collide by construction — this is the exact case the
    # principle says must never be resolved by overwriting, and it says so
    # including when the person asked for 'overwrite': that instruction is
    # about replacing some other file, not about destroying the original they
    # are working from. Answering it here means the source cannot be lost no
    # matter what the client sends.
    if _is_same_file(output_path, job['input_path']):
        output_path = _suffixed(output_path)

    if os.path.exists(output_path):
        if payload.conflict == 'ask':
            raise HTTPException(409, {'reason': 'conflict', 'path': output_path})
        if payload.conflict == 'rename':
            output_path = _free_path(_suffixed(output_path))
        # 'overwrite' falls through and just writes over it

    try:
        jobs.export_job(job_id, output_path, payload.quality)
    except ValueError as error:
        raise HTTPException(409, str(error))
    return {'output_path': output_path}


def _job_public_view(job: dict) -> dict:
    view = {k: v for k, v in job.items() if k not in _INTERNAL_FIELDS}
    view['queue_position'] = jobs.queue_position(job['id'])
    return view


# ------------------------------- /jobs/{job_id}/download (no prefix) ------------------------------- #

files_router = APIRouter()


@files_router.get('/jobs/{job_id}/download')
def download_job_output(job_id: str):
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(404, 'Job não encontrado.')
    if job['status'] != 'done' or not job['output_path']:
        raise HTTPException(409, 'Job ainda não foi concluído.')
    if not os.path.isfile(job['output_path']):
        raise HTTPException(410, 'Arquivo de saída não existe mais.')
    return FileResponse(job['output_path'], filename=os.path.basename(job['output_path']))


# ------------------------------- /components ------------------------------- #
#
# T070 — GET /components, GET /components/{id}/details, install/update/delete
# (contracts/api.md). Replaces GET /models (removed) which returned raw model
# identifiers as `name` — a direct FR-009/FR-063 violation flagged by the
# analyze pass (G8) once video/audio content types made "one row per file in
# astros_upscale.processing.MODELS" stop matching "one component per content
# type" (FR-095).

components_router = APIRouter()


def _to_component(info: processing.ComponentInfo) -> Component:
    return Component(
        id=info.id, capability_label=info.capability_label, size_mb=info.size_mb,
        install_state=info.install_state, update_available=info.update_available,
    )


def _to_details(info: processing.ComponentInfo) -> ComponentDetails:
    return ComponentDetails(
        id=info.id, capability_label=info.capability_label, size_mb=info.size_mb,
        install_state=info.install_state, update_available=info.update_available,
        technical_name=info.technical_name, version=info.version, provenance=info.provenance,
        license=info.license,
    )


@components_router.get('', response_model=list[Component])
def list_components():
    return [_to_component(c) for c in processing.list_components()]


@components_router.get('/{component_id}/details', response_model=ComponentDetails)
def get_component_details(component_id: str):
    try:
        return _to_details(processing.get_component_details(component_id))
    except processing.ComponentNotFoundError:
        raise HTTPException(404, 'Componente não encontrado.')


@components_router.post('/{component_id}/install', response_model=Component)
def install_component(component_id: str):
    try:
        return _to_component(processing.install_component(component_id))
    except processing.ComponentNotFoundError:
        raise HTTPException(404, 'Componente não encontrado.')
    except processing.ComponentActionUnsupportedError as error:
        raise HTTPException(422, str(error))


@components_router.post('/{component_id}/update', response_model=Component)
def update_component(component_id: str):
    try:
        return _to_component(processing.update_component(component_id))
    except processing.ComponentNotFoundError:
        raise HTTPException(404, 'Componente não encontrado.')
    except processing.ComponentActionUnsupportedError as error:
        raise HTTPException(422, str(error))


# ------------------------------- /identity ------------------------------- #
#
# Read-only view of this installation's cryptographic identity (Fase 2). Never
# exposes the private key — only what a future activation flow (Fase 3) would
# need to send to a remote licensing service: the install id and the public key.

identity_router = APIRouter()


@identity_router.get('')
def get_identity():
    identity = security.ensure_identity()
    return {
        'install_id': identity.install_id,
        'signing_public_key_b64': identity.signing_public_key_b64,
        'encryption_public_key_b64': identity.encryption_public_key_b64,
    }


# ------------------------------- /preview ------------------------------- #

preview_router = APIRouter()

# Keeps the preview fast enough to feel interactive on slider release — the actual
# job always runs the filter on the real, full-resolution upscaled output; this is
# only a representative before/after, not the final result.
_PREVIEW_MAX_DIM = 480


class DenoisePreviewRequest(BaseModel):
    input_path: str
    strength: int = Field(ge=0, le=100)


def _encode_png(img) -> str:
    ok, buffer = cv2.imencode('.png', img)
    if not ok:
        raise HTTPException(500, 'Falha ao codificar prévia.')
    return base64.b64encode(buffer.tobytes()).decode('ascii')


@preview_router.post('/denoise')
def preview_denoise(payload: DenoisePreviewRequest):
    from astros_upscale.media import imread

    if not os.path.isfile(payload.input_path):
        raise HTTPException(404, 'Arquivo não encontrado no caminho informado.')

    img = imread(payload.input_path)
    h, w = img.shape[0:2]
    scale = min(1.0, _PREVIEW_MAX_DIM / max(h, w))
    if scale < 1.0:
        img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)

    after = processing.Upscaler.denoise_filter(img, payload.strength)
    return {
        'before': _encode_png(img),
        'after': _encode_png(after),
        'width': img.shape[1],
        'height': img.shape[0],
    }


# ------------------------------- /license ------------------------------- #
#
# T036 — the local API's facade over astros_licensing_service (Constitution
# Principle II: no reimplementation, delegate to the service). GET /status
# reuses the same real check the T016 gate runs (app.licensing.check_gate())
# — one source of truth for "is this installation allowed to work", not two
# independently-drifting implementations.

license_router = APIRouter()


class ActivateRequest(BaseModel):
    license_id: str


@license_router.get('/status', response_model=LicenseStatusResponse)
def get_status() -> LicenseStatusResponse:
    result = licensing.check_gate()
    return LicenseStatusResponse(
        state=result.state,
        installations_used=result.installations_used or 0,
        installations_limit=result.installations_limit or 0,
        offline_days_remaining=result.offline_days_remaining,
    )


@license_router.post('/activate')
def activate_license(payload: ActivateRequest) -> dict:
    if not settings.licensing_service_url:
        raise HTTPException(409, 'Nenhum serviço de licenciamento configurado.')
    identity = security.ensure_identity()
    try:
        security.activate(settings.licensing_service_url, payload.license_id, identity)
    except security.ProtectedLoadError as error:
        raise HTTPException(502, f'Não foi possível ativar a licença: {error}') from error
    licensing.record_successful_check()
    return {'ok': True}


@license_router.post('/release')
def release_license() -> dict:
    if not settings.licensing_service_url:
        raise HTTPException(409, 'Nenhum serviço de licenciamento configurado.')
    identity = security.ensure_identity()
    status = licensing.check_gate()
    if status.state == 'not_activated':
        raise HTTPException(409, 'Esta instalação não está ativada.')
    # check_gate() doesn't carry license_id (only installations_used/limit) —
    # ask the service directly, the one place that actually knows it.
    try:
        body = security.installation_status(settings.licensing_service_url, identity.install_id)
        security.release(settings.licensing_service_url, body['license_id'], identity.install_id)
    except (security.ProtectedLoadError, urllib.error.HTTPError) as error:
        raise HTTPException(502, f'Não foi possível liberar a instalação: {error}') from error
    return {'ok': True}


# ------------------------------- /ws/jobs/{job_id} (no prefix) ------------------------------- #

ws_router = APIRouter()


@ws_router.websocket('/ws/jobs/{job_id}')
async def job_progress(websocket: WebSocket, job_id: str):
    await websocket.accept()

    job = jobs.get_job(job_id)
    if job is None:
        await websocket.close(code=4404)
        return

    await websocket.send_json(_ws_job_view(job))

    queue = jobs.subscribe(job_id)
    try:
        while True:
            update = await queue.get()
            await websocket.send_json(_ws_job_view(update))
            if update['status'] in ('done', 'error', 'cancelled'):
                break
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        jobs.unsubscribe(job_id, queue)


def _ws_job_view(job: dict) -> dict:
    view = {k: v for k, v in job.items() if k not in ('input_path', 'queue_order')}
    view.setdefault('queue_position', jobs.queue_position(job['id']))
    return view


# ------------------------------- /media, /video ------------------------------- #
#
# specs/007-video-editor-player. Two properties hold across every route below,
# and test_video_contract_surface.py is what keeps them true:
#
#   1. Media is referenced by handle_id. The single exception is
#      POST /media/handles, which exists precisely so no other route needs a
#      path — the bounded exception added to Princípio XIII in constitution
#      v3.0.0.
#   2. No route accepts a codec, encoder, preset, CRF or pixel format. The
#      client sends container and profile; the backend resolves the rest
#      (Princípio V).

media_router = APIRouter()
video_router = APIRouter()


def _handle_error_status(reason: str) -> int:
    return {
        'not_found': 404,
        'unsupported_media': 415,
        'unreadable': 415,
        'source_changed': 409,
    }.get(reason, 422)


@media_router.post('/handles', response_model=MediaHandleResponse, status_code=201)
def register_media_handle(payload: MediaHandleRequest) -> MediaHandleResponse:
    """The one route permitted to accept a filesystem path — for every media kind.

    Conditions of the v3.0.0 exception enforced here: the path is validated
    before anything else is done with it (inside media_handles.register), and
    the response carries no path — MediaHandleResponse has no such field, so
    it cannot leak by accident.

    **Despacha pelo conteúdo, e o vídeo continua indo pelo caminho de sempre.**
    A Central de Compressão (specs/008) trabalha com quatro tipos de mídia e
    precisava registrar todos; abrir uma segunda rota de caminho para ela teria
    quebrado a terceira condição da exceção, que é justamente a que erode
    primeiro. Registrar tudo aqui mantém uma porta só.

    Um vídeo passa por `register`, que é o registro do editor, e a resposta sai
    byte a byte igual à de antes — o contrato da spec 007 não muda por causa de
    uma feature nova (FR-069). O resto passa por `register_media`, que detecta o
    tipo pelo conteúdo.
    """
    try:
        if _is_video(payload.path):
            handle_id = media_handles.register(payload.path)
        else:
            handle_id = media_handles.register_media(payload.path)
    except media_handles.HandleError as error:
        raise HTTPException(_handle_error_status(error.reason),
                            {'reason': error.reason, 'message': str(error)}) from error
    info = media_handles.describe(handle_id)
    # Só os campos que esta resposta declara: o registro da Central guarda mais
    # (bitrate, codec, canais), e é `GET /compression/media/{id}` que os entrega.
    conhecidos = MediaHandleResponse.model_fields
    return MediaHandleResponse(handle_id=handle_id,
                               **{k: v for k, v in info.items() if k in conhecidos})


def _is_video(path: str) -> bool:
    """Pelo **conteúdo**, não pela extensão.

    Um `.mp4` sem trilha de vídeo e um `.png` com bytes de vídeo existem, e é o
    que está dentro do arquivo que decide qual registro o descreve corretamente.
    """
    from app.compression import detect

    try:
        return detect.detect_media_kind(path) == 'video'
    except Exception:  # noqa: BLE001 — indecidível aqui vira recusa no registro
        return False


@media_router.get('/handles/{handle_id}', response_model=MediaHandleResponse)
def get_media_handle(handle_id: str) -> MediaHandleResponse:
    """Re-probe and return current metadata. A client compares the returned
    content_key against the one it cached to discover that its thumbnails
    belong to content that no longer exists (FR-017)."""
    try:
        metadata = media_handles.refresh(handle_id)
    except media_handles.HandleError as error:
        raise HTTPException(_handle_error_status(error.reason),
                            {'reason': error.reason, 'message': str(error)}) from error
    return MediaHandleResponse(handle_id=handle_id, **metadata)


@video_router.get('/export-options', response_model=VideoExportOptionsResponse)
def get_video_export_options() -> VideoExportOptionsResponse:
    """What this environment can actually produce.

    This is what makes FR-027 happen BEFORE a person chooses, rather than after
    an export fails. `available` comes from a functional probe — one real frame
    encoded — not from what ffmpeg lists as compiled in; on the development
    machine those two answers differ for all three H.264 encoders.
    """
    return VideoExportOptionsResponse(
        containers=[ContainerAvailability(**entry) for entry in video_edits.available_containers()],
        profiles=['fast', 'balanced', 'quality'],
        ceilings=VideoCeilingsResponse(**VIDEO_EDIT_CEILINGS._asdict()),
    )


compression_router = APIRouter()


@compression_router.get('/media/{handle_id}', response_model=CompressionMediaResponse)
def describe_compression_media(handle_id: str) -> CompressionMediaResponse:
    """O que a sondagem obteve sobre um arquivo já registrado (FR-008).

    **Não aceita caminho, e é por isso que existe separada.** A terceira condição
    da exceção do Princípio XIII (constituição v3.0.0) diz que só uma rota pode
    receber um caminho de disco, e ela é `POST /media/handles`. Uma segunda seria
    a erosão que a condição existe para impedir — sempre parece razoável deixar
    "só mais uma" receber um caminho.

    A Central então importa em dois passos: registra pela rota única e pergunta
    aqui o que precisa saber.
    """
    try:
        info = media_handles.describe(handle_id)
    except media_handles.HandleError as error:
        raise HTTPException(_handle_error_status(error.reason),
                            {'reason': error.reason, 'message': str(error)}) from error
    return CompressionMediaResponse(handle_id=handle_id, **info)


@compression_router.get('/capabilities', response_model=CompressionCapabilitiesResponse)
def get_compression_capabilities() -> CompressionCapabilitiesResponse:
    """O que esta máquina consegue produzir, por tipo de mídia.

    É a rota que torna FR-043 e FR-044 possíveis: a interface desabilita antes
    de a pessoa escolher, em vez de falhar depois. `available` sempre vem de
    sonda funcional — nesta máquina os três encoders H.264 de hardware estão
    listados pelo binário e nenhum codifica um quadro, e uma verificação por
    listagem ofereceria MP4/H.264 para morrer no meio da exportação.
    """
    return CompressionCapabilitiesResponse(**compression_capabilities.snapshot())


@compression_router.post('/estimate', response_model=CompressionEstimateResponse)
def estimate_compression(payload: CompressionEstimateRequest) -> CompressionEstimateResponse:
    """Quanto o arquivo vai pesar com estas configurações (FR-021).

    **Idempotente e sem efeito colateral.** É chamada a cada mudança de
    controle; criar job, escrever arquivo ou deixar temporário aqui seriam
    dezenas de resíduos por sessão. A amostragem de imagem vive em memória.

    `estimated_bytes` nulo é resposta legítima, não falha: modo de qualidade
    constante sem tabela calibrada e formatos sem perda dependem do conteúdo de
    um jeito que nenhum número único descreve. `confidence` e `assumptions`
    dizem à interface o que ela pode afirmar.
    """
    try:
        info = media_handles.describe(payload.handle_id)
        # `resolve` é o acessor interno; o caminho nunca entra numa resposta.
        source = media_handles.resolve(payload.handle_id)
    except media_handles.HandleError as error:
        raise HTTPException(_handle_error_status(error.reason),
                            {'reason': error.reason, 'message': str(error)}) from error

    alvo_bytes = None
    if payload.target is not None:
        alvo_bytes = compression_estimator.target_to_bytes(payload.target.value,
                                                           payload.target.unit)

    resultado = compression_estimator.estimate_for_kind(
        payload.media_kind, source, info, payload.settings, alvo_bytes)
    return CompressionEstimateResponse(**resultado.as_dict())


def _preset_error_status(reason: str) -> int:
    return {'not_found': 404, 'readonly_preset': 409}.get(reason, 422)


@compression_router.get('/presets', response_model=CompressionPresetsResponse)
def list_compression_presets(media_kind: str | None = None) -> CompressionPresetsResponse:
    """Internos, de plataforma e do usuário — filtrados por tipo de mídia quando
    pedido, porque um preset pertence a um só (FR-014)."""
    return CompressionPresetsResponse(
        presets=[CompressionPreset(**p) for p in compression_presets.all_presets(media_kind)])


@compression_router.post('/presets', response_model=CompressionPreset, status_code=201)
def create_compression_preset(payload: CompressionPresetCreateRequest) -> CompressionPreset:
    try:
        criado = compression_presets.create(payload.name, payload.media_kind, payload.settings)
    except compression_presets.PresetError as error:
        raise HTTPException(_preset_error_status(error.reason),
                            {'reason': error.reason, 'message': str(error)}) from error
    return CompressionPreset(**criado)


@compression_router.patch('/presets/{preset_id}', response_model=CompressionPreset)
def update_compression_preset(preset_id: str,
                              payload: CompressionPresetUpdateRequest) -> CompressionPreset:
    """Só `origin: user` aceita escrita. Um interno responde 409 em vez de
    aceitar e ignorar — aceitar seria prometer uma alteração que não acontece."""
    try:
        atualizado = compression_presets.update(preset_id, name=payload.name,
                                                settings=payload.settings)
    except compression_presets.PresetError as error:
        raise HTTPException(_preset_error_status(error.reason),
                            {'reason': error.reason, 'message': str(error)}) from error
    return CompressionPreset(**atualizado)


@compression_router.delete('/presets/{preset_id}', status_code=204)
def delete_compression_preset(preset_id: str) -> None:
    try:
        compression_presets.delete(preset_id)
    except compression_presets.PresetError as error:
        raise HTTPException(_preset_error_status(error.reason),
                            {'reason': error.reason, 'message': str(error)}) from error


@compression_router.post('/presets/{preset_id}/duplicate',
                         response_model=CompressionPreset, status_code=201)
def duplicate_compression_preset(preset_id: str, name: str) -> CompressionPreset:
    try:
        copia = compression_presets.duplicate(preset_id, name)
    except compression_presets.PresetError as error:
        raise HTTPException(_preset_error_status(error.reason),
                            {'reason': error.reason, 'message': str(error)}) from error
    return CompressionPreset(**copia)


_COMPRESSION_REFUSAL_STATUS = {
    'unsupported_media': 415,
    'unreadable': 415,
}


@compression_router.post('/jobs', response_model=CompressionJobResponse, status_code=202)
async def create_compression_job(payload: CompressionJobRequest) -> CompressionJobResponse:
    """Enfileira uma compressão — **depois** de recusar tudo que é recusável.

    Toda verificação aqui acontece antes de qualquer processamento (FR-064).
    Uma recusa que chega depois de a barra começar já custou o tempo da pessoa,
    e uma que chega no meio pode deixar um arquivo pela metade.
    """
    _enforce_license_gate()

    try:
        info = media_handles.describe(payload.handle_id)
        source = media_handles.resolve(payload.handle_id)
    except media_handles.HandleError as error:
        raise HTTPException(_handle_error_status(error.reason),
                            {'reason': error.reason, 'message': str(error)}) from error
    if source is None or not os.path.isfile(source):
        raise HTTPException(404, {'reason': 'not_found', 'message': 'Arquivo não encontrado.'})

    settings = dict(payload.settings)
    estimativa = None

    try:
        compression_runner.validate(payload.media_kind, settings, advanced=payload.advanced)

        if payload.target is not None:
            alvo = compression_estimator.target_to_bytes(payload.target.value,
                                                         payload.target.unit)
            estimativa = compression_estimator.estimate_for_kind(
                payload.media_kind, source, info, settings, alvo)
            if estimativa.feasibility == 'below_floor':
                raise compression_runner.CompressionRefused(
                    'target_below_floor',
                    'O tamanho pedido não é atingível sem destruir a mídia.')
            # As configurações derivadas do alvo entram de fato — sem isto o
            # alvo seria decoração, e o arquivo sairia com a qualidade padrão.
            settings.update(estimativa.resolved_settings or {})

        destino = _compression_output_path(source, payload)
        compression_runner.check_disk(source, os.path.dirname(destino))
    except compression_runner.CompressionRefused as error:
        raise HTTPException(
            _COMPRESSION_REFUSAL_STATUS.get(error.reason, 422),
            {'reason': error.reason, 'message': str(error), **error.detail}) from error

    job_id = jobs.create_job(
        source, info.get('display_name') or os.path.basename(source),
        {'media_kind': payload.media_kind, 'settings': settings,
         'output_path': destino, 'preset_id': payload.preset_id,
         'advanced': payload.advanced},
        media_type='image' if payload.media_kind == 'image' else 'video',
        operation='compression')
    await jobs.enqueue(job_id)

    return CompressionJobResponse(
        job_id=job_id, status=jobs.get_job(job_id)['status'],
        estimate=CompressionEstimateResponse(**estimativa.as_dict()) if estimativa else None)


def _compression_output_path(source: str, payload: CompressionJobRequest) -> str:
    """Onde o resultado vai, aplicando o padrão de nome (FR-060).

    **Nunca a origem** (Princípio XV/FR-059). A decisão é aqui e não confiada ao
    cliente: mesmo com `conflict_policy: overwrite`, sobrescrever o arquivo de
    onde a pessoa está partindo não é o que "substituir" significa.
    """
    diretorio = payload.export.directory or os.path.dirname(source) or settings.outputs_dir
    base = os.path.splitext(os.path.basename(source))[0]
    formato = (payload.settings.get('output_format') or '').lower()
    if not formato or formato == 'keep':
        extensao = os.path.splitext(source)[1].lstrip('.').lower()
    else:
        extensao = 'jpg' if formato == 'jpeg' else formato

    nome = payload.export.naming_pattern.format(
        filename=base,
        quality=payload.settings.get('quality', ''),
        resolution=_resolution_token(payload.settings),
        codec=payload.settings.get('video_codec') or payload.settings.get('codec') or '',
    ).strip('_- ') or f'{base}_compressed'

    destino = os.path.join(diretorio, f'{nome}.{extensao}')

    if os.path.abspath(destino) == os.path.abspath(source):
        destino = os.path.join(diretorio, f'{nome}_compressed.{extensao}')
    if os.path.exists(destino) and payload.export.conflict_policy != 'overwrite':
        destino = _free_path(destino)
    return destino


def _resolution_token(settings: dict) -> str:
    largura, altura = settings.get('width'), settings.get('height')
    if largura and altura:
        return f'{largura}x{altura}'
    return str(largura or altura or '')


image_router = APIRouter()


@image_router.get('/export-options', response_model=ImageExportOptionsResponse)
def get_image_export_options() -> ImageExportOptionsResponse:
    """What this machine can actually write, for the image export panel.

    The mirror of `GET /video/export-options`, and it exists for the same
    reason: an allowed format is not a present one. Image export re-encodes
    through OpenCV, and OpenCV builds differ in which codecs they carry — WebP
    and TIFF are optional, and headless is not the same build as full. Offering
    one the build cannot write means failing after the person chose, which is
    what Princípio XIII forbids.

    `available` is a functional probe — a real 4×4 image encoded — not a claim
    read off a table.
    """
    formats = []
    for value in get_args(ExportFormat):
        usable = image_format_works(f'.{value}')
        formats.append(ImageFormatAvailability(
            value=value,
            available=usable,
            unavailable_reason=None if usable else 'unsupported_build',
        ))
    return ImageExportOptionsResponse(formats=formats)


@media_router.get('/handles/{handle_id}/thumbnails')
def get_media_thumbnails(handle_id: str):
    """Timeline thumbnail sprite (FR-007a).

    The grid is described in headers rather than a JSON envelope so the image
    can be consumed directly by an <img> — wrapping it in base64 would inflate
    it by a third for no gain the caller can use.
    """
    metadata = None
    try:
        metadata = media_handles.refresh(handle_id)
        path = media_handles.resolve(handle_id)
        sprite = video_thumbnails.build(
            path, handle_id, metadata['content_key'],
            duration_seconds=metadata['duration_seconds'],
            source_width=metadata['width'], source_height=metadata['height'],
        )
    except media_handles.HandleError as error:
        raise HTTPException(_handle_error_status(error.reason),
                            {'reason': error.reason, 'message': str(error)}) from error

    # FR-017: sprites for older content of the same handle are removed, not just
    # bypassed — otherwise the cache grows every time someone re-exports over
    # their source.
    video_thumbnails.discard_stale(handle_id, metadata['content_key'])

    return FileResponse(sprite.path, media_type='image/jpeg', headers={
        'X-Astros-Thumb-Count': str(sprite.count),
        'X-Astros-Thumb-Interval': f'{sprite.interval_seconds:.6f}',
        'X-Astros-Thumb-Width': str(sprite.thumbnail_width),
        'X-Astros-Thumb-Height': str(sprite.thumbnail_height),
        # Without this the browser cannot read the headers above: the renderer
        # is a different origin from the API.
        'Access-Control-Expose-Headers':
            'X-Astros-Thumb-Count, X-Astros-Thumb-Interval, X-Astros-Thumb-Width, X-Astros-Thumb-Height',
    })


@media_router.post('/handles/{handle_id}/preview-frame')
def preview_video_frame(handle_id: str, payload: VideoPreviewFrameRequest):
    """One frame at a position, rendered through the real filter graph (FR-015,
    research.md Decisão 2).

    This is the second preview tier: the renderer's shader reproduces the colour
    and hue passes exactly, but not denoise, blur, grain or unsharp. Rather than approximate
    those on the GPU — which would produce a convincing and wrong picture — the
    frame is rendered here by the same FFmpeg that will perform the export, and
    returned as a before/after pair.

    Reduced in resolution and written to a temporary file that is removed on
    every exit path, success or failure alike (FR-016, FR-022). It is never the
    result of an operation.
    """
    path = media_handles.resolve(handle_id)
    if path is None:
        raise HTTPException(404, {'reason': 'not_found', 'message': 'Identificador desconhecido.'})
    if media_handles.has_content_changed(handle_id):
        raise HTTPException(409, {'reason': 'source_changed',
                                  'message': 'O arquivo de origem mudou desde o registro.'})

    metadata = media_handles.describe(handle_id)
    edits = payload.edits.model_dump()
    temp_dir = tempfile.mkdtemp(prefix='astros_preview_')
    try:
        before = os.path.join(temp_dir, 'before.png')
        after = os.path.join(temp_dir, 'after.png')

        video_edits.render_frame(path, before, payload.time_seconds, {},
                                 source_width=metadata['width'], source_height=metadata['height'])
        video_edits.render_frame(path, after, payload.time_seconds, edits,
                                 source_width=metadata['width'], source_height=metadata['height'])

        with open(before, 'rb') as f:
            before_bytes = f.read()
        with open(after, 'rb') as f:
            after_bytes = f.read()
    except video_edits.EditError as error:
        raise HTTPException(422, {'reason': error.reason, 'message': str(error)}) from error
    except (OSError, RuntimeError) as error:
        raise HTTPException(422, {'reason': 'preview_failed', 'message': str(error)}) from error
    finally:
        # Every exit path, not only the happy one (FR-022). A preview that
        # leaves files behind would accumulate one pair per slider movement.
        shutil.rmtree(temp_dir, ignore_errors=True)

    return {
        'before': base64.b64encode(before_bytes).decode('ascii'),
        'after': base64.b64encode(after_bytes).decode('ascii'),
    }


@video_router.post('/edit-jobs', status_code=202)
async def create_video_edit_job(payload: VideoExportRequest):
    """Create an export (FR-013f, FR-021).

    Everything that can refuse does so BEFORE the job exists, so a refusal never
    arrives after minutes of processing (FR-025). Four reasons, in the order a
    person would hit them:

      source_changed        the file is not what was registered
      ceiling_exceeded      this job is unreasonable, whatever the machine
      hardware_insufficient this machine cannot cope
      encoder_unavailable   nothing here can write that container

    The job itself then rides the existing job system — progress, cancellation
    and the WebSocket are the ones every other operation uses.
    """
    _enforce_license_gate()

    input_path = media_handles.resolve(payload.handle_id)
    if input_path is None:
        raise HTTPException(404, {'reason': 'not_found', 'message': 'Identificador desconhecido.'})
    if media_handles.has_content_changed(payload.handle_id):
        raise HTTPException(409, {'reason': 'source_changed',
                                  'message': 'O arquivo de origem mudou desde o registro.'})

    metadata = media_handles.describe(payload.handle_id)
    edits = payload.edits.model_dump()

    # The ceiling is checked against the OUTPUT: a 30-second trim out of a
    # three-hour recording is thirty seconds of work (T014).
    trim = edits.get('trim')
    duration = (trim['end_seconds'] - trim['start_seconds']) if trim else metadata['duration_seconds']
    transform = edits.get('transform') or {}
    crop = transform.get('crop')
    width = (transform.get('output_width') or (crop or {}).get('width') or metadata['width'] or 0)
    height = (transform.get('output_height') or (crop or {}).get('height') or metadata['height'] or 0)

    try:
        video_edits.check_ceilings(video_edits.OperationSize(
            duration_seconds=duration, width=int(width), height=int(height),
            frame_rate=metadata['frame_rate'] or 30.0, size_bytes=metadata['size_bytes'],
        ))
        video_edits.resolve_encoder(payload.container, payload.profile,
                                    want_audio=metadata['has_audio'])
        video_edits.check_disk_space(
            payload.output_directory or os.path.dirname(input_path), metadata['size_bytes'])
    except video_edits.EditError as error:
        raise HTTPException(422, {'reason': error.reason, 'message': str(error), **error.detail}) from error

    # The machine-capacity floor is a separate question from the ceilings above,
    # and both have to pass (plan.md, Complexity Tracking).
    from astros_upscale.processing import detect_hardware

    capacity = processing.check_capacity(
        detect_hardware(), 'video', width=int(width), height=int(height), duration_seconds=duration)
    if not capacity.fits:
        raise HTTPException(422, {'reason': 'hardware_insufficient',
                                  'limiting_resource': capacity.limiting_resource,
                                  'message': 'Este equipamento não tem capacidade para esta exportação.'})

    job_id = jobs.create_job(
        input_path=input_path,
        filename=media_handles.sanitise_display_name(payload.output_filename or metadata['display_name']),
        media_type='video',
        operation='video_edit',
        params={
            'edits': edits,
            'container': payload.container,
            'profile': payload.profile,
            'source_width': metadata['width'],
            'source_height': metadata['height'],
            'has_audio': metadata['has_audio'],
            'output_target': {
                'format': payload.container,
                'directory': payload.output_directory,
                'filename': payload.output_filename,
                'conflict': payload.conflict,
            },
        },
    )
    jobs.set_capacity_check(job_id, True, capacity.estimated_duration, None)
    await jobs.enqueue(job_id)

    return {'job_id': job_id, 'status': 'queued',
            'estimated_duration_seconds': capacity.estimated_duration}
