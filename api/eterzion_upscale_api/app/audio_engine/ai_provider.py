"""AudioRestorationProvider (Constitution Princípio XII) + SonicMasterProvider —
the ONLY place in this codebase authorized to reach the SonicMaster worker.
`mastering.py` (and nothing else) talks to this module; this module (and
nothing else) talks to `app.jobs.get_audio_worker_supervisor()`.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from typing import Protocol

from app.audio_engine.analyzer import ProblemDetection
from app.config import settings

# Conservative estimate from the technical audit (specs/006-audio-engine-
# masterizacao — VRAM never officially documented by the SonicMaster authors,
# research.md flags this as measured, not assumed). Used only to avoid
# attempting to load a GPU-bound model when clearly insufficient VRAM is
# present — not a substitute for the real measurement task (T043).
_MIN_VRAM_MB_ESTIMATE = 6000


class AudioRestorationProvider(Protocol):
    def is_available(self) -> bool: ...
    def initialize(self) -> None: ...
    def restore(self, input_path: str, instruction: str, strength: int = 50) -> str: ...
    def restore_full_song(self, input_path: str, instruction: str, strength: int = 50) -> str: ...
    def shutdown(self) -> None: ...


@dataclass(frozen=True)
class _StrengthProfile:
    ai_threshold: float  # overrides analyzer.detect_problems' default when strength is set
    num_inference_steps: int


# data-model.md's AI Strength -> estratégia table. Not a linear multiplier
# (FR-013) — each band changes the acceptance threshold and inference depth.
def _strength_profile(strength: int) -> _StrengthProfile:
    if strength <= 0:
        return _StrengthProfile(ai_threshold=2.0, num_inference_steps=0)  # threshold >1.0 => never triggers
    if strength <= 25:
        return _StrengthProfile(ai_threshold=0.75, num_inference_steps=6)
    if strength <= 50:
        return _StrengthProfile(ai_threshold=0.5, num_inference_steps=10)
    if strength <= 75:
        return _StrengthProfile(ai_threshold=0.35, num_inference_steps=14)
    return _StrengthProfile(ai_threshold=0.2, num_inference_steps=20)


# FR-005 — Problem Detection -> natural-language instruction. Deliberately a
# plain lookup over dominant_problems, not a template with free variables:
# the model only ever sees phrases justified by what analyzer.py actually
# measured.
_PROBLEM_PHRASES = {
    'reverb_severity': 'reduce excessive reverberation',
    'clipping_severity': 'restore clipping while preserving transients',
    'distortion_severity': 'restore distortion artifacts',
    'tonal_imbalance_severity': 'correct tonal imbalance and improve clarity',
    'stereo_imbalance_severity': 'restore stereo image balance',
}
_GENERAL_RESTORATION_PHRASE = 'perform general music restoration'
_PRESERVE_INTENT_SUFFIX = 'while preserving the original musical character'  # FR-009


def build_prompt(problems: ProblemDetection) -> str:
    phrases = [_PROBLEM_PHRASES[key] for key in problems.dominant_problems if key in _PROBLEM_PHRASES]
    if not phrases:
        phrases = [_GENERAL_RESTORATION_PHRASE]
    return f'{" and ".join(phrases)} {_PRESERVE_INTENT_SUFFIX}'


class SonicMasterProvider:
    """Lazy-loaded (FR-019): the worker process isn't spawned until the
    first real `restore()`/`restore_full_song()` call. `is_available()` is
    cheap and side-effect-free — safe to call before deciding whether to use
    this provider at all (FR-020's fallback check)."""

    def __init__(self) -> None:
        self._initialized = False

    def is_available(self) -> bool:
        """FR-017/FR-018 — reuses the project's existing hardware detection
        (Princípio VII) instead of duplicating GPU-query logic here. CPU-only
        inference is deliberately treated as unavailable, not attempted and
        left to time out: a diffusion-transformer pass this size on CPU
        would take far longer than a job should reasonably block for."""
        if not settings.audio_worker_python:
            return False
        if not os.path.isfile(settings.audio_worker_python):
            return False
        if not os.path.isfile(settings.audio_worker_checkpoint):
            return False
        from eterzion_upscale.processing import detect_hardware

        hardware = detect_hardware()
        if not hardware.gpu_present:
            return False
        if hardware.vram_total_mb is not None and hardware.vram_total_mb < _MIN_VRAM_MB_ESTIMATE:
            return False
        return True

    def initialize(self) -> None:
        if self._initialized:
            return  # FR-019 — never re-spawn on a second call
        from app.jobs import get_audio_worker_supervisor
        supervisor = get_audio_worker_supervisor()
        if supervisor is None:
            raise RuntimeError('SonicMasterProvider.initialize() chamado sem ASTROS_AUDIO_WORKER_PYTHON configurado.')
        supervisor.ensure_started()
        self._initialized = True

    def restore(self, input_path: str, instruction: str, strength: int = 50) -> str:
        """Handles both a short clip and a full song identically — no
        `full_song` flag to plumb through. `vendor/sonicmaster/infer.py`'s
        own chunking (split_into_chunks/stitch_chunks_with_crossfade)
        already produces exactly one chunk for audio shorter than
        `chunk_duration` (FR-016) and multiple crossfaded chunks otherwise
        (FR-014/FR-015) — a separate code path here would duplicate that
        decision instead of relying on it."""
        from app.jobs import get_audio_worker_supervisor

        if not self._initialized:
            self.initialize()
        supervisor = get_audio_worker_supervisor()
        assert supervisor is not None  # initialize() already raised if it would be None
        profile = _strength_profile(strength)
        output_path = tempfile.mktemp(suffix='.wav')
        return supervisor.restore_audio(
            ckpt=settings.audio_worker_checkpoint,
            input_path=input_path,
            prompt=instruction,
            output_path=output_path,
            num_inference_steps=profile.num_inference_steps,
            hf_token=settings.hf_token,
        )

    def restore_full_song(self, input_path: str, instruction: str, strength: int = 50) -> str:
        """Same as restore() — kept as its own method to satisfy the
        AudioRestorationProvider contract (spec.md's explicit two-method
        interface) and to make call sites self-documenting, not because the
        implementation differs."""
        return self.restore(input_path, instruction, strength)

    def shutdown(self) -> None:
        from app.jobs import get_audio_worker_supervisor
        supervisor = get_audio_worker_supervisor()
        if supervisor is not None:
            supervisor.terminate()
        self._initialized = False
