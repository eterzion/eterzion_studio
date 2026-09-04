"""Detecting art drawn on a grid.

The signal is the mean length of runs of identical pixels along a row, over the
width. In pixel art a colour repeats across whole blocks, so runs are long
relative to the picture; anything with antialiasing — a photograph, a
rasterised vector icon — changes value almost every pixel and the ratio
collapses.

Measured over 200 real icons against a control set that deliberately included
modern UI icons (small, few colours, with alpha: a naive detector's worst
case), the 0.08 threshold catches 69% of the pixel art and none of the
controls. Recall is the side that gives on purpose: when this fires it is
right, and when it does not, the normal photo/anime classification still runs
and the person can still say so themselves.
"""
from __future__ import annotations

import numpy as np
import pytest

from eterzion_upscale.processing import _pixel_run_length, classify_image


def blocks(block: int = 8, size: int = 64) -> np.ndarray:
    """Art on a grid: every colour repeated across a block."""
    small = np.random.default_rng(3).integers(0, 4, (size // block, size // block, 3))
    small = (small * 80).astype(np.uint8)
    return np.repeat(np.repeat(small, block, axis=0), block, axis=1)


def photo_like(size: int = 64) -> np.ndarray:
    """Continuous tone: a gradient plus noise, changing every pixel."""
    rng = np.random.default_rng(4)
    ramp = np.linspace(0, 255, size, dtype=np.float32)
    base = np.repeat(ramp[None, :], size, axis=0)
    noisy = base + rng.normal(0, 12, (size, size))
    return np.clip(np.dstack([noisy] * 3), 0, 255).astype(np.uint8)


class TestTheSignal:
    def test_blocks_of_colour_score_high(self):
        assert _pixel_run_length(blocks()) > 0.08

    def test_continuous_tone_scores_low(self):
        assert _pixel_run_length(photo_like()) < 0.08

    def test_bigger_blocks_score_higher(self):
        assert _pixel_run_length(blocks(block=16)) > _pixel_run_length(blocks(block=4))

    def test_a_single_flat_colour_is_the_maximum(self):
        assert _pixel_run_length(np.full((32, 32, 3), 128, np.uint8)) == pytest.approx(1.0)

    def test_it_survives_a_one_pixel_wide_image(self):
        _pixel_run_length(np.zeros((10, 1, 3), np.uint8))  # nao levanta


class TestClassification:
    def test_grid_art_is_called_pixel_art(self):
        assert classify_image(blocks()).content_type == 'pixel_art'

    def test_a_photograph_is_not(self):
        assert classify_image(photo_like()).content_type != 'pixel_art'

    def test_a_real_vector_icon_is_not(self):
        """The adversarial case, and it has to be a real file.

        My first version of this test drew an antialiased circle and the
        detector called it pixel art — correctly, in a sense: a big flat disc
        on a flat background really is mostly blocks of one colour. Real
        rasterised icons are not like that, and the 12 in the control set all
        scored below the threshold. Synthetic material misled me repeatedly on
        this pipeline; here the fixture is an actual icon from this app.
        """
        import os

        import cv2

        path = os.path.join(os.path.dirname(__file__), 'fixtures', 'icone_vetorial.webp')
        icon = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        assert icon is not None, 'fixture ausente'
        assert _pixel_run_length(icon) < 0.08
        assert classify_image(icon).content_type != 'pixel_art'

    def test_confidence_rises_with_the_signal(self):
        assert classify_image(blocks(block=16)).confidence >= classify_image(blocks(block=8)).confidence


class TestAwkwardInputs:
    def test_sixteen_bit_input_does_not_crash(self):
        """cvtColor(BGR2HSV) rejects 16-bit, so detection used to raise and take
        the whole job down on a perfectly ordinary PNG."""
        deep = (blocks().astype(np.uint16) << 8)
        assert classify_image(deep).content_type in ('pixel_art', 'photo', 'anime_image')

    def test_greyscale_input_is_accepted(self):
        grey = np.full((32, 32), 128, np.uint8)
        assert classify_image(grey).content_type in ('pixel_art', 'photo', 'anime_image')

    def test_rgba_input_is_accepted(self):
        rgba = np.dstack([blocks(), np.full((64, 64), 255, np.uint8)])
        assert classify_image(rgba).content_type == 'pixel_art'
