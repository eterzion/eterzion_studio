"""Real validation tests for the Unified Media Processing schemas (T015)."""
import pytest
from pydantic import ValidationError

from app.schemas import Component, JobStatus, MediaRequest


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


def test_media_request_without_audio_mode_is_unaffected():
    """specs/006-audio-engine-masterizacao contracts/README.md — the whole
    point of making audio_mode/ai_strength optional additive fields."""
    request = MediaRequest(media_type='audio', operation='enhance', input_path='faixa.wav')
    assert request.audio_mode is None
    assert request.ai_strength is None
    dumped = request.model_dump(exclude_none=True)
    assert 'audio_mode' not in dumped
    assert 'ai_strength' not in dumped


def test_media_request_accepts_a_valid_audio_mode_and_strength():
    request = MediaRequest(
        media_type='audio', operation='enhance', content_type_override='music',
        input_path='faixa.wav', audio_mode='auto_master', ai_strength=75,
    )
    assert request.audio_mode == 'auto_master'
    assert request.ai_strength == 75


def test_media_request_rejects_an_invalid_audio_mode():
    with pytest.raises(ValidationError):
        MediaRequest(media_type='audio', operation='enhance', input_path='faixa.wav', audio_mode='not-a-real-mode')


def test_media_request_rejects_ai_strength_out_of_range():
    with pytest.raises(ValidationError):
        MediaRequest(media_type='audio', operation='enhance', input_path='faixa.wav', ai_strength=150)


def test_job_status_without_audio_fields_is_unaffected():
    job = JobStatus(id='job_1', status='pending', input_file='faixa.wav', created_at='2026-01-01T00:00:00Z')
    assert job.audio_analysis is None
    assert job.quality_verdict is None
    dumped = job.model_dump(exclude_none=True)
    assert 'audio_analysis' not in dumped
    assert 'quality_verdict' not in dumped


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


def test_component_is_available_unless_told_otherwise():
    component = Component(id='photo', capability_label='Melhoria de imagem — Foto',
                           size_mb=0, install_state='not_installed')
    assert component.available is True
