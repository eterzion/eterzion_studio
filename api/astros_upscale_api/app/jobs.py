"""In-memory job store + single-worker asyncio queue, the parent-side
supervisor that owns the isolated worker subprocess, and the isolated
worker's own entry point (run as `python -m app.jobs <pipe-address>`).
Consolidates what were `job_manager.py`, `worker_supervisor.py` and
`isolated_worker.py` (Constitution Princípio XI) — execution model (async
queue, subprocess isolation, IPC, cancellation, progress, failure handling)
is unchanged.
"""
from __future__ import annotations

import asyncio
import itertools
import os
import secrets
import subprocess
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from multiprocessing.connection import Client, Listener
from pathlib import Path
from typing import Any, Callable, TypedDict
from uuid import uuid4

from astros_upscale.media import ImageOpenError

from app.config import settings

# ------------------------------- worker supervisor (parent side) ------------------------------- #
#
# Parent-side manager for the isolated processing worker (Fase 1 — isolamento
# de processo, docs/processing-protection-architecture.md).
#
# Owns the child process lifecycle: spawns it with a restricted environment (no
# shell, no inherited secrets beyond a one-time IPC authkey), talks to it over an
# authenticated local pipe, and can actually kill it — unlike the old
# ThreadPoolExecutor approach, cancellation here stops real work instead of just
# discarding a thread's result. A single job runs at a time, mirroring the
# previous single-worker semantics; concurrency, if ever needed, would mean a
# pool of these, not larger messages on one pipe.

_API_ROOT = Path(__file__).resolve().parent.parent  # app -> astros_upscale_api


class ProcessResult(TypedDict, total=False):
    source_size: tuple[int, int]
    output_size: tuple[int, int]
    audio_meta: dict


class WorkerCrashed(RuntimeError):
    pass


class WorkerFailure(RuntimeError):
    def __init__(self, message: str, error_class: str):
        super().__init__(message)
        self.error_class = error_class


def _restricted_env(authkey: str) -> dict[str, str]:
    """Only what the interpreter/CUDA/DLL loader genuinely needs — not the
    API process's full environment (no API keys, no unrelated secrets)."""
    passthrough = (
        'SYSTEMROOT', 'SYSTEMDRIVE', 'PATH', 'TEMP', 'TMP', 'USERNAME', 'USERDOMAIN',
        'NUMBER_OF_PROCESSORS', 'PROCESSOR_ARCHITECTURE', 'CUDA_PATH', 'CUDA_VISIBLE_DEVICES',
        'PROGRAMDATA', 'PROGRAMFILES', 'WINDIR',
        # Needed for app.security's DPAPI-protected identity file (Fase 2/4)
        # to resolve the same per-user path the API process itself uses.
        'LOCALAPPDATA', 'APPDATA', 'USERPROFILE',
    )
    env = {k: os.environ[k] for k in passthrough if k in os.environ}
    env['ASTROS_WORKER_AUTHKEY'] = authkey
    return env


