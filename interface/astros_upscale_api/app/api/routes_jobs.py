import os

from fastapi import APIRouter, Form, HTTPException, UploadFile

from app.config import settings
from app.core import job_manager, license_gate
from app.core.profile_resolver import UnresolvableRequestError
from app.models.schemas import Adjustments, DetectContentTypeRequest, ExportRequest, LocalJobRequest, MediaRequest

router = APIRouter()

_INTERNAL_FIELDS = ('input_path', 'queue_order')


def _enforce_license_gate() -> None:
    """FR-051/FR-060: every POST /jobs* route calls this before a job is
    created. `blocked`/`not_activated` refuse outright; every other state
    (including today's default, no license infra deployed) lets the request
    through — see license_gate.py."""
    result = license_gate.check_gate()
    if not result.allowed:
        raise HTTPException(403, {'error_category': 'license_invalid', 'message': result.message})


def _detect_image_content_type(input_path: str) -> str:
    from astros_upscale.content_type import classify_image
    from astros_upscale.utils.image_io import ImageOpenError, imread

    try:
        image = imread(input_path)
    except ImageOpenError as error:
        raise HTTPException(422, f'Não foi possível ler a imagem para detectar o tipo de conteúdo: {error}') from error
    return classify_image(image).content_type


def _detect_audio_content_type(input_path: str) -> str:
    """T056 — wires content_type.py's real VAD+harmonic/percussive classifier
    (T008) into the job-creation path, same shared function image detection
    already uses. Converts to WAV via ffmpeg first so any ffmpeg-readable
    input format (mp3/flac/a video file's audio track...) works, not just wav."""
    import tempfile

    import soundfile as sf

    from astros_upscale.content_type import classify_audio
    from astros_upscale.media_engine.transcode import run_ffmpeg

    tmp_wav = tempfile.mktemp(suffix='.wav')
    try:
        run_ffmpeg(lambda f: f.input(input_path).output(tmp_wav, {'vn': None, 'acodec': 'pcm_s16le'}))
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
    resolve to a fixed ffmpeg/OpenCV path regardless of it (profile_resolver.py
    mirrors this same rule), so this never runs detection, or requires an
    override, for those operations."""
    if media_request.operation != 'enhance':
        return media_request.content_type_override
    if media_request.content_type_override:
        return media_request.content_type_override
    return _detect_content_type(media_request.media_type, input_path)


@router.post('/detect-content-type')
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
    from app.core import profile_resolver

    try:
        profile_resolver.resolve(profile_resolver.MediaRequest(
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
    from app.core import capacity
    from astros_upscale.hardware import detect_hardware

    hardware = detect_hardware()
    width = height = None
    duration_seconds = None
    if media_request.media_type == 'image':
        import cv2

        image = cv2.imread(input_path)
        if image is not None:
            height, width = image.shape[:2]
    elif media_request.media_type == 'video':
        from astros_upscale.media_engine.probe import ProbeError, probe_streams

        try:
            info = probe_streams(input_path)
            duration_seconds = info['duration_seconds']
        except ProbeError:
            pass
        import cv2

        cap = cv2.VideoCapture(input_path)
        if cap.isOpened():
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or None
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or None
        cap.release()
    elif media_request.media_type == 'audio':
        from astros_upscale.media_engine.probe import ProbeError, probe_streams

        try:
            duration_seconds = probe_streams(input_path)['duration_seconds']
        except ProbeError:
            pass

    return capacity.check_capacity(
        hardware, media_request.media_type, width=width, height=height, duration_seconds=duration_seconds)


def _detect_secondary_elements(media_request: MediaRequest, input_path: str) -> dict | None:
    """FR-081/FR-085: only video-enhance jobs can lose extra audio tracks,
    subtitles or chapters (the video pipeline only carries one video + one
    audio stream through) — every other media_type/operation combination
    never has anything at stake, so this returns None (no prompt, ever) for
    them instead of probing a file that was never going to lose anything."""
    if media_request.media_type != 'video' or media_request.operation != 'enhance':
        return None
    from astros_upscale.media_engine.probe import ProbeError, detect_secondary_elements

    try:
        return detect_secondary_elements(input_path)
    except ProbeError as error:
        raise HTTPException(422, f'Não foi possível inspecionar o vídeo: {error}') from error


def _build_job_params(media_request: MediaRequest, adjustments: Adjustments) -> dict:
    """What job_manager.py actually stores as `job['params']` — intent only
    (scale/profile/device/adjustments), never a model/engine identifier
    (FR-009/FR-011). The engine_ref profile_resolver.py resolves at
    processing time (job_manager._process_job) never lands here."""
    return {
        'scale': media_request.scale,
        'profile': media_request.profile,
        'device': media_request.device,
        'custom_size': media_request.custom_size.model_dump() if media_request.custom_size else None,
        'adjustments': adjustments.model_dump(),
        'quality': media_request.quality,
        'output_target': media_request.output_target.model_dump() if media_request.output_target else None,
    }


@router.post('')
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
    job_id = job_manager.create_job(
        dest_path, file.filename, _build_job_params(media_req, adj),
        media_type=media_req.media_type, operation=media_req.operation, content_type_detected=content_type,
        secondary_elements=secondary_elements, secondary_elements_ack=media_req.secondary_elements_ack,
    )
    if capacity_result is not None:
        job_manager.set_capacity_check(job_id, True, capacity_result.estimated_duration, None)
    # T063/FR-078 — surfaced right in the creation response, so the client
    # can decide whether to proceed with a long job without a follow-up GET.
    return {'id': job_id, 'estimated_duration': capacity_result.estimated_duration if capacity_result else None}


@router.post('/local')
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
    job_id = job_manager.create_job(
        input_path, filename, _build_job_params(payload.media_request, payload.adjustments),
        media_type=payload.media_request.media_type, operation=payload.media_request.operation,
        content_type_detected=content_type,
        secondary_elements=secondary_elements, secondary_elements_ack=payload.media_request.secondary_elements_ack,
    )
    if capacity_result is not None:
        job_manager.set_capacity_check(job_id, True, capacity_result.estimated_duration, None)
    return {'id': job_id, 'estimated_duration': capacity_result.estimated_duration if capacity_result else None}


@router.get('')
def list_jobs():
    return {'jobs': [_public_view(job) for job in job_manager.list_jobs()]}


@router.get('/{job_id}')
def get_job(job_id: str):
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(404, 'Job não encontrado.')
    return _public_view(job)


@router.delete('/{job_id}')
def delete_job(job_id: str):
    if not job_manager.cancel_job(job_id):
        raise HTTPException(404, 'Job não encontrado.')
    return {'ok': True}


_FORBIDDEN_PARAM_KEYS = ('model', 'engine', 'checkpoint_id')


@router.patch('/{job_id}/params')
def update_job_params(job_id: str, params: dict):
    leaked = [key for key in params if key in _FORBIDDEN_PARAM_KEYS]
    if leaked:
        raise HTTPException(422, f'Campo(s) não permitido(s): {", ".join(leaked)} (FR-011).')
    if not job_manager.update_params(job_id, params):
        raise HTTPException(409, 'Job não encontrado ou já iniciado.')
    return _public_view(job_manager.get_job(job_id))


@router.post('/{job_id}/confirm-secondary-elements')
def confirm_secondary_elements(job_id: str):
    """FR-081/FR-085: moves a video-enhance job out of pending_confirmation
    once the person has seen and accepted what will be lost (extra audio
    tracks/subtitles/chapters). 404 covers both "no such job" and "job
    wasn't waiting on this in the first place" — job_manager.py already
    treats those as the same real state (nothing to confirm)."""
    if not job_manager.confirm_secondary_elements(job_id):
        raise HTTPException(404, 'Job não encontrado ou não está aguardando confirmação.')
    return _public_view(job_manager.get_job(job_id))


@router.post('/{job_id}/process')
async def process_job(job_id: str):
    _enforce_license_gate()
    if not await job_manager.enqueue(job_id):
        raise HTTPException(409, 'Job não encontrado ou já processado.')
    return {'ok': True}


@router.post('/{job_id}/export')
def export_job(job_id: str, payload: ExportRequest):
    """Re-encodes a done job's already-upscaled result to the requested format,
    quality and destination. Never re-runs the model (see upscaler.py/job_manager.py)."""
    job = job_manager.get_job(job_id)
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
        job_manager.export_job(job_id, output_path, payload.quality)
    except ValueError as error:
        raise HTTPException(409, str(error))
    return {'output_path': output_path}


def _public_view(job: dict) -> dict:
    view = {k: v for k, v in job.items() if k not in _INTERNAL_FIELDS}
    view['queue_position'] = job_manager.queue_position(job['id'])
    return view
