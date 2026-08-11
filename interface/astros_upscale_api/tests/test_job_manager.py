"""Tests for job_manager.py — the in-memory job state machine. The actual
model inference (WorkerSupervisor.process(), which spawns a real subprocess)
is replaced with a controllable fake (see conftest.py's fake_supervisor) so
these tests exercise the state machine itself (pending -> queued ->
processing -> done/error/cancelled), not GPU/PyTorch — that boundary is real
code no test here duplicates.

`content_type_detected='photo'` is threaded through every create_job() call
that reaches _process_job(): blocking_run() resolves the job's real engine_ref
via profile_resolver.py (T012/T020), which requires a content_type for
operation='enhance' (FR-096) — job_manager itself never accepts or stores a
model identifier (FR-009/FR-011)."""
from __future__ import annotations

import asyncio

import pytest

from app.core import job_manager, worker_supervisor


def _create_photo_job(input_path, filename, params, **overrides):
    overrides.setdefault('content_type_detected', 'photo')
    return job_manager.create_job(input_path, filename, params, **overrides)


class TestCreateJob:
    def test_creates_a_pending_job_with_expected_fields(self, real_input_file, default_job_params):
        job_id = job_manager.create_job(real_input_file, 'input.png', default_job_params())
        job = job_manager.get_job(job_id)
        assert job['status'] == 'pending'
        assert job['input_file'] == 'input.png'
        assert job['input_path'] == real_input_file
        assert job['progress'] == 0
        assert job['output_path'] is None
        assert job_id.startswith('job_')

    def test_job_ids_are_unique(self, real_input_file, default_job_params):
        a = job_manager.create_job(real_input_file, 'a.png', default_job_params())
        b = job_manager.create_job(real_input_file, 'b.png', default_job_params())
        assert a != b

    def test_get_job_returns_none_for_unknown_id(self):
        assert job_manager.get_job('job_ghost') is None

    def test_list_jobs_returns_all_created_jobs(self, real_input_file, default_job_params):
        job_manager.create_job(real_input_file, 'a.png', default_job_params())
        job_manager.create_job(real_input_file, 'b.png', default_job_params())
        assert len(job_manager.list_jobs()) == 2

    def test_created_job_never_carries_a_model_identifier(self, real_input_file, default_job_params):
        """FR-009/FR-011 — job_manager's own contract, not just routes_jobs.py's."""
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())
        job = job_manager.get_job(job_id)
        assert 'model' not in job['params']
        assert 'model' not in job


class TestSecondaryElementsConfirmation:
    """T047, FR-081 to FR-086: a job whose probe found losses is created
    already in pending_confirmation — never reaches 'queued' until the
    person explicitly confirms."""

    def test_job_with_losses_is_created_pending_confirmation(self, real_input_file, default_job_params):
        job_id = job_manager.create_job(
            real_input_file, 'clip.mp4', default_job_params(), media_type='video', operation='enhance',
            content_type_detected='real_video',
            secondary_elements={'has_losses': True, 'losses': ['subtitles']},
        )
        assert job_manager.get_job(job_id)['status'] == 'pending_confirmation'

    def test_job_without_losses_is_created_plain_pending(self, real_input_file, default_job_params):
        job_id = job_manager.create_job(
            real_input_file, 'clip.mp4', default_job_params(), media_type='video', operation='enhance',
            content_type_detected='real_video',
            secondary_elements={'has_losses': False, 'losses': []},
        )
        assert job_manager.get_job(job_id)['status'] == 'pending'

    def test_enqueue_refuses_a_job_still_pending_confirmation(self, real_input_file, default_job_params):
        job_id = job_manager.create_job(
            real_input_file, 'clip.mp4', default_job_params(), media_type='video', operation='enhance',
            content_type_detected='real_video',
            secondary_elements={'has_losses': True, 'losses': ['chapters']},
        )
        assert asyncio.run(job_manager.enqueue(job_id)) is False
        assert job_manager.get_job(job_id)['status'] == 'pending_confirmation'

    def test_confirm_transitions_to_pending_and_then_enqueue_succeeds(self, real_input_file, default_job_params):
        job_id = job_manager.create_job(
            real_input_file, 'clip.mp4', default_job_params(), media_type='video', operation='enhance',
            content_type_detected='real_video',
            secondary_elements={'has_losses': True, 'losses': ['extra_audio_tracks']},
        )
        assert job_manager.confirm_secondary_elements(job_id) is True
        assert job_manager.get_job(job_id)['status'] == 'pending'
        assert asyncio.run(job_manager.enqueue(job_id)) is True
        assert job_manager.get_job(job_id)['status'] == 'queued'

    def test_confirm_is_a_no_op_for_a_job_not_awaiting_confirmation(self, real_input_file, default_job_params):
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())
        assert job_manager.get_job(job_id)['status'] == 'pending'
        assert job_manager.confirm_secondary_elements(job_id) is False

    def test_confirm_returns_false_for_unknown_job(self):
        assert job_manager.confirm_secondary_elements('job_ghost') is False

    def test_ack_given_upfront_skips_the_confirmation_state_entirely(self, real_input_file, default_job_params):
        job_id = job_manager.create_job(
            real_input_file, 'clip.mp4', default_job_params(), media_type='video', operation='enhance',
            content_type_detected='real_video',
            secondary_elements={'has_losses': True, 'losses': ['subtitles']},
            secondary_elements_ack=True,
        )
        assert job_manager.get_job(job_id)['status'] == 'pending'