class WorkerSupervisor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._listener: Listener | None = None
        self._conn = None
        self._process: subprocess.Popen | None = None
        self._runtime_dir: str | None = None
        self._authkey: str | None = None

    # ---------------------------------------------------------------- lifecycle
    def _spawn(self) -> None:
        from app.security import create_private_dir

        self._runtime_dir = create_private_dir()
        self._authkey = secrets.token_hex(32)
        self._listener = Listener(family='AF_PIPE', authkey=self._authkey.encode('utf-8'))
        self._process = subprocess.Popen(
            [sys.executable, '-m', 'app.jobs', self._listener.address],
            cwd=str(_API_ROOT),
            env=_restricted_env(self._authkey),
            shell=False,
            stdin=subprocess.DEVNULL,
        )
        with open(os.path.join(self._runtime_dir, 'worker.pid'), 'w', encoding='utf-8') as fh:
            fh.write(str(self._process.pid))
        self._conn = self._accept_with_timeout(timeout=45.0)

    def _accept_with_timeout(self, timeout: float):
        """Listener.accept() has no native timeout — bound it so a child that
        fails to import/connect (crash, missing dependency, integrity check
        refusal) doesn't hang the caller forever instead of surfacing as a
        clear error.

        Deliberately NOT `with ThreadPoolExecutor() as pool:` — that context
        manager's __exit__ calls shutdown(wait=True), which blocks until the
        background thread's still-pending accept() call returns... which, if
        the child already died and nothing will ever connect, is never. That
        defeated the whole timeout in testing (a job stayed stuck at
        "processing" indefinitely instead of failing after 45s). Closing the
        listener on timeout is what actually unblocks the pending accept()."""
        assert self._listener is not None
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(self._listener.accept)
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError as error:
            if self._process is not None:
                self._process.kill()
            try:
                self._listener.close()  # unblocks the still-pending accept() in the background thread
            except OSError:
                pass
            pool.shutdown(wait=False)
            raise WorkerCrashed('O worker isolado não respondeu a tempo ao iniciar.') from error
        else:
            pool.shutdown(wait=False)

    def ensure_started(self) -> None:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return
            self._spawn()

    def is_alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def terminate(self) -> None:
        """Hard-stops the worker — used both for real cancellation (stop wasted
        GPU work instead of letting it run to a discarded result) and by the
        watchdog when a worker stops responding."""
        with self._lock:
            self._terminate_locked()

    def _terminate_locked(self) -> None:
        from app.security import remove_dir

        if self._conn is not None:
            try:
                self._conn.close()
            except OSError:
                pass
            self._conn = None
        if self._listener is not None:
            try:
                self._listener.close()
            except OSError:
                pass
            self._listener = None
        if self._process is not None:
            if self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=5)
            self._process = None
        if self._runtime_dir is not None:
            remove_dir(self._runtime_dir)
            self._runtime_dir = None

    def ping(self, timeout: float = 5.0) -> bool:
        """Health check for the watchdog — returns False if the worker didn't
        answer in time (hung, deadlocked, or dead)."""
        if not self.is_alive() or self._conn is None:
            return False
        try:
            self._conn.send({'type': 'ping'})
            if self._conn.poll(timeout):
                reply = self._conn.recv()
                return reply.get('type') == 'pong'
            return False
        except (OSError, EOFError):
            return False

    # ----------------------------------------------------------------- jobs
    def process(
        self,
        job_id: str,
        input_path: str,
        master_path: str,
        model: str,
        models_dir: str,
        device: str | None,
        scale: int,
        custom_size: dict | None,
        denoise: int,
        on_progress: Callable[[int], None] | None = None,
        on_stage: Callable[[str], None] | None = None,
        protected: dict | None = None,
        sharpen: int = 0,
        face_recovery: bool = False,
        face_recovery_strength: int = 80,
        denoise_filter_strength: int = 0,
        media_type: str = 'image',
        operation: str = 'enhance',
        half: bool = True,
        stabilize: bool = False,
        tile_threshold: int | None = None,
        tile_size: int | None = None,
    ) -> ProcessResult:
        """Blocking call — meant to run inside jobs.py's single-worker
        executor thread, same as the direct-call version it replaces.
        `protected`, when set, tells the worker to fetch the orchestration
        logic from the licensing service (Fase 4) instead of using its own
        static import — see the isolated worker's module registry below.

        `media_type`/`operation` select which handler the isolated worker
        dispatches to (T014) — default to the only one implemented today
        (image/enhance, i.e. Upscaler); video/audio handlers land with
        T042/T053 without any change to this IPC layer."""
        self.ensure_started()
        assert self._conn is not None
        self._conn.send({
            'type': 'process', 'job_id': job_id, 'media_type': media_type, 'operation': operation,
            'input_path': input_path, 'master_path': master_path,
            'model': model, 'models_dir': models_dir, 'device': device, 'scale': scale,
            'custom_size': custom_size, 'denoise': denoise, 'protected': protected, 'sharpen': sharpen,
            'face_recovery': face_recovery, 'face_recovery_strength': face_recovery_strength,
            'denoise_filter_strength': denoise_filter_strength, 'half': half, 'stabilize': stabilize,
            'tile_threshold': tile_threshold, 'tile_size': tile_size,
        })
        while True:
            try:
                msg = self._conn.recv()
            except (EOFError, OSError) as error:
                raise WorkerCrashed('O worker isolado encerrou inesperadamente durante o processamento.') from error
            msg_type = msg.get('type')
            if msg_type == 'progress' and on_progress:
                on_progress(msg['pct'])
            elif msg_type == 'stage' and on_stage:
                on_stage(msg['stage'])
            elif msg_type == 'result':
                result: ProcessResult = {
                    'source_size': tuple(msg['source_size']), 'output_size': tuple(msg['output_size']),
                }
                if msg.get('audio_meta') is not None:
                    result['audio_meta'] = msg['audio_meta']
                return result
            elif msg_type == 'error':
                raise WorkerFailure(msg['message'], msg.get('error_class', 'Unknown'))


