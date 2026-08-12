"""In-memory job store + a single-worker asyncio queue.

Deliberately simple (asyncio.Queue, dict) for the local/single-user case. If
this API is ever hosted for multiple concurrent users, swap _queue/jobs for
Redis + RQ/Celery — the route layer (routes_jobs.py) doesn't need to change,
only this module.

Status lifecycle: pending (created, being configured) -> queued (user clicked
"process", waiting its turn — concurrency is 1, enforced by _executor's single
worker thread) -> processing -> done | error | cancelled. Export is a separate,
much cheaper step handled by export_job() below — it never touches this state
machine or re-runs the model, it only reads the master PNG process_job() wrote.
"""
from __future__ import annotations

import asyncio
import itertools
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import uuid4

from app.config import settings
from app.core import worker_supervisor
from app.core.upscaler import Upscaler
from app.core.worker_supervisor import WorkerCrashed, WorkerFailure
from astros_upscale.utils.image_io import ImageOpenError

jobs: dict[str, dict[str, Any]] = {}


class HardwareInsufficientError(Exception):
    """Raised when the capacity check (FR-076 to FR-080, wired in T062) determines
    the input can't fit this machine's hardware — a named limiting resource, not a
    generic failure. Distinct from out_of_memory (a runtime OOM during processing):
    this is a pre-flight refusal, before any processing starts."""


class LicenseInvalidError(Exception):
    """Raised by the license gate (T016) when a job is attempted while
    license.state is `blocked`/`not_activated` (FR-051/FR-060)."""

_queue: 'asyncio.Queue[str]' = asyncio.Queue()
_listeners: dict[str, list['asyncio.Queue[dict]']] = {}
# Bridges the blocking IPC call to the isolated worker process (worker_supervisor)
# onto the asyncio loop — the actual model inference no longer runs on this thread,
# it runs in a separate OS process (see docs/processing-protection-architecture.md,
# Fase 1). One thread because the isolated worker itself only handles one job at a
# time, matching the previous single-worker semantics.
_executor = ThreadPoolExecutor(max_workers=1)
_worker_task: asyncio.Task | None = None
_watchdog_task: asyncio.Task | None = None
_enqueue_counter = itertools.count(1)
_processing_job_id: str | None = None


def _now_iso() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _master_path(job_id: str) -> str:
    return os.path.join(settings.outputs_dir, f'{job_id}_master.png')


def _video_output_path(job_id: str) -> str:
    """Unlike the image path's master PNG (re-exportable to any format/quality
    later), a video job's output is the real, final file the moment
    VideoUpscaler.process() returns — there is no cheap re-encode step for
    video yet, so this IS what job['output_path'] points at."""
    return os.path.join(settings.outputs_dir, f'{job_id}.mp4')


def _audio_output_path(job_id: str, input_path: str) -> str:
    """Same reasoning as _video_output_path — audio_processor.py writes the
    real, final result directly, preserving the original file's format."""
    ext = os.path.splitext(input_path)[1] or '.wav'
    return os.path.join(settings.outputs_dir, f'{job_id}{ext}')


def _compress_convert_output_path(job: dict, params: dict) -> str:
    """Where a compress/convert job's real (non-cached, final) output goes —
    unlike enhance, there's no lossless "master" to re-export later, so this
    path is the actual, final result the moment optimize_file() returns."""
    input_path = job['input_path']
    output_target = params.get('output_target') or {}
    fmt = (output_target.get('format') or os.path.splitext(input_path)[1].lstrip('.')).lstrip('.').lower()
    directory = output_target.get('directory') or os.path.dirname(input_path) or settings.outputs_dir
    stem = os.path.splitext(os.path.basename(input_path))[0]
    filename = output_target.get('filename') or f'{stem}.{fmt}'
    if not filename.lower().endswith(f'.{fmt}'):
        filename = os.path.splitext(filename)[0] + f'.{fmt}'
    output_path = os.path.join(directory, filename)

    conflict = output_target.get('conflict', 'rename')
    if os.path.exists(output_path) and conflict != 'overwrite':
        # 'ask' can't actually prompt from here (processing already started) —
        # renaming is the safe default that never destroys an existing file.
        base, ext = os.path.splitext(output_path)
        n = 1
        while os.path.exists(output_path):
            output_path = f'{base} ({n}){ext}'
            n += 1
    return output_path


