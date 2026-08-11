"""Real validation tests for the Unified Media Processing schemas (T015)."""
import pytest
from pydantic import ValidationError

from app.models.schemas import Component, JobStatus, MediaRequest


def test_media_request_accepts_a_well_formed_intent():
    request = MediaRequest(
        media_type='video', operation='enhance', scale='2x', profile='balanced',
        input_path='C:\\clipe.mp4',
    )
    assert request.media_type == 'video'
    assert request.profile == 'balanced'


def test_media_request_rejects_a_model_field_with_a_validation_error():
    with pytest.raises(ValidationError, match='model'):
        MediaRequest(media_type='image', operation='enhance', input_path='foo.png', model='realesrgan-x4')


def test_media_request_rejects_any_other_unknown_field():
    with pytest.raises(ValidationError):
        MediaRequest(media_type='image', operation='enhance', input_path='foo.png', engine='whatever')


def test_media_request_rejects_invalid_media_type():
    with pytest.raises(ValidationError):
        MediaRequest(media_type='pdf', operation='enhance', input_path='foo.pdf')


def test_job_status_defaults_to_image_enhance_for_backward_compatibility():
    job = JobStatus(id='job_1', status='pending', input_file='a.png', created_at='2026-01-01T00:00:00Z')
    assert job.media_type == 'image'
    assert job.operation == 'enhance'
    assert job.capacity_check is None


def test_job_status_accepts_extended_error_categories():
    job = JobStatus(
        id='job_2', status='error', input_file='a.mp4', created_at='2026-01-01T00:00:00Z',
        error_category='hardware_insufficient',
    )
    assert job.error_category == 'hardware_insufficient'


def test_component_never_carries_technical_fields():
    component = Component(id='img-enhance-photo', capability_label='Melhoria de imagem — Fotos',
                           size_mb=64, install_state='installed')
    assert not hasattr(component, 'technical_name')
