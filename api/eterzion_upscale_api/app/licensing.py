"""License gate, offline-tolerance windowing, model-license registry, and the
media-request -> profile -> engine resolver chain. Consolidates what were
`license_gate.py`, `license_cache.py`, `license_registry.py`,
`profile_resolver.py` and `offline_tolerance.py` (Constitution Princípio XI).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from eterzion_upscale import __version__
from eterzion_upscale.processing import HardwareCapability, detect_hardware

from app.config import settings

# ------------------------------- offline tolerance ------------------------------- #
#
# Pure offline-tolerance state math (FR-056 to FR-058) — no I/O, no clock
# reads. The local API only ever calls this once it already knows it CAN'T
# reach eterzion_licensing_service right now (see check_gate() below); while
# reachable, the service's own answer is authoritative and this doesn't
# apply at all.
#
# Assumption from spec.md: 30 days since the last successful revalidation,
# warning from day 23 — "valor adotado como padrão razoável de mercado, não
# especificado pelo dono do projeto — confirmar antes do lançamento."

TOLERANCE_DAYS = 30
WARN_FROM_DAY = 23

OfflineState = str  # 'offline_tolerance' | 'offline_expiring' | 'blocked'


def compute_offline_state(days_since_last_success: float | None) -> tuple[OfflineState, int]:
    """Returns (state, offline_days_remaining).

    `days_since_last_success=None` means there is no cached successful
    check-in at all (e.g. never activated while online, or the cache was
    lost) — nothing to extend tolerance from, so this is `blocked` same as
    exceeding the window, never a silent pass."""
    if days_since_last_success is None:
        return 'blocked', 0
    if days_since_last_success < WARN_FROM_DAY:
        return 'offline_tolerance', max(0, round(TOLERANCE_DAYS - days_since_last_success))
    if days_since_last_success <= TOLERANCE_DAYS:
        return 'offline_expiring', max(0, round(TOLERANCE_DAYS - days_since_last_success))
    return 'blocked', 0


# ------------------------------- license cache ------------------------------- #
#
# Local, persistent record of the last successful license revalidation
# (FR-056) — this is what lets compute_offline_state() above compute a real
# day count across app restarts, and what makes FR-058 (clock rollback must
# not extend tolerance) enforceable: `max_observed_epoch` only ever moves
# forward, so a system clock rolled backward can't manufacture a
# fresher-looking check-in.
#
# Not secret material (just a timestamp) — no DPAPI, unlike security.py's
# install identity. Lives in a sibling directory of the install identity for
# the same reason that one picked %LOCALAPPDATA%/%APPDATA%: per-user,
# survives reinstalls of the app itself.

_CACHE_DIRNAME = 'AstrosUpscale'
_CACHE_FILENAME = 'license_cache.json'


def _cache_dir() -> str:
    base = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or str(Path.home())
    path = os.path.join(base, _CACHE_DIRNAME, 'license')
    os.makedirs(path, exist_ok=True)
    return path


def _cache_path() -> str:
    return os.path.join(_cache_dir(), _CACHE_FILENAME)


def load_license_cache() -> dict | None:
    try:
        with open(_cache_path(), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def record_successful_check(now_epoch: float | None = None) -> None:
    """Called every time check_gate() below successfully reaches the licensing
    service (any 2xx/404-not-activated response — actual reachability, not
    just 'active' status). FR-058: last_success_epoch tracks the largest
    'now' this process has ever observed, so a rolled-back clock can't undo
    it on the next read."""
    now_epoch = now_epoch if now_epoch is not None else time.time()
    cached = load_license_cache() or {}
    max_seen = max(cached.get('max_observed_epoch', 0.0), now_epoch)
    with open(_cache_path(), 'w', encoding='utf-8') as f:
        json.dump({'last_success_epoch': max_seen, 'max_observed_epoch': max_seen}, f)


def days_since_last_success(now_epoch: float | None = None) -> float | None:
    """None when there's no cached successful check at all — see
    compute_offline_state()'s handling of that case."""
    cached = load_license_cache()
    if not cached or 'last_success_epoch' not in cached:
        return None
    now_epoch = now_epoch if now_epoch is not None else time.time()
    effective_now = max(now_epoch, cached.get('max_observed_epoch', now_epoch))
    return (effective_now - cached['last_success_epoch']) / 86400.0


