"""Real tests for the profile_resolver chokepoint (T012) — no mocking of
detect_hardware(): every resolve() call here measures this machine for real."""
import pytest

from app.licensing import (
    MediaRequest,
    ResolvedPipeline,
    UnresolvableRequestError,
    resolve,
)
from astros_upscale.processing import HardwareCapability

pytestmark = pytest.mark.hardware


def test_resolve_photo_enhance_default_profile():
    request = MediaRequest(media_type='image', operation='enhance', content_type='photo', scale='4x')
    pipeline = resolve(request)
    assert isinstance(pipeline, ResolvedPipeline)
    assert pipeline.engine_ref == 'nomos-webphoto'
    assert pipeline.profile == 'fast'
    # T061 — tile_threshold/tile_size are real, hardware-derived values (see
    # test_hardware.py), not fixed — only the profile-driven keys are asserted
    # exactly here.
    assert pipeline.execution_params['denoise_strength'] == 1.0
    assert pipeline.execution_params['half'] is True
    assert pipeline.execution_params['tile_threshold'] > 0
    assert pipeline.execution_params['tile_size'] > 0
    assert isinstance(pipeline.hardware, HardwareCapability)
    assert pipeline.hardware.cpu_cores >= 1


def test_resolve_anime_image_quality_profile():
    request = MediaRequest(
        media_type='image', operation='enhance', content_type='anime_image', scale='2x', profile='quality')
    pipeline = resolve(request)
    assert pipeline.engine_ref == 'hfa2k-span'
    assert pipeline.execution_params['denoise_strength'] == 0.0
    assert pipeline.execution_params['half'] is False


def test_resolve_speech_enhance_has_no_scale_requirement():
    request = MediaRequest(media_type='audio', operation='enhance', content_type='speech', profile='balanced')
    pipeline = resolve(request)
    assert pipeline.engine_ref == 'super-voz'
    assert pipeline.execution_params == {'ddim_steps': 50}


def test_resolve_real_video_has_an_approved_implementation():
    """T045: real_video was a known gap (LC per spec.md) until this benchmark-
    free but license-clean model landed."""
    request = MediaRequest(media_type='video', operation='enhance', content_type='real_video', scale='2x')
    pipeline = resolve(request)
    assert pipeline.engine_ref == 'realplksr-video-real'


def test_resolve_music_has_an_approved_conditional_implementation():
    """T055 — SonicMaster is approved, but conditionally (Stable Audio Open's
    VAE licence caps commercial use, docs/models/MODEL_LICENSES.md §3-bis)."""
    request = MediaRequest(media_type='audio', operation='enhance', content_type='music')
    pipeline = resolve(request)
    assert pipeline.engine_ref == 'sonicmaster'
    assert pipeline.license_status == 'approved_conditional'
    assert pipeline.license_condition is not None


def test_resolve_speech_is_approved_unconditionally():
    request = MediaRequest(media_type='audio', operation='enhance', content_type='speech')
    pipeline = resolve(request)
    assert pipeline.engine_ref == 'super-voz'
    assert pipeline.license_status == 'approved'
    assert pipeline.license_condition is None


def test_resolve_rejects_a_content_type_with_no_approved_implementation(monkeypatch):
    """FR-098 — every one of today's 6 content types now has an approved
    implementation (T024/T045/T046/T055), so this exercises the rejection
    path directly against a real (temporarily unapproved) registry entry
    instead of relying on a content type that no longer stays unapproved."""
    from app import licensing as profile_resolver

    monkeypatch.setitem(
        profile_resolver._CONTENT_TYPE_IMPLEMENTATIONS, 'music',
        profile_resolver._ContentTypeImplementation(engine_ref=None))
    request = MediaRequest(media_type='audio', operation='enhance', content_type='music')
    with pytest.raises(UnresolvableRequestError, match='music'):
        resolve(request)


def test_resolve_enhance_image_without_scale_rejected():
    request = MediaRequest(media_type='image', operation='enhance', content_type='photo')
    with pytest.raises(UnresolvableRequestError, match='scale'):
        resolve(request)


def test_resolve_enhance_without_content_type_rejected():
    request = MediaRequest(media_type='image', operation='enhance', scale='4x')
    with pytest.raises(UnresolvableRequestError, match='content_type'):
        resolve(request)


