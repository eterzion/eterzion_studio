"""Real integration tests for worker_supervisor.py — actually spawns the
isolated worker subprocess (python -m app.jobs) and talks to
it over a real local IPC pipe, the same way job_manager does in production.
This is deliberately NOT mocked: it's the one module in this codebase whose
entire job is process lifecycle + IPC, so a test that mocked subprocess.Popen
would prove nothing real. Slower than the rest of the suite (each spawn pays
a real Python-interpreter-plus-torch-import cost) but honest."""
from __future__ import annotations

import os
import threading
import time
from multiprocessing.connection import Listener

import cv2
import numpy as np
import pytest

from app.config import settings
from app import jobs as worker_supervisor
from app.jobs import WorkerCrashed, WorkerFailure, WorkerSupervisor


def _make_test_image_path(tmp_path, name='in.png'):
    img = np.full((24, 24, 3), 150, dtype=np.uint8)
    cv2.rectangle(img, (2, 2), (22, 22), (200, 90, 90), -1)
    path = tmp_path / name
    cv2.imwrite(str(path), img)
    return str(path)


@pytest.fixture
def supervisor():
    sup = WorkerSupervisor()
    yield sup
    sup.terminate()  # always clean up the real child process, pass or fail


class TestRestrictedEnv:
    def test_includes_the_authkey(self):
        env = worker_supervisor._restricted_env('secret-key-123')
        assert env['ASTROS_WORKER_AUTHKEY'] == 'secret-key-123'

    def test_only_passes_through_the_documented_allowlist(self, monkeypatch):
        monkeypatch.setenv('ASTROS_SOME_API_SECRET', 'must-not-leak')
        monkeypatch.setenv('PATH', os.environ.get('PATH', ''))
        env = worker_supervisor._restricted_env('key')
        assert 'ASTROS_SOME_API_SECRET' not in env

    def test_passes_through_path_when_present(self, monkeypatch):
        monkeypatch.setenv('PATH', 'C:\\some\\real\\path')
        env = worker_supervisor._restricted_env('key')
        assert env.get('PATH') == 'C:\\some\\real\\path'


class TestRealWorkerLifecycle:
    pytestmark = pytest.mark.slow

    def test_ensure_started_spawns_a_real_alive_process(self, supervisor):
        supervisor.ensure_started()
        assert supervisor.is_alive() is True
        assert supervisor._process.pid > 0

    def test_ensure_started_is_idempotent_while_alive(self, supervisor):
        supervisor.ensure_started()
        first_pid = supervisor._process.pid
        supervisor.ensure_started()  # must not spawn a second process
        assert supervisor._process.pid == first_pid

    def test_ping_gets_a_real_pong_over_the_pipe(self, supervisor):
        supervisor.ensure_started()
        assert supervisor.ping(timeout=10) is True

    def test_ping_is_false_when_never_started(self, supervisor):
        assert supervisor.ping() is False

    def test_terminate_actually_kills_the_process(self, supervisor):
        supervisor.ensure_started()
        pid = supervisor._process.pid
        supervisor.terminate()
        assert supervisor.is_alive() is False
        # the OS-level process is really gone, not just forgotten by us
        time.sleep(0.2)
        assert not _pid_exists(pid)

    def test_ping_is_false_after_terminate(self, supervisor):
        supervisor.ensure_started()
        supervisor.terminate()
        assert supervisor.ping() is False

    def test_ensure_started_respawns_after_terminate(self, supervisor):
        supervisor.ensure_started()
        first_pid = supervisor._process.pid
        supervisor.terminate()
        supervisor.ensure_started()
        assert supervisor.is_alive() is True
        assert supervisor._process.pid != first_pid


def _pid_exists(pid: int) -> bool:
    import subprocess

    result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], capture_output=True, text=True, check=False)
    return str(pid) in result.stdout