def _run_compress_convert(job: dict, params: dict, on_progress, on_stage) -> dict:
    """FR-025 to FR-030: real ffmpeg/OpenCV transcoding, never an AI model —
    this never touches profile_resolver.py or worker_supervisor.py, both of
    which exist specifically for the AI-model path (T012/T014)."""
    from astros_upscale.optimize import optimize_file

    output_path = _compress_convert_output_path(job, params)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
    if on_stage:
        on_stage('Comprimindo' if job.get('operation') == 'compress' else 'Convertendo')
    optimize_file(job['input_path'], output_path, quality=params.get('quality') or 80)
    if on_progress:
        on_progress(100)
    return {
        'output_path': output_path,
        'size_bytes': os.path.getsize(output_path) if os.path.isfile(output_path) else None,
    }


def create_job(
        input_path: str, filename: str, params: dict,
        media_type: str = 'image', operation: str = 'enhance',
        content_type_detected: str | None = None,
        secondary_elements: dict | None = None, secondary_elements_ack: bool = False) -> str:
    """`secondary_elements` (T047, FR-081 to FR-086): when the caller (routes_jobs.py)
    already probed the file and found something enhance would silently drop
    (extra audio tracks, subtitles, chapters) and the person hasn't already
    confirmed via `secondary_elements_ack` in the original request, the job is
    created directly in `pending_confirmation` — never `pending` — so
    enqueue() (which only accepts `pending`) refuses it until
    confirm_secondary_elements() runs."""
    job_id = f'job_{uuid4().hex[:8]}'
    needs_confirmation = bool(
        secondary_elements and secondary_elements.get('has_losses') and not secondary_elements_ack)
    jobs[job_id] = {
        'id': job_id,
        'status': 'pending_confirmation' if needs_confirmation else 'pending',
        'media_type': media_type,
        'operation': operation,
        'content_type_detected': content_type_detected,
        'secondary_elements': secondary_elements,
        'progress': 0,
        'stage': None,
        'eta_seconds': None,
        'queue_order': None,
        'input_file': filename,
        'input_path': input_path,
        'output_path': None,
        'error': None,
        'error_category': None,
        'capacity_check': None,
        'created_at': _now_iso(),
        'processing_started_at': None,
        'processing_ended_at': None,
        'source_meta': None,
        'output_meta': None,
        'params': params,
    }
    return job_id


def confirm_secondary_elements(job_id: str) -> bool:
    """FR-082/FR-084: the person has seen what would be lost and explicitly
    proceeds. Only valid from `pending_confirmation` — returns False (no-op)
    for a job that was never in that state, already confirmed, or gone."""
    job = jobs.get(job_id)
    if job is None or job['status'] != 'pending_confirmation':
        return False
    job['status'] = 'pending'
    _notify(job_id)
    return True


def set_content_type_detected(job_id: str, content_type: str) -> bool:
    """Records the automatic content-type classification (or the person's
    content_type_override, FR-096) once it's known — may run after create_job()
    since classification needs the uploaded file's bytes."""
    job = jobs.get(job_id)
    if job is None:
        return False
    job['content_type_detected'] = content_type
    _notify(job_id)
    return True


def set_capacity_check(job_id: str, fits: bool, estimated_duration: float | None,
                        limiting_resource: str | None) -> bool:
    """Records the FR-076 to FR-080 capacity-check result (real computation lands
    in T062) ahead of processing. `limiting_resource` is only meaningful when
    `fits` is False — e.g. 'vram', 'ram', 'disk'."""
    job = jobs.get(job_id)
    if job is None:
        return False
    job['capacity_check'] = {
        'fits': fits, 'estimated_duration': estimated_duration, 'limiting_resource': limiting_resource,
    }
    _notify(job_id)
    return True


