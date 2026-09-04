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
import logging
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

from eterzion_upscale.media import ImageOpenError

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

_API_ROOT = Path(__file__).resolve().parent.parent  # app -> eterzion_upscale_api


logger = logging.getLogger(__name__)


class ProcessResult(TypedDict, total=False):
    source_size: tuple[int, int]
    output_size: tuple[int, int]
    audio_meta: dict


class WorkerCrashed(RuntimeError):
    pass


# De quanto em quanto tempo se verifica se o filho ainda está vivo enquanto se
# espera a conexão. Curto o bastante para a falha ser imediata na percepção de
# quem espera, longo o bastante para não virar espera ocupada.
_SPAWN_POLL_SECONDS = 0.25

# Códigos de saída que o worker usa em `main()` antes de abrir o canal IPC.
# Traduzi-los aqui é o que transforma "não respondeu" numa frase acionável.
_SPAWN_EXIT_REASONS = {
    2: 'O worker isolado foi iniciado sem os argumentos que precisa.',
    3: ('O worker isolado recusou iniciar: os arquivos protegidos não conferem '
        'com o manifesto de integridade. Rode `python -m app.security` para '
        'regerá-lo depois de alterar um deles.'),
}


def _spawn_exit_message(codigo: int) -> str:
    return _SPAWN_EXIT_REASONS.get(
        codigo, f'O worker isolado encerrou ao iniciar (código {codigo}).')


class WorkerFailure(RuntimeError):
    def __init__(self, message: str, error_class: str):
        super().__init__(message)
        self.error_class = error_class


def _restricted_env(authkey: str, extra_passthrough: tuple[str, ...] = ()) -> dict[str, str]:
    """Only what the interpreter/CUDA/DLL loader genuinely needs — not the
    API process's full environment (no API keys, no unrelated secrets).
    `extra_passthrough` lets a specific supervisor (e.g. the audio-worker's,
    which needs HF_TOKEN to fetch the gated Stable Audio Open VAE) opt into a
    few more names without widening what the image/video worker receives."""
    passthrough = (
        'SYSTEMROOT', 'SYSTEMDRIVE', 'PATH', 'TEMP', 'TMP', 'USERNAME', 'USERDOMAIN',
        'NUMBER_OF_PROCESSORS', 'PROCESSOR_ARCHITECTURE', 'CUDA_PATH', 'CUDA_VISIBLE_DEVICES',
        'PROGRAMDATA', 'PROGRAMFILES', 'WINDIR',
        # Needed for app.security's DPAPI-protected identity file (Fase 2/4)
        # to resolve the same per-user path the API process itself uses.
        'LOCALAPPDATA', 'APPDATA', 'USERPROFILE',
    ) + extra_passthrough
    env = {k: os.environ[k] for k in passthrough if k in os.environ}
    env['ASTROS_WORKER_AUTHKEY'] = authkey
    return env