# ------------------------------- license gate ------------------------------- #
#
# License gate for POST /jobs* (T016/T035, FR-051/FR-056 to FR-061): blocks
# job creation when this installation is known to be blocked/not activated,
# and applies the real offline-tolerance window (above) when
# eterzion_licensing_service can't be reached at all — FR-061: a communication
# failure MUST NOT be treated as an invalid licence while the tolerance
# window is still open.
#
# `settings.licensing_service_url` empty means no license infra is configured
# at all — that alone still blocks (T037) unless `settings.dev_allow_unlicensed`
# is explicitly true (default for local dev/pytest), so a build that turns that
# flag off can never end up unenforced just because the URL was left unset.

# Statuses a license row (eterzion_licensing_service's own licensing module)
# can carry. Only 'active' passes the gate — anything else (suspended,
# refunded, revoked, ...) is a real reason to block, per FR-060.
_ACTIVE_STATUS = 'active'
_HTTP_HEADERS = {
    'Accept': 'application/json',
    'User-Agent': f'EterzionStudio/{__version__}',
}


@dataclass
class GateResult:
    allowed: bool
    state: str  # LicenseState-ish, see app.schemas.LicenseState
    message: str | None = None
    installations_used: int | None = None
    installations_limit: int | None = None
    offline_days_remaining: int | None = None


