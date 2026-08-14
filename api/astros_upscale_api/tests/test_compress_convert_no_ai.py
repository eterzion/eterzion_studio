"""T026: compress/convert operations must never load an AI model — real
ffmpeg/OpenCV transcoding only (FR-029, Constitution "No AI Without Benefit").
Spies on profile_resolver.resolve() and astros_upscale.processing.load_model() (the
one place a spandrel/torch model actually gets loaded) to prove the AI path
is never even touched, then runs a REAL compress job end-to-end and confirms
distinct quality levels produce measurably different file sizes (the
Independent Test criterion for User Story 2)."""
from __future__ import annotations

import asyncio
import os

import cv2
import numpy as np
import pytest

from app import jobs as job_manager


def _write_test_image(path, size=96):
    rng = np.random.default_rng(3)
    img = rng.integers(0, 255, (size, size, 3), dtype=np.uint8)
    cv2.imwrite(str(path), img)
    return str(path)


@pytest.fixture(autouse=True)
def spy_on_ai_paths(monkeypatch):
    calls = {'resolve': 0, 'load_model': 0}

    from app import licensing as profile_resolver
    from astros_upscale import processing as astros_core

    real_resolve = profile_resolver.resolve
    real_load_model = astros_core.load_model

    def spy_resolve(*args, **kwargs):
        calls['resolve'] += 1
        return real_resolve(*args, **kwargs)

    def spy_load_model(*args, **kwargs):
        calls['load_model'] += 1
        return real_load_model(*args, **kwargs)

    monkeypatch.setattr(profile_resolver, 'resolve', spy_resolve)
    monkeypatch.setattr(astros_core, 'load_model', spy_load_model)
    return calls


def _make_job(tmp_path, operation, quality, input_name='in.jpg'):
    input_path = _write_test_image(tmp_path / input_name)
    job_id = job_manager.create_job(
        input_path, input_name,
        {'output_target': {'format': 'jpg', 'directory': str(tmp_path), 'filename': f'out_{quality}.jpg'},
         'quality': quality, 'adjustments': {}},
        media_type='image', operation=operation,
    )
    job_manager.jobs[job_id]['status'] = 'queued'
    return job_id


def test_compress_job_never_calls_profile_resolver_or_load_model(tmp_path, spy_on_ai_paths):
    job_id = _make_job(tmp_path, 'compress', quality=50)
    asyncio.run(job_manager._process_job(job_id))

    job = job_manager.get_job(job_id)
    assert job['status'] == 'done', job.get('error')
    assert spy_on_ai_paths['resolve'] == 0
    assert spy_on_ai_paths['load_model'] == 0


def test_convert_job_never_calls_profile_resolver_or_load_model(tmp_path, spy_on_ai_paths):
    input_path = _write_test_image(tmp_path / 'in.jpg')
    job_id = job_manager.create_job(
        input_path, 'in.jpg',
        {'output_target': {'format': 'png', 'directory': str(tmp_path), 'filename': 'out.png'}, 'adjustments': {}},
        media_type='image', operation='convert',
    )
    job_manager.jobs[job_id]['status'] = 'queued'
    asyncio.run(job_manager._process_job(job_id))

    job = job_manager.get_job(job_id)
    assert job['status'] == 'done', job.get('error')
    assert spy_on_ai_paths['resolve'] == 0
    assert spy_on_ai_paths['load_model'] == 0
    assert job['output_path'].endswith('out.png')


def test_compress_quality_levels_produce_measurably_different_file_sizes(tmp_path):
    """Independent Test for User Story 2 (Phase 4 goal): distinct compression
    levels must produce distinct file sizes — a real, end-to-end assertion,
    not a mock of optimize.py's internals."""
    low_job = _make_job(tmp_path, 'compress', quality=5, input_name='low.jpg')
    high_job = _make_job(tmp_path, 'compress', quality=95, input_name='high.jpg')

    asyncio.run(job_manager._process_job(low_job))
    asyncio.run(job_manager._process_job(high_job))

    low = job_manager.get_job(low_job)
    high = job_manager.get_job(high_job)
    assert low['status'] == 'done', low.get('error')
    assert high['status'] == 'done', high.get('error')
    assert low['output_meta']['size_bytes'] < high['output_meta']['size_bytes']


