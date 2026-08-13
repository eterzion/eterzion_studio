"""Real tests for app.audio_engine.analyzer — synthetic audio, real
measurement (pyloudnorm/NumPy), no mocking of the analysis itself
(Constitution Princípio VIII)."""
from __future__ import annotations

import numpy as np
import soundfile as sf

from app.audio_engine.analyzer import analyze, detect_problems

_RATE = 44100


def _write_wav(tmp_path, name: str, data: np.ndarray, rate: int = _RATE) -> str:
    path = str(tmp_path / name)
    sf.write(path, data, rate)
    return path


def _clean_tone(duration=2.0, freq=440.0, amplitude=0.3, rate=_RATE) -> np.ndarray:
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    mono = amplitude * np.sin(2 * np.pi * freq * t)
    return np.column_stack([mono, mono * 0.98])  # near-identical channels, not perfectly correlated


def _clipped_tone(duration=2.0, freq=440.0, rate=_RATE) -> np.ndarray:
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    mono = 3.0 * np.sin(2 * np.pi * freq * t)  # deliberately over-driven before clamp
    mono = np.clip(mono, -1.0, 1.0)
    return np.column_stack([mono, mono])


class TestAnalyze:
    def test_measures_real_loudness_and_peak_for_a_clean_tone(self, tmp_path):
        path = _write_wav(tmp_path, 'clean.wav', _clean_tone())
        report = analyze(path)
        assert -60 < report.integrated_lufs < 0
        assert report.true_peak_db < 0  # amplitude 0.3, well under full scale
        assert report.clipping_ratio == 0.0
        assert report.measured_at == 'input'

    def test_detects_clipping_in_a_hard_clipped_signal(self, tmp_path):
        path = _write_wav(tmp_path, 'clipped.wav', _clipped_tone())
        report = analyze(path)
        assert report.clipping_ratio > 0.1  # a large fraction of samples pinned at full scale

    def test_out_of_phase_stereo_is_detected(self, tmp_path):
        t = np.linspace(0, 1.0, _RATE, endpoint=False)
        left = 0.5 * np.sin(2 * np.pi * 440 * t)
        right = -left  # perfectly out of phase
        path = _write_wav(tmp_path, 'outofphase.wav', np.column_stack([left, right]))
        report = analyze(path)
        assert report.stereo_correlation < -0.9
        assert report.phase_issues_detected is True

    def test_mono_file_does_not_crash_and_reports_no_phase_issue(self, tmp_path):
        t = np.linspace(0, 1.0, _RATE, endpoint=False)
        mono = 0.4 * np.sin(2 * np.pi * 440 * t)
        path = _write_wav(tmp_path, 'mono.wav', mono)
        report = analyze(path)
        assert report.phase_issues_detected is False


class TestDetectProblems:
    def test_clean_audio_does_not_require_ai_restoration(self, tmp_path):
        path = _write_wav(tmp_path, 'clean.wav', _clean_tone())
        report = analyze(path)
        problems = detect_problems(report)
        assert problems.requires_ai_restoration is False
        assert problems.dominant_problems == []

    def test_severely_clipped_audio_requires_ai_restoration(self, tmp_path):
        path = _write_wav(tmp_path, 'clipped.wav', _clipped_tone())
        report = analyze(path)
        problems = detect_problems(report)
        assert problems.clipping_severity > 0.5
        assert problems.requires_ai_restoration is True
        assert 'clipping_severity' in problems.dominant_problems

    def test_noise_alone_never_triggers_ai_restoration(self, tmp_path):
        """FR-003 — noise/hum are DSP-only, must never drive requires_ai_restoration
        even conceptually (this analyzer never scores noise_severity above 0)."""
        rng = np.random.default_rng(42)
        noise = 0.05 * rng.standard_normal(_RATE)
        path = _write_wav(tmp_path, 'noisy.wav', np.column_stack([noise, noise]))
        report = analyze(path)
        problems = detect_problems(report)
        assert problems.noise_severity == 0.0
        assert problems.requires_ai_restoration is False