def get_job(job_id: str) -> dict | None:
    return jobs.get(job_id)


def list_jobs() -> list[dict]:
    return list(jobs.values())


def queue_position(job_id: str) -> int | None:
    job = jobs.get(job_id)
    if job is None or job['status'] != 'queued' or job['queue_order'] is None:
        return None
    ahead = sum(
        1 for other in jobs.values()
        if other['status'] == 'queued' and other['queue_order'] is not None
        and other['queue_order'] < job['queue_order']
    )
    return ahead + 1


def update_params(job_id: str, params: dict) -> bool:
    job = jobs.get(job_id)
    if job is None or job['status'] != 'pending':
        return False
    job['params'].update(params)
    return True


def cancel_job(job_id: str) -> bool:
    """Cancels a job. Jobs still 'pending'/'queued' are cancelled outright. A job
    already 'processing' runs in the isolated worker process (Fase 1), so it can
    actually be killed instead of just having its result discarded — this stops
    wasted GPU/CPU work immediately rather than letting it run to completion for
    nothing. The worker is respawned lazily on the next job."""
    job = jobs.get(job_id)
    if job is None:
        return False
    if job['status'] in ('pending', 'queued', 'processing'):
        was_processing = job['status'] == 'processing' and job_id == _processing_job_id
        job['status'] = 'cancelled'
        _notify(job_id)
        if was_processing:
            worker_supervisor.get_supervisor().terminate()
    return True


async def enqueue(job_id: str) -> bool:
    job = jobs.get(job_id)
    if job is None or job['status'] != 'pending':
        return False
    job['status'] = 'queued'
    job['queue_order'] = next(_enqueue_counter)
    _notify(job_id)
    await _queue.put(job_id)
    return True


def subscribe(job_id: str) -> 'asyncio.Queue[dict]':
    q: 'asyncio.Queue[dict]' = asyncio.Queue()
    _listeners.setdefault(job_id, []).append(q)
    return q


def unsubscribe(job_id: str, q: 'asyncio.Queue[dict]') -> None:
    listeners = _listeners.get(job_id, [])
    if q in listeners:
        listeners.remove(q)


def _notify(job_id: str) -> None:
    job = jobs.get(job_id)
    if job is None:
        return
    view = dict(job)
    view['queue_position'] = queue_position(job_id)
    for q in _listeners.get(job_id, []):
        q.put_nowait(view)


def _categorize_error(error: Exception) -> str:
    if isinstance(error, HardwareInsufficientError):
        return 'hardware_insufficient'
    if isinstance(error, LicenseInvalidError):
        return 'license_invalid'
    if isinstance(error, WorkerCrashed):
        return 'model_failure'
    text = str(error).lower()
    if isinstance(error, MemoryError) or 'out of memory' in text or 'cuda out of memory' in text:
        return 'out_of_memory'
    if isinstance(error, OSError) and ('no space left' in text or 'disk full' in text):
        return 'disk_full'
    if isinstance(error, ImageOpenError) or 'cannot identify image' in text or 'corrupt' in text:
        return 'corrupted_input'
    return 'model_failure'


