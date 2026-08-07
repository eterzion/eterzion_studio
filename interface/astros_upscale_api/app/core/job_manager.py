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


def create_job(input_path: str, filename: str, params: dict) -> str:
    job_id = f'job_{uuid4().hex[:8]}'
    jobs[job_id] = {
        'id': job_id,
        'status': 'pending',
        'progress': 0,
        'stage': None,
        'eta_seconds': None,
        'queue_order': None,
        'input_file': filename,
        'input_path': input_path,
        'output_path': None,
        'error': None,
        'error_category': None,
        'created_at': _now_iso(),
        'processing_started_at': None,
        'processing_ended_at': None,
        'source_meta': None,
        'output_meta': None,
        'params': params,
    }
    return job_id


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
        custom = params.get('custom_size')
        adjustments = params.get('adjustments', {})
        denoise = adjustments.get('denoise', 50)
        sharpen = adjustments.get('deblur', 0)
        face_recovery = adjustments.get('face_correction', False)
        face_recovery_strength = adjustments.get('face_recovery_strength', 80)
        denoise_filter_strength = adjustments.get('denoise_filter_strength', 0) if adjustments.get('denoise_filter_enabled') else 0
        protected = None
        if settings.licensing_service_url:
            # Fase 4 — fetch the orchestration logic from the licensing service
            # instead of the worker's static import. Empty licensing_service_url
            # (the default: no license infra deployed) keeps today's behavior.
            protected = {
                'base_url': settings.licensing_service_url,
                'trusted_pubkey_b64': settings.licensing_service_public_key_b64,
                'model': params['model'],
                'version': 'latest',
            }
        # Runs in the isolated worker process (Fase 1), not on this thread — this
        # call just relays the request over IPC and blocks for the reply.
        return worker_supervisor.get_supervisor().process(
            job_id=job_id,
            input_path=job['input_path'],
            master_path=_master_path(job_id),
            model=params['model'],
            models_dir=settings.models_dir,
            device=params.get('device'),
            scale=params.get('scale', 4),
            custom_size=custom,
            denoise=denoise,
            sharpen=sharpen,
            face_recovery=face_recovery,
            face_recovery_strength=face_recovery_strength,
            denoise_filter_strength=denoise_filter_strength,
            on_progress=on_progress,
            on_stage=on_stage,
            protected=protected,
        )

    try:
        result_meta = await loop.run_in_executor(_executor, blocking_run)
        if job['status'] == 'cancelled':
            _notify(job_id)
            return
        master_path = _master_path(job_id)
        source_w, source_h = result_meta['source_size']
        output_w, output_h = result_meta['output_size']
        job['status'] = 'done'
        job['progress'] = 100
        job['stage'] = None
        job['processing_ended_at'] = _now_iso()
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
    when idle) to avoid false positives on long GPU-bound work."""
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
