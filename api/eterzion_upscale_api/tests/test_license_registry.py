"""Real integrity tests for the backend model-license authority (T017)."""
from app.licensing import get_model_license, verify_registry_completeness
from eterzion_upscale.processing import MODELS


def test_registry_has_no_gaps_against_the_live_model_registry():
    problems = verify_registry_completeness()
    assert problems == []


def test_every_live_model_resolves_to_a_license():
    for name in MODELS:
        license_ = get_model_license(name)
        assert license_ is not None, f'{name} has no license entry'
        assert license_.commercial_use == 'allowed'


def test_unknown_model_returns_none():
    assert get_model_license('this-model-does-not-exist') is None


def test_nomos_webphoto_matches_the_known_verified_license():
    license_ = get_model_license('nomos-webphoto')
    assert license_.license == 'CC-BY-4.0'
    assert license_.commercial_use == 'allowed'
    assert license_.attribution_required is True
