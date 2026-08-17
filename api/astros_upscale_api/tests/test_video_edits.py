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
        chain.index([c for c in chain if c.startswith('eq')][0])


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


def test_eq_maps_adjustments_by_name():
    """The FFmpeg half of the parity the renderer's shader must reproduce
    (research.md Decisão 1). If this mapping changes, the shader changes with
    it or the preview starts lying."""
    edits = {'adjustments': {'brightness': 0.2, 'contrast': 1.3, 'saturation': 0.8, 'gamma': 1.1}}
    chain = video_edits.build_filter_chain(edits, 1920, 1080)
    assert chain == ['eq=brightness=0.2:contrast=1.3:saturation=0.8:gamma=1.1']


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
    assert len(chain) == 1 and chain[0].startswith('hqdn3d=')


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
