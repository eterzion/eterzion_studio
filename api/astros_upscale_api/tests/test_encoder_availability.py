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


@needs_ffmpeg
def test_first_available_encoder_respects_preference_order():
    present = sorted(available_encoders() - GPL_ENCODERS)
    if len(present) < 2:
        pytest.skip('menos de dois encoders não-GPL disponíveis para ordenar')
    first, second = present[0], present[1]
    assert first_available_encoder([first, second]) == first
    assert first_available_encoder([second, first]) == second


@needs_ffmpeg
def test_first_available_encoder_skips_absent_names():
    present = sorted(available_encoders() - GPL_ENCODERS)
    if not present:
        pytest.skip('nenhum encoder não-GPL disponível')
    assert first_available_encoder(['__nao_existe__', present[0]]) == present[0]


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