def test_compress_job_resizes_to_the_exact_requested_dimensions(tmp_path):
    """The Exportar screen's Dimensões field travels as `custom_size` in the
    job params — this walks the same path the UI uses (create_job -> params ->
    _run_compress_convert -> optimize_file) and asserts the pixels actually
    changed, so a break anywhere in that chain fails here."""
    input_path = _write_test_image(tmp_path / 'in.jpg', size=200)
    job_id = job_manager.create_job(
        input_path, 'in.jpg',
        {'output_target': {'format': 'jpg', 'directory': str(tmp_path), 'filename': 'resized.jpg'},
         'quality': 80, 'custom_size': {'width': 120, 'height': 90}, 'adjustments': {}},
        media_type='image', operation='compress',
    )
    job_manager.jobs[job_id]['status'] = 'queued'
    asyncio.run(job_manager._process_job(job_id))

    job = job_manager.get_job(job_id)
    assert job['status'] == 'done', job.get('error')
    assert cv2.imread(job['output_path']).shape[:2] == (90, 120)
    # The Exportar screen reads these back to show what actually came out —
    # they used to be hardcoded None, so a resize was invisible in the UI.
    assert job['source_meta']['width'] == 200 and job['source_meta']['height'] == 200
    assert job['output_meta']['width'] == 120 and job['output_meta']['height'] == 90


def test_compress_without_an_output_target_writes_to_the_outputs_dir(tmp_path, monkeypatch):
    """The Imagem screen's "Original" scale mode sends no output_target: it
    re-encodes without scaling and lets its own export panel choose where the
    file really goes. Defaulting to the source's folder there would drop an
    unrequested file next to the person's original."""
    from app.config import settings

    outputs = tmp_path / 'outputs'
    outputs.mkdir()
    monkeypatch.setattr(settings, 'outputs_dir', str(outputs))

    source_dir = tmp_path / 'source'
    source_dir.mkdir()
    input_path = _write_test_image(source_dir / 'in.jpg')
    job_id = job_manager.create_job(
        input_path, 'in.jpg', {'quality': 80, 'adjustments': {}},
        media_type='image', operation='compress',
    )
    job_manager.jobs[job_id]['status'] = 'queued'
    asyncio.run(job_manager._process_job(job_id))

    job = job_manager.get_job(job_id)
    assert job['status'] == 'done', job.get('error')
    assert os.path.dirname(job['output_path']) == str(outputs)
    assert list(source_dir.iterdir()) == [source_dir / 'in.jpg']


def test_export_falls_back_to_the_result_when_a_job_has_no_master(tmp_path, monkeypatch):
    """Only an enhance job caches a lossless master to re-encode from. A
    compress job's real result is the file optimize_file() already wrote, and
    the export panel has to be able to re-encode from that instead."""
    from app.config import settings

    outputs = tmp_path / 'outputs'
    outputs.mkdir()
    monkeypatch.setattr(settings, 'outputs_dir', str(outputs))

    input_path = _write_test_image(tmp_path / 'in.jpg')
    job_id = job_manager.create_job(
        input_path, 'in.jpg', {'quality': 80, 'adjustments': {}},
        media_type='image', operation='compress',
    )
    job_manager.jobs[job_id]['status'] = 'queued'
    asyncio.run(job_manager._process_job(job_id))
    assert not os.path.isfile(job_manager._master_path(job_id))

    exported = str(tmp_path / 'exported.png')
    job_manager.export_job(job_id, exported, quality=90)
    assert cv2.imread(exported) is not None