class TestRealProcessCall:
    pytestmark = pytest.mark.slow

    def test_processes_a_real_image_through_the_real_isolated_worker(self, supervisor, tmp_path):
        """The full real path: spawn subprocess -> subprocess passes its own
        integrity self-check -> imports app.processing -> loads the real
        hfa2k-span model -> runs real inference -> sends the result back
        over the pipe. Nothing here is mocked."""
        input_path = _make_test_image_path(tmp_path)
        master_path = str(tmp_path / 'master.png')
        progress_events = []
        stage_events = []

        result = supervisor.process(
            job_id='job_test_real',
            input_path=input_path,
            master_path=master_path,
            model='hfa2k-span',
            models_dir=settings.models_dir,
            device='cpu',
            scale=2,
            custom_size=None,
            denoise=50,
            on_progress=progress_events.append,
            on_stage=stage_events.append,
        )

        assert result['source_size'] == (24, 24)
        assert result['output_size'] == (48, 48)
        assert os.path.isfile(master_path)
        written = cv2.imread(master_path)
        assert written.shape == (48, 48, 3)
        assert progress_events[-1] == 100
        assert 'Aplicando modelo de IA' in stage_events

    def test_worker_is_reused_across_multiple_process_calls(self, supervisor, tmp_path):
        input_path = _make_test_image_path(tmp_path)
        supervisor.process(
            job_id='job_1', input_path=input_path, master_path=str(tmp_path / 'a.png'),
            model='hfa2k-span', models_dir=settings.models_dir, device='cpu', scale=2,
            custom_size=None, denoise=50,
        )
        pid_after_first = supervisor._process.pid

        supervisor.process(
            job_id='job_2', input_path=input_path, master_path=str(tmp_path / 'b.png'),
            model='hfa2k-span', models_dir=settings.models_dir, device='cpu', scale=2,
            custom_size=None, denoise=50,
        )
        assert supervisor._process.pid == pid_after_first  # same child, no respawn

    def test_raises_worker_failure_for_a_missing_input_file(self, supervisor, tmp_path):
        with pytest.raises(WorkerFailure):
            supervisor.process(
                job_id='job_bad', input_path=str(tmp_path / 'does-not-exist.png'),
                master_path=str(tmp_path / 'out.png'), model='hfa2k-span',
                models_dir=settings.models_dir, device='cpu', scale=2, custom_size=None, denoise=50,
            )

    def test_raises_worker_failure_for_an_unknown_model(self, supervisor, tmp_path):
        input_path = _make_test_image_path(tmp_path)
        with pytest.raises(WorkerFailure):
            supervisor.process(
                job_id='job_bad_model', input_path=input_path, master_path=str(tmp_path / 'out.png'),
                model='this-model-does-not-exist', models_dir=settings.models_dir,
                device='cpu', scale=2, custom_size=None, denoise=50,
            )

    def test_raises_worker_crashed_when_the_pipe_dies_mid_call(self, supervisor, tmp_path):
        """Simulates the child dying unexpectedly *while process() is blocked
        waiting on the pipe* — a real dead connection, not a simulated
        exception. Killing it beforehand would just make ensure_started()'s
        own auto-recovery spawn a fresh worker and succeed (confirmed by
        hand: that was this test's first, wrong version) — the connection
        has to die mid-flight, so a background thread kills the real OS
        process shortly after process() has already sent its request and
        started blocking on the reply."""
        supervisor.ensure_started()  # connection established while process is confirmed alive
        input_path = _make_test_image_path(tmp_path)

        def kill_shortly_after_the_request_is_sent():
            time.sleep(0.05)
            supervisor._process.kill()

        killer = threading.Thread(target=kill_shortly_after_the_request_is_sent)
        killer.start()
        try:
            with pytest.raises(WorkerCrashed):
                supervisor.process(
                    job_id='job_after_kill', input_path=input_path, master_path=str(tmp_path / 'out.png'),
                    model='hfa2k-span', models_dir=settings.models_dir, device='cpu', scale=2,
                    custom_size=None, denoise=50,
                )
        finally:
            killer.join()


