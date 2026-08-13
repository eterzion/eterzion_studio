"""Tests for app.audio_engine.mastering.MasteringEngine — real DSP/analysis
(ffmpeg + pyloudnorm), fake AI provider (no GPU/checkpoint needed for these,
same rationale as test_audio_engine_ai_provider.py)."""
from __future__ import annotations

import shutil

import numpy as np
import soundfile as sf

from app.audio_engine.mastering import MasteringEngine

_RATE = 44100


def _write_wav(tmp_path, name, data, rate=_RATE):
    path = str(tmp_path / name)
    sf.write(path, data, rate)
    return path


def _clean_tone(tmp_path, name='clean.wav', duration=2.0, freq=440.0, amplitude=0.3):
    t = np.linspace(0, duration, int(_RATE * duration), endpoint=False)
    mono = amplitude * np.sin(2 * np.pi * freq * t)
    return _write_wav(tmp_path, name, np.column_stack([mono, mono * 0.98]))


def _clipped_tone(tmp_path, name='clipped.wav', duration=2.0, freq=440.0):
    t = np.linspace(0, duration, int(_RATE * duration), endpoint=False)
    mono = np.clip(3.0 * np.sin(2 * np.pi * freq * t), -1.0, 1.0)
    return _write_wav(tmp_path, name, np.column_stack([mono, mono]))


class _NeverCalledProvider:
    """Fails the test if the AI path is invoked at all — used to confirm
    FR-002 (never send audio to AI unconditionally)."""

    def is_available(self):
        return True

    def initialize(self):
        pass

    def restore(self, *a, **k):
        raise AssertionError('AI provider must not be called for clean audio')

    def restore_full_song(self, *a, **k):
        raise AssertionError('AI provider must not be called for clean audio')

    def shutdown(self):
        pass


class _FakeProvider:
    """A "working" fake: copies the input through, simulating an AI pass
    that doesn't introduce any regression (dsp.restore is still applied
    afterward by MasteringEngine, same as a real provider's output would be)."""

    def __init__(self):
        self.calls = []

    def is_available(self):
        return True

    def initialize(self):
        pass

    def restore(self, input_path, instruction, strength=50):
        self.calls.append((input_path, instruction, strength))
        out = input_path.replace('.wav', '_ai.wav')
        shutil.copyfile(input_path, out)
        return out

    def restore_full_song(self, input_path, instruction, strength=50):
        return self.restore(input_path, instruction, strength)

    def shutdown(self):
        pass


class TestAutoMaster:
    def test_clean_audio_never_calls_the_ai_provider(self, tmp_path):
        input_path = _clean_tone(tmp_path)
        engine = MasteringEngine(provider=_NeverCalledProvider())
        result = engine.auto_master(input_path, str(tmp_path / 'out.wav'))
        assert result.quality_verdict is None  # AI never ran
        assert -20 < result.audio_analysis.integrated_lufs < -8

    def test_problematic_audio_calls_the_ai_provider_and_passes_through_quality_guard(self, tmp_path):
        input_path = _clipped_tone(tmp_path)
        provider = _FakeProvider()
        engine = MasteringEngine(provider=provider)
        result = engine.auto_master(input_path, str(tmp_path / 'out.wav'), ai_strength=75)
        assert len(provider.calls) == 1
        assert result.quality_verdict is not None
        assert result.quality_verdict.outcome in ('accepted', 'reduced', 'rejected')

    def test_ai_strength_zero_never_calls_the_provider_even_with_problems(self, tmp_path):
        input_path = _clipped_tone(tmp_path)
        engine = MasteringEngine(provider=_NeverCalledProvider())
        result = engine.auto_master(input_path, str(tmp_path / 'out.wav'), ai_strength=0)
        assert result.quality_verdict is None

    def test_unavailable_provider_falls_back_to_dsp_only(self, tmp_path):
        class _UnavailableProvider(_NeverCalledProvider):
            def is_available(self):
                return False

        input_path = _clipped_tone(tmp_path)
        output_path = str(tmp_path / 'out.wav')
        engine = MasteringEngine(provider=_UnavailableProvider())
        result = engine.auto_master(input_path, output_path, ai_strength=75)
        assert result.quality_verdict is None
        assert sf.info(output_path).frames > 0  # a real result was still produced


class TestRestore:
    def test_does_not_apply_a_mastering_loudness_target(self, tmp_path):
        input_path = _clean_tone(tmp_path, amplitude=0.02)  # deliberately quiet
        engine = MasteringEngine(provider=_NeverCalledProvider())
        result = engine.restore(input_path, str(tmp_path / 'out.wav'))
        # restore() must not push a quiet source up toward the -14 LUFS master target
        assert result.audio_analysis.integrated_lufs < -20