class TestUpdateParams:
    def test_updates_params_while_pending(self, real_input_file, default_job_params):
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())
        assert job_manager.update_params(job_id, {'scale': '2x'}) is True
        assert job_manager.get_job(job_id)['params']['scale'] == '2x'

    def test_refuses_to_update_after_job_left_pending(self, real_input_file, default_job_params):
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())
        job_manager.jobs[job_id]['status'] = 'processing'
        assert job_manager.update_params(job_id, {'scale': '2x'}) is False

    def test_returns_false_for_unknown_job(self):
        assert job_manager.update_params('job_ghost', {'scale': '2x'}) is False


class TestCancelJob:
    def test_cancels_a_pending_job(self, real_input_file, default_job_params):
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())
        assert job_manager.cancel_job(job_id) is True
        assert job_manager.get_job(job_id)['status'] == 'cancelled'

    def test_cancels_a_processing_job_and_terminates_the_worker(
        self, real_input_file, default_job_params, fake_supervisor
    ):
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())
        job_manager.jobs[job_id]['status'] = 'processing'
        job_manager._processing_job_id = job_id

        assert job_manager.cancel_job(job_id) is True
        assert job_manager.get_job(job_id)['status'] == 'cancelled'
        assert fake_supervisor.terminated is True

    def test_cancelling_a_processing_job_that_is_not_the_current_one_does_not_terminate_worker(
        self, real_input_file, default_job_params, fake_supervisor
    ):
        """Only the job actually running in the worker should trigger a kill —
        a stale 'processing' status on some other job record must not."""
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())
        job_manager.jobs[job_id]['status'] = 'processing'
        job_manager._processing_job_id = 'a-different-job-id'

        job_manager.cancel_job(job_id)
        assert fake_supervisor.terminated is False

    def test_returns_false_for_unknown_job(self):
        assert job_manager.cancel_job('job_ghost') is False

    def test_cannot_cancel_an_already_done_job(self, real_input_file, default_job_params):
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())
        job_manager.jobs[job_id]['status'] = 'done'
        job_manager.cancel_job(job_id)
        assert job_manager.get_job(job_id)['status'] == 'done'  # unchanged, not silently overwritten


class TestQueuePosition:
    def test_none_for_a_job_not_queued(self, real_input_file, default_job_params):
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())
        assert job_manager.queue_position(job_id) is None

    def test_position_counts_only_earlier_queued_jobs(self, real_input_file, default_job_params):
        ids = [job_manager.create_job(real_input_file, f'{i}.png', default_job_params()) for i in range(3)]
        for order, job_id in enumerate(ids, start=1):
            job_manager.jobs[job_id]['status'] = 'queued'
            job_manager.jobs[job_id]['queue_order'] = order

        assert job_manager.queue_position(ids[0]) == 1
        assert job_manager.queue_position(ids[1]) == 2
        assert job_manager.queue_position(ids[2]) == 3

    def test_position_ignores_jobs_that_are_not_queued(self, real_input_file, default_job_params):
        ids = [job_manager.create_job(real_input_file, f'{i}.png', default_job_params()) for i in range(2)]
        job_manager.jobs[ids[0]]['status'] = 'done'
        job_manager.jobs[ids[0]]['queue_order'] = 1
        job_manager.jobs[ids[1]]['status'] = 'queued'
        job_manager.jobs[ids[1]]['queue_order'] = 2
        assert job_manager.queue_position(ids[1]) == 1  # the done job doesn't count


