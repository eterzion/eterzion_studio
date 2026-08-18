"""Filter-graph construction, encoder resolution and per-operation ceilings for
the video editor.

Justified as its own module under Princípio XI by conditions (a) and (c): it is
exercised directly by test_video_edits.py without going through routes or jobs,
and it isolates the FFmpeg contract — no other module in this domain builds a
filter.

**On Princípio XIII and the filter graph.** The principle forbids composing a
command line from outside values. FFmpeg's filter graph is, unavoidably, a
string: `-vf` takes text and there is no structural alternative in any binding.
What the principle actually protects is that no value originating outside this
process reaches that text unvalidated. So:

  - the invocation itself is built by `run_ffmpeg`, argument list, shell=False;
  - every number in the graph passes through `_num()`, which accepts only
    finite floats already range-checked by the Pydantic schemas;
  - every non-numeric token (filter names, container, encoder, preset) comes
    from a constant in this module or from the allowlist in config.py, never
    from a request;
  - no client-supplied string is ever interpolated into the graph. There is no
    request field that could carry one — the API accepts container and profile
    and nothing else (contracts/api.md).

That is the honest reading. Claiming the graph is "not a string" would be
false; claiming client input cannot reach it is true, and is what matters.
"""
from __future__ import annotations

import math
import os
import shutil
from typing import Any, NamedTuple

from app.config import (
    VIDEO_CONTAINER_ALLOWLIST,
    VIDEO_EDIT_CEILINGS,
    VIDEO_REMUX_CEILINGS,
    VideoCeilings,
)
from astros_upscale.media import first_available_encoder, run_ffmpeg


class EditError(ValueError):
    """Base for refusals. `reason` is a key the interface translates, never a
    sentence to display verbatim (Princípio XIV)."""

    def __init__(self, reason: str, message: str, **detail: Any):
        super().__init__(message)
        self.reason = reason
        self.detail = detail


class CeilingExceeded(EditError):
    def __init__(self, limiting_factor: str, limit: float, actual: float):
        super().__init__(
            'ceiling_exceeded',
            f'Excede o limite de {limiting_factor}: {actual} > {limit}.',
            limiting_factor=limiting_factor, limit=limit, actual=actual,
        )


class InsufficientDisk(EditError):
    def __init__(self, needed: int, available: int):
        super().__init__(
            'disk_full',
            f'Espaço insuficiente: são necessários ~{needed} bytes, há {available}.',
            needed_bytes=needed, available_bytes=available,
        )


class EncoderUnavailable(EditError):
    def __init__(self, container: str):
        super().__init__(
            'encoder_unavailable',
            f'Nenhum encoder disponível neste ambiente para {container}.',
            container=container,
        )


# --------------------------------- ceilings --------------------------------- #


class OperationSize(NamedTuple):
    """What the ceilings are checked against. `duration_seconds` is the duration
    of the OUTPUT, not of the source file: trimming 30 s out of a 3 h recording
    is 30 s of work, and charging it 3 h would refuse a job the machine handles
    easily (FR-013d + T014)."""
    duration_seconds: float
    width: int
    height: int
    frame_rate: float
    size_bytes: int

    @property
    def frame_count(self) -> int:
        return int(math.ceil(self.duration_seconds * self.frame_rate))


def check_ceilings(size: OperationSize, *, reencoding: bool = True) -> None:
    """Refuse oversized work BEFORE starting it, naming the limiting factor.

    Princípio VII. This does not replace `processing.check_capacity()` and MUST
    NOT be read as doing so — that asks "can this machine cope", adaptively,
    from detected hardware; this asks "is this job reasonable at all". A video
    passes both or is refused.

    Checks run in the order a person would notice them, so the reported factor
    is the most explanatory one rather than whichever happened to be first in
    the tuple.
    """
    ceilings: VideoCeilings = VIDEO_EDIT_CEILINGS if reencoding else VIDEO_REMUX_CEILINGS

    if size.duration_seconds > ceilings.max_duration_seconds:
        raise CeilingExceeded('duration', ceilings.max_duration_seconds, size.duration_seconds)
    if size.width > ceilings.max_width:
        raise CeilingExceeded('width', ceilings.max_width, size.width)
    if size.height > ceilings.max_height:
        raise CeilingExceeded('height', ceilings.max_height, size.height)
    if size.frame_rate > ceilings.max_frame_rate:
        raise CeilingExceeded('frame_rate', ceilings.max_frame_rate, size.frame_rate)
    if size.frame_count > ceilings.max_frame_count:
        raise CeilingExceeded('frame_count', ceilings.max_frame_count, size.frame_count)
    if size.size_bytes > ceilings.max_size_bytes:
        raise CeilingExceeded('size_bytes', ceilings.max_size_bytes, size.size_bytes)