_supervisor: WorkerSupervisor | None = None


def get_supervisor() -> WorkerSupervisor:
    global _supervisor
    if _supervisor is None:
        _supervisor = WorkerSupervisor()
    return _supervisor


def shutdown() -> None:
    global _supervisor
    if _supervisor is not None:
        _supervisor.terminate()
        _supervisor = None


# ------------------------------- job store + queue (parent side) ------------------------------- #
#
# In-memory job store + a single-worker asyncio queue.
#
# Deliberately simple (asyncio.Queue, dict) for the local/single-user case. If
# this API is ever hosted for multiple concurrent users, swap _queue/jobs for
# Redis + RQ/Celery — the route layer (routes.py) doesn't need to change,
# only this module.
#
# Status lifecycle: pending (created, being configured) -> queued (user clicked
# "process", waiting its turn — concurrency is 1, enforced by _executor's single
# worker thread) -> processing -> done | error | cancelled. Export is a separate,
# much cheaper step handled by export_job() below — it never touches this state
# machine or re-runs the model, it only reads the master PNG _process_job() wrote.

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
# Bridges the blocking IPC call to the isolated worker process (WorkerSupervisor
# above) onto the asyncio loop — the actual model inference no longer runs on
# this thread, it runs in a separate OS process (see
# docs/processing-protection-architecture.md, Fase 1). One thread because the
# isolated worker itself only handles one job at a time, matching the previous
# single-worker semantics.
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
    """Same reasoning as _video_output_path — app.processing's audio pipeline
    writes the real, final result directly, preserving the original file's
    format."""
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
    this never touches app.licensing's profile resolver or WorkerSupervisor,
    both of which exist specifically for the AI-model path (T012/T014)."""
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
    """`secondary_elements` (T047, FR-081 to FR-086): when the caller (routes.py)
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
            get_supervisor().terminate()
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

        from app import licensing

        custom = params.get('custom_size')
        adjustments = params.get('adjustments', {})
        denoise = adjustments.get('denoise', 50)
        sharpen = adjustments.get('deblur', 0)
        face_recovery = adjustments.get('face_correction', False)
        face_recovery_strength = adjustments.get('face_recovery_strength', 80)
        denoise_filter_strength = adjustments.get('denoise_filter_strength', 0) if adjustments.get('denoise_filter_enabled') else 0

        # The one place a job's intent (content_type/scale/profile) becomes an
        # internal engine_ref — resolved fresh here, never stored on the job
        # dict itself, so nothing HTTP/WS-visible (jobs.jobs, _notify)
        # ever carries a model identifier (FR-009/FR-011).
        pipeline = licensing.resolve(licensing.MediaRequest(
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
        return get_supervisor().process(
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
    and the supervisor are the same single shared isolated-worker process for
    image/video/audio alike (see _MODULE_REGISTRY below), so this loop needs
    no per-media-type branch to already cover the video/audio paths Phases
    6–7 added."""
    supervisor = get_supervisor()
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
    from app.processing import Upscaler

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


# ------------------------------- isolated worker (child process entry point) ------------------------------- #
#
# Entry point for the isolated processing worker (Fase 1 — isolamento de
# processo, docs/processing-protection-architecture.md).
#
# Runs as its own OS process, spawned by WorkerSupervisor above with a
# restricted environment (no shell, no inherited secrets beyond the one-time
# authkey it needs to open the IPC channel). It receives only what a job
# needs — never arbitrary filesystem access, never the API's full
# environment, never a shell.
#
# Communication is a local named pipe (multiprocessing.connection, AF_PIPE on
# Windows) authenticated with a per-run ephemeral token (authkey) generated by
# the parent — not a global secret shared across installs.
#
# Run as: python -m app.jobs <pipe-address>
# Reads the authkey from the ASTROS_WORKER_AUTHKEY env var (set only for this
# child process by the parent, not inherited from the API's full environment).

from app import processing as _static_audio_processor  # noqa: E402 - see module docstring
from app.processing import Upscaler as _StaticUpscaler  # noqa: E402
from app.processing import VideoUpscaler as _StaticVideoUpscaler  # noqa: E402

_upscaler_cache: dict[tuple, object] = {}
_video_upscaler_cache: dict[tuple, object] = {}
_protected_module_cache: dict[str, object] = {}


def _resolve_protected_module(protected: dict | None):
    """Opt-in path (protected != None): fetch, verify, decrypt and exec the
    orchestration-logic package in memory (Fase 4) — see app.security's
    protected loader. Returns None on any failure (or when protected loading
    isn't requested), so a licensing-service outage degrades to a handler's
    own static fallback rather than breaking processing outright."""
    if not protected:
        return None
    cache_key = f"{protected['base_url']}::{protected['version']}"
    cached = _protected_module_cache.get(cache_key)
    if cached is not None:
        return cached
    from app.security import ProtectedLoadError, ensure_identity, load_protected_module
    try:
        identity = ensure_identity()
        module = load_protected_module(
            base_url=protected['base_url'], trusted_pubkey_b64=protected.get('trusted_pubkey_b64', ''),
            identity=identity, model=protected['model'], version=protected['version'],
            operation=protected.get('operation', 'process'),
        )
        _protected_module_cache[cache_key] = module
        return module
    except ProtectedLoadError:
        traceback.print_exc(file=sys.stderr)
        return None


def _get_upscaler(model: str, models_dir: str, device: str | None, denoise: float, half: bool,
                   protected: dict | None, tile_threshold: int | None, tile_size: int | None):
    module = _resolve_protected_module(protected)
    upscaler_class = module.Upscaler if module is not None else _StaticUpscaler
    key = (upscaler_class, model, device, half, tile_threshold, tile_size)
    cached = _upscaler_cache.get(key)
    if cached is not None:
        return cached
    upscaler = upscaler_class(
        model, models_dir, device=device, denoise_strength=denoise, half=half,
        tile_threshold=tile_threshold, tile_size=tile_size)
    _upscaler_cache[key] = upscaler
    return upscaler


def _handle_image_enhance(msg: dict, send) -> None:
    """Today's only real handler: static-model super-resolution via
    astros_upscale.processing.load_model, wrapped by app.processing.Upscaler.
    `msg['model']` is the internal engine_ref app.licensing already resolved
    in jobs.py's own _process_job()."""
    denoise = msg.get('denoise', 50) / 100
    half = msg.get('half', True)
    upscaler = _get_upscaler(
        msg['model'], msg['models_dir'], msg.get('device'), denoise, half, msg.get('protected'),
        msg.get('tile_threshold'), msg.get('tile_size'))
    custom = msg.get('custom_size')
    custom_size = (custom['width'], custom['height']) if custom else None
    result = upscaler.process(
        msg['input_path'], msg.get('scale', 4), custom_size, msg['master_path'],
        on_progress=lambda pct: send({'type': 'progress', 'pct': pct}),
        on_stage=lambda stage: send({'type': 'stage', 'stage': stage}),
        sharpen_strength=msg.get('sharpen', 0),
        face_recovery=msg.get('face_recovery', False),
        face_recovery_strength=msg.get('face_recovery_strength', 80),
        denoise_filter_strength=msg.get('denoise_filter_strength', 0),
    )
    send({'type': 'result', 'source_size': result['source_size'], 'output_size': result['output_size']})


def _get_video_upscaler(model: str, models_dir: str, device: str | None, denoise: float, half: bool,
                         protected: dict | None, tile_threshold: int | None, tile_size: int | None):
    module = _resolve_protected_module(protected)
    upscaler_class = getattr(module, 'VideoUpscaler', None) if module is not None else None
    upscaler_class = upscaler_class or _StaticVideoUpscaler
    key = (upscaler_class, model, device, half, tile_threshold, tile_size)
    cached = _video_upscaler_cache.get(key)
    if cached is not None:
        return cached
    upscaler = upscaler_class(
        model, models_dir, device=device, denoise_strength=denoise, half=half,
        tile_threshold=tile_threshold, tile_size=tile_size)
    _video_upscaler_cache[key] = upscaler
    return upscaler


def _handle_video_enhance(msg: dict, send) -> None:
    """T042 — wraps the same astros_upscale frame-by-frame model pipeline the
    old CLI's `run_video` used. `msg['master_path']` is where the final,
    audio-muxed video is written directly — video has no separate "master then
    export" step like images do."""
    denoise = msg.get('denoise', 50) / 100
    half = msg.get('half', True)
    upscaler = _get_video_upscaler(
        msg['model'], msg['models_dir'], msg.get('device'), denoise, half, msg.get('protected'),
        msg.get('tile_threshold'), msg.get('tile_size'))
    result = upscaler.process(
        msg['input_path'], msg.get('scale', 2), msg['master_path'],
        on_progress=lambda pct: send({'type': 'progress', 'pct': pct}),
        on_stage=lambda stage: send({'type': 'stage', 'stage': stage}),
        stabilize=msg.get('stabilize', False),
    )
    send({'type': 'result', 'source_size': result['source_size'], 'output_size': result['output_size']})


def _handle_audio_enhance(msg: dict, send) -> None:
    """T053 — DSP chain (always) + content-type model pass (speech/music).
    `msg['protected']` is accepted for interface symmetry with the other
    handlers but unused here — the audio pipeline has no protected-orchestration
    variant today, same as compress/convert never invoking one."""
    module = _resolve_protected_module(msg.get('protected'))
    processor = getattr(module, 'audio_processor', None) if module is not None else None
    processor = processor or _static_audio_processor
    result = processor.process(
        msg['input_path'], msg['model'], msg['master_path'],
        on_progress=lambda pct: send({'type': 'progress', 'pct': pct}),
        on_stage=lambda stage: send({'type': 'stage', 'stage': stage}),
    )
    send({'type': 'result', 'source_size': (0, 0), 'output_size': (0, 0), 'audio_meta': result})


# Dispatch table: (media_type, operation) -> handler(msg, send). This is the
# generalization T014 asks for — the isolated worker no longer hardcodes a
# single processing class, it looks up a handler by what the job actually is.
_MODULE_REGISTRY: dict[tuple[str, str], object] = {
    ('image', 'enhance'): _handle_image_enhance,
    ('video', 'enhance'): _handle_video_enhance,
    ('audio', 'enhance'): _handle_audio_enhance,
}


def _handle_process(conn, msg: dict) -> None:
    job_id = msg['job_id']

    def send(payload: dict) -> None:
        conn.send({**payload, 'job_id': job_id})

    media_type = msg.get('media_type', 'image')
    operation = msg.get('operation', 'enhance')
    handler = _MODULE_REGISTRY.get((media_type, operation))
    if handler is None:
        send({
            'type': 'error',
            'message': f"Nenhum processador disponível para media_type={media_type!r}, operation={operation!r}.",
            'error_class': 'NoHandlerAvailable',
        })
        return

    try:
        handler(msg, send)
    except Exception as error:  # noqa: BLE001 - reported to the parent, not re-raised
        send({'type': 'error', 'message': str(error), 'error_class': type(error).__name__})


def main() -> None:
    # Fase 5 — recusa iniciar se os próprios arquivos do worker foram
    # modificados desde que o manifesto foi gerado. Checado antes de qualquer
    # outra coisa, inclusive antes de abrir o canal IPC.
    from app.security import verify_integrity

    ok, problems = verify_integrity()
    if not ok:
        print('Falha de integridade do worker isolado — recusando iniciar:', file=sys.stderr)
        for problem in problems:
            print(f'  - {problem}', file=sys.stderr)
        sys.exit(3)

    if len(sys.argv) < 2:
        print('usage: python -m app.jobs <pipe-address>', file=sys.stderr)
        sys.exit(2)
    address = sys.argv[1]
    authkey = os.environ.get('ASTROS_WORKER_AUTHKEY', '')
    if not authkey:
        print('ASTROS_WORKER_AUTHKEY not set', file=sys.stderr)
        sys.exit(2)

    conn = Client(address, authkey=authkey.encode('utf-8'))
    try:
        while True:
            try:
                msg = conn.recv()
            except (EOFError, OSError):
                break
            msg_type = msg.get('type')
            if msg_type == 'shutdown':
                break
            if msg_type == 'ping':
                conn.send({'type': 'pong'})
                continue
            if msg_type == 'process':
                try:
                    _handle_process(conn, msg)
                except Exception:  # noqa: BLE001 - last-resort guard, worker must survive
                    traceback.print_exc(file=sys.stderr)
                    conn.send({'type': 'error', 'job_id': msg.get('job_id'), 'message': 'Falha interna do worker.', 'error_class': 'WorkerCrash'})
    finally:
        conn.close()


if __name__ == '__main__':
    main()
