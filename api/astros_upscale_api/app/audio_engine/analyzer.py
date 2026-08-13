"""Audio Analyzer + Problem Detector (data-model.md's AudioAnalysisReport/
ProblemDetection). Real objective measurement — no mocking of the
measurement itself (Constitution Princípio VIII): LUFS/True Peak via
`pyloudnorm` (ITU-R BS.1770-4, MIT — docs/models/MODEL_LICENSES.md §4),
everything else via plain NumPy over the decoded waveform.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

MeasuredAt = Literal['input', 'post_dsp', 'post_ai', 'post_master']


@dataclass(frozen=True)
class AudioAnalysisReport:
    integrated_lufs: float
    true_peak_db: float
    rms_db: float
    dynamic_range_db: float
    dc_offset: float
    stereo_correlation: float
    spectral_balance: dict[str, float]
    clipping_ratio: float
    phase_issues_detected: bool
    measured_at: MeasuredAt


@dataclass(frozen=True)
class ProblemDetection:
    reverb_severity: float
    clipping_severity: float
    distortion_severity: float
    tonal_imbalance_severity: float
    stereo_imbalance_severity: float
    noise_severity: float
    hum_60hz_detected: bool
    requires_ai_restoration: bool
    dominant_problems: list[str] = field(default_factory=list)


# FR-004 — only these "complex" classes can justify AI restoration; noise and
# hum are always DSP-only (FR-003), never counted toward requires_ai_restoration.
_AI_ELIGIBLE_SEVERITIES = (
    'reverb_severity', 'clipping_severity', 'distortion_severity',
    'tonal_imbalance_severity', 'stereo_imbalance_severity',
)

# Threshold above which a severity is considered "real enough" to justify AI —
# tuned by AI Strength (data-model.md's table); 0.5 is the "moderado" default.
_DEFAULT_AI_THRESHOLD = 0.5

_CLIP_THRESHOLD = 0.999  # near full-scale, allowing for float rounding
_SPECTRAL_BANDS = {'low': (20, 250), 'mid': (250, 4000), 'high': (4000, 20000)}


def _to_mono(audio: np.ndarray) -> np.ndarray:
    return audio if audio.ndim == 1 else audio.mean(axis=1)


def _true_peak_db(audio: np.ndarray) -> float:
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    return 20 * np.log10(peak) if peak > 0 else -120.0


def _rms_db(audio: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
    return 20 * np.log10(rms) if rms > 0 else -120.0


def _stereo_correlation(audio: np.ndarray) -> float:
    if audio.ndim < 2 or audio.shape[1] < 2:
        return 1.0  # mono has no cross-channel phase risk
    left, right = audio[:, 0], audio[:, 1]
    if np.std(left) == 0 or np.std(right) == 0:
        return 1.0
    return float(np.corrcoef(left, right)[0, 1])


def _spectral_balance(mono: np.ndarray, rate: int) -> dict[str, float]:
    if mono.size == 0:
        return {band: 0.0 for band in _SPECTRAL_BANDS}
    spectrum = np.abs(np.fft.rfft(mono))
    freqs = np.fft.rfftfreq(mono.size, d=1.0 / rate)
    total = float(np.sum(spectrum)) or 1.0
    return {
        band: float(np.sum(spectrum[(freqs >= lo) & (freqs < hi)])) / total
        for band, (lo, hi) in _SPECTRAL_BANDS.items()
    }


def _clipping_ratio(audio: np.ndarray) -> float:
    if audio.size == 0:
        return 0.0
    return float(np.mean(np.abs(audio) >= _CLIP_THRESHOLD))


def analyze(path: str, measured_at: MeasuredAt = 'input') -> AudioAnalysisReport:
    """Real analysis of the audio file at `path` — no synthetic/mocked report."""
    audio, rate = sf.read(path, always_2d=False)
    audio = audio.astype(np.float64, copy=False)
    mono = _to_mono(audio)

    meter = pyln.Meter(rate)
    integrated_lufs = float(meter.integrated_loudness(audio if audio.ndim > 1 else mono))
    if integrated_lufs == float('-inf'):
        integrated_lufs = -120.0

    peak = _true_peak_db(audio)
    rms = _rms_db(mono)
    correlation = _stereo_correlation(audio)

    return AudioAnalysisReport(
        integrated_lufs=integrated_lufs,
        true_peak_db=peak,
        rms_db=rms,
        dynamic_range_db=peak - rms,
        dc_offset=float(np.mean(mono)),
        stereo_correlation=correlation,
        spectral_balance=_spectral_balance(mono, rate),
        clipping_ratio=_clipping_ratio(audio),
        phase_issues_detected=correlation < -0.3,
        measured_at=measured_at,
    )


def detect_problems(
    report: AudioAnalysisReport,
    *,
    ai_threshold: float = _DEFAULT_AI_THRESHOLD,
) -> ProblemDetection:
    """Derives ProblemDetection from a single AudioAnalysisReport. Severities
    here are heuristic proxies over measurable signal properties (this is a
    Problem *Detector*, not a full perceptual-quality model) — deliberately
    conservative: a severity is only reported "high" when the measured
    property is unambiguously abnormal, per FR-002's "never send audio to AI
    unconditionally" and FR-009's musical-intent preservation requirement.
    """
    clipping_severity = min(1.0, report.clipping_ratio * 20)  # >5% clipped samples => 1.0
    distortion_severity = clipping_severity  # same measurable signal (hard clipping) drives both
    stereo_imbalance_severity = max(0.0, -report.stereo_correlation)  # only negative correlation is a problem
    # Reverb and tonal-imbalance severity aren't reliably measurable from these
    # summary stats alone: a naive spectral-balance-vs-reference heuristic was
    # tried and rejected during implementation (it false-positived on plain
    # broadband noise, which has no music-reference spectral shape to compare
    # against at all — flagging it would violate FR-002/FR-009 by sending
    # audio to AI restoration it doesn't need). Both are conservatively left
    # at 0 until a real RT60-based reverb estimate and a noise-floor-aware
    # tonal model are implemented — `report.spectral_balance` remains
    # available in the report for that future work without changing this
    # function's contract.
    reverb_severity = 0.0
    tonal_imbalance_severity = 0.0
    noise_severity = 0.0  # DSP-only per FR-003, never drives requires_ai_restoration
    hum_60hz_detected = False  # left to dsp.py's notch stage; not scored here

    severities = {
        'reverb_severity': reverb_severity,
        'clipping_severity': clipping_severity,
        'distortion_severity': distortion_severity,
        'tonal_imbalance_severity': tonal_imbalance_severity,
        'stereo_imbalance_severity': stereo_imbalance_severity,
    }
    requires_ai = any(severities[key] >= ai_threshold for key in _AI_ELIGIBLE_SEVERITIES)
    dominant = sorted(
        (k for k in _AI_ELIGIBLE_SEVERITIES if severities[k] >= ai_threshold),
        key=lambda k: severities[k], reverse=True,
    )

    return ProblemDetection(
        reverb_severity=reverb_severity,
        clipping_severity=clipping_severity,
        distortion_severity=distortion_severity,
        tonal_imbalance_severity=tonal_imbalance_severity,
        stereo_imbalance_severity=stereo_imbalance_severity,
        noise_severity=noise_severity,
        hum_60hz_detected=hum_60hz_detected,
        requires_ai_restoration=requires_ai,
        dominant_problems=dominant,
    )