def check_disk_space(destination: str, source_size_bytes: int) -> None:
    """Refuse before starting when the destination cannot hold the result.

    Estimated as the source's size: a re-encode is usually smaller, but assuming
    so would turn a refusal into a failure partway through — and running out of
    space mid-encode is the case the spec lists as an edge case precisely
    because it is silent until it is not.
    """
    try:
        directory = os.path.dirname(os.path.abspath(destination))
        while directory and not os.path.isdir(directory):
            parent = os.path.dirname(directory)
            if parent == directory:
                break
            directory = parent
        free = shutil.disk_usage(directory).free
    except (OSError, ValueError):
        # A destination that cannot even be measured — unreadable, or not a
        # valid path at all (a null byte raises ValueError, not OSError) — is
        # the caller's problem to report. Refusing here would turn an unrelated
        # problem into a capacity error.
        return
    if free < source_size_bytes:
        raise InsufficientDisk(source_size_bytes, free)


# ---------------------------- encoder resolution ---------------------------- #

# Profile → encoder settings. Chosen from the measurements in
# docs/benchmarks/video-encoder-profiles.md (T011a), not from reputation —
# the Development Workflow requires benchmarks to precede this choice.
#
# Values are per-encoder because a CRF means different things to different
# encoders; a single number applied to all of them would be a guess wearing a
# constant's clothing.
_PROFILE_SETTINGS: dict[str, dict[str, dict[str, str]]] = {
    'libvpx-vp9': {
        'fast': {'crf': '38', 'cpu-used': '5', 'deadline': 'realtime'},
        'balanced': {'crf': '32', 'cpu-used': '2', 'deadline': 'good'},
        'quality': {'crf': '26', 'cpu-used': '1', 'deadline': 'good'},
    },
    'libaom-av1': {
        'fast': {'crf': '40', 'cpu-used': '8'},
        'balanced': {'crf': '34', 'cpu-used': '6'},
        'quality': {'crf': '28', 'cpu-used': '4'},
    },
    'h264_nvenc': {
        'fast': {'preset': 'p1', 'cq': '32'},
        'balanced': {'preset': 'p4', 'cq': '26'},
        'quality': {'preset': 'p6', 'cq': '21'},
    },
    'h264_qsv': {
        'fast': {'preset': 'veryfast', 'global_quality': '32'},
        'balanced': {'preset': 'medium', 'global_quality': '26'},
        'quality': {'preset': 'slow', 'global_quality': '21'},
    },
    'h264_amf': {
        'fast': {'quality': 'speed', 'qp_i': '32'},
        'balanced': {'quality': 'balanced', 'qp_i': '26'},
        'quality': {'quality': 'quality', 'qp_i': '21'},
    },
}


class EncoderChoice(NamedTuple):
    video_encoder: str
    audio_encoder: str | None
    options: dict[str, str]


def resolve_encoder(container: str, profile: str, *, want_audio: bool = True) -> EncoderChoice:
    """Resolve intent (container + profile) to an encoder that actually works
    here.

    Princípio V: the client never names an encoder or a preset — it names what
    it wants, and this decides how. Princípio XIII: permitted is not present,
    so the choice is made against a functional probe, falling through the
    container's preference order.
    """
    spec = VIDEO_CONTAINER_ALLOWLIST.get(container)
    if spec is None:
        raise EditError('container_not_allowed', f'Container não permitido: {container!r}')
    if profile not in ('fast', 'balanced', 'quality'):
        raise EditError('profile_not_allowed', f'Perfil desconhecido: {profile!r}')

    video_encoder = first_available_encoder(spec.video_encoders)
    if video_encoder is None:
        raise EncoderUnavailable(container)

    audio_encoder = first_available_encoder(spec.audio_encoders) if want_audio else None

    return EncoderChoice(
        video_encoder=video_encoder,
        audio_encoder=audio_encoder,
        options=dict(_PROFILE_SETTINGS.get(video_encoder, {}).get(profile, {})),
    )


