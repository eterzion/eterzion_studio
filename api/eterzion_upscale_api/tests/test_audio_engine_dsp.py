"""Real tests for app.audio_engine.dsp — actually runs ffmpeg (Constitution
Princípio VIII: no mocking of the DSP itself), measures loudness/clipping via
pyloudnorm/NumPy independently of ffmpeg's own reporting (research.md
Decisão 6 — the whole point of a separate measurement path)."""
from __future__ import annotations

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

from app.audio_engine import dsp
from app.audio_engine.analyzer import ProblemDetection

_RATE = 44100


def _write_wav(tmp_path, name, data, rate=_RATE):
    path = str(tmp_path / name)
    sf.write(path, data, rate)
    return path


def _measure_lufs(path):
    data, rate = sf.read(path)
    meter = pyln.Meter(rate)
    return meter.integrated_loudness(data)


def _clipped_tone(duration=2.0, freq=440.0, rate=_RATE):
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    mono = np.clip(3.0 * np.sin(2 * np.pi * freq * t), -1.0, 1.0)
    return np.column_stack([mono, mono])


def _quiet_tone(duration=2.0, freq=440.0, amplitude=0.05, rate=_RATE):
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    mono = amplitude * np.sin(2 * np.pi * freq * t)
    return np.column_stack([mono, mono])


_NO_PROBLEMS = ProblemDetection(
    reverb_severity=0.0, clipping_severity=0.0, distortion_severity=0.0,
    tonal_imbalance_severity=0.0, stereo_imbalance_severity=0.0, noise_severity=0.0,
    hum_60hz_detected=False, requires_ai_restoration=False,
)

_CLIPPING_PROBLEMS = ProblemDetection(
    reverb_severity=0.0, clipping_severity=0.9, distortion_severity=0.9,
    tonal_imbalance_severity=0.0, stereo_imbalance_severity=0.0, noise_severity=0.0,
    hum_60hz_detected=False, requires_ai_restoration=True, dominant_problems=['clipping_severity'],
)

_HUM_PROBLEMS = ProblemDetection(
    reverb_severity=0.0, clipping_severity=0.0, distortion_severity=0.0,
    tonal_imbalance_severity=0.0, stereo_imbalance_severity=0.0, noise_severity=0.0,
    hum_60hz_detected=True, requires_ai_restoration=False,
)


class TestRestore:
    def test_runs_baseline_chain_without_error(self, tmp_path):
        input_path = _write_wav(tmp_path, 'in.wav', _quiet_tone())
        output_path = str(tmp_path / 'out.wav')
        dsp.restore(input_path, output_path, _NO_PROBLEMS)
        assert sf.info(output_path).frames > 0

    def test_does_not_change_loudness_target(self, tmp_path):
        """restore() must not push audio toward a mastering loudness target —
        FR-011 (restore mode never masters)."""
        input_path = _write_wav(tmp_path, 'in.wav', _quiet_tone(amplitude=0.05))
        output_path = str(tmp_path / 'out.wav')
        dsp.restore(input_path, output_path, _NO_PROBLEMS)
        before = _measure_lufs(input_path)
        after = _measure_lufs(output_path)
        assert abs(after - before) < 3.0  # noise reduction/filtering only, not normalization

    def test_reduces_clipping_when_detected(self, tmp_path):
        input_path = _write_wav(tmp_path, 'clipped.wav', _clipped_tone())
        output_path = str(tmp_path / 'out.wav')
        dsp.restore(input_path, output_path, _CLIPPING_PROBLEMS)
        out_data, _ = sf.read(output_path)
        clip_ratio_after = float(np.mean(np.abs(out_data) >= 0.999))
        in_data, _ = sf.read(input_path)
        clip_ratio_before = float(np.mean(np.abs(in_data) >= 0.999))
        assert clip_ratio_after <= clip_ratio_before

    def test_applies_hum_notch_when_detected(self, tmp_path):
        # 60Hz hum tone — the notch chain must not error and must reduce its energy.
        t = np.linspace(0, 2.0, int(_RATE * 2.0), endpoint=False)
        hum = 0.3 * np.sin(2 * np.pi * 60 * t)
        input_path = _write_wav(tmp_path, 'hum.wav', np.column_stack([hum, hum]))
        output_path = str(tmp_path / 'out.wav')
        dsp.restore(input_path, output_path, _HUM_PROBLEMS)
        in_data, _ = sf.read(input_path)
        out_data, _ = sf.read(output_path)
        assert np.sqrt(np.mean(out_data ** 2)) < np.sqrt(np.mean(in_data ** 2))


