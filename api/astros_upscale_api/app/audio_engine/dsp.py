"""Deterministic DSP — Constitution Princípio XII's "DSP determinístico nunca
é substituído por IA": loudness, EQ, dynamics, stereo correction, limiting,
normalization all live here as real ffmpeg filter chains (LGPL-safe, same
approach `app.processing.apply_dsp_chain` already uses), never delegated to
`ai_provider.py`. Two entry points: `restore()` (corrective — reduces
clipping/noise/hum without touching loudness target) and `master()` (the
Auto Master chain — EQ, dynamics, stereo, limiter, loudness normalization).
"""
from __future__ import annotations

from astros_upscale.media import run_ffmpeg

from app.audio_engine.analyzer import ProblemDetection

# afftdn: FFT noise reduction. highpass=20: removes subsonic rumble/DC-adjacent
# content no music mix needs. Both always run — deterministic, no ML, no GPU.
_BASELINE_RESTORE_FILTERS = ['highpass=f=20', 'afftdn']

# 60Hz mains hum + its first harmonic — narrow rejection, doesn't touch
# musical content elsewhere in the spectrum.
_HUM_NOTCH_FILTERS = ['bandreject=f=60:width_type=h:w=4', 'bandreject=f=120:width_type=h:w=6']

# Gentle limiter to tame residual peaks after clipping-restoration — not the
# final master limiter (that's in master()'s chain, with the real loudness target).
_POST_RESTORE_LIMITER = 'alimiter=limit=0.95:level=disabled'

# A phase-corrective downmix-toward-mono — only applied when analyzer.py
# flagged phase_issues_detected (real negative stereo correlation), never
# unconditionally (would needlessly narrow a healthy stereo image).
_PHASE_CORRECTION_FILTER = 'pan=stereo|c0=0.5*c0+0.5*c1|c1=0.5*c0+0.5*c1'

# Auto Master chain: gentle low-shelf presence, single-band compression
# (a real 3-band split is a documented future refinement — see module
# docstring's "not over-built beyond what's measured" rationale), limiter,
# then loudness normalization to the target LUFS last, so everything upstream
# already has stable input dynamics before the final normalization pass.
_MASTER_EQ = 'equalizer=f=100:t=q:w=1:g=1,equalizer=f=8000:t=q:w=1:g=1'
_MASTER_COMPRESSOR = 'acompressor=threshold=-18dB:ratio=3:attack=20:release=250'
_MASTER_LIMITER = 'alimiter=limit=0.97:level=disabled'

DEFAULT_TARGET_LUFS = -14.0  # streaming-platform-style target (Spotify/YouTube Music range)


def restore(input_path: str, output_path: str, problems: ProblemDetection) -> None:
    """Corrective DSP — reduces noise/hum/residual clipping without touching
    loudness (FR-011's `restore` mode never masters). Always runs the
    baseline chain; hum notch and post-clip limiter only when the analyzer
    actually detected those specific problems (never applied speculatively)."""
    filters = list(_BASELINE_RESTORE_FILTERS)
    if problems.hum_60hz_detected:
        filters.extend(_HUM_NOTCH_FILTERS)
    if problems.clipping_severity > 0:
        filters.append(_POST_RESTORE_LIMITER)
    run_ffmpeg(lambda f: f.input(input_path).output(output_path, {'af': ','.join(filters)}))


def master(
    input_path: str,
    output_path: str,
    *,
    target_lufs: float = DEFAULT_TARGET_LUFS,
    correct_phase: bool = False,
) -> None:
    """Auto Master chain — EQ, dynamics, limiter, then loudness normalization
    to `target_lufs` last (FR-010). `correct_phase` is only True when
    analyzer.py's AudioAnalysisReport.phase_issues_detected was real —
    never applied unconditionally."""
    filters = []
    if correct_phase:
        filters.append(_PHASE_CORRECTION_FILTER)
    filters.extend([_MASTER_EQ, _MASTER_COMPRESSOR, _MASTER_LIMITER,
                     f'loudnorm=I={target_lufs}:TP=-1.5:LRA=11'])
    run_ffmpeg(lambda f: f.input(input_path).output(output_path, {'af': ','.join(filters)}))