class WorkerSupervisor:
    """`python_executable`/`spawn_args` default to this process's own interpreter
    running `-m app.jobs` (the image/video worker, unchanged behaviour). A second,
    independent instance (see `get_audio_worker_supervisor()` below) passes a
    different interpreter and a standalone entry script instead — the audio-worker
    venv doesn't have `eterzion_upscale_api`'s own `app` package installed, so it
    can't run `-m app.jobs` at all. Two distinct instances, never one instance
    switching behaviour per call — a single persistent child process can't serve
    two incompatible dependency sets (specs/006-audio-engine-masterizacao/
    research.md Decisão 3, found during /speckit.analyze)."""

    def __init__(
        self, python_executable: str | None = None, spawn_args: list[str] | None = None,
        extra_env_passthrough: tuple[str, ...] = (),
    ) -> None:
        self._lock = threading.Lock()
        self._listener: Listener | None = None
        self._conn = None
        self._process: subprocess.Popen | None = None
        self._runtime_dir: str | None = None
        self._authkey: str | None = None
        self._python_executable = python_executable or sys.executable
        self._spawn_args = spawn_args if spawn_args is not None else ['-m', 'app.jobs']
        self._extra_env_passthrough = extra_env_passthrough
        # Updated after every restore_audio() call (success or failure) — read by
        # _audio_worker_idle_watchdog_loop() to release VRAM after real inactivity.
        # None until the first call: an audio-worker instance never spawned yet
        # is not "idle", it's simply not running (nothing to release).
        self._last_used_at: float | None = None

    # ---------------------------------------------------------------- lifecycle
    def _spawn(self) -> None:
        from app.security import create_private_dir

        self._runtime_dir = create_private_dir()
        self._authkey = secrets.token_hex(32)
        self._listener = Listener(family='AF_PIPE', authkey=self._authkey.encode('utf-8'))
        self._process = subprocess.Popen(
            [self._python_executable, *self._spawn_args, self._listener.address],
            cwd=str(_API_ROOT),
            env=_restricted_env(self._authkey, self._extra_env_passthrough),
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
        limite = time.monotonic() + timeout
        try:
            while True:
                restante = limite - time.monotonic()
                if restante <= 0:
                    raise FutureTimeoutError()
                try:
                    # Espera em fatias em vez de uma só. A fatia não é
                    # impaciência: é o que permite notar, **enquanto** se espera,
                    # que o filho já morreu — e um filho que já morreu não é um
                    # timeout. Esperar os 45 segundos inteiros por uma resposta
                    # que já existe é metade do defeito, e foi o que escondeu
                    # duas vezes um manifesto de integridade vencido atrás de
                    # "não respondeu a tempo".
                    return future.result(timeout=min(_SPAWN_POLL_SECONDS, restante))
                except FutureTimeoutError:
                    codigo = self._process.poll() if self._process is not None else None
                    if codigo is not None:
                        self._cleanup_failed_spawn(pool)
                        raise WorkerCrashed(_spawn_exit_message(codigo)) from None
        except FutureTimeoutError as error:
            if self._process is not None:
                self._process.kill()
            self._cleanup_failed_spawn(pool)
            raise WorkerCrashed('O worker isolado não respondeu a tempo ao iniciar.') from error
        finally:
            if not future.running():
                pool.shutdown(wait=False)

    def _cleanup_failed_spawn(self, pool: ThreadPoolExecutor) -> None:
        """Fecha o canal de um filho que já saiu.

        Fechar o `Listener` é o que desbloqueia o `accept()` ainda pendente na
        thread de fundo — sem isto ela ficaria viva até o processo terminar.
        """
        try:
            self._listener.close()  # type: ignore[union-attr]
        except OSError:
            pass
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

    # ------------------------------------------------------------ audio jobs
    def restore_audio(self, *, timeout: float = 900.0, **payload: Any) -> str:
        """Blocking call for the audio-worker's `restore` message type
        (vendor/sonicmaster/worker_main.py) — the same connect/spawn/authkey
        mechanism as `process()`, a distinct message type/protocol (no
        progress callbacks yet; SonicMaster inference doesn't report
        per-step progress the way image/video does). Only meaningful on an
        instance returned by `get_audio_worker_supervisor()`. Returns the
        output path. `timeout` bounds a single `conn.recv()` wait — real
        inference over several chunks can legitimately take minutes.
        Always stamps `_last_used_at` on the way out (success or failure) —
        `_audio_worker_idle_watchdog_loop()` reads it to release VRAM after
        real inactivity, not after a call that merely started."""
        try:
            self.ensure_started()
            assert self._conn is not None
            self._conn.send({'type': 'restore', **payload})
            if not self._conn.poll(timeout):
                raise WorkerCrashed('O audio-worker não respondeu a tempo.')
            try:
                msg = self._conn.recv()
            except (EOFError, OSError) as error:
                raise WorkerCrashed('O audio-worker encerrou inesperadamente.') from error
            if msg.get('type') == 'result':
                return msg['output_path']
            if msg.get('type') == 'error':
                raise WorkerFailure(msg['message'], msg.get('error_class', 'Unknown'))
            raise WorkerFailure(f'Resposta inesperada do audio-worker: {msg!r}', 'UnexpectedMessage')
        finally:
            self._last_used_at = time.monotonic()


_supervisor: WorkerSupervisor | None = None
_audio_worker_supervisor: WorkerSupervisor | None = None


def get_supervisor() -> WorkerSupervisor:
    global _supervisor
    if _supervisor is None:
        _supervisor = WorkerSupervisor()
    return _supervisor


def get_audio_worker_supervisor() -> WorkerSupervisor | None:
    """A second, independent WorkerSupervisor for AI music restoration
    (SonicMaster) — never the same instance/process as get_supervisor()'s
    image/video worker (see WorkerSupervisor's docstring). Returns None when
    settings.audio_worker_python is unset — app.audio_engine.ai_provider
    treats that as "provider unavailable" and falls back to DSP (FR-020)."""
    global _audio_worker_supervisor
    if not settings.audio_worker_python:
        return None
    if _audio_worker_supervisor is None:
        worker_main = _API_ROOT / 'vendor' / 'sonicmaster' / 'worker_main.py'
        _audio_worker_supervisor = WorkerSupervisor(
            python_executable=settings.audio_worker_python,
            spawn_args=[str(worker_main)],
            # infer.py checks all three names for the Stable Audio Open VAE's
            # gated-repo auth (research.md — VAE is a real, required inference
            # dependency, not optional). Image/video's supervisor never gets
            # these — _restricted_env's default passthrough is unchanged.
            extra_env_passthrough=('HF_TOKEN', 'HUGGINGFACE_TOKEN', 'HUGGINGFACEHUB_API_TOKEN'),
        )
    return _audio_worker_supervisor


def shutdown() -> None:
    """FR-023a, second half: closing the editing area leaves an export running,
    but shutting the application down cancels one — and a cancellation leaves no
    partial file behind (FR-023)."""
    global _supervisor, _audio_worker_supervisor

    for job in jobs.values():
        if job.get('operation') != 'video_edit':
            continue
        if job['status'] in ('pending', 'queued', 'processing'):
            job['status'] = 'cancelled'
        partial = job.get('partial_output')
        if partial and os.path.exists(partial):
            try:
                os.remove(partial)
            except OSError:
                # A file the encoder still holds open cannot be removed here.
                # Reporting it is more useful than pretending the sweep was
                # complete.
                logger.warning('não foi possível remover o parcial %s no encerramento', partial)

    if _supervisor is not None:
        _supervisor.terminate()
        _supervisor = None
    if _audio_worker_supervisor is not None:
        _audio_worker_supervisor.terminate()
        _audio_worker_supervisor = None


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
_audio_idle_watchdog_task: asyncio.Task | None = None
_enqueue_counter = itertools.count(1)
_processing_job_id: str | None = None


def _now_iso() -> str:
    """ISO 8601 UTC, with milliseconds.

    Second precision made the duration of any fast job unreportable: an image
    that takes 0.5s starts and ends inside the same second, so the difference
    came out as zero and the panel showed its 1ms floor. The stat was there to
    say how long the work took and could not say it for exactly the jobs people
    run most. Date.parse() in the renderer reads this form unchanged.
    """
    now = time.time()
    millis = int((now % 1) * 1000)
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(now)) + f'.{millis:03d}Z'


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


