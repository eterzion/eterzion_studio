"""MasteringEngine — the only orchestrator for the 3 operation modes
(FR-010/FR-011/FR-012). Ties together analyzer, dsp, quality and ai_provider
without any of those modules talking to each other directly. Constitution
Princípio XII in one place: AI is optional and conditional (FR-002/FR-004),
its output always passes through Quality Guard (FR-006/FR-008), and
unavailability always falls back to DSP-only (FR-020).
"""
from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from typing import Literal

from app.audio_engine import analyzer, dsp
from app.audio_engine.ai_provider import AudioRestorationProvider, SonicMasterProvider, build_prompt
from app.audio_engine.analyzer import AudioAnalysisReport
from app.audio_engine.quality import QualityVerdict, evaluate

AudioMode = Literal['enhance', 'auto_master', 'restore', 'restore_master']


@dataclass
class MasteringResult:
    output_path: str
    audio_analysis: AudioAnalysisReport
    quality_verdict: QualityVerdict | None
    stages_output_paths: dict[str, str]


def _restore_stage(
    input_path: str,
    provider: AudioRestorationProvider,
    ai_strength: int,
    *,
    full_song: bool,
) -> tuple[str, QualityVerdict | None]:
    """Runs analysis -> problem detection -> (AI if needed and available) ->
    corrective DSP -> Quality Guard. Never trusts the AI's output directly
    (FR-006/FR-008) — always re-validates and falls back to the DSP-only
    result on a rejection."""
    before = analyzer.analyze(input_path, measured_at='input')
    problems = analyzer.detect_problems(before)

    dsp_only_path = tempfile.mktemp(suffix='.wav')
    dsp.restore(input_path, dsp_only_path, problems)

    if not problems.requires_ai_restoration or ai_strength <= 0 or not provider.is_available():
        return dsp_only_path, None  # FR-002/FR-020 — no AI call at all

    instruction = build_prompt(problems)
    restore_fn = provider.restore_full_song if full_song else provider.restore
    ai_raw_path = restore_fn(input_path, instruction, ai_strength)

    ai_corrected_path = tempfile.mktemp(suffix='.wav')
    dsp.restore(ai_raw_path, ai_corrected_path, problems)  # FR-006 — always corrective DSP after AI

    after = analyzer.analyze(ai_corrected_path, measured_at='post_ai')
    verdict = evaluate(before, after)

    if verdict.outcome == 'rejected':
        return dsp_only_path, verdict  # FR-008 — AI result discarded entirely
    return ai_corrected_path, verdict  # 'accepted' or 'reduced' — dsp.restore already applied corrective DSP


class MasteringEngine:
    def __init__(self, provider: AudioRestorationProvider | None = None) -> None:
        self._provider = provider or SonicMasterProvider()

    def auto_master(
        self,
        input_path: str,
        output_path: str,
        *,
        ai_strength: int = 50,
        target_lufs: float = dsp.DEFAULT_TARGET_LUFS,
        full_song: bool = False,
    ) -> MasteringResult:
        """FR-010 — Analyze -> Detect -> (AI if needed) -> Analyze -> Master
        -> Quality Guard -> saída."""
        restored_path, verdict = _restore_stage(
            input_path, self._provider, ai_strength, full_song=full_song)
        pre_master = analyzer.analyze(restored_path, measured_at='post_dsp' if verdict is None else 'post_ai')
        dsp.master(restored_path, output_path, target_lufs=target_lufs,
                   correct_phase=pre_master.phase_issues_detected)
        final_analysis = analyzer.analyze(output_path, measured_at='post_master')
        return MasteringResult(
            output_path=output_path, audio_analysis=final_analysis, quality_verdict=verdict,
            stages_output_paths={'original': input_path, 'restored': restored_path, 'mastered': output_path},
        )

    def restore(
        self,
        input_path: str,
        output_path: str,
        *,
        ai_strength: int = 50,
        full_song: bool = False,
    ) -> MasteringResult:
        """FR-011 — corrective restoration only, no loudness-target mastering."""
        restored_path, verdict = _restore_stage(
            input_path, self._provider, ai_strength, full_song=full_song)
        shutil.copyfile(restored_path, output_path)
        final_analysis = analyzer.analyze(output_path, measured_at='post_dsp' if verdict is None else 'post_ai')
        return MasteringResult(
            output_path=output_path, audio_analysis=final_analysis, quality_verdict=verdict,
            stages_output_paths={'original': input_path, 'restored': output_path},
        )

    def restore_master(
        self,
        input_path: str,
        output_path: str,
        *,
        ai_strength: int = 50,
        target_lufs: float = dsp.DEFAULT_TARGET_LUFS,
        full_song: bool = False,
    ) -> MasteringResult:
        """FR-012 — restore, then master the restored result. Reuses restore()'s
        analysis/AI/quality-guard pass instead of duplicating it (single
        `_restore_stage` call, per research.md Decisão 1's "no new abstraction
        just to ease the merge" spirit — restore_master IS restore + master,
        not a parallel implementation)."""
        restored_path, verdict = _restore_stage(
            input_path, self._provider, ai_strength, full_song=full_song)
        pre_master = analyzer.analyze(restored_path, measured_at='post_dsp' if verdict is None else 'post_ai')
        dsp.master(restored_path, output_path, target_lufs=target_lufs,
                   correct_phase=pre_master.phase_issues_detected)
        final_analysis = analyzer.analyze(output_path, measured_at='post_master')
        return MasteringResult(
            output_path=output_path, audio_analysis=final_analysis, quality_verdict=verdict,
            stages_output_paths={'original': input_path, 'restored': restored_path, 'mastered': output_path},
        )

    def run(self, mode: AudioMode, input_path: str, output_path: str, **kwargs) -> MasteringResult:
        if mode == 'restore':
            return self.restore(input_path, output_path, **kwargs)
        if mode == 'restore_master':
            return self.restore_master(input_path, output_path, **kwargs)
        # 'auto_master' and the default ('enhance', routed here only when the
        # caller explicitly opted into audio_engine — app.processing keeps its
        # own separate 'enhance' path for backward compatibility, see
        # app/processing.py's dispatch, Decisão 2/data-model.md).
        return self.auto_master(input_path, output_path, **kwargs)
