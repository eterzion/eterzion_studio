"""T012/T014 (specs/007-video-editor-player) — filter graph, encoder resolution
and per-operation ceilings.

Princípio VIII: FFmpeg runs for real in the export test at the bottom. The graph
tests are pure string assertions on purpose — they pin the exact text FFmpeg
will receive, which is the thing that regresses silently.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app import video_edits
from app.config import VIDEO_EDIT_CEILINGS
from app.video_edits import CeilingExceeded, EditError, OperationSize
from astros_upscale.media import has_ffmpeg

FIXTURES = Path(__file__).resolve().parent / 'fixtures'
needs_ffmpeg = pytest.mark.skipif(not has_ffmpeg(), reason='ffmpeg não encontrado')


def _size(**overrides):
    base = dict(duration_seconds=10.0, width=1920, height=1080, frame_rate=30.0,
                size_bytes=1024 * 1024)
    base.update(overrides)
    return OperationSize(**base)


# --------------------------------- ceilings --------------------------------- #


def test_a_reasonable_job_passes():
    video_edits.check_ceilings(_size())


@pytest.mark.parametrize(
    'field, value, expected_factor',
    [
        ('duration_seconds', VIDEO_EDIT_CEILINGS.max_duration_seconds + 1, 'duration'),
        ('width', VIDEO_EDIT_CEILINGS.max_width + 1, 'width'),
        ('height', VIDEO_EDIT_CEILINGS.max_height + 1, 'height'),
        ('frame_rate', VIDEO_EDIT_CEILINGS.max_frame_rate + 1, 'frame_rate'),
        ('size_bytes', VIDEO_EDIT_CEILINGS.max_size_bytes + 1, 'size_bytes'),
    ],
)
def test_each_ceiling_refuses_and_names_itself(field, value, expected_factor):
    """FR-025: the refusal must name the limiting factor. A generic 'too big'
    tells the person nothing about what to change."""
    with pytest.raises(CeilingExceeded) as excinfo:
        video_edits.check_ceilings(_size(**{field: value}))
    assert excinfo.value.detail['limiting_factor'] == expected_factor
    assert excinfo.value.reason == 'ceiling_exceeded'


def test_frame_count_ceiling_is_derived_not_declared():
    """Duration and frame rate can each be legal while their product is not."""
    with pytest.raises(CeilingExceeded) as excinfo:
        video_edits.check_ceilings(_size(duration_seconds=7000.0, frame_rate=119.0))
    assert excinfo.value.detail['limiting_factor'] == 'frame_count'


def test_remux_ceilings_are_looser_than_reencode_ceilings():
    oversized = _size(duration_seconds=VIDEO_EDIT_CEILINGS.max_duration_seconds + 60, frame_rate=1.0)
    with pytest.raises(CeilingExceeded):
        video_edits.check_ceilings(oversized, reencoding=True)
    video_edits.check_ceilings(oversized, reencoding=False)


def test_ceilings_measure_the_trimmed_output_not_the_source_file():
    """T014. Trimming 30 s out of a 3 h recording is 30 s of work. Charging it
    the source duration would refuse a job the machine handles trivially — and
    would make the trim feature useless on exactly the long files people trim.

    OperationSize carries the OUTPUT duration; this pins that contract.
    """
    three_hours = 3 * 60 * 60
    assert three_hours > VIDEO_EDIT_CEILINGS.max_duration_seconds

    with pytest.raises(CeilingExceeded):
        video_edits.check_ceilings(_size(duration_seconds=three_hours))

    # The same source, trimmed to 30 s, passes.
    video_edits.check_ceilings(_size(duration_seconds=30.0))


# ------------------------------- filter graph ------------------------------- #


def test_neutral_edits_produce_no_filters():
    """An empty chain is what lets a trim-only job skip re-encoding."""
    assert video_edits.build_filter_chain({}, 1920, 1080) == []


def test_neutral_values_are_omitted_rather_than_written_as_no_ops():
    edits = {'adjustments': {'brightness': 0.0, 'contrast': 1.0, 'saturation': 1.0, 'gamma': 1.0}}
    assert video_edits.build_filter_chain(edits, 1920, 1080) == []


def test_transform_order_is_crop_rotate_flip_scale():
    """Normative in data-model.md, and the preview must agree with it — a
    different order produces a different picture, not a different route to the
    same one."""
    edits = {'transform': {
        'crop': {'x': 10, 'y': 20, 'width': 640, 'height': 480},
        'rotation_degrees': 90,
        'flip_horizontal': True,
        'output_width': 320, 'output_height': 240,
    }}
    chain = video_edits.build_filter_chain(edits, 1920, 1080)
    kinds = [c.split('=')[0] for c in chain]
    assert kinds == ['crop', 'transpose', 'hflip', 'scale']


def test_geometry_comes_before_colour():
    """Scaling down first means the colour pass runs over fewer pixels."""
    edits = {
        'transform': {'output_width': 640, 'output_height': 360},
        'adjustments': {'contrast': 1.4},
    }
    chain = video_edits.build_filter_chain(edits, 1920, 1080)
    assert chain.index([c for c in chain if c.startswith('scale')][0]) < \
        chain.index([c for c in chain if c.startswith('lutyuv')][0])


def test_odd_dimensions_are_rounded_to_even():
    """Encoders reject odd dimensions in yuv420p — optimize.py already learned
    this, and the editor lets a person type any number."""
    edits = {'transform': {'output_width': 641, 'output_height': 361}}
    assert video_edits.build_filter_chain(edits, 1920, 1080) == ['scale=640:360']


def test_scale_is_omitted_when_output_matches_source():
    edits = {'transform': {'output_width': 1920, 'output_height': 1080}}
    assert video_edits.build_filter_chain(edits, 1920, 1080) == []


def test_rotation_180_is_two_transposes():
    edits = {'transform': {'rotation_degrees': 180}}
    assert video_edits.build_filter_chain(edits, 1920, 1080) == ['transpose=1', 'transpose=1']


def test_unsupported_rotation_is_refused():
    with pytest.raises(EditError):
        video_edits.build_filter_chain({'transform': {'rotation_degrees': 45}}, 1920, 1080)


def test_adjustments_split_between_luma_and_chroma():
    """The FFmpeg half of the parity the renderer's shader must reproduce
    (research.md Decisão 1). If this mapping changes, the shader changes with
    it or the preview starts lying.

    Asserting on the shape, not on the exact expression text: the arithmetic is
    pinned where it belongs, by rendering it and comparing against eqLuma()
    below. Two passes, and only two: luma through `lutyuv`, chroma through
    `hue`."""
    edits = {'adjustments': {'brightness': 0.2, 'contrast': 1.3, 'saturation': 0.8,
                             'gamma': 1.1, 'hue_degrees': 15}}
    chain = video_edits.build_filter_chain(edits, 1920, 1080)
    assert len(chain) == 2
    assert chain[0].startswith('lutyuv=y=')
    assert chain[1] == 'hue=h=15:s=0.8'


def test_saturation_never_goes_through_a_chroma_lut():
    """It used to, as `lutyuv=u=..:v=..` before `hue`. That pass writes 8-bit
    chroma and saturates it before `hue` reads it, while the shader scales and
    rotates in float and clamps once — measured at 5,95 levels of average
    divergence against 0,93 when merged into a single `hue` pass
    (docs/technical-debt/preview-export-parity-combined.md)."""
    chain = video_edits.build_filter_chain({'adjustments': {'saturation': 1.25}}, 1920, 1080)
    assert chain == ['hue=s=1.25']
    assert not any('u=' in f or 'v=' in f for f in chain)


def test_a_neutral_adjustment_adds_no_pass():
    """A no-op filter is a wasted pass over every frame."""
    assert video_edits.build_filter_chain(
        {'adjustments': {'brightness': 0.0, 'contrast': 1.0, 'saturation': 1.0,
                         'gamma': 1.0, 'hue_degrees': 0}},
        1920, 1080) == []


def test_hue_alone_still_works():
    assert video_edits.build_filter_chain(
        {'adjustments': {'hue_degrees': 20}}, 1920, 1080) == ['hue=h=20']


def test_non_finite_values_never_reach_the_graph():
    """_num() is the single choke point. A NaN reaching the graph would become
    a token FFmpeg parses as syntax."""
    for bad in (float('nan'), float('inf'), float('-inf')):
        with pytest.raises(EditError):
            video_edits.build_filter_chain({'adjustments': {'contrast': bad}}, 1920, 1080)


def test_effects_are_separate_from_adjustments():
    """Effects are what the shader cannot reproduce, which is why FR-015's
    disclosure exists — they must be distinguishable in the graph."""
    edits = {'effects': {'denoise_enabled': True, 'denoise_strength': 50}}
    chain = video_edits.build_filter_chain(edits, 1920, 1080)
    # Mid-strength lands on the sigma the benchmark measured as the peak.
    assert chain == ['fftdnoiz=sigma=6']


# ---------------------------- encoder resolution ---------------------------- #


def test_container_outside_the_allowlist_is_refused():
    with pytest.raises(EditError) as excinfo:
        video_edits.resolve_encoder('avi', 'balanced')
    assert excinfo.value.reason == 'container_not_allowed'


def test_unknown_profile_is_refused():
    with pytest.raises(EditError) as excinfo:
        video_edits.resolve_encoder('webm', 'ultra')
    assert excinfo.value.reason == 'profile_not_allowed'


@needs_ffmpeg
def test_resolution_never_returns_a_gpl_encoder():
    """Even on a machine where libx264 is installed and would work."""
    from astros_upscale.media import GPL_ENCODERS

    for container in ('mp4', 'mov', 'mkv', 'webm'):
        try:
            choice = video_edits.resolve_encoder(container, 'balanced')
        except video_edits.EncoderUnavailable:
            continue
        assert choice.video_encoder not in GPL_ENCODERS


@needs_ffmpeg
def test_available_containers_reports_a_reason_not_an_encoder_name():
    """Princípio V applies to this surface too — a person is told the container
    is unavailable, never which encoder was missing."""
    for entry in video_edits.available_containers():
        assert set(entry) == {'value', 'available', 'unavailable_reason'}
        if not entry['available']:
            assert entry['unavailable_reason'] == 'no_encoder_available'


# ------------------------------- real export -------------------------------- #


@needs_ffmpeg
def test_export_produces_a_file_and_leaves_the_source_untouched(tmp_path):
    """Real FFmpeg, real file. Princípio XV: the input must still be there,
    byte-identical, when the operation finishes."""
    source = FIXTURES / 'curto.mp4'
    if not source.exists():
        pytest.skip('fixtures ausentes — rode tests/fixtures/make_video_fixtures.py')

    working = tmp_path / 'origem.mp4'
    working.write_bytes(source.read_bytes())
    before = working.read_bytes()

    try:
        choice = video_edits.resolve_encoder('webm', 'fast')
    except video_edits.EncoderUnavailable:
        pytest.skip('nenhum encoder disponível para webm nesta máquina')
    assert choice.video_encoder

    output = tmp_path / 'saida.webm'
    video_edits.export(
        str(working), str(output),
        {'adjustments': {'contrast': 1.2}, 'trim': {'start_seconds': 0.0, 'end_seconds': 2.0}},
        container='webm', profile='fast', source_width=1920, source_height=1080,
    )

    assert output.is_file() and output.stat().st_size > 0
    assert working.read_bytes() == before, 'o arquivo de origem foi modificado'


# ------------------------- preview/export parity (T042) ------------------------- #
#
# The renderer previews with a WebGL shader; FFmpeg produces the export. FR-015
# forbids the two differing silently, so the agreement has to be measured rather
# than asserted in a comment.
#
# Comparing two copies of the same formula would prove nothing — both could be
# wrong together. So this runs the colour chain THIS MODULE BUILDS over a known
# colour and checks the resulting pixel against the formula the shader implements
# (interface/src/renderer/src/composables/useVideoPreviewPipeline.ts, eqLuma).
# If FFmpeg's behaviour ever diverges from that formula, this fails and the
# shader is the thing that must change.
#
# It used to hand-write `eq=...` here instead of calling `_colour_filters`. That
# tested FFmpeg's eq filter, not the graph the product emits — so when eq turned
# out to be GPL and missing from the shipped LGPL build, this test could not have
# noticed. Rendering the real chain is what closes that gap.


def _eq_luma(value: float, brightness: float = 0.0, contrast: float = 1.0, gamma: float = 1.0) -> float:
    """The luma arithmetic eqLuma() implements in the renderer, transcribed here
    so the two can be compared against FFmpeg rather than against each other.

    `value` is full-range luma in 0..1. The limited-range hop matters: the filter
    operates on the STORED plane, which video carries in 16..235, so applying it
    to full-range luma makes brightness land 255/219 too weak. The first version
    of this test omitted it and failed against real FFmpeg by exactly that
    factor — the shader was corrected, not the tolerance."""
    stored = (16.0 + 219.0 * value) / 255.0
    v = contrast * (stored - 0.5) + 0.5 + brightness
    v = min(1.0, max(0.0, v))
    v = v ** (1.0 / max(0.1, gamma))
    return (v * 255.0 - 16.0) / 219.0


def _render_gray_through_eq(tmp_path, level: float, **eq_params) -> float:
    """Render one solid grey frame through the module's own colour chain and
    read back its luma."""
    import subprocess

    from astros_upscale.media import ffmpeg_path

    value = int(round(level * 255))
    # An all-neutral request builds no filter at all, and that case still has to
    # come out at the value it went in — `null` keeps the graph shape identical.
    graph = ','.join(video_edits._colour_filters(eq_params)) or 'null'
    output = tmp_path / 'out.png'
    subprocess.run(
        [ffmpeg_path() or 'ffmpeg', '-y', '-v', 'error',
         '-f', 'lavfi', '-i', f'color=c=0x{value:02x}{value:02x}{value:02x}:size=32x32:duration=0.1:rate=1',
         '-vf', graph, '-frames:v', '1', str(output)],
        capture_output=True, check=True,
    )
    import cv2

    image = cv2.imread(str(output))
    # Grey in, grey out — any channel carries the luma.
    return float(image[16, 16, 0]) / 255.0


@needs_ffmpeg
@pytest.mark.parametrize(
    'level, params',
    [
        (0.5, {'brightness': 0.0, 'contrast': 1.0}),
        (0.5, {'brightness': 0.2, 'contrast': 1.0}),
        (0.25, {'brightness': 0.0, 'contrast': 1.5}),
        (0.75, {'brightness': -0.1, 'contrast': 1.0}),
    ],
)
def test_ffmpeg_eq_matches_the_formula_the_shader_implements(tmp_path, level, params):
    measured = _render_gray_through_eq(tmp_path, level, **params)
    expected = _eq_luma(level, **params)
    # Tolerance covers 8-bit quantisation and the RGB/YUV round trip FFmpeg does
    # around the filter — not a licence for the formulas to disagree.
    assert measured == pytest.approx(expected, abs=0.02), (
        f'FFmpeg produziu {measured:.4f}, a fórmula do shader prevê {expected:.4f}'
    )


def test_no_adjustment_or_effect_emits_a_gpl_filter():
    """`eq` and `hqdn3d` are GPL and are simply not in the LGPL binary the
    installer ships, so a graph naming one dies with `No such filter` in the
    packaged app while working on a developer's GPL build. That asymmetry hid
    the defect for the whole of 007; the rule was a comment in media.py and a
    comment cannot fail a build."""
    from astros_upscale.media import graph_has_gpl_filter

    every_control = {
        'adjustments': {'brightness': 0.2, 'contrast': 1.4, 'saturation': 1.3, 'gamma': 1.6,
                        'hue_degrees': 20, 'sharpness': 1.5},
        'effects': {'denoise_enabled': True, 'denoise_strength': 60,
                    'blur_enabled': True, 'blur_strength': 30,
                    'grain_enabled': True, 'grain_strength': 20},
        'transform': {'rotation': 90, 'flip_horizontal': True},
    }
    chain = video_edits.build_filter_chain(every_control, 1920, 1080)
    offending = graph_has_gpl_filter(chain)
    assert offending is None, f'filtro GPL na cadeia: {offending}'


@needs_ffmpeg
def test_the_whole_control_surface_runs_on_the_local_ffmpeg(tmp_path):
    """Every filter the product can emit, in one graph, actually executed. A
    name that does not exist here fails at graph-open time — which is exactly
    how `eq` and `hqdn3d` would have been caught."""
    import subprocess

    from astros_upscale.media import ffmpeg_path

    every_control = {
        'adjustments': {'brightness': 0.2, 'contrast': 1.4, 'saturation': 1.3, 'gamma': 1.6,
                        'hue_degrees': 20, 'sharpness': 1.5},
        'effects': {'denoise_enabled': True, 'denoise_strength': 60,
                    'blur_enabled': True, 'blur_strength': 30,
                    'grain_enabled': True, 'grain_strength': 20},
    }
    graph = ','.join(video_edits.build_filter_chain(every_control, 64, 64))
    result = subprocess.run(
        [ffmpeg_path() or 'ffmpeg', '-y', '-v', 'error',
         '-f', 'lavfi', '-i', 'testsrc2=s=64x64:d=0.1:rate=1',
         '-vf', graph, '-frames:v', '1', '-f', 'null', '-'],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f'a cadeia não roda aqui: {result.stderr.strip()}'


@needs_ffmpeg
def test_brightness_is_additive_in_ffmpeg_too(tmp_path):
    """The single fact that ruled CSS filters out (research.md Decisão 1).
    Multiplicative brightness would leave black at black; additive lifts it."""
    lifted = _render_gray_through_eq(tmp_path, 0.0, brightness=0.25, contrast=1.0)
    assert lifted > 0.15, 'brilho não somou — a premissa da Decisão 1 mudou'


# ---------------------------- on-demand preview (T050) ---------------------------- #


@needs_ffmpeg
def test_render_frame_produces_an_image(tmp_path):
    source = FIXTURES / 'curto.mp4'
    if not source.exists():
        pytest.skip('fixtures ausentes — rode tests/fixtures/make_video_fixtures.py')
    output = tmp_path / 'frame.png'
    video_edits.render_frame(str(source), str(output), 2.0, {},
                             source_width=1920, source_height=1080)
    assert output.is_file() and output.stat().st_size > 0


@needs_ffmpeg
def test_render_frame_applies_the_edits(tmp_path):
    """The preview must differ from the source, or the tier is decorative."""
    import cv2

    source = FIXTURES / 'curto.mp4'
    if not source.exists():
        pytest.skip('fixtures ausentes')
    plain, edited = tmp_path / 'a.png', tmp_path / 'b.png'
    video_edits.render_frame(str(source), str(plain), 2.0, {}, source_width=1920, source_height=1080)
    video_edits.render_frame(str(source), str(edited), 2.0,
                             {'adjustments': {'brightness': 0.3}},
                             source_width=1920, source_height=1080)
    assert cv2.imread(str(plain)).mean() < cv2.imread(str(edited)).mean()


@needs_ffmpeg
def test_render_frame_downscales_after_the_edits_not_before(tmp_path):
    """Scaling first would soften a sharpen and hide a denoise — the person
    would be judging the effect at a size it is not being applied at."""
    source = FIXTURES / 'curto.mp4'
    if not source.exists():
        pytest.skip('fixtures ausentes')
    chain = video_edits.build_filter_chain({'effects': {'denoise_enabled': True, 'denoise_strength': 50}},
                                           1920, 1080)
    # The production chain has no scale; render_frame appends it last.
    assert not any(c.startswith('scale') for c in chain)


@needs_ffmpeg
def test_render_frame_leaves_the_source_untouched(tmp_path):
    source = FIXTURES / 'curto.mp4'
    if not source.exists():
        pytest.skip('fixtures ausentes')
    working = tmp_path / 'origem.mp4'
    working.write_bytes(source.read_bytes())
    before = working.read_bytes()
    video_edits.render_frame(str(working), str(tmp_path / 'f.png'), 1.0, {},
                             source_width=1920, source_height=1080)
    assert working.read_bytes() == before
