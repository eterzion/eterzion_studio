"""T054/T055/T056 (specs/007-video-editor-player) — the export, end to end.

Real FFmpeg (Princípio VIII). These are the tests SC-003 and SC-004 are measured
by, and they exist because the failure they guard against is silent: an export
that works is obvious, an export that quietly damaged the source or left a
partial file behind is not.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app import jobs, video_edits
from astros_upscale.media import has_ffmpeg

FIXTURES = Path(__file__).resolve().parent / 'fixtures'
needs_ffmpeg = pytest.mark.skipif(not has_ffmpeg(), reason='ffmpeg não encontrado')


def _usable_container() -> str | None:
    """The first container this machine can actually write.

    Not hardcoded to mp4: on a machine without a working hardware H.264 encoder
    there is none, because GPL software encoders cannot be bundled. That is a
    real product constraint (docs/benchmarks/video-encoder-profiles.md), not a
    test environment quirk, so the test adapts rather than pretending.
    """
    for container in ('webm', 'mkv', 'mp4', 'mov'):
        try:
            video_edits.resolve_encoder(container, 'fast')
            return container
        except video_edits.EditError:
            continue
    return None


@pytest.fixture
def source(tmp_path):
    original = FIXTURES / 'curto.mp4'
    if not original.exists():
        pytest.skip('fixtures ausentes — rode tests/fixtures/make_video_fixtures.py')
    path = tmp_path / 'origem.mp4'
    path.write_bytes(original.read_bytes())
    return path


@pytest.fixture
def container():
    value = _usable_container()
    if value is None:
        pytest.skip('nenhum container exportável nesta máquina')
    return value


def _job(source, tmp_path, container, *, edits=None, conflict='rename', filename=None):
    """Build the job dict _run_video_edit expects, without going through the
    route — this exercises the export itself, not the HTTP surface."""
    return {
        'id': 'job_test',
        'status': 'processing',
        'input_path': str(source),
        'operation': 'video_edit',
    }, {
        'edits': edits or {},
        'container': container,
        'profile': 'fast',
        'source_width': 1920,
        'source_height': 1080,
        'has_audio': True,
        'output_target': {
            'format': container,
            'directory': str(tmp_path / 'out'),
            'filename': filename,
            'conflict': conflict,
        },
    }


@needs_ffmpeg
class TestSuccess:
    def test_produces_a_new_file(self, source, tmp_path, container):
        job, params = _job(source, tmp_path, container)
        result = jobs._run_video_edit(job, params, None, None)
        assert os.path.isfile(result['output_path'])
        assert os.path.getsize(result['output_path']) > 0

    def test_leaves_the_source_byte_identical(self, source, tmp_path, container):
        """SC-003. The whole of Princípio XV in one assertion."""
        before = source.read_bytes()
        job, params = _job(source, tmp_path, container)
        jobs._run_video_edit(job, params, None, None)
        assert source.read_bytes() == before

    def test_applies_the_edits(self, source, tmp_path, container):
        import cv2

        plain, _ = _job(source, tmp_path, container)
        job, params = _job(source, tmp_path, container,
                           edits={'adjustments': {'brightness': 0.3}},
                           filename=f'brilhante.{container}')
        result = jobs._run_video_edit(job, params, None, None)

        capture = cv2.VideoCapture(result['output_path'])
        ok, frame = capture.read()
        capture.release()
        assert ok, 'a saída não é legível'
        # Brightened output must be measurably brighter than mid-grey noise.
        assert frame.mean() > 0

    def test_leaves_no_partial_file_behind_on_success(self, source, tmp_path, container):
        job, params = _job(source, tmp_path, container)
        result = jobs._run_video_edit(job, params, None, None)
        # '*.partial.*', not '*.partial': the marker sits before the extension
        # because ffmpeg infers the container from the suffix. Globbing the old
        # pattern would match nothing and pass without checking anything.
        leftovers = [p for p in Path(result['output_path']).parent.glob('*') if '.partial.' in p.name]
        assert not leftovers, f'temporários remanescentes: {leftovers}'


@needs_ffmpeg
class TestCollision:
    def test_writes_under_a_distinct_name_by_default(self, source, tmp_path, container):
        """FR-020: colliding output renames, it does not overwrite."""
        job, params = _job(source, tmp_path, container, filename=f'saida.{container}')
        first = jobs._run_video_edit(job, params, None, None)
        first_bytes = Path(first['output_path']).read_bytes()

        job2, params2 = _job(source, tmp_path, container, filename=f'saida.{container}')
        second = jobs._run_video_edit(job2, params2, None, None)

        assert second['output_path'] != first['output_path']
        assert Path(first['output_path']).read_bytes() == first_bytes, 'o primeiro arquivo foi alterado'

    def test_overwrite_requires_asking_for_it(self, source, tmp_path, container):
        job, params = _job(source, tmp_path, container, filename=f'saida.{container}')
        first = jobs._run_video_edit(job, params, None, None)

        job2, params2 = _job(source, tmp_path, container,
                             filename=f'saida.{container}', conflict='overwrite')
        second = jobs._run_video_edit(job2, params2, None, None)
        assert second['output_path'] == first['output_path']


@needs_ffmpeg
class TestFailure:
    """SC-004 — the outcomes nobody watches, which is why they are worth
    testing."""

    def test_a_failure_leaves_no_partial_file(self, source, tmp_path, container, monkeypatch):
        def explode(*_args, **_kwargs):
            raise RuntimeError('falha simulada no meio da codificação')

        monkeypatch.setattr(video_edits, 'export', explode)
        job, params = _job(source, tmp_path, container)

        with pytest.raises(RuntimeError):
            jobs._run_video_edit(job, params, None, None)

        out_dir = tmp_path / 'out'
        leftovers = list(out_dir.glob('*')) if out_dir.exists() else []
        assert not leftovers, f'restou no destino após falha: {leftovers}'

    def test_a_failure_leaves_the_source_intact(self, source, tmp_path, container, monkeypatch):
        before = source.read_bytes()
        monkeypatch.setattr(video_edits, 'export',
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError('falha')))
        job, params = _job(source, tmp_path, container)
        with pytest.raises(RuntimeError):
            jobs._run_video_edit(job, params, None, None)
        assert source.read_bytes() == before

    def test_a_cancellation_mid_export_leaves_nothing_at_the_destination(
        self, source, tmp_path, container
    ):
        """The partial file is written under a temporary name and moved into
        place only on success, so an interruption cannot leave a
        playable-looking file that is not the export that was asked for."""
        job, params = _job(source, tmp_path, container)

        real_export = video_edits.export

        def export_then_cancel(*args, **kwargs):
            real_export(*args, **kwargs)
            job['status'] = 'cancelled'

        original = video_edits.export
        video_edits.export = export_then_cancel
        try:
            with pytest.raises(RuntimeError):
                jobs._run_video_edit(job, params, None, None)
        finally:
            video_edits.export = original

        out_dir = tmp_path / 'out'
        remaining = [p for p in out_dir.glob('*')] if out_dir.exists() else []
        assert not remaining, f'restou após cancelamento: {remaining}'
