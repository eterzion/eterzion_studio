"""The single chokepoint every job passes through, per FR-012 and briefing Seção 11:

    MediaRequest -> Operation Resolver -> Profile Resolver -> Hardware Detection
    -> Engine Resolver -> Pipeline

The caller (job_manager.py, from T013 on) never picks a model/engine directly — it
builds a MediaRequest (media_type, operation, scale, profile, content_type) and gets
back a ResolvedPipeline with an opaque engine_ref. FR-009/FR-011: no model identifier
ever crosses this boundary in either direction.

FR-095 (exactly one implementation per content type) is not yet fully true of the
underlying registries this module reads from — `astros_upscale.core.MODELS` still
carries multiple entries per category, collapsed to one by T024 once the FR-087/093
benchmark picks a winner. Until then, `_CONTENT_TYPE_IMPLEMENTATIONS` below is this
resolver's own single choice per content type, so every caller already gets exactly
one implementation even though the registry underneath has not been pruned yet.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from astros_upscale.hardware import HardwareCapability, detect_hardware

MediaType = Literal['image', 'video', 'audio']
Operation = Literal['enhance', 'compress', 'convert']
Profile = Literal['fast', 'balanced', 'quality']
ContentType = Literal['photo', 'anime_image', 'real_video', 'anime_video', 'speech', 'music']

_IMAGE_VIDEO_CONTENT_TYPES = {'photo', 'anime_image', 'real_video', 'anime_video'}
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
# (docs/models/BENCHMARK_RESULTS.md), finalized in T024 — astros_upscale.core.MODELS
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
# (capacity.compute_tile_params), merged into execution_params by _resolve_engine
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
    media_engine ffmpeg/OpenCV path instead, identified by a fixed engine_ref."""
    if request.operation == 'compress':
        return f'ffmpeg-compress-{request.media_type}', {'quality': request.quality or 75}, 'approved', None
    if request.operation == 'convert':
        return f'ffmpeg-convert-{request.media_type}', {}, 'approved', None

    # operation == 'enhance'
    content_type = request.content_type
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
        from app.core.capacity import compute_tile_params

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
