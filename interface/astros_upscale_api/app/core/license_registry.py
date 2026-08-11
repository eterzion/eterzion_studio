"""Model-license authority (T017, FR-046, Constitution "Licensing and
Distribution Constraints") — moved here from
interface/astros_upscale_app/src/renderer/src/data/modelLicenses.ts. The
backend that resolves a model (astros_upscale.core.resolve_model) MUST be the
backend that enforces its licence; a renderer-side TypeScript file could never
actually gate anything, it could only display what someone remembered to keep
in sync.

Sourced from docs/models/MODEL_LICENSES.md §1 (image models) — the legal
source of truth this module is a technical projection of, same relationship
data-model.md describes between ContentTypeImplementation and that document.
Every entry here MUST have a live counterpart in astros_upscale.core.MODELS;
`verify_registry_completeness()` below is a real, testable guarantee of that,
not just a comment promising it.

The frontend (`modelLicenses.ts`) still exists today — switching the UI to
fetch this from the API instead of importing its own copy is T071 (Polish),
not this task. This module is the new authority; retiring the old one is a
separate, later step.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CommercialUse = Literal['allowed', 'restricted', 'not_allowed', 'unverified']
SourceKind = Literal['official-repo-license', 'official-model-card', 'openmodeldb', 'unverified']


@dataclass(frozen=True)
class ModelLicense:
    license: str
    developer: str
    commercial_use: CommercialUse
    modification_allowed: bool | Literal['unverified']
    redistribution_allowed: bool | Literal['unverified']
    attribution_required: bool | Literal['unverified']
    restrictions: tuple[str, ...]
    source_url: str
    source_kind: SourceKind
    verified_at: str  # ISO date


_BSD3_REAL_ESRGAN = (
    'BSD-3-Clause', 'Xintao Wang (xinntao) / Real-ESRGAN',
    'https://github.com/xinntao/Real-ESRGAN/blob/master/LICENSE', 'official-repo-license',
    ('Preservar aviso de copyright e isenção de responsabilidade do BSD-3-Clause.',),
)

_CC_BY_PHHOFM = ('CC-BY-4.0', 'Philip Hofmann (Phhofm)', 'official-model-card',
                  ('Crédito ao autor original obrigatório.',))


def _bsd3(source_url: str = _BSD3_REAL_ESRGAN[2]) -> ModelLicense:
    return ModelLicense(
        license=_BSD3_REAL_ESRGAN[0], developer=_BSD3_REAL_ESRGAN[1],
        commercial_use='allowed', modification_allowed=True, redistribution_allowed=True,
        attribution_required=True, restrictions=_BSD3_REAL_ESRGAN[3],
        source_url=source_url, source_kind='official-repo-license', verified_at='2026-08-06',
    )


def _cc_by_phhofm(source_url: str, source_kind: SourceKind = 'official-model-card') -> ModelLicense:
    return ModelLicense(
        license=_CC_BY_PHHOFM[0], developer=_CC_BY_PHHOFM[1],
        commercial_use='allowed', modification_allowed=True, redistribution_allowed=True,
        attribution_required=True, restrictions=_CC_BY_PHHOFM[3],
        source_url=source_url, source_kind=source_kind, verified_at='2026-08-06',
    )


# Every key here MUST match a key in astros_upscale.core.MODELS — enforced by
# verify_registry_completeness(). T024 reduced photo/anime_image to exactly one
# implementation each (FR-095, per docs/models/BENCHMARK_RESULTS.md); the
# runner-up identifiers (realesrgan-x4/x2, realesr-general, realesrnet-x4,
# nomos2-dat2, realesrgan-anime) plus the earlier license-rejected ones are
# tracked in astros_upscale.legacy_identifiers, not here.
MODEL_LICENSES: dict[str, ModelLicense] = {
    'nomos-webphoto': _cc_by_phhofm('https://huggingface.co/Phips/4xNomosWebPhoto_RealPLKSR'),
    'hfa2k-span': _cc_by_phhofm('https://huggingface.co/Phips/2xHFA2kSPAN'),
    'realesr-animevideo': _bsd3(),
    'hfa2k-avc': _cc_by_phhofm('https://huggingface.co/Phips/2xHFA2kAVCCompact'),
    'nomosuni-span': _cc_by_phhofm('https://huggingface.co/Phips/2xNomosUni_span_multijpg_ldl', 'openmodeldb'),
    'denoise': _cc_by_phhofm('https://openmodeldb.info/models/1x-DeNoise-realplksr-otf', 'openmodeldb'),
    'dejpg': _cc_by_phhofm('https://openmodeldb.info/models/1x-DeJPG-realplksr-otf', 'openmodeldb'),
    'deh264': _cc_by_phhofm('https://huggingface.co/Phips/1xDeH264_realplksr'),
    # T045 — docs/models/MODEL_LICENSES.md §3-ter: Apache-2.0 código e pesos,
    # dataset 100% domínio público, sem ressalva ("SIM, sem ressalva").
    'realplksr-video-real': ModelLicense(
        license='Apache-2.0', developer='Philip Hofmann (Phhofm)', commercial_use='allowed',
        modification_allowed=True, redistribution_allowed=True, attribution_required=False,
        restrictions=(),
        source_url='https://github.com/Phhofm/models/releases/tag/2xPublic_realplksr_dysample_layernorm_real',
        source_kind='official-repo-license', verified_at='2026-08-08',
    ),
}


def get_model_license(name: str) -> ModelLicense | None:
    return MODEL_LICENSES.get(name)


def verify_registry_completeness() -> list[str]:
    """Real integrity check, not a promise in a comment: returns the list of
    problems (empty = clean) between this registry and astros_upscale.core's
    live model registry. Both directions matter — a model with no license
    entry could ship unlicensed; a license entry for a model that no longer
    exists is dead data pretending to still govern something."""
    from astros_upscale.core import MODELS

    problems = []
    for name in MODELS:
        if name not in MODEL_LICENSES:
            problems.append(f'{name}: presente em core.MODELS mas sem entrada de licença')
    for name in MODEL_LICENSES:
        if name not in MODELS:
            problems.append(f'{name}: entrada de licença para um modelo que não existe mais em core.MODELS')
    return problems
