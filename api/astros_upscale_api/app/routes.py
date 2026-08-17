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
import urllib.error

import cv2
from fastapi import APIRouter, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import jobs, licensing, media_handles, processing, security, video_edits
from app.config import VIDEO_EDIT_CEILINGS, settings
from app.licensing import UnresolvableRequestError
from app.schemas import (Adjustments, Component, ComponentDetails, ContainerAvailability,
                         DetectContentTypeRequest, ExportRequest, LicenseStatusResponse,
                         LocalJobRequest, MediaHandleRequest, MediaHandleResponse, MediaRequest,
                         VideoCeilingsResponse, VideoExportOptionsResponse)

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


def _detect_content_type(media_type: str, input_path: str) -> str:
    """Real detection (T008/T056) — image and audio have a real classifier;
    video content type (real_video/anime_video) has no automatic classifier
    and always requires content_type_override. Shared by POST
    /content-type/detect (called by the UI before a Job exists, so its
    editable indicator, FR-096, shows a real default) and
    _resolve_content_type below (job creation)."""
    if media_type == 'image':
        return _detect_image_content_type(input_path)
    if media_type == 'audio':
        return _detect_audio_content_type(input_path)
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
    name = payload.filename or os.path.splitext(job['input_file'])[0] + '_upscaled' + ext
    if not name.lower().endswith(ext):
        name = os.path.splitext(name)[0] + ext
    output_dir = payload.output_dir or os.path.dirname(job['input_path']) or settings.outputs_dir
    output_path = os.path.join(output_dir, name)

    if os.path.exists(output_path):
        if payload.conflict == 'ask':
            raise HTTPException(409, {'reason': 'conflict', 'path': output_path})
        if payload.conflict == 'rename':
            base, ext2 = os.path.splitext(output_path)
            n = 1
            while os.path.exists(output_path):
                output_path = f'{base} ({n}){ext2}'
                n += 1
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
    """The one route permitted to accept a filesystem path.

    Conditions of the v3.0.0 exception enforced here: the path is validated
    before anything else is done with it (inside media_handles.register), and
    the response carries no path — MediaHandleResponse has no such field, so
    it cannot leak by accident.
    """
    try:
        handle_id = media_handles.register(payload.path)
    except media_handles.HandleError as error:
        raise HTTPException(_handle_error_status(error.reason),
                            {'reason': error.reason, 'message': str(error)}) from error
    return MediaHandleResponse(handle_id=handle_id, **media_handles.describe(handle_id))


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
