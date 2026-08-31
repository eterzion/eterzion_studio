"""T065 — real, subprocess-level coverage that cancelling a video job kills
its isolated worker process within 5 seconds, extending the real-subprocess
pattern test_worker_supervisor.py already uses for images. Nothing mocked:
a real ffmpeg-built video, the real 'realesr-animevideo' model, a real OS
process killed from another thread while genuinely mid-inference.

Video/audio share the exact same WorkerSupervisor.terminate() mechanism
image jobs already use (job_manager.cancel_job() has no media_type branch at
all — see job_manager.py) — this test's real value is proving that holds for
a job whose worker call takes long enough to still be running when cancelled,
not just for an already-finished quick image job."""
from __future__ import annotations

import subprocess
import threading
import time

import pytest

from app.config import settings
from app.jobs import WorkerCrashed, WorkerFailure, WorkerSupervisor
from eterzion_upscale.media import has_ffmpeg
from eterzion_upscale.media import ffmpeg_path

pytestmark = [pytest.mark.slow, pytest.mark.skipif(not has_ffmpeg(), reason='requires a real ffmpeg binary')]


def _build_test_video(path: str, fps: int = 10, duration: float = 6.0) -> None:
    """Long enough (60 frames) that real CPU inference genuinely takes a few
    seconds — enough time for the cancelling thread to call terminate() while
    the worker is still mid-job, not before it starts or after it's done."""
    result = subprocess.run([
        ffmpeg_path() or 'ffmpeg', '-y', '-f', 'lavfi', '-i', f'color=c=blue:s=96x64:r={fps}:d={duration}',
        '-c:v', 'mpeg4', '-an', path,
    ], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


@pytest.fixture
def supervisor():
    sup = WorkerSupervisor()
    yield sup
    sup.terminate()


class TestCancelRunningVideoJobKillsWorker:
    def test_terminate_mid_processing_kills_the_subprocess_within_5_seconds(self, supervisor, tmp_path):
        input_path = str(tmp_path / 'in.mp4')
        output_path = str(tmp_path / 'out.mp4')
        _build_test_video(input_path)

        call_error: list[Exception] = []
        started = threading.Event()

        def on_progress(pct: int) -> None:
            started.set()  # real progress means the worker is genuinely mid-job

        def run_call() -> None:
            try:
                supervisor.process(
                    job_id='job_cancel_test', media_type='video', operation='enhance',
                    input_path=input_path, master_path=output_path,
                    model='realesr-animevideo', models_dir=settings.models_dir, device='cpu',
                    scale=2, custom_size=None, denoise=50, on_progress=on_progress,
                )
            except (WorkerCrashed, WorkerFailure) as error:
                call_error.append(error)

        worker_thread = threading.Thread(target=run_call, daemon=True)
        worker_thread.start()

        assert started.wait(timeout=30), 'worker never reported progress — job never actually started'
        assert supervisor.is_alive()

        cancel_started_at = time.monotonic()
        supervisor.terminate()
        worker_thread.join(timeout=5.0)
        elapsed = time.monotonic() - cancel_started_at

        assert not worker_thread.is_alive(), 'the process() call thread never returned after terminate()'
        assert elapsed < 5.0
        assert not supervisor.is_alive()
        # The in-flight call must have surfaced as a real failure (the pipe
        # died mid-call) — not silently returned a fabricated success result.
        assert len(call_error) == 1
        assert isinstance(call_error[0], (WorkerCrashed, WorkerFailure))