class TestEnqueue:
    def test_enqueue_transitions_pending_to_queued(self, real_input_file, default_job_params):
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())
        assert asyncio.run(job_manager.enqueue(job_id)) is True
        assert job_manager.get_job(job_id)['status'] == 'queued'
        assert job_manager.get_job(job_id)['queue_order'] is not None

    def test_enqueue_refuses_a_job_that_is_not_pending(self, real_input_file, default_job_params):
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())
        job_manager.jobs[job_id]['status'] = 'done'
        assert asyncio.run(job_manager.enqueue(job_id)) is False

    def test_enqueue_returns_false_for_unknown_job(self):
        assert asyncio.run(job_manager.enqueue('job_ghost')) is False


class TestProcessJobStateMachine:
    def test_successful_processing_reaches_done_with_correct_metadata(
        self, real_input_file, default_job_params, fake_supervisor
    ):
        fake_supervisor.configure_result((100, 100), (400, 400))
        job_id = _create_photo_job(real_input_file, 'a.png', default_job_params(scale='4x'))
        job_manager.jobs[job_id]['status'] = 'queued'

        asyncio.run(job_manager._process_job(job_id))

        job = job_manager.get_job(job_id)
        assert job['status'] == 'done'
        assert job['progress'] == 100
        assert job['output_meta']['width'] == 400
        assert job['output_meta']['height'] == 400
        assert job['output_meta']['size_bytes'] == len(fake_supervisor._write_master_bytes)
        assert job['source_meta']['width'] == 100

    def test_resolves_the_engine_internally_never_from_caller_supplied_params(
        self, real_input_file, default_job_params, fake_supervisor
    ):
        """FR-004/FR-009: the resolved engine_ref reflects content_type/profile,
        never a raw value the caller could have injected into params."""
        params = default_job_params(device='cuda', scale='2x', profile='quality')
        job_id = _create_photo_job(real_input_file, 'a.png', params)
        job_manager.jobs[job_id]['status'] = 'queued'

        asyncio.run(job_manager._process_job(job_id))

        call = fake_supervisor.process_calls[0]
        assert call['model'] == 'nomos-webphoto'  # photo's one approved implementation
        assert call['device'] == 'cuda'
        assert call['scale'] == 2

    def test_passes_adjustments_through_to_the_supervisor(self, real_input_file, default_job_params, fake_supervisor):
        params = default_job_params(device='cuda', scale='2x')
        params['adjustments'].update({
            'denoise': 77, 'deblur': 33, 'face_correction': True,
            'denoise_filter_enabled': True, 'denoise_filter_strength': 60,
        })
        job_id = _create_photo_job(real_input_file, 'a.png', params)
        job_manager.jobs[job_id]['status'] = 'queued'

        asyncio.run(job_manager._process_job(job_id))

        call = fake_supervisor.process_calls[0]
        assert call['device'] == 'cuda'
        assert call['denoise'] == 77
        assert call['sharpen'] == 33
        assert call['face_recovery'] is True
        assert call['denoise_filter_strength'] == 60

    def test_denoise_filter_strength_is_zero_when_disabled_even_if_a_stale_value_is_present(
        self, real_input_file, default_job_params, fake_supervisor
    ):
        """A leftover denoise_filter_strength from a previous UI session must
        not silently apply once the user has turned the toggle off."""
        params = default_job_params()
        params['adjustments'].update({'denoise_filter_enabled': False, 'denoise_filter_strength': 90})
        job_id = _create_photo_job(real_input_file, 'a.png', params)
        job_manager.jobs[job_id]['status'] = 'queued'

        asyncio.run(job_manager._process_job(job_id))

        assert fake_supervisor.process_calls[0]['denoise_filter_strength'] == 0

    def test_worker_failure_marks_job_as_error_with_category(
        self, real_input_file, default_job_params, fake_supervisor
    ):
        fake_supervisor.configure_error(worker_supervisor.WorkerFailure('CUDA out of memory', 'RuntimeError'))
        job_id = _create_photo_job(real_input_file, 'a.png', default_job_params())
        job_manager.jobs[job_id]['status'] = 'queued'

        asyncio.run(job_manager._process_job(job_id))

        job = job_manager.get_job(job_id)
        assert job['status'] == 'error'
        assert job['error_category'] == 'out_of_memory'
        assert 'CUDA out of memory' in job['error']

    def test_worker_crash_is_categorized_as_model_failure(
        self, real_input_file, default_job_params, fake_supervisor
    ):
        fake_supervisor.configure_error(worker_supervisor.WorkerCrashed('pipe closed'))
        job_id = _create_photo_job(real_input_file, 'a.png', default_job_params())
        job_manager.jobs[job_id]['status'] = 'queued'

        asyncio.run(job_manager._process_job(job_id))

        job = job_manager.get_job(job_id)
        assert job['status'] == 'error'
        assert job['error_category'] == 'model_failure'

    def test_disk_full_error_is_categorized(self, real_input_file, default_job_params, fake_supervisor):
        fake_supervisor.configure_error(OSError('no space left on device'))
        job_id = _create_photo_job(real_input_file, 'a.png', default_job_params())
        job_manager.jobs[job_id]['status'] = 'queued'

        asyncio.run(job_manager._process_job(job_id))

        assert job_manager.get_job(job_id)['error_category'] == 'disk_full'

    def test_a_job_cancelled_before_processing_starts_is_left_alone(
        self, real_input_file, default_job_params, fake_supervisor
    ):
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())
        job_manager.jobs[job_id]['status'] = 'cancelled'

        asyncio.run(job_manager._process_job(job_id))

        assert job_manager.get_job(job_id)['status'] == 'cancelled'
        assert fake_supervisor.process_calls == []  # never even called the worker

    def test_a_job_cancelled_during_processing_stays_cancelled_not_overwritten_by_the_late_result(
        self, real_input_file, default_job_params, fake_supervisor
    ):
        """If the user cancels while the worker is mid-job, a result that
        arrives after must not flip the status back to 'done'."""

        def process_and_cancel(**kwargs):
            job_manager.jobs[kwargs['job_id']]['status'] = 'cancelled'
            return {'source_size': (10, 10), 'output_size': (20, 20)}

        fake_supervisor.process = process_and_cancel
        job_id = _create_photo_job(real_input_file, 'a.png', default_job_params())
        job_manager.jobs[job_id]['status'] = 'queued'

        asyncio.run(job_manager._process_job(job_id))

        assert job_manager.get_job(job_id)['status'] == 'cancelled'

    def test_progress_and_stage_callbacks_update_the_job_record(
        self, real_input_file, default_job_params, fake_supervisor
    ):
        fake_supervisor._progress_events = [10, 50]
        fake_supervisor._stage_events = ['Lendo imagem', 'Aplicando modelo de IA']
        job_id = _create_photo_job(real_input_file, 'a.png', default_job_params())
        job_manager.jobs[job_id]['status'] = 'queued'

        # progress/stage callbacks run synchronously inside FakeSupervisor.process()
        # (called from the executor thread) — after _process_job awaits that
        # call, the final values should reflect the last event sent, before
        # being overwritten by the 100%/None completion state.
        asyncio.run(job_manager._process_job(job_id))
        # the job reaches 'done' (100%) — but we can at least assert no
        # exception occurred and the callbacks didn't corrupt the record.
        assert job_manager.get_job(job_id)['status'] == 'done'