def _media_dimensions(path: str) -> tuple[int | None, int | None]:
    """Real pixel dimensions of a compress/convert input or result. Purely
    informational — the Exportar screen reports blanks rather than failing a
    finished job, so anything unreadable here (AVIF, which OpenCV can't decode;
    a codec ffprobe doesn't know; audio, which has no dimensions at all) comes
    back as (None, None)."""
    from eterzion_upscale.optimize import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS

    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in IMAGE_EXTENSIONS:
            from eterzion_upscale.media import imread

            image = imread(path)
            return int(image.shape[1]), int(image.shape[0])
        if ext in VIDEO_EXTENSIONS:
            from eterzion_upscale.media import ffprobe_json

            for stream in ffprobe_json(path).get('streams', []):
                if stream.get('codec_type') == 'video':
                    return int(stream['width']), int(stream['height'])
    except Exception:  # noqa: BLE001 — see docstring: never fail a done job over metadata
        pass
    return None, None


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


def _video_edit_output_path(job: dict, params: dict) -> str:
    """Where an edited video lands.

    Reuses _compress_convert_output_path's shape rather than growing a second
    collision policy: renaming on collision is already the established default,
    and Princípio XV requires that overwriting be an explicit per-operation
    instruction — never a fallback when a destination is ambiguous.
    """
    return _compress_convert_output_path(job, params)