class TestRestoreMaster:
    def test_restore_then_master_produces_a_mastered_result(self, tmp_path):
        input_path = _clean_tone(tmp_path, amplitude=0.02)
        engine = MasteringEngine(provider=_NeverCalledProvider())
        result = engine.restore_master(input_path, str(tmp_path / 'out.wav'))
        assert -16 <= result.audio_analysis.integrated_lufs <= -12
        assert 'restored' in result.stages_output_paths
        assert 'mastered' in result.stages_output_paths


class TestAiStrengthStrategy:
    """FR-013 — ai_strength changes the restoration strategy (via
    ai_provider._strength_profile, exercised end-to-end here), never a
    linear multiplier on the output."""

    def test_higher_strength_requests_more_inference_steps(self, tmp_path):
        input_path = _clipped_tone(tmp_path)
        provider = _FakeProvider()
        engine = MasteringEngine(provider=provider)
        engine.auto_master(input_path, str(tmp_path / 'low.wav'), ai_strength=10)
        _, _, strength_low = provider.calls[-1]
        engine.auto_master(_clipped_tone(tmp_path, name='clipped2.wav'), str(tmp_path / 'high.wav'), ai_strength=90)
        _, _, strength_high = provider.calls[-1]
        assert strength_low == 10 and strength_high == 90  # engine forwards the value, doesn't rescale it
        # the actual steps-per-strength mapping is asserted directly in
        # test_audio_engine_ai_provider.py::TestRestore — here we only
        # confirm the engine plumbs ai_strength through unchanged, not that
        # it invents its own multiplier.


class _RegressingProvider:
    """A fake provider whose "restoration" makes the audio measurably worse —
    used to confirm FR-008 (Quality Guard rejection) actually discards the
    AI output rather than letting it through."""

    def is_available(self):
        return True

    def initialize(self):
        pass

    def restore(self, input_path, instruction, strength=50):
        # dsp.restore()'s own corrective chain (afftdn/notch/limiter) only
        # touches noise/clipping, never stereo phase — so a stereo-correlation
        # regression is the one thing that reliably survives to reach
        # quality.evaluate() unmodified, making it the right choice for this
        # test (as opposed to clipping, which the corrective DSP step
        # legitimately fixes on its own, per FR-006 — that's a feature, not
        # a test bug).
        out = input_path.replace('.wav', '_regressed.wav')
        data, rate = sf.read(input_path)
        regressed = data.copy()
        if regressed.ndim == 2 and regressed.shape[1] == 2:
            regressed[:, 1] = -regressed[:, 0]  # force near-perfect phase inversion
        sf.write(out, regressed, rate)
        return out

    def restore_full_song(self, input_path, instruction, strength=50):
        return self.restore(input_path, instruction, strength)

    def shutdown(self):
        pass


class TestQualityGuardRejection:
    """FR-008/quickstart.md Cenário 3 — an AI result with a real technical
    regression must never reach the user as-is."""

    def test_regressed_ai_output_is_not_used_as_the_final_result(self, tmp_path):
        input_path = _clipped_tone(tmp_path)  # already has clipping -> AI gets invoked
        engine = MasteringEngine(provider=_RegressingProvider())
        result = engine.restore(input_path, str(tmp_path / 'out.wav'), ai_strength=75)

        assert result.quality_verdict is not None
        assert result.quality_verdict.outcome in ('reduced', 'rejected')
        assert result.quality_verdict.regression_flags['stereo_correlation'] is True
        if result.quality_verdict.outcome == 'rejected':
            # The DSP-only fallback path was used instead of the AI's phase-
            # inverted output — confirmed by the final result NOT being
            # phase-inverted (correlation stays positive, like the original).
            out_data, _ = sf.read(result.output_path)
            correlation = float(np.corrcoef(out_data[:, 0], out_data[:, 1])[0, 1])
            assert correlation > 0


class TestMusicalIntentPreservation:
    """FR-009/SC-006 — objective comparison, not subjective."""

    def test_clean_audio_with_no_problems_is_not_perceptibly_altered(self, tmp_path):
        input_path = _clean_tone(tmp_path)
        engine = MasteringEngine(provider=_NeverCalledProvider())
        result = engine.restore(input_path, str(tmp_path / 'out.wav'))  # restore(), not auto_master — isolates DSP-restore-only change
        in_data, _ = sf.read(input_path)
        out_data, _ = sf.read(result.output_path)
        n = min(len(in_data), len(out_data))
        # Correlation between input and output waveforms — restore() on
        # already-clean audio should barely touch it (only baseline
        # noise-floor filtering runs, no AI, no mastering EQ/compression).
        correlation = np.corrcoef(in_data[:n, 0], out_data[:n, 0])[0, 1]
        assert correlation > 0.9
