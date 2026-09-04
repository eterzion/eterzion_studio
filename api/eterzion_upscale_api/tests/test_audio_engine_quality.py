"""Tests for app.audio_engine.quality — the Quality Guard. Uses synthetic
AudioAnalysisReport pairs (real dataclass instances, not full audio
pipelines — this module's job is pure comparison logic, tested directly)."""
from __future__ import annotations

from app.audio_engine.analyzer import AudioAnalysisReport
from app.audio_engine.quality import evaluate

_BASELINE_KWARGS = dict(
    integrated_lufs=-14.0, dc_offset=0.0, spectral_balance={'low': 0.3, 'mid': 0.5, 'high': 0.2},
    phase_issues_detected=False, measured_at='input',
)


def _report(**overrides) -> AudioAnalysisReport:
    kwargs = dict(_BASELINE_KWARGS, true_peak_db=-1.0, rms_db=-16.0, dynamic_range_db=15.0,
                  stereo_correlation=0.8, clipping_ratio=0.0)
    kwargs.update(overrides)
    return AudioAnalysisReport(**kwargs)


class TestEvaluate:
    def test_no_regression_is_accepted(self):
        before = _report()
        after = _report(true_peak_db=-1.2, dynamic_range_db=15.5)  # slightly better, not worse
        verdict = evaluate(before, after)
        assert verdict.outcome == 'accepted'
        assert verdict.reasons == []

    def test_single_severe_regression_is_reduced(self):
        before = _report()
        after = _report(true_peak_db=0.5)  # clear true-peak regression, nothing else worse
        verdict = evaluate(before, after)
        assert verdict.outcome == 'reduced'
        assert any('true_peak_db' in r for r in verdict.reasons)
        assert verdict.regression_flags['true_peak_db'] is True

    def test_multiple_severe_regressions_are_rejected(self):
        before = _report()
        after = _report(true_peak_db=0.5, clipping_ratio=0.05, dynamic_range_db=5.0)
        verdict = evaluate(before, after)
        assert verdict.outcome == 'rejected'
        assert len(verdict.reasons) >= 2

    def test_minor_true_peak_change_within_tolerance_is_accepted(self):
        before = _report()
        after = _report(true_peak_db=-0.5)  # worse, but under the 1.0dB regression threshold
        verdict = evaluate(before, after)
        assert verdict.outcome == 'accepted'

    def test_stereo_correlation_collapse_is_flagged(self):
        before = _report(stereo_correlation=0.8)
        after = _report(stereo_correlation=-0.2)
        verdict = evaluate(before, after)
        assert verdict.regression_flags['stereo_correlation'] is True
        assert verdict.outcome in ('reduced', 'rejected')
