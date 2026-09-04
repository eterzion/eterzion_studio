"""Sharpening emphasises edges without inventing colour.

An unsharp mask applied to each colour channel separately moves them by
different amounts at an edge, and the difference between channels IS colour.
Measured on a real 32x32 black-and-white icon: chroma came back from 8 to 22 at
strength 100, undoing what the chroma guard had just removed — the two filters
were fighting each other in the same pipeline.

Sharpening only the luminance is the standard answer and costs nothing: the
impression of sharpness lives in the luminance edge, and the colour planes ride
through untouched.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.processing import Upscaler

sharpen = Upscaler._sharpen


def chroma(image):
    rgb = image[:, :, :3].astype(int)
    return rgb.max(axis=2) - rgb.min(axis=2)


def gradient(image):
    grey = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY).astype(np.float32)
    return float(np.abs(cv2.Laplacian(grey, cv2.CV_32F)).mean())


def grey_edge(tint: int = 5):
    """A near-black-and-white edge, softened — the shape of an upscaled icon.

    `tint` matters and a perfectly neutral image would hide the bug: with
    R==G==B everywhere, a per-channel unsharp mask moves all three identically
    and invents nothing. Real material is never that clean — the icon this came
    from carries a maximum chroma of 5 — and it is that small difference the
    filter multiplies into a visible fringe.
    """
    image = np.zeros((64, 64, 3), np.uint8)
    image[:, 32:] = (255, 255, 255 - tint)
    image[:, :32] = (0, 0, min(tint, 255))
    return cv2.GaussianBlur(image, (0, 0), 2)


class TestItDoesNotInventColour:
    def test_a_faint_tint_is_not_multiplied_into_a_fringe(self):
        edge = grey_edge()
        before = chroma(edge).max()
        after = chroma(sharpen(edge, 100)).max()
        assert after <= before + 2, f'croma subiu de {before} para {after}'

    def test_a_perfectly_neutral_edge_stays_neutral(self):
        assert chroma(sharpen(grey_edge(tint=0), 100)).max() == 0

    def test_that_holds_at_every_strength(self):
        edge = grey_edge()
        limit = chroma(edge).max() + 2
        for strength in (25, 50, 75, 100):
            assert chroma(sharpen(edge, strength)).max() <= limit, f'forca {strength}'

    def test_it_does_not_undo_the_chroma_guard(self):
        """The two ran in the same pipeline, and this is the interaction that
        made the fix invisible: the guard cleaned the colour and the sharpener
        put it back. Measured on the real icon, chroma went 8 -> 22 at
        strength 100."""
        edge = grey_edge()
        guarded = Upscaler._suppress_invented_chroma(edge, edge)
        limit = chroma(guarded).max() + 2
        assert chroma(sharpen(guarded, 100)).max() <= limit


class TestItStillSharpens:
    def test_edges_get_stronger(self):
        edge = grey_edge()
        assert gradient(sharpen(edge, 100)) > gradient(edge)

    def test_more_strength_means_more_effect(self):
        edge = grey_edge()
        assert gradient(sharpen(edge, 100)) > gradient(sharpen(edge, 50)) > gradient(edge)

    def test_zero_is_a_no_op(self):
        edge = grey_edge()
        assert np.array_equal(sharpen(edge, 0), edge)


class TestItLeavesRealColourAlone:
    def test_a_colourful_picture_keeps_its_colours(self):
        photo = np.zeros((64, 64, 3), np.uint8)
        photo[:, :32] = (40, 60, 220)
        photo[:, 32:] = (60, 190, 70)
        photo = cv2.GaussianBlur(photo, (0, 0), 2)
        before = chroma(photo).mean()
        after = chroma(sharpen(photo, 100)).mean()
        assert abs(after - before) < 1.0, f'croma mudou de {before:.1f} para {after:.1f}'


class TestTransparency:
    def test_alpha_is_carried_through_untouched(self):
        image = np.zeros((32, 32, 4), np.uint8)
        image[:, 16:, :3] = 255
        image[..., 3] = np.linspace(0, 255, 32, dtype=np.uint8)
        out = sharpen(image.copy(), 100)
        assert out.shape[2] == 4
        assert np.array_equal(out[..., 3], image[..., 3])

    def test_the_visible_part_of_a_transparent_icon_gains_no_colour(self):
        image = np.zeros((32, 32, 4), np.uint8)
        image[8:24, 8:24, :3] = (255, 255, 250)   # o tinte leve do material real
        image[8:24, 8:24, 3] = 255
        blurred = cv2.GaussianBlur(image, (0, 0), 1.5)
        before = chroma(blurred)[blurred[..., 3] > 128].max()
        out = sharpen(blurred, 100)
        visible = out[..., 3] > 128
        assert chroma(out)[visible].max() <= before + 2
