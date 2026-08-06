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
from app.core.upscaler import Upscaler
from astros_upscale.utils.image_io import ImageOpenError

jobs: dict[str, dict[str, Any]] = {}

_queue: 'asyncio.Queue[str]' = asyncio.Queue()
_listeners: dict[str, list['asyncio.Queue[dict]']] = {}
_executor = ThreadPoolExecutor(max_workers=1)
_upscaler_cache: dict[tuple[str, str | None], Upscaler] = {}
_worker_task: asyncio.Task | None = None
_enqueue_counter = itertools.count(1)


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
    already 'processing' can't be safely killed mid-inference (it runs on a plain
    thread, not a subprocess) — it's marked cancelled and its result is discarded
    once the thread finishes; the client sees the cancellation immediately via the
    status flip, not after the (now-pointless) work actually completes."""
    job = jobs.get(job_id)
    if job is None:
        return False
    if job['status'] in ('pending', 'queued', 'processing'):
        job['status'] = 'cancelled'
        _notify(job_id)
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
    text = str(error).lower()
    if isinstance(error, MemoryError) or 'out of memory' in text or 'cuda out of memory' in text:
        return 'out_of_memory'
    if isinstance(error, OSError) and ('no space left' in text or 'disk full' in text):
        return 'disk_full'
    if isinstance(error, ImageOpenError) or 'cannot identify image' in text or 'corrupt' in text:
        return 'corrupted_input'
    return 'model_failure'


async def _process_job(job_id: str) -> None:
    job = jobs[job_id]
    if job['status'] == 'cancelled':
        return
    job['status'] = 'processing'
    job['processing_started_at'] = _now_iso()
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
        cache_key = (params['model'], params.get('device'))
        upscaler = _upscaler_cache.get(cache_key)
        if upscaler is None:
            on_stage('Carregando modelo de IA')
            denoise = params.get('adjustments', {}).get('denoise', 50) / 100
            upscaler = Upscaler(params['model'], settings.models_dir, device=params.get('device'), denoise_strength=denoise)
            _upscaler_cache[cache_key] = upscaler
        custom = params.get('custom_size')
        custom_size = (custom['width'], custom['height']) if custom else None
        return upscaler.process(
            job['input_path'], params.get('scale', 4), custom_size, _master_path(job_id),
            on_progress=on_progress, on_stage=on_stage,
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
    except Exception as error:  # noqa: BLE001 - surfaced to the client as job.error
        job['status'] = 'error'
        job['error'] = str(error)
        job['error_category'] = _categorize_error(error)
    _notify(job_id)


async def _worker_loop() -> None:
    while True:
        job_id = await _queue.get()
        try:
            await _process_job(job_id)
        finally:
            _queue.task_done()


def start_worker() -> None:
    global _worker_task
    if _worker_task is None:
        _worker_task = asyncio.get_event_loop().create_task(_worker_loop())


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