class TestAcceptWithTimeout:
    def test_times_out_and_raises_worker_crashed_when_nothing_connects(self, supervisor):
        """A real Listener that nothing ever connects to — proves the
        timeout path itself (not the torch-import-speed-dependent real
        spawn path other tests exercise)."""
        supervisor._listener = Listener(family='AF_PIPE', authkey=b'test-authkey-for-timeout-check')
        supervisor._process = None
        start = time.time()
        with pytest.raises(WorkerCrashed):
            supervisor._accept_with_timeout(timeout=0.5)
        assert time.time() - start < 5  # actually bounded by the timeout, not hanging


class TestShutdown:
    pytestmark = pytest.mark.slow

    def test_shutdown_terminates_and_clears_the_module_singleton(self, monkeypatch):
        fresh = WorkerSupervisor()
        monkeypatch.setattr(worker_supervisor, '_supervisor', fresh)
        fresh.ensure_started()
        assert fresh.is_alive() is True

        worker_supervisor.shutdown()

        assert fresh.is_alive() is False
        assert worker_supervisor._supervisor is None

    def test_shutdown_is_a_no_op_when_never_started(self, monkeypatch):
        monkeypatch.setattr(worker_supervisor, '_supervisor', None)
        worker_supervisor.shutdown()  # must not raise
        assert worker_supervisor._supervisor is None


class TestGetSupervisor:
    def test_returns_the_same_instance_across_calls(self, monkeypatch):
        monkeypatch.setattr(worker_supervisor, '_supervisor', None)
        first = worker_supervisor.get_supervisor()
        second = worker_supervisor.get_supervisor()
        assert first is second
        first.terminate()
        monkeypatch.setattr(worker_supervisor, '_supervisor', None)


class TestConfigurableInterpreter:
    """specs/006-audio-engine-masterizacao — WorkerSupervisor's constructor now
    accepts an interpreter/spawn-args override. Not `slow`: only checks the
    stored spawn configuration, no real subprocess."""

    def test_defaults_match_the_original_hardcoded_behaviour(self):
        import sys
        sup = WorkerSupervisor()
        assert sup._python_executable == sys.executable
        assert sup._spawn_args == ['-m', 'app.jobs']

    def test_accepts_a_custom_interpreter_and_spawn_args(self):
        sup = WorkerSupervisor(python_executable='C:/fake/python.exe', spawn_args=['worker_main.py'])
        assert sup._python_executable == 'C:/fake/python.exe'
        assert sup._spawn_args == ['worker_main.py']


class TestGetAudioWorkerSupervisor:
    """FR-021/FR-023, research.md Decisão 3 (corrigida em /speckit.analyze): um
    segundo supervisor, nunca a mesma instância de get_supervisor()."""

    def test_returns_none_when_audio_worker_python_is_unset(self, monkeypatch):
        monkeypatch.setattr(settings, 'audio_worker_python', '')
        monkeypatch.setattr(worker_supervisor, '_audio_worker_supervisor', None)
        assert worker_supervisor.get_audio_worker_supervisor() is None

    def test_returns_a_distinct_instance_from_get_supervisor(self, monkeypatch):
        monkeypatch.setattr(settings, 'audio_worker_python', 'C:/fake/audio-venv/python.exe')
        monkeypatch.setattr(worker_supervisor, '_audio_worker_supervisor', None)
        monkeypatch.setattr(worker_supervisor, '_supervisor', None)
        image_sup = worker_supervisor.get_supervisor()
        audio_sup = worker_supervisor.get_audio_worker_supervisor()
        assert audio_sup is not None
        assert audio_sup is not image_sup
        assert image_sup._python_executable != audio_sup._python_executable
        image_sup.terminate()
        monkeypatch.setattr(worker_supervisor, '_supervisor', None)
        monkeypatch.setattr(worker_supervisor, '_audio_worker_supervisor', None)

    def test_returns_the_same_audio_instance_across_calls(self, monkeypatch):
        monkeypatch.setattr(settings, 'audio_worker_python', 'C:/fake/audio-venv/python.exe')
        monkeypatch.setattr(worker_supervisor, '_audio_worker_supervisor', None)
        first = worker_supervisor.get_audio_worker_supervisor()
        second = worker_supervisor.get_audio_worker_supervisor()
        assert first is second
        monkeypatch.setattr(worker_supervisor, '_audio_worker_supervisor', None)