def _http_get(url: str, timeout: float = 5.0) -> dict:
    request = urllib.request.Request(url, headers=_HTTP_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310 - fixed, config-provided base_url
        return json.loads(resp.read().decode('utf-8'))


def _offline_fallback(message: str) -> GateResult:
    """FR-061: unreachable service, not an invalid license — fall back to the
    real 30-day/23-day window computed from the last time we DID reach it
    (license cache above), never a blanket 'allow'."""
    days = days_since_last_success()
    state, remaining = compute_offline_state(days)
    if state == 'blocked':
        return GateResult(
            allowed=False, state='blocked',
            message='Não foi possível confirmar sua licença e o período de uso offline expirou. '
                    'Conecte-se à internet para continuar.')
    return GateResult(allowed=True, state=state, message=message, offline_days_remaining=remaining)


def check_gate() -> GateResult:
    """Real check when a licensing service is configured. When it isn't,
    T037: the permissive fallback requires the EXPLICIT dev_allow_unlicensed
    flag (default True for local dev/pytest) — an empty licensing_service_url
    alone is never enough to silently disable enforcement in a build that set
    that flag to false."""
    if not settings.licensing_service_url:
        if settings.dev_allow_unlicensed:
            return GateResult(allowed=True, state='not_configured')
        return GateResult(
            allowed=False, state='not_activated',
            message='Nenhum serviço de licenciamento configurado. Ative sua licença para continuar.')

    from app.security import ensure_identity

    identity = ensure_identity()
    url = f'{settings.licensing_service_url}/activations/{identity.install_id}/status'
    try:
        body = _http_get(url)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return GateResult(
                allowed=False, state='not_activated',
                message='Este produto ainda não foi ativado. Ative sua licença para continuar.')
        # Any other HTTP error from the service itself (5xx, etc.) is a real
        # reachability problem from the caller's point of view — same offline
        # fallback as a network-level failure below.
        return _offline_fallback('Não foi possível confirmar o estado da licença agora.')
    except (urllib.error.URLError, TimeoutError, OSError):
        return _offline_fallback('Não foi possível confirmar o estado da licença agora.')

    # Reaching the service at all — regardless of what it says — is a real
    # revalidation (FR-056): resets the offline clock the cache above tracks.
    record_successful_check()

    if body.get('status') == _ACTIVE_STATUS:
        return GateResult(
            allowed=True, state='active',
            installations_used=body.get('installations_used'), installations_limit=body.get('installations_limit'),
        )
    return GateResult(
        allowed=False, state='blocked',
        message='Sua licença não está mais ativa. Verifique o status da sua assinatura.')


# ------------------------------- model-license registry ------------------------------- #
#
# Model-license authority (T017, FR-046, Constitution "Licensing and
# Distribution Constraints") — moved here from
# interface/astros_upscale_app/src/renderer/src/data/modelLicenses.ts. The
# backend that resolves a model (eterzion_upscale.processing.resolve_model) MUST
# be the backend that enforces its licence; a renderer-side TypeScript file
# could never actually gate anything, it could only display what someone
# remembered to keep in sync.
#
# Sourced from docs/models/MODEL_LICENSES.md §1 (image models) — the legal
# source of truth this is a technical projection of, same relationship
# data-model.md describes between ContentTypeImplementation and that document.
# Every entry here MUST have a live counterpart in eterzion_upscale.processing.MODELS;
# `verify_registry_completeness()` below is a real, testable guarantee of that,
# not just a comment promising it.
#
# The frontend (`modelLicenses.ts`) still exists today — switching the UI to
# fetch this from the API instead of importing its own copy is T071 (Polish),
# not this task. This is the new authority; retiring the old one is a
# separate, later step.

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


# Every key here MUST match a key in eterzion_upscale.processing.MODELS — enforced
# by verify_registry_completeness(). T024 reduced photo/anime_image to exactly
# one implementation each (FR-095, per docs/models/BENCHMARK_RESULTS.md); the
# runner-up identifiers (realesrgan-x4/x2, realesr-general, realesrnet-x4,
# nomos2-dat2, realesrgan-anime) plus the earlier license-rejected ones are
# tracked in eterzion_upscale.processing.REMOVED_MODEL_IDENTIFIERS, not here.
MODEL_LICENSES: dict[str, ModelLicense] = {
    'nomos-webphoto': _cc_by_phhofm('https://huggingface.co/Phips/4xNomosWebPhoto_RealPLKSR'),
    'hfa2k-span': _cc_by_phhofm('https://huggingface.co/Phips/2xHFA2kSPAN'),
    'realesr-animevideo': _bsd3(),
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
    problems (empty = clean) between this registry and eterzion_upscale's live
    model registry. Both directions matter — a model with no license entry
    could ship unlicensed; a license entry for a model that no longer exists
    is dead data pretending to still govern something."""
    from eterzion_upscale.processing import MODELS

    problems = []
    for name in MODELS:
        if name not in MODEL_LICENSES:
            problems.append(f'{name}: presente em core.MODELS mas sem entrada de licença')
    for name in MODEL_LICENSES:
        if name not in MODELS:
            problems.append(f'{name}: entrada de licença para um modelo que não existe mais em core.MODELS')
    return problems


# ------------------------------- profile resolver ------------------------------- #
#
# The single chokepoint every job passes through, per FR-012 and briefing Seção 11:
#
#     MediaRequest -> Operation Resolver -> Profile Resolver -> Hardware Detection
#     -> Engine Resolver -> Pipeline
#
# The caller (jobs.py) never picks a model/engine directly — it builds a
# MediaRequest (media_type, operation, scale, profile, content_type) and gets
# back a ResolvedPipeline with an opaque engine_ref. FR-009/FR-011: no model
# identifier ever crosses this boundary in either direction.
#
# FR-095 (exactly one implementation per content type) is not yet fully true of
# the underlying registries this reads from — `eterzion_upscale.processing.MODELS`
# still carries multiple entries per category, collapsed to one by T024 once the
# FR-087/093 benchmark picks a winner. Until then, `_CONTENT_TYPE_IMPLEMENTATIONS`
# below is this resolver's own single choice per content type, so every caller
# already gets exactly one implementation even though the registry underneath
# has not been pruned yet.

MediaType = Literal['image', 'video', 'audio']
Operation = Literal['enhance', 'compress', 'convert']
Profile = Literal['fast', 'balanced', 'quality']
ContentType = Literal[
    'photo', 'pixel_art', 'no_model', 'anime_image', 'real_video', 'anime_video', 'speech', 'music'
]

_IMAGE_VIDEO_CONTENT_TYPES = {
    'photo', 'pixel_art', 'no_model', 'anime_image', 'real_video', 'anime_video'
}

# The one content type that resolves no model at all.
#
# Every super-resolution model here is trained on photographs and drawings,
# where softening an edge is correct. Art drawn pixel by pixel is the case
# where it is not: measured over 40 of the owner's real 32x32 icons, all four
# approved models shifted the shape by 18 to 24 mean luma levels, while
# repeating pixels shifts it by none and invents no colour at all.
#
# So this is not 'the model we chose for pixel art' — it is the finding that
# no model belongs here, recorded as a content type so the person can say so
# and the pipeline can act on it.
# 'no_model' is the person saying "run the filters, skip the AI". It was the
# Escala tab called "Manter tamanho", which never belonged there: whether a
# model runs is not a question about size, and keeping it among the sizes
# meant each of the two menus answered half of the other's question.
MODEL_FREE_CONTENT_TYPES = {'pixel_art', 'no_model'}
_AUDIO_CONTENT_TYPES = {'speech', 'music'}


class UnresolvableRequestError(ValueError):
    """Raised when a MediaRequest can't be resolved to a pipeline — either the
    combination is structurally invalid (Operation Resolver) or no approved
    implementation exists for the content type (FR-098, Engine Resolver)."""


@dataclass
class MediaRequest:
    media_type: MediaType
    operation: Operation
    content_type: ContentType | None = None  # required when operation == 'enhance'
    scale: Literal['2x', '4x'] | None = None
    profile: Profile | None = None
    quality: int | None = None  # 0-100, used by compress; ignored otherwise


@dataclass
class ResolvedPipeline:
    media_type: MediaType
    operation: Operation
    content_type: ContentType | None
    profile: Profile | None
    engine_ref: str  # internal identifier only — never serialized to the frontend (FR-009)
    execution_params: dict
    hardware: HardwareCapability
    license_status: Literal['approved', 'approved_conditional'] = 'approved'
    license_condition: str | None = None


@dataclass(frozen=True)
class _ContentTypeImplementation:
    """data-model.md's ContentTypeImplementation — engine_ref plus the
    licence disclosure T055/FR-099/FR-100 require to be trackable in code,
    not just in docs/models/MODEL_LICENSES.md. `engine_ref=None` marks a
    content type with no approved implementation yet (FR-098)."""
    engine_ref: str | None
    license_status: Literal['approved', 'approved_conditional'] = 'approved'
    license_condition: str | None = None


# Engine Resolver: the one approved implementation per content type this resolver
# will ever hand out. photo/anime_image per T023's real benchmark
# (docs/models/BENCHMARK_RESULTS.md), finalized in T024 — eterzion_upscale.processing.MODELS
# now only carries these two winners for their categories (FR-095: exactly one
# implementation).
_CONTENT_TYPE_IMPLEMENTATIONS: dict[str, _ContentTypeImplementation] = {
    'photo': _ContentTypeImplementation('nomos-webphoto'),
    'anime_image': _ContentTypeImplementation('hfa2k-span'),
    'anime_video': _ContentTypeImplementation('realesr-animevideo'),
    'real_video': _ContentTypeImplementation('realplksr-video-real'),  # T045, MODEL_LICENSES.md §3-ter
    'speech': _ContentTypeImplementation('super-voz'),
    # T055 — SonicMaster (Apache-2.0 code/weights) depends at inference time on
    # Stable Audio Open's VAE, whose licence cuts off commercial use above
    # USD $1M/year revenue. Accepted consciously by the product owner
    # (docs/models/MODEL_LICENSES.md §3-bis) — tracked here as a real, checkable
    # data field (FR-099/FR-100) rather than a boolean nobody can interpret
    # without going back to that document.
    'music': _ContentTypeImplementation(
        'sonicmaster', license_status='approved_conditional',
        license_condition=(
            'Cessar o uso ou negociar uma licença comercial com a Stability AI caso a receita '
            'anual ultrapasse USD $1.000.000, por causa da dependência do VAE do Stable Audio Open.'
        ),
    ),
}

# Profile -> execution parameters. tile_threshold/tile_size are NOT here — T061
# (US5, FR-032/FR-035) computes those fresh per-request from HardwareCapability
# (processing.compute_tile_params), merged into execution_params by _resolve_engine
# below, replacing the old fixed _TILE_THRESHOLD=1600/_TILE_SIZE=512 constants
# upscaler.py/video_upscaler.py used to hardcode.
_IMAGE_PROFILE_PARAMS: dict[Profile, dict] = {
    'fast': {'denoise_strength': 1.0, 'half': True},
    'balanced': {'denoise_strength': 0.5, 'half': True},
    'quality': {'denoise_strength': 0.0, 'half': False},
}

_AUDIO_PROFILE_PARAMS: dict[Profile, dict] = {
    'fast': {'ddim_steps': 25},
    'balanced': {'ddim_steps': 50},
    'quality': {'ddim_steps': 100},
}

# FR-005: operations where a profile makes no real difference simply never get one.
_OPERATIONS_WITH_PROFILE = {'enhance'}


def _resolve_operation(request: MediaRequest) -> None:
    """Operation Resolver: structural validation of the MediaRequest itself, before
    any engine/hardware concern. Raises UnresolvableRequestError on a malformed
    combination rather than silently defaulting around it."""
    if request.operation == 'enhance':
        if request.media_type in ('image', 'video') and request.scale is None:
            raise UnresolvableRequestError(
                "'scale' é obrigatório para enhance de imagem/vídeo (FR-005).")
        if request.content_type is None:
            raise UnresolvableRequestError(
                "'content_type' é obrigatório para enhance — deve vir da detecção "
                "automática ou de content_type_override (FR-096).")
        expected_types = _IMAGE_VIDEO_CONTENT_TYPES if request.media_type in ('image', 'video') \
            else _AUDIO_CONTENT_TYPES
        if request.content_type not in expected_types:
            raise UnresolvableRequestError(
                f"content_type {request.content_type!r} não é válido para media_type "
                f"{request.media_type!r}.")
    elif request.operation == 'compress':
        if request.media_type == 'image' and request.scale is not None:
            raise UnresolvableRequestError("'scale' não se aplica a compress de imagem.")
    elif request.operation == 'convert':
        if request.scale is not None:
            raise UnresolvableRequestError("'scale' não se aplica a convert.")


def _resolve_profile(request: MediaRequest) -> Profile | None:
    """Profile Resolver: FR-008 default, FR-005 omission for profile-less operations."""
    if request.operation not in _OPERATIONS_WITH_PROFILE:
        return None
    return request.profile or 'fast'


def _resolve_engine(
        request: MediaRequest, profile: Profile | None,
        hardware: HardwareCapability) -> tuple[str, dict, str, str | None]:
    """Engine Resolver: the one approved implementation for this content type/operation,
    plus its profile-driven execution parameters. Compress/convert never pick an AI
    engine at all (Constitution "No AI Without Benefit") — they resolve to the
    ffmpeg/OpenCV path instead, identified by a fixed engine_ref."""
    if request.operation == 'compress':
        return f'ffmpeg-compress-{request.media_type}', {'quality': request.quality or 75}, 'approved', None
    if request.operation == 'convert':
        return f'ffmpeg-convert-{request.media_type}', {}, 'approved', None

    # operation == 'enhance'
    content_type = request.content_type

    # Same shape as compress/convert above, and for the same reason: this
    # resolves to a real implementation that is simply not an AI engine.
    # pixel_art enlarges by repeating pixels, so there is no model to pick,
    # no profile to tune it with and no VRAM to budget for -- and demanding
    # an entry in _CONTENT_TYPE_IMPLEMENTATIONS made the resolver reject the
    # request outright with "tipo de conteudo desconhecido".
    if content_type in MODEL_FREE_CONTENT_TYPES:
        return 'nearest-enlarge', {}, 'approved', None

    if content_type not in _CONTENT_TYPE_IMPLEMENTATIONS:
        raise UnresolvableRequestError(f"Tipo de conteúdo desconhecido: {content_type!r}.")
    implementation = _CONTENT_TYPE_IMPLEMENTATIONS[content_type]
    if implementation.engine_ref is None:
        raise UnresolvableRequestError(
            f"Ainda não há implementação aprovada para {content_type!r} (FR-098). "
            "Esta operação não está disponível para este tipo de conteúdo.")
    is_image_video = content_type in _IMAGE_VIDEO_CONTENT_TYPES
    params_table = _IMAGE_PROFILE_PARAMS if is_image_video else _AUDIO_PROFILE_PARAMS
    execution_params = dict(params_table[profile])
    if is_image_video:
        # T061/FR-032/FR-035 — computed fresh from this request's real
        # HardwareCapability snapshot, never a fixed constant.
        from app.processing import compute_tile_params

        tile_threshold, tile_size = compute_tile_params(hardware)
        execution_params['tile_threshold'] = tile_threshold
        execution_params['tile_size'] = tile_size
    return (implementation.engine_ref, execution_params,
            implementation.license_status, implementation.license_condition)


def resolve(request: MediaRequest) -> ResolvedPipeline:
    """Runs the full chain and returns a ResolvedPipeline, or raises
    UnresolvableRequestError. Never returns a partially-resolved result."""
    _resolve_operation(request)
    profile = _resolve_profile(request)
    hardware = detect_hardware()
    engine_ref, execution_params, license_status, license_condition = _resolve_engine(request, profile, hardware)
    return ResolvedPipeline(
        media_type=request.media_type,
        operation=request.operation,
        content_type=request.content_type,
        profile=profile,
        engine_ref=engine_ref,
        execution_params=execution_params,
        hardware=hardware,
        license_status=license_status,
        license_condition=license_condition,
    )