async def _process_job(job_id: str) -> None:
    global _processing_job_id
    job = jobs[job_id]
    if job['status'] == 'cancelled':
        return
    job['status'] = 'processing'
    job['processing_started_at'] = _now_iso()
    _processing_job_id = job_id
    _notify(job_id)

    loop = asyncio.get_running_loop()
    params = job['params']

    def on_progress(pct: int) -> None:
        if job['status'] == 'cancelled':
            return
        job['progress'] = pct
        loop.call_soon_threadsafe(_notify, job_id)

    def on_stage(stage: str) -> None:
        if job['status'] == 'cancelled':
            return
        job['stage'] = stage
        loop.call_soon_threadsafe(_notify, job_id)

    def blocking_run():
        if job.get('operation') in ('compress', 'convert'):
            return _run_compress_convert(job, params, on_progress, on_stage)

        from app.core import profile_resolver

        custom = params.get('custom_size')
        adjustments = params.get('adjustments', {})
        denoise = adjustments.get('denoise', 50)
        sharpen = adjustments.get('deblur', 0)
        face_recovery = adjustments.get('face_correction', False)
        face_recovery_strength = adjustments.get('face_recovery_strength', 80)
        denoise_filter_strength = adjustments.get('denoise_filter_strength', 0) if adjustments.get('denoise_filter_enabled') else 0

        # The one place a job's intent (content_type/scale/profile) becomes an
        # internal engine_ref — resolved fresh here, never stored on the job
        # dict itself, so nothing HTTP/WS-visible (job_manager.jobs, _notify)
        # ever carries a model identifier (FR-009/FR-011).
        pipeline = profile_resolver.resolve(profile_resolver.MediaRequest(
            media_type=job.get('media_type', 'image'), operation=job.get('operation', 'enhance'),
            content_type=job.get('content_type_detected'), scale=params.get('scale'), profile=params.get('profile'),
        ))
        scale_int = int(str(params.get('scale') or '4x').rstrip('xX'))

        protected = None
        if settings.licensing_service_url:
            # Fase 4 — fetch the orchestration logic from the licensing service
            # instead of the worker's static import. Empty licensing_service_url
            # (the default: no license infra deployed) keeps today's behavior.
            protected = {
                'base_url': settings.licensing_service_url,
                'trusted_pubkey_b64': settings.licensing_service_public_key_b64,
                'model': pipeline.engine_ref,
                'version': 'latest',
            }
        is_video = job.get('media_type') == 'video'
        is_audio = job.get('media_type') == 'audio'
        if is_audio:
            output_path = _audio_output_path(job_id, job['input_path'])
        elif is_video:
            output_path = _video_output_path(job_id)
        else:
            output_path = _master_path(job_id)
        # Runs in the isolated worker process (Fase 1), not on this thread — this
        # call just relays the request over IPC and blocks for the reply.
        return worker_supervisor.get_supervisor().process(
            job_id=job_id,
            media_type=job.get('media_type', 'image'),
            operation=job.get('operation', 'enhance'),
            input_path=job['input_path'],
            master_path=output_path,
            model=pipeline.engine_ref,
            models_dir=settings.models_dir,
            device=params.get('device'),
            scale=scale_int,
            custom_size=custom,
            denoise=denoise,
            sharpen=sharpen,
            face_recovery=face_recovery,
            face_recovery_strength=face_recovery_strength,
            denoise_filter_strength=denoise_filter_strength,
            half=pipeline.execution_params.get('half', True),
            on_progress=on_progress,
            on_stage=on_stage,
            protected=protected,
            stabilize=bool(params.get('stabilize', False)) if is_video else False,
            tile_threshold=pipeline.execution_params.get('tile_threshold'),
            tile_size=pipeline.execution_params.get('tile_size'),
        )

    try:
        result_meta = await loop.run_in_executor(_executor, blocking_run)
        if job['status'] == 'cancelled':
            _notify(job_id)
            return
        job['status'] = 'done'
        job['progress'] = 100
        job['stage'] = None
        job['processing_ended_at'] = _now_iso()
        if job.get('operation') in ('compress', 'convert'):
            # No lossless "master" here (unlike enhance) — optimize_file()
            # already wrote the real, final result.
            job['output_path'] = result_meta['output_path']
            job['source_meta'] = {
                'width': None, 'height': None,
                'size_bytes': os.path.getsize(job['input_path']) if os.path.isfile(job['input_path']) else None,
            }
            job['output_meta'] = {'width': None, 'height': None, 'size_bytes': result_meta['size_bytes']}
        elif job.get('media_type') == 'video':
            # No separate "master" for video (unlike image) — VideoUpscaler
            # already wrote the real, final, audio-muxed file.
            video_path = _video_output_path(job_id)
            source_w, source_h = result_meta['source_size']
            output_w, output_h = result_meta['output_size']
            job['output_path'] = video_path
            job['source_meta'] = {
                'width': source_w, 'height': source_h,
                'size_bytes': os.path.getsize(job['input_path']) if os.path.isfile(job['input_path']) else None,
            }
            job['output_meta'] = {
                'width': output_w, 'height': output_h,
                'size_bytes': os.path.getsize(video_path) if os.path.isfile(video_path) else None,
            }
        elif job.get('media_type') == 'audio':
            # No pixel dimensions for audio (SizeMeta.width/height stay None,
            # same as compress/convert) — duration/channels live in `params`
            # via audio_meta instead, there is no dedicated schema field for them.
            audio_path = _audio_output_path(job_id, job['input_path'])
            job['output_path'] = audio_path
            job['source_meta'] = {
                'width': None, 'height': None,
                'size_bytes': os.path.getsize(job['input_path']) if os.path.isfile(job['input_path']) else None,
            }
            job['output_meta'] = {
                'width': None, 'height': None,
                'size_bytes': os.path.getsize(audio_path) if os.path.isfile(audio_path) else None,
            }
        else:
            master_path = _master_path(job_id)
            source_w, source_h = result_meta['source_size']
            output_w, output_h = result_meta['output_size']
            job['source_meta'] = {
                'width': source_w, 'height': source_h,
                'size_bytes': os.path.getsize(job['input_path']) if os.path.isfile(job['input_path']) else None,
            }
            job['output_meta'] = {
                'width': output_w, 'height': output_h,
                'size_bytes': os.path.getsize(master_path) if os.path.isfile(master_path) else None,
            }
    except WorkerFailure as error:
        if job['status'] != 'cancelled':
            job['status'] = 'error'
            job['error'] = str(error)
            job['error_category'] = _categorize_error(error)
    except Exception as error:  # noqa: BLE001 - surfaced to the client as job.error
        if job['status'] != 'cancelled':
            job['status'] = 'error'
            job['error'] = str(error)
            job['error_category'] = _categorize_error(error)
    finally:
        _processing_job_id = None
    _notify(job_id)