class TestMaster:
    def test_normalizes_to_the_target_lufs(self, tmp_path):
        input_path = _write_wav(tmp_path, 'in.wav', _quiet_tone(amplitude=0.02))
        output_path = str(tmp_path / 'out.wav')
        dsp.master(input_path, output_path, target_lufs=-14.0)
        measured = _measure_lufs(output_path)
        assert -16.0 <= measured <= -12.0  # within a reasonable tolerance of the target

    def test_output_never_clips(self, tmp_path):
        input_path = _write_wav(tmp_path, 'loud.wav', _clipped_tone())
        output_path = str(tmp_path / 'out.wav')
        dsp.master(input_path, output_path)
        out_data, _ = sf.read(output_path)
        assert float(np.max(np.abs(out_data))) <= 1.0

    def test_phase_correction_runs_without_error_on_perfectly_out_of_phase_content(self, tmp_path):
        # Perfectly out-of-phase (left = -right) downmixes toward near-silence
        # before loudnorm — an extreme, synthetic edge case not representative
        # of real content (loudnorm's own gain-to-target behavior on a
        # near-zero signal is upstream ffmpeg behavior, not this module's
        # correctness question); this only asserts the chain runs and
        # produces valid, finite output, matching what Quality Guard
        # (quality.py, not this module) is responsible for catching.
        t = np.linspace(0, 1.0, _RATE, endpoint=False)
        left = 0.4 * np.sin(2 * np.pi * 440 * t)
        right = -left
        input_path = _write_wav(tmp_path, 'outofphase.wav', np.column_stack([left, right]))
        output_path = str(tmp_path / 'out.wav')
        dsp.master(input_path, output_path, correct_phase=True)
        out_data, _ = sf.read(output_path)
        assert np.all(np.isfinite(out_data))

    def test_phase_correction_improves_stereo_correlation_for_partially_out_of_phase_content(self, tmp_path):
        rng = np.random.default_rng(7)
        t = np.linspace(0, 1.0, _RATE, endpoint=False)
        left = 0.4 * np.sin(2 * np.pi * 440 * t)
        independent = 0.1 * rng.standard_normal(_RATE)
        right = -0.8 * left + independent  # strongly anti-correlated, not a perfect cancellation
        input_path = _write_wav(tmp_path, 'partial_outofphase.wav', np.column_stack([left, right]))
        output_path = str(tmp_path / 'out.wav')
        dsp.master(input_path, output_path, correct_phase=True)
        out_data, _ = sf.read(output_path)
        correlation_after = float(np.corrcoef(out_data[:, 0], out_data[:, 1])[0, 1])
        assert correlation_after > -0.4  # measurably improved vs. the strongly anti-correlated input


def test_exciter_only_for_files_that_lost_their_highs():
    """Excitador so' onde a compressao cortou os agudos: sintetizar harmonicos
    num arquivo com banda cheia so' deixaria o som aspero."""
    assert dsp._exciter_for(None) is None
    assert dsp._exciter_for(20000) is None
    assert dsp._exciter_for(16500) is None  # MP3 128 kbps
    filtro = dsp._exciter_for(11000)  # MP3 64 kbps
    assert filtro is not None and filtro.startswith('aexciter=')
    assert 'freq=5500' in filtro and 'ceil=16500' in filtro


def test_master_with_the_exciter_adds_energy_above_the_cutoff(tmp_path):
    rng = np.random.default_rng(2)
    n = _RATE * 3
    mono = rng.standard_normal(n)
    spec = np.fft.rfft(mono)
    freqs = np.fft.rfftfreq(n, 1 / _RATE)
    spec[freqs > 11000] = 0
    mono = 0.2 * np.fft.irfft(spec, n) / np.max(np.abs(np.fft.irfft(spec, n)))
    src = _write_wav(tmp_path, 'lossy.wav', np.column_stack([mono, mono]))

    def energia_acima(path, lo=12000):
        data, rate = sf.read(path)
        m = data.mean(axis=1)
        s = np.abs(np.fft.rfft(m)) ** 2
        return s[np.fft.rfftfreq(m.size, 1 / rate) >= lo].sum() / s.sum()

    sem = str(tmp_path / 'sem.wav')
    com = str(tmp_path / 'com.wav')
    dsp.master(src, sem)
    dsp.master(src, com, bandwidth_hz=11000)
    assert energia_acima(com) > 10 * energia_acima(sem)


def test_master_keeps_the_input_sample_rate(tmp_path):
    """loudnorm sai a 192 kHz por dentro; a masterizacao devolvia um WAV 4x
    maior que o original. A saida tem a taxa da entrada."""
    src = _write_wav(tmp_path, 'in.wav', _quiet_tone())
    out = str(tmp_path / 'out.wav')
    dsp.master(src, out)
    assert sf.info(out).samplerate == _RATE