def _run_video_edit(job: dict, params: dict, on_progress, on_stage) -> dict:
    """FR-013f. Renders the edit set to a new file.

    Cleanup is a single exit path, not a cuidado repeated per error branch: the
    finally block below covers success, failure and cancellation alike, which is
    what makes FR-022 checkable rather than aspirational. The partial output is
    removed too — FR-023 forbids leaving one behind, and ffmpeg will have
    written bytes before any interruption.
    """
    from app import video_edits

    output_path = _video_edit_output_path(job, params)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)

    # Written to a temporary name and moved into place only on success. Without
    # this, a cancellation halfway leaves a playable-looking file at the
    # destination that is not the export the person asked for.
    #
    # The marker goes BEFORE the extension: ffmpeg infers the container from the
    # suffix, and 'saida.webm.partial' fails with "Invalid argument" because
    # .partial is not a format. Found by the export test, which is what it is
    # for.
    stem, extension = os.path.splitext(output_path)
    temp_output = f'{stem}.partial{extension}'
    # Recorded on the job so shutdown() can remove exactly this file. Sweeping
    # the destination directory by pattern would mean deleting from a folder the
    # person chose, on a guess about which files are ours — not a trade worth
    # making for a cleanup.
    job['partial_output'] = temp_output
    if on_stage:
        on_stage('Exportando')

    try:
        video_edits.export(
            job['input_path'], temp_output, params.get('edits') or {},
            container=params['container'], profile=params.get('profile', 'balanced'),
            source_width=params['source_width'], source_height=params['source_height'],
            has_audio=params.get('has_audio', True),
        )
        if job['status'] == 'cancelled':
            raise RuntimeError('cancelado')
        os.replace(temp_output, output_path)
        if on_progress:
            on_progress(100)
    finally:
        # Success moved it; anything else leaves it here to remove. One place,
        # every outcome.
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except OSError:
                pass

    # Same shape _run_compress_convert returns, because both are consumed by the
    # same branch of _process_job. Dimensions are derived there; size is not, so
    # it belongs here. Returning less than the sibling was a KeyError waiting on
    # the first real export — and it got one.
    return {
        'output_path': output_path,
        'size_bytes': os.path.getsize(output_path) if os.path.isfile(output_path) else None,
    }


# Marcadores de que uma mensagem veio do FFmpeg, e não de nós. O que a pessoa
# precisa ver é uma frase que fale do que ela pediu; o resto é diagnóstico, e
# esconder o diagnóstico é tão ruim quanto exibi-lo como se fosse a explicação.
_FFMPEG_MARKERS = ('Falha ao processar com ffmpeg', 'ffmpeg', 'Conversion failed',
                   'Invalid argument', 'Error opening')


def _record_failure(job: dict, error: Exception) -> None:
    """Registra a falha com a razão separada da saída bruta (FR-065).

    A saída do FFmpeg é indispensável para diagnosticar e ilegível para decidir:
    "Task finished with error code: -22 (Invalid argument)" não diz a ninguém o
    que fazer a seguir. Apresentá-la como *a* mensagem de erro transfere para a
    pessoa um trabalho que é nosso.

    Então ela vai num campo separado — `error_detail` — que a interface mostra
    numa área recolhida. Quem precisa copiar para um relatório encontra; quem só
    quer saber o que aconteceu lê a frase de cima.
    """
    mensagem = str(error)
    job['status'] = 'error'
    job['error'] = mensagem
    job['error_category'] = _categorize_error(error)

    reason = getattr(error, 'reason', None)
    if reason:
        job['error_reason'] = reason
    if any(marcador in mensagem for marcador in _FFMPEG_MARKERS):
        job['error_detail'] = mensagem