def available_containers() -> list[dict[str, Any]]:
    """Which containers this environment can actually produce, for
    `GET /video/export-options`.

    Reports the container and a categorical reason, never an encoder name —
    Princípio V applies to this surface like any other.
    """
    result = []
    for container, spec in VIDEO_CONTAINER_ALLOWLIST.items():
        usable = first_available_encoder(spec.video_encoders) is not None
        result.append({
            'value': container,
            'available': usable,
            'unavailable_reason': None if usable else 'no_encoder_available',
        })
    return result


# ------------------------------- filter graph ------------------------------- #


def _num(value: float) -> str:
    """Format a number for the filter graph.

    The single choke point through which every value in the graph passes. It
    accepts a finite number and nothing else — a NaN, an infinity or a string
    raises here rather than becoming a token FFmpeg parses as syntax.
    """
    number = float(value)
    if not math.isfinite(number):
        raise EditError('invalid_value', f'Valor não finito no grafo de filtros: {value!r}')
    if number == int(number):
        return str(int(number))
    return f'{number:.6f}'.rstrip('0').rstrip('.')


def _even(value: int) -> int:
    """Round down to an even number. Encoders reject odd dimensions in the
    common yuv420p pixel formats — optimize.py already learned this."""
    return max(2, int(value) // 2 * 2)


def build_filter_chain(edits: dict[str, Any], source_width: int, source_height: int) -> list[str]:
    """The ordered filter list for a set of edits. Empty when everything is
    neutral, which is what lets a trim-only job skip re-encoding entirely.

    Order is normative (data-model.md) and the tests assert it: geometry first,
    then colour, then effects. Geometry first is not arbitrary — scaling down
    before the colour and effect passes means those passes run over fewer
    pixels, which is Princípio III applied to the graph itself.
    """
    chain: list[str] = []

    transform = edits.get('transform') or {}
    crop = transform.get('crop')
    if crop:
        chain.append(
            f"crop={_num(_even(crop['width']))}:{_num(_even(crop['height']))}"
            f":{_num(crop['x'])}:{_num(crop['y'])}"
        )

    rotation = int(transform.get('rotation_degrees') or 0)
    if rotation:
        if rotation not in (90, 180, 270):
            raise EditError('invalid_value', f'Rotação não permitida: {rotation}')
        # transpose=1 is 90° clockwise; 180 is two of them. Named constants
        # rather than a computed expression, because the mapping is not
        # arithmetic and pretending it is invites an off-by-one quadrant.
        chain.extend({90: ['transpose=1'], 180: ['transpose=1', 'transpose=1'],
                      270: ['transpose=2']}[rotation])

    if transform.get('flip_horizontal'):
        chain.append('hflip')
    if transform.get('flip_vertical'):
        chain.append('vflip')

    out_w = transform.get('output_width')
    out_h = transform.get('output_height')
    if out_w and out_h and (int(out_w), int(out_h)) != (source_width, source_height):
        chain.append(f'scale={_num(_even(out_w))}:{_num(_even(out_h))}')

    chain.extend(_colour_filters(edits.get('adjustments') or {}))
    chain.extend(_effect_filters(edits.get('effects') or {}))
    return chain


# Neutral values, from data-model.md. A parameter at its neutral value is
# omitted from the graph rather than written as a no-op: a shorter graph is a
# faster graph, and `eq=contrast=1` costs a pass for nothing.
_EQ_NEUTRAL = {'brightness': 0.0, 'contrast': 1.0, 'saturation': 1.0, 'gamma': 1.0}


def _colour_filters(adjustments: dict[str, Any]) -> list[str]:
    """The `eq` and `hue` filters. This is the FFmpeg side of the parity the
    renderer's WebGL shader must reproduce (research.md Decisão 1) — the two
    implement the same formula, and test_video_edits.py pins the mapping."""
    filters = []
    eq_parts = [
        f'{name}={_num(adjustments[name])}'
        for name, neutral in _EQ_NEUTRAL.items()
        if adjustments.get(name) is not None and float(adjustments[name]) != neutral
    ]
    if eq_parts:
        filters.append('eq=' + ':'.join(eq_parts))

    hue = adjustments.get('hue_degrees')
    if hue:
        filters.append(f'hue=h={_num(hue)}')

    sharpness = adjustments.get('sharpness')
    if sharpness:
        # unsharp's amount is the last field; 5:5 is the default kernel size.
        filters.append(f'unsharp=5:5:{_num(sharpness)}')
    return filters


def _effect_filters(effects: dict[str, Any]) -> list[str]:
    """Effects the renderer's shader does NOT reproduce — these are what make
    FR-015's disclosure necessary, and why the on-demand preview exists."""
    filters = []
    if effects.get('denoise_enabled') and effects.get('denoise_strength'):
        # hqdn3d's four parameters are luma/chroma spatial and temporal. Scaled
        # from one 0-100 control so a person tunes one thing, not four.
        strength = float(effects['denoise_strength']) / 100.0
        filters.append(
            f'hqdn3d={_num(4 * strength)}:{_num(3 * strength)}'
            f':{_num(6 * strength)}:{_num(4.5 * strength)}'
        )
    if effects.get('blur_enabled') and effects.get('blur_strength'):
        filters.append(f'gblur=sigma={_num(float(effects["blur_strength"]) / 10.0)}')
    if effects.get('grain_enabled') and effects.get('grain_strength'):
        filters.append(f'noise=alls={_num(float(effects["grain_strength"]) / 2.0)}:allf=t')
    return filters


# -------------------------------- the export -------------------------------- #


def build_audio_options(audio: dict[str, Any], choice: EncoderChoice) -> dict[str, str]:
    """Audio handling for FR-013e: keep, mute, or drop the track."""
    mode = (audio or {}).get('mode', 'keep')
    if mode == 'remove':
        return {'an': None}  # type: ignore[dict-item]
    options: dict[str, str] = {}
    if choice.audio_encoder:
        options['c:a'] = choice.audio_encoder
    volume = float((audio or {}).get('volume', 1.0))
    if mode == 'mute':
        options['af'] = 'volume=0'
    elif volume != 1.0:
        options['af'] = f'volume={_num(volume)}'
    return options


def export(
    input_path: str,
    output_path: str,
    edits: dict[str, Any],
    *,
    container: str,
    profile: str,
    source_width: int,
    source_height: int,
    has_audio: bool = True,
) -> None:
    """Run the export. Invocation goes through `run_ffmpeg` — argument list,
    shell=False, the form Princípio XIII requires.

    The caller is responsible for having checked ceilings first and for
    cleaning up on every exit path; this function only encodes.
    """
    choice = resolve_encoder(container, profile, want_audio=has_audio)
    chain = build_filter_chain(edits, source_width, source_height)
    trim = edits.get('trim') or None

    input_options: dict[str, Any] = {}
    output_options: dict[str, Any] = {'c:v': choice.video_encoder, **choice.options}

    if trim:
        # -ss before -i seeks the input, which is dramatically faster than
        # decoding to the start point and discarding. -t is the output
        # duration, applied after the seek.
        input_options['ss'] = _num(trim['start_seconds'])
        output_options['t'] = _num(float(trim['end_seconds']) - float(trim['start_seconds']))

    if chain:
        output_options['vf'] = ','.join(chain)

    if has_audio:
        output_options.update(build_audio_options(edits.get('audio') or {}, choice))
    else:
        output_options['an'] = None

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    run_ffmpeg(lambda f: f.input(input_path, input_options).output(output_path, output_options))


# Preview frames are decoded at reduced size: the point is to judge whether an
# effect looks right, not to inspect the master. Matches the image pipeline's
# existing preview, which caps at 480 on the long edge.
_PREVIEW_MAX_DIM = 640


def render_frame(input_path: str, output_path: str, time_seconds: float,
                 edits: dict[str, Any], *, source_width: int, source_height: int) -> None:
    """Render one frame with the edits applied, for the on-demand preview tier
    (research.md Decisão 2).

    Uses the SAME chain builder the export uses. That is the whole point: a
    preview built by a second, simpler code path would drift from the export
    exactly where it matters most — on the effects the shader could not
    reproduce, which is why this tier exists at all.
    """
    chain = build_filter_chain(edits, source_width, source_height)

    # Downscale last, after the edits, so the person sees what the filters do at
    # the size they are being applied — scaling first would soften a sharpen and
    # hide a denoise.
    scale = min(1.0, _PREVIEW_MAX_DIM / max(source_width or 1, source_height or 1))
    if scale < 1.0:
        chain = [*chain, f'scale={_num(_even(int(source_width * scale)))}:'
                         f'{_num(_even(int(source_height * scale)))}']

    output_options: dict[str, Any] = {'frames:v': '1'}
    if chain:
        output_options['vf'] = ','.join(chain)

    # -ss before -i seeks without decoding everything up to the point, which is
    # what keeps this interactive on a long file.
    run_ffmpeg(lambda f: f.input(input_path, {'ss': _num(max(0.0, time_seconds))})
               .output(output_path, output_options))