def test_resolve_mismatched_content_type_for_media_type_rejected():
    request = MediaRequest(media_type='image', operation='enhance', content_type='speech', scale='4x')
    with pytest.raises(UnresolvableRequestError, match='não é válido'):
        resolve(request)


def test_resolve_compress_has_no_profile():
    request = MediaRequest(media_type='video', operation='compress', quality=60)
    pipeline = resolve(request)
    assert pipeline.profile is None
    assert pipeline.engine_ref == 'ffmpeg-compress-video'
    assert pipeline.execution_params == {'quality': 60}


def test_resolve_compress_image_with_scale_rejected():
    request = MediaRequest(media_type='image', operation='compress', scale='2x')
    with pytest.raises(UnresolvableRequestError, match='scale'):
        resolve(request)


def test_resolve_convert_has_no_profile_and_no_scale():
    request = MediaRequest(media_type='audio', operation='convert')
    pipeline = resolve(request)
    assert pipeline.profile is None
    assert pipeline.engine_ref == 'ffmpeg-convert-audio'


def test_resolve_convert_with_scale_rejected():
    request = MediaRequest(media_type='image', operation='convert', scale='4x')
    with pytest.raises(UnresolvableRequestError, match='scale'):
        resolve(request)


class TestProfileNeverChangesTheImplementation:
    """FR-004: the three profiles MUST resolve to execution parameters over the
    SAME implementation — never a different model. T018."""

    @pytest.mark.parametrize('profile', ['fast', 'balanced', 'quality'])
    def test_same_engine_ref_across_all_profiles_for_photo(self, profile):
        request = MediaRequest(media_type='image', operation='enhance', content_type='photo',
                                scale='2x', profile=profile)
        pipeline = resolve(request)
        assert pipeline.engine_ref == 'nomos-webphoto'

    def test_unspecified_profile_resolves_to_fast(self):
        """FR-008."""
        request = MediaRequest(media_type='image', operation='enhance', content_type='photo', scale='2x')
        assert resolve(request).profile == 'fast'

    def test_the_three_profiles_produce_distinct_execution_parameters(self):
        results = {
            profile: resolve(MediaRequest(
                media_type='image', operation='enhance', content_type='photo', scale='2x', profile=profile,
            )).execution_params
            for profile in ('fast', 'balanced', 'quality')
        }
        assert results['fast'] != results['balanced'] != results['quality']
        assert results['fast'] != results['quality']


@pytest.mark.slow
def test_profile_half_precision_flag_never_gets_more_aggressive_from_fast_to_quality():
    """FR-006: Rápido MUST priorizar velocidade; Qualidade MUST NEVER be cheaper
    than Equilibrado, which MUST NEVER be cheaper than Rápido.

    This was originally a real wall-clock timing test (build the three profiles'
    AstrosUpscaler and measure real astros_upscale.processing inference on a tiny
    image). Run for real against this machine, it was flaky: `half=True` (used
    by fast/balanced) only affects CUDA/MPS devices — on this CPU-only dev
    machine it's a documented no-op (see AstrosUpscaler.__init__), so the
    measured costs were dominated by first-call warm-up/cache noise, not any
    real profile-driven difference, and the ordering assertion failed on a
    completely valid run (balanced measured slower than quality by chance).
    A test that only passes by luck on some runs is worse than no test.

    What IS real and deterministic today: the `half` flag itself is configured
    to never get MORE aggressive (i.e. never cheaper) going from fast to
    quality. True wall-clock validation needs a cost lever that's real on any
    hardware (e.g. self-ensemble passes for `quality`) — that's what T023's
    benchmark is expected to establish before T024 finalizes the registry.
    """
    costs_by_half = {True: 0, False: 1}  # half=True is presumed cheaper-or-equal
    values = []
    for profile in ('fast', 'balanced', 'quality'):
        pipeline = resolve(MediaRequest(
            media_type='image', operation='enhance', content_type='photo', scale='2x', profile=profile,
        ))
        values.append(costs_by_half[pipeline.execution_params['half']])
    assert values == sorted(values), f'half-precision aggressiveness must be non-decreasing fast->quality: {values}'