async def _worker_loop() -> None:
    while True:
        job_id = await _queue.get()
        try:
            await _process_job(job_id)
        finally:
            _queue.task_done()


async def _watchdog_loop(interval_seconds: float = 20.0) -> None:
    """Detects a worker that died or stopped responding between jobs and kills
    it so the next job spawns a fresh one, instead of hanging forever waiting
    on a dead pipe. Doesn't touch a worker that's mid-job (ping is only sent
    when idle) to avoid false positives on long GPU-bound work.

    T067 — already media_type-agnostic by construction: `_processing_job_id`
    and `worker_supervisor` are the same single shared isolated-worker
    process for image/video/audio alike (see _MODULE_REGISTRY in
    isolated_worker.py), so this loop needs no per-media-type branch to
    already cover the video/audio paths Phases 6–7 added."""
    supervisor = worker_supervisor.get_supervisor()
    while True:
        await asyncio.sleep(interval_seconds)
        if _processing_job_id is not None:
            continue
        if supervisor.is_alive() and not supervisor.ping():
            supervisor.terminate()


def start_worker() -> None:
    global _worker_task, _watchdog_task
    if _worker_task is None:
        _worker_task = asyncio.get_event_loop().create_task(_worker_loop())
    if _watchdog_task is None:
        _watchdog_task = asyncio.get_event_loop().create_task(_watchdog_loop())


def export_job(job_id: str, output_path: str, quality: int | None) -> None:
    """Re-encodes a done job's cached master result — no model inference, so this
    is always fast regardless of the original image's size."""
    job = jobs.get(job_id)
    if job is None:
        raise ValueError('Job não encontrado.')
    if job['status'] != 'done':
        raise ValueError('Job ainda não foi concluído.')
    master_path = _master_path(job_id)
    if not os.path.isfile(master_path):
        raise ValueError('Resultado do job não está mais disponível.')
    Upscaler.export(master_path, output_path, quality)
    job['output_path'] = output_path
