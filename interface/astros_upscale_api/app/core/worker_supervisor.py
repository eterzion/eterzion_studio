"""Parent-side manager for the isolated processing worker (Fase 1 — isolamento
de processo, docs/processing-protection-architecture.md).

Owns the child process lifecycle: spawns it with a restricted environment (no
shell, no inherited secrets beyond a one-time IPC authkey), talks to it over an
authenticated local pipe, and can actually kill it — unlike the old
ThreadPoolExecutor approach, cancellation here stops real work instead of just
discarding a thread's result. A single job runs at a time, mirroring the
previous single-worker semantics; concurrency, if ever needed, would mean a
pool of these, not larger messages on one pipe.
"""
from __future__ import annotations

import os
import secrets
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from multiprocessing.connection import Listener
from pathlib import Path
from typing import Callable, TypedDict

from app.core import secure_tempdir

_API_ROOT = Path(__file__).resolve().parent.parent.parent  # app/core -> app -> astros_upscale_api


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
        # Needed for install_identity.py's DPAPI-protected identity file (Fase 2/4)
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
        self._runtime_dir = secure_tempdir.create_private_dir()
        self._authkey = secrets.token_hex(32)
        self._listener = Listener(family='AF_PIPE', authkey=self._authkey.encode('utf-8'))
        self._process = subprocess.Popen(
            [sys.executable, '-m', 'app.core.isolated_worker', self._listener.address],
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
            secure_tempdir.remove_dir(self._runtime_dir)
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
        """Blocking call — meant to run inside job_manager's single-worker
        executor thread, same as the direct-call version it replaces.
        `protected`, when set, tells the worker to fetch the orchestration
        logic from the licensing service (Fase 4) instead of using its own
        static import — see isolated_worker.py's module registry.

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