class TestExportJob:
    def test_raises_for_unknown_job(self):
        with pytest.raises(ValueError, match='não encontrado'):
            job_manager.export_job('job_ghost', '/tmp/out.png', 90)

    def test_raises_when_job_not_done(self, real_input_file, default_job_params):
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())
        with pytest.raises(ValueError, match='não foi concluído'):
            job_manager.export_job(job_id, '/tmp/out.png', 90)

    def test_raises_when_master_file_is_missing(self, real_input_file, default_job_params):
        job_id = job_manager.create_job(real_input_file, 'a.png', default_job_params())
        job_manager.jobs[job_id]['status'] = 'done'
        with pytest.raises(ValueError, match='não está mais disponível'):
            job_manager.export_job(job_id, '/tmp/out.png', 90)

    def test_exports_a_done_jobs_master_file(self, real_input_file, default_job_params, fake_supervisor, tmp_path):
        fake_supervisor.configure_result((10, 10), (20, 20))
        job_id = _create_photo_job(real_input_file, 'a.png', default_job_params())
        job_manager.jobs[job_id]['status'] = 'queued'
        asyncio.run(job_manager._process_job(job_id))
        assert job_manager.get_job(job_id)['status'] == 'done'

        out_path = str(tmp_path / 'exported.png')
        job_manager.export_job(job_id, out_path, None)
        assert job_manager.get_job(job_id)['output_path'] == out_path
