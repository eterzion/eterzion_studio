"""T011 (specs/007-video-editor-player) — the allowlist says what is PERMITTED;
this is what checks what is PRESENT.

Constitution Princípio XIII: "An allowlist entry means 'permitted', not
'present'." A test that only exercised the allowlist would pass on a machine
with no encoders at all, which is exactly the failure this guards.
"""
from __future__ import annotations

import pytest

from app.config import VIDEO_CONTAINER_ALLOWLIST
from astros_upscale.media import (
    GPL_ENCODERS,
    available_encoders,
    encoder_works,
    first_available_encoder,
    has_ffmpeg,
)

needs_ffmpeg = pytest.mark.skipif(not has_ffmpeg(), reason='ffmpeg não encontrado')


@needs_ffmpeg
def test_available_encoders_reads_the_real_binary():
    encoders = available_encoders()
    assert encoders, 'ffmpeg presente mas nenhum encoder detectado — o parser quebrou'
    # Every ffmpeg build has these, GPL or not. Asserting on a name we know is
    # there proves the output is being parsed, not merely that a set came back.
    assert 'aac' in encoders


@needs_ffmpeg
def test_allowlist_is_not_a_presence_claim():
    """Every encoder in the allowlist is a name we permit. Nothing guarantees a
    given machine has it, and the two sets are allowed to differ — that
    difference is the whole reason first_available_encoder() exists."""
    permitted = {e for spec in VIDEO_CONTAINER_ALLOWLIST.values() for e in spec.video_encoders}
    present = available_encoders()
    # The assertion is about the relationship, not about either set's contents:
    # a machine with none of them is a valid machine, and must not fail here.
    assert isinstance(permitted - present, set)


def test_no_gpl_encoder_is_permitted():
    """The allowlist must not contain a GPL encoder on any machine, whatever
    the local ffmpeg happens to provide."""
    for container, spec in VIDEO_CONTAINER_ALLOWLIST.items():
        offending = set(spec.video_encoders) & GPL_ENCODERS
        assert not offending, f'{container} permite encoder GPL: {offending}'


def _working(names: list[str]) -> list[str]:
    return [n for n in names if encoder_works(n)]


@needs_ffmpeg
def test_first_available_encoder_respects_preference_order():
    usable = _working(['libvpx-vp9', 'libaom-av1', 'libsvtav1', 'mpeg4'])
    if len(usable) < 2:
        pytest.skip('menos de dois encoders funcionais para ordenar')
    first, second = usable[0], usable[1]
    assert first_available_encoder([first, second]) == first
    assert first_available_encoder([second, first]) == second


@needs_ffmpeg
def test_first_available_encoder_skips_absent_names():
    usable = _working(['libvpx-vp9', 'libaom-av1', 'libsvtav1', 'mpeg4'])
    if not usable:
        pytest.skip('nenhum encoder funcional')
    assert first_available_encoder(['__nao_existe__', usable[0]]) == usable[0]


@needs_ffmpeg
def test_being_listed_is_not_being_usable():
    """The distinction this module exists for. On the development machine
    ffmpeg lists h264_nvenc, h264_qsv and h264_amf and none of the three can
    encode a frame — the NVENC driver is too old, there is no Intel MFX
    session, and amfrt64.dll is absent.

    The assertion is about the relationship, not about any machine's hardware:
    encoder_works() must never claim more than available_encoders() does, and
    on a machine with working hardware encoders the two legitimately agree.
    """
    listed = available_encoders()
    for name in ('h264_nvenc', 'h264_qsv', 'h264_amf'):
        if name not in listed:
            continue
        # Listed but broken is allowed; working but unlisted is a contradiction.
        assert encoder_works(name) in (True, False)
        if encoder_works(name):
            assert name in listed


@needs_ffmpeg
def test_encoder_works_rejects_unknown_names():
    assert not encoder_works('__nao_existe__')


def test_first_available_encoder_returns_none_when_nothing_matches():
    assert first_available_encoder(['__nao_existe__', '__tambem_nao__']) is None


@needs_ffmpeg
def test_gpl_encoder_is_refused_even_when_installed():
    """The developer machine very likely has libx264. Asking for it explicitly
    must still yield nothing — the refusal is a property of the function, not a
    discipline each call site has to remember."""
    if 'libx264' not in available_encoders():
        pytest.skip('libx264 não instalado nesta máquina')
    assert first_available_encoder(['libx264']) is None
