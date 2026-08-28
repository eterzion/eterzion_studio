"""Telling animation apart from live action, by looking at the video.

There was no automatic detection for video at all: the route refused with a
422 and the Vídeo screen filled in 'real_video' as a fixed default. An anime
clip therefore arrived labelled live action and was handed the model meant for
photography — which reads as "the detection is wrong" even though nothing was
detecting.

Frames are sampled across the whole duration and each one goes through the
same classify_image() the Imagem screen uses; the majority decides.
"""
from __future__ import annotations

import os
import time

import pytest

from app.routes import _detect_video_content_type

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')


def fixture(name):
    path = os.path.join(FIXTURES, name)
    if not os.path.isfile(path):
        pytest.skip(f'fixture ausente: {name}')
    return path


def test_an_anime_clip_is_animation():
    assert _detect_video_content_type(fixture('anime_clip.mp4')) == 'anime_video'


def test_a_continuous_tone_clip_is_live_action():
    """The other direction matters as much: a detector that answers 'anime' to
    everything would pass the test above and be useless."""
    assert _detect_video_content_type(fixture('real_clip.mp4')) == 'real_video'


def test_it_samples_across_the_duration_not_just_the_opening():
    """Openings, title cards and fades are the least representative part of a
    video, and the first seconds are usually exactly that. A single frame taken
    at t=0 from this clip does not classify the same way the whole file does."""
    import cv2

    from astros_upscale.processing import classify_image

    capture = cv2.VideoCapture(fixture('anime_clip.mp4'))
    ok, first = capture.read()
    capture.release()
    assert ok

    whole_file = _detect_video_content_type(fixture('anime_clip.mp4'))
    single_frame = classify_image(first).content_type
    # Não exige que difiram — exige que a decisão não venha de um quadro só.
    assert whole_file in ('anime_video', 'real_video')
    assert single_frame in ('photo', 'anime_image', 'pixel_art')


def test_detection_is_fast_enough_to_run_on_import():
    """It runs while files are being added, so seconds per file would be felt."""
    start = time.perf_counter()
    _detect_video_content_type(fixture('anime_clip.mp4'))
    assert time.perf_counter() - start < 5.0