def _record_compression_history(job: dict, medido: dict) -> None:
    """Registra a compressão no histórico local (FR-062).

    Guarda o **snapshot** das configurações, e não o `preset_id`: o preset é
    editável, e "repetir" lendo o preset atual produziria um resultado diferente
    do que a entrada exibe (FR-063).

    Falhar aqui não pode derrubar o job. O arquivo já existe no disco e é o que
    a pessoa pediu; um histórico que não gravou custa memória, não trabalho.
    """
    from app.compression import history

    params = job.get('params') or {}
    try:
        history.record(
            entry_id=job['id'],
            display_name=job.get('input_file') or '',
            media_kind=params.get('media_kind') or 'image',
            settings_snapshot=params.get('settings') or {},
            preset_id=params.get('preset_id'),
            result=medido,
            output_path=job.get('output_path'),
            finished_at=job.get('processing_ended_at'))
    except Exception:  # noqa: BLE001
        logger.warning('Não foi possível gravar o histórico de compressão.', exc_info=True)


def _run_compression(job: dict, params: dict, on_progress, on_stage) -> dict:
    """Central de Compressão (specs/008-compression-centre).

    Separado de `_run_compress_convert`, que serve o fluxo antigo e continua
    funcionando: o Princípio II proíbe duplicar sem motivo, e o motivo aqui é
    que os dois têm contratos diferentes — este devolve números medidos,
    economia e o que de fato aplicou, e aquele devolve caminho e tamanho.
    Fundi-los mudaria o contrato de um caminho que já está em uso (FR-069).
    """
    from app.compression import runner

    resultado = runner.run(
        params['media_kind'], job['input_path'], params['output_path'],
        params.get('settings') or {},
        on_progress=on_progress, on_stage=on_stage)
    # `output_meta` é o que a fila e o histórico leem; `compression` carrega o
    # que só esta tela usa, sem alargar o contrato compartilhado.
    return {
        'output_path': resultado['output_path'],
        'size_bytes': resultado['output_size_bytes'],
        'compression': resultado,
    }


def _run_compress_convert(job: dict, params: dict, on_progress, on_stage) -> dict:
    """FR-025 to FR-030: real ffmpeg/OpenCV transcoding, never an AI model —
    this never touches app.licensing's profile resolver or WorkerSupervisor,
    both of which exist specifically for the AI-model path (T012/T014)."""
    from eterzion_upscale.optimize import optimize_file

    output_path = _compress_convert_output_path(job, params)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
    if on_stage:
        on_stage('Comprimindo' if job.get('operation') == 'compress' else 'Convertendo')
    # Resize is optional and plain resampling — this path never runs a model
    # (FR-029), so a larger target here just interpolates, it does not upscale
    # in the AI sense the Imagem/Vídeo screens mean.
    custom_size = params.get('custom_size')
    resize = (int(custom_size['width']), int(custom_size['height'])) if custom_size else None
    optimize_file(job['input_path'], output_path, quality=params.get('quality') or 80, resize=resize)
    if on_progress:
        on_progress(100)
    return {
        'output_path': output_path,
        'size_bytes': os.path.getsize(output_path) if os.path.isfile(output_path) else None,
    }


