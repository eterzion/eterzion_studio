"""Quality Guard — Constitution Princípio XII: "a saída de qualquer provedor
de restauração por IA MUST sempre passar por uma etapa de correção DSP e por
uma validação de qualidade antes de se tornar a saída entregue ao usuário".
Compares two AudioAnalysisReport (FR-007) and produces a QualityVerdict
(FR-008) — the only place in audio_engine/ authorized to decide whether an
AI-restored result is trustworthy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.audio_engine.analyzer import AudioAnalysisReport

Outcome = Literal['accepted', 'reduced', 'rejected']


@dataclass(frozen=True)
class QualityVerdict:
    outcome: Outcome
    reasons: list[str] = field(default_factory=list)
    regression_flags: dict[str, bool] = field(default_factory=dict)


# Tolerances: how much a metric may regress before it counts against the
# verdict. Conservative on purpose — FR-008 says a "regressão técnica grave"
# rejects/reduces, not any measurable difference (DSP/AI processing always
# changes *something*).
_TRUE_PEAK_REGRESSION_DB = 1.0       # true_peak_db got at least this much worse (higher)
_DYNAMIC_RANGE_LOSS_DB = 6.0         # dynamic_range_db dropped by at least this much
_CLIPPING_INCREASE_RATIO = 0.01      # clipping_ratio increased by at least 1 percentage point
_STEREO_CORRELATION_DROP = 0.3       # stereo_correlation got at least this much more negative


def evaluate(before: AudioAnalysisReport, after: AudioAnalysisReport) -> QualityVerdict:
    """Real, objective before/after comparison — no heuristic proxy for
    "sounds worse", only the measurable properties FR-007 lists."""
    flags: dict[str, bool] = {}
    reasons: list[str] = []

    if after.true_peak_db - before.true_peak_db >= _TRUE_PEAK_REGRESSION_DB:
        flags['true_peak_db'] = True
        reasons.append(
            f'true_peak_db regrediu de {before.true_peak_db:.1f} para {after.true_peak_db:.1f}')
    else:
        flags['true_peak_db'] = False

    dynamic_range_loss = before.dynamic_range_db - after.dynamic_range_db
    if dynamic_range_loss >= _DYNAMIC_RANGE_LOSS_DB:
        flags['dynamic_range_db'] = True
        reasons.append(
            f'dynamic_range_db caiu {dynamic_range_loss:.1f}dB '
            f'({before.dynamic_range_db:.1f} -> {after.dynamic_range_db:.1f})')
    else:
        flags['dynamic_range_db'] = False

    clipping_increase = after.clipping_ratio - before.clipping_ratio
    if clipping_increase >= _CLIPPING_INCREASE_RATIO:
        flags['clipping_ratio'] = True
        reasons.append(
            f'clipping_ratio aumentou de {before.clipping_ratio:.3f} para {after.clipping_ratio:.3f}')
    else:
        flags['clipping_ratio'] = False

    correlation_drop = before.stereo_correlation - after.stereo_correlation
    if correlation_drop >= _STEREO_CORRELATION_DROP:
        flags['stereo_correlation'] = True
        reasons.append(
            f'stereo_correlation piorou de {before.stereo_correlation:.2f} para {after.stereo_correlation:.2f}')
    else:
        flags['stereo_correlation'] = False

    regressions = sum(1 for v in flags.values() if v)
    if regressions == 0:
        outcome: Outcome = 'accepted'
    elif regressions == 1:
        outcome = 'reduced'
    else:
        outcome = 'rejected'

    return QualityVerdict(outcome=outcome, reasons=reasons, regression_flags=flags)