def has_meaningful_edits(edits: dict | None) -> bool:
    """True when an edit set asks for something other than the neutral state.

    A neutral set produces an empty filter chain, and a second encode pass that
    changes nothing is pure cost — on an upscaled 4K frame, a very large one.
    """
    if not edits:
        return False
    from app import video_edits

    if edits.get('trim'):
        return True
    if (edits.get('audio') or {}).get('mode', 'keep') != 'keep':
        return True
    if float((edits.get('audio') or {}).get('volume', 1.0)) != 1.0:
        return True
    # Dimensions do not matter here: the chain builder only emits `scale` when
    # the requested output differs from the source, and the upscale already
    # decided the size.
    return bool(video_edits.build_filter_chain(edits, 0, 0))


def _apply_edits_to_upscaled(job: dict, params: dict, output_path: str, on_stage) -> None:
    """Apply the editor's settings to an upscaled video, as a second pass.

    A separate pass rather than a change to the model pipeline: VideoUpscaler
    owns frame generation and knows nothing about colour grading or trimming,
    and teaching it would couple two things that change for different reasons.
    The cost is one extra encode, which is small beside the model pass that
    just ran.

    The filters run on the UPSCALED frames, not the source. That is the right
    order — sharpening or denoising before an upscale would feed the model an
    altered picture, and the person adjusted against a preview of the result.
    """
    from app import video_edits

    edits = params.get('edits')
    if not has_meaningful_edits(edits):
        return

    width, height = _media_dimensions(output_path)
    if not width or not height:
        logger.warning('dimensões desconhecidas em %s — ajustes não aplicados', output_path)
        return

    if on_stage:
        on_stage('Aplicando ajustes')

    stem, extension = os.path.splitext(output_path)
    temp_output = f'{stem}.edited{extension}'
    job['partial_output'] = temp_output
    try:
        video_edits.export(
            output_path, temp_output, edits,
            # The upscale already produced an .mp4; keeping the container avoids
            # a format change the person did not ask for. Profile follows the
            # job's, so "quality" does not silently become "fast" here.
            container='mp4', profile=params.get('profile') or 'balanced',
            source_width=width, source_height=height,
            has_audio=params.get('has_audio', True),
        )
        os.replace(temp_output, output_path)
    finally:
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except OSError:
                pass


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
        if job.get('operation') == 'video_edit':
            return _run_video_edit(job, params, on_progress, on_stage)

        if job.get('operation') == 'compression':
            return _run_compression(job, params, on_progress, on_stage)

        if job.get('operation') in ('compress', 'convert'):
            return _run_compress_convert(job, params, on_progress, on_stage)

        from app import licensing

        # pixel_art resolves no model at any scale — see
        # licensing.MODEL_FREE_CONTENT_TYPES for the measurements behind that.
        model_free_content = (
            job.get('content_type_detected') in licensing.MODEL_FREE_CONTENT_TYPES
            or params.get('content_type_override') in licensing.MODEL_FREE_CONTENT_TYPES
        )
        if job.get('media_type') == 'image' and (
            params.get('scale') == '1x' or model_free_content
        ):
            # Imagem screen's Original mode: keep or reduce the size, run the
            # filters, never the model. No engine is resolved and the isolated
            # worker is not involved — that subprocess exists to contain model
            # inference, and there is none here (same reasoning as the
            # compress/convert branch above). It still writes the job's master,
            # so export/re-export downstream is unchanged.
            from app.processing import Upscaler

            adjustments = params.get('adjustments', {})
            custom = params.get('custom_size')
            resize = (int(custom['width']), int(custom['height'])) if custom else None

            # A scale of 2x/4x has to be honoured here too, not only a
            # custom size. Original mode always sends an explicit target,
            # so this branch never needed to read `scale` -- and when
            # pixel_art started arriving with '4x' and no custom size, the
            # job completed and quietly returned the source at its own
            # resolution. Silently doing nothing is the worst way to fail.
            if resize is None:
                factor = {'2x': 2, '4x': 4}.get(params.get('scale'))
                if factor:
                    import cv2

                    probe = cv2.imread(job['input_path'], cv2.IMREAD_UNCHANGED)
                    if probe is not None:
                        resize = (probe.shape[1] * factor, probe.shape[0] * factor)

            return Upscaler.process_without_model(
                job['input_path'],
                _master_path(job_id),
                settings.models_dir,
                resize=resize,
                on_progress=on_progress,
                on_stage=on_stage,
                sharpen_strength=adjustments.get('deblur', 0),
                face_recovery=adjustments.get('face_correction', False),
                face_recovery_strength=adjustments.get('face_recovery_strength', 80),
                denoise_filter_strength=(
                    adjustments.get('denoise_filter_strength', 0)
                    if adjustments.get('denoise_filter_enabled') else 0
                ),
            )

        audio_mode = params.get('audio_mode')
        if (job.get('media_type') == 'audio' and job.get('content_type_detected') == 'music'
                and audio_mode not in (None, 'enhance')):
            # specs/006-audio-engine-masterizacao — audio_mode opts a music job
            # into app.audio_engine.mastering.MasteringEngine instead of the
            # single-pass _ENGINE_ENHANCERS['sonicmaster'] path below. Runs in
            # this same executor thread (not the primary isolated worker
            # subprocess) — MasteringEngine's own AI step is isolated via its
            # own audio-worker subprocess (get_audio_worker_supervisor()),
            # which is the real isolation boundary here, not this thread.
            from app.audio_engine.mastering import MasteringEngine

            output_path = _audio_output_path(job_id, job['input_path'])
            os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
            if on_stage:
                on_stage('Analisando e restaurando áudio')
            result = MasteringEngine().run(
                audio_mode, job['input_path'], output_path,
                ai_strength=params.get('ai_strength') or 50,
            )
            job['audio_analysis'] = {
                'integrated_lufs': result.audio_analysis.integrated_lufs,
                'true_peak_db': result.audio_analysis.true_peak_db,
                'dynamic_range_db': result.audio_analysis.dynamic_range_db,
                'clipping_ratio': result.audio_analysis.clipping_ratio,
            }
            if result.quality_verdict is not None:
                job['quality_verdict'] = {
                    'outcome': result.quality_verdict.outcome,
                    'reasons': result.quality_verdict.reasons,
                }
            if on_progress:
                on_progress(100)
            return {'source_size': (0, 0), 'output_size': (0, 0)}

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
        upscale_result = get_supervisor().process(
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

        # The editor's settings, applied to the upscaled result (007 §Upscale
        # com edição). Video only: the image path has its own adjustment
        # pipeline inside the model pass, and a second one here would be two
        # ways to do the same thing.
        if is_video:
            _apply_edits_to_upscaled(job, params, output_path, on_stage)
        return upscale_result

    try:
        result_meta = await loop.run_in_executor(_executor, blocking_run)
        if job['status'] == 'cancelled':
            _notify(job_id)
            return
        job['status'] = 'done'
        job['progress'] = 100
        job['stage'] = None
        job['processing_ended_at'] = _now_iso()
        if job.get('operation') in ('compress', 'convert', 'video_edit', 'compression'):
            # No lossless "master" here (unlike enhance) — optimize_file(),
            # video_edits.export() and the Compression Centre's runner already
            # wrote the real, final result.
            #
            # video_edit belongs in THIS branch, not the media_type == 'video'
            # one below: that branch is the upscale path, which reads
            # result_meta['source_size'] and resolves the output to
            # _video_output_path(job_id). Falling into it raised KeyError on
            # 'source_size' and would then have pointed output_path at the
            # upscale location rather than where the export was written.
            # Checking the OPERATION before the media type is what keeps the two
            # apart.
            job['output_path'] = result_meta['output_path']
            source_w, source_h = _media_dimensions(job['input_path'])
            output_w, output_h = _media_dimensions(result_meta['output_path'])
            job['source_meta'] = {
                'width': source_w, 'height': source_h,
                'size_bytes': os.path.getsize(job['input_path']) if os.path.isfile(job['input_path']) else None,
            }
            job['output_meta'] = {
                'width': output_w, 'height': output_h, 'size_bytes': result_meta['size_bytes'],
            }
            # Os números medidos da Central — economia, redução, tempo, e se o
            # arquivo cresceu. Ficam num campo próprio para não alargar
            # `output_meta`, que é contrato compartilhado com telas antigas.
            if 'compression' in result_meta:
                job['compression'] = result_meta['compression']
                _record_compression_history(job, result_meta['compression'])
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
            _record_failure(job, error)
    except Exception as error:  # noqa: BLE001 - surfaced to the client as job.error
        if job['status'] != 'cancelled':
            _record_failure(job, error)
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


async def _audio_worker_idle_watchdog_loop(
    idle_timeout_seconds: float = 300.0, check_interval_seconds: float = 30.0,
) -> None:
    """Releases the audio-worker's VRAM after real inactivity — FR-019 only
    requires the model to stay loaded *for reuse across operations*, not
    forever; on an 8GB GPU, SonicMaster's ~7.9GB footprint (measured, T043)
    otherwise starves everything else indefinitely after a single job. Added
    after real operator testing surfaced this, not part of the original
    spec — a deliberate product decision, not a correctness fix. Never
    touches a worker mid-job (same non-interference rule as _watchdog_loop),
    and does nothing when the audio-worker isn't configured or was never
    actually spawned."""
    while True:
        await asyncio.sleep(check_interval_seconds)
        supervisor = _audio_worker_supervisor
        if supervisor is None or not supervisor.is_alive():
            continue
        if _processing_job_id is not None:
            continue
        if supervisor._last_used_at is None:
            continue
        if time.monotonic() - supervisor._last_used_at >= idle_timeout_seconds:
            supervisor.terminate()


def start_worker() -> None:
    global _worker_task, _watchdog_task, _audio_idle_watchdog_task
    if _worker_task is None:
        _worker_task = asyncio.get_event_loop().create_task(_worker_loop())
    if _watchdog_task is None:
        _watchdog_task = asyncio.get_event_loop().create_task(_watchdog_loop())
    if _audio_idle_watchdog_task is None:
        _audio_idle_watchdog_task = asyncio.get_event_loop().create_task(_audio_worker_idle_watchdog_loop())


def export_job(job_id: str, output_path: str, quality: int | None) -> None:
    """Re-encodes a done job's cached master result — no model inference, so this
    is always fast regardless of the original image's size."""
    from app.processing import Upscaler

    job = jobs.get(job_id)
    if job is None:
        raise ValueError('Job não encontrado.')
    if job['status'] != 'done':
        raise ValueError('Job ainda não foi concluído.')
    # An enhance job caches a lossless master to re-encode from. A compress or
    # convert job has no master — optimize_file() already wrote the real result,
    # and that file is what this re-encodes from instead.
    master_path = _master_path(job_id)
    source_path = master_path if os.path.isfile(master_path) else job.get('output_path')
    if not source_path or not os.path.isfile(source_path):
        raise ValueError('Resultado do job não está mais disponível.')
    Upscaler.export(source_path, output_path, quality)
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
    eterzion_upscale.processing.load_model, wrapped by app.processing.Upscaler.
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
    """T042 — wraps the same eterzion_upscale frame-by-frame model pipeline the
    old CLI's `run_video` used. `msg['master_path']` is where the final,
    audio-muxed video is written directly — video has no separate "master then
    export" step like images do."""
    denoise = msg.get('denoise', 50) / 100
    half = msg.get('half', True)
    upscaler = _get_video_upscaler(
        msg['model'], msg['models_dir'], msg.get('device'), denoise, half, msg.get('protected'),
        msg.get('tile_threshold'), msg.get('tile_size'))
    custom = msg.get('custom_size')
    result = upscaler.process(
        msg['input_path'], msg.get('scale', 2), msg['master_path'],
        on_progress=lambda pct: send({'type': 'progress', 'pct': pct}),
        on_stage=lambda stage: send({'type': 'stage', 'stage': stage}),
        stabilize=msg.get('stabilize', False),
        custom_size=(custom['width'], custom['height']) if custom else None,
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
