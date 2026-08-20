"""Colour the model invented in pixels that had none is taken back out.

Why this exists, measured rather than assumed: 2xHFA2kSPAN (the
anime/illustration model) turned 73% of the originally-neutral pixels of a
32x32 UI icon coloured, chroma up to 171 — pink and green blotches in white
areas of flat art. The same model leaves a smooth grey ramp nearly alone
(1.45%), so it is not general colour drift: it invents chroma at hard edges,
which is exactly what icons and line art consist of. The photo model does not
do this (2.19% worst case, chroma <= 26).

These tests drive the pure function directly with synthetic images. The model
itself is not involved: what needs pinning is the promise — invention out, real
colour untouched — not any particular model's behaviour, which can change when
a model is swapped.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.processing import Upscaler

guard = Upscaler._suppress_invented_chroma


def chroma(image):
    return image.max(axis=2).astype(int) - image.min(axis=2).astype(int)


class TestInventionIsRemoved:
    def test_colour_in_a_pixel_that_was_grey_is_taken_out(self):
        source = np.full((8, 8, 3), 128, np.uint8)
        polluted = source.copy()
        polluted[4, 4] = (40, 200, 180)  # a blotch the model invented
        assert chroma(guard(polluted, source)).max() == 0

    def test_the_luminance_the_model_produced_is_kept(self):
        """The upscaling work is in the luminance — only chroma is pulled."""
        source = np.full((8, 8, 3), 100, np.uint8)
        brightened = np.full((8, 8, 3), 180, np.uint8)
        out = guard(brightened, source)
        assert out.mean() == 180, 'a luminancia do modelo foi alterada'

    def test_a_blotch_on_white_becomes_white_again(self):
        source = np.full((16, 16, 3), 255, np.uint8)
        polluted = source.copy()
        polluted[8, 8] = (255, 180, 240)
        out = guard(polluted, source)
        assert chroma(out).max() == 0

    def test_it_works_when_the_output_is_larger_than_the_source(self):
        """The real case: the output has been upscaled, so the source has to be
        mapped onto it before anything can be compared."""
        source = np.full((4, 4, 3), 128, np.uint8)
        upscaled = np.full((16, 16, 3), 128, np.uint8)
        upscaled[10, 10] = (30, 210, 90)
        assert chroma(guard(upscaled, source)).max() == 0


class TestRealColourIsUntouched:
    def test_a_saturated_pixel_keeps_every_bit_of_its_colour(self):
        source = np.zeros((8, 8, 3), np.uint8)
        source[:, :] = (40, 60, 220)
        out = guard(source.copy(), source)
        assert np.array_equal(out, source), 'cor legitima foi alterada'

    def test_colour_next_to_neutral_survives(self):
        """Half the image coloured, half grey: the correction must land on one
        side only."""
        source = np.zeros((8, 8, 3), np.uint8)
        source[:, :4] = (200, 50, 50)
        source[:, 4:] = (128, 128, 128)
        out = guard(source.copy(), source)
        assert np.array_equal(out[:, :4], source[:, :4]), 'o lado colorido mudou'
        assert chroma(out[:, 4:]).max() == 0

    def test_a_faintly_tinted_source_is_not_forced_to_grey(self):
        """Above the hard threshold the source had real, if subtle, colour."""
        source = np.zeros((8, 8, 3), np.uint8)
        source[:, :] = (100, 100, 130)  # chroma 30, comfortably above `hard`
        out = guard(source.copy(), source)
        assert chroma(out).max() == 30

    def test_the_correction_fades_instead_of_drawing_a_new_edge(self):
        """A hard on/off boundary would replace one artefact with another, so
        sources between the thresholds are corrected partially."""
        source = np.zeros((1, 3, 3), np.uint8)
        source[0, 0] = (128, 128, 128)  # chroma 0  -> fully corrected
        source[0, 1] = (128, 128, 138)  # chroma 10 -> partially
        source[0, 2] = (128, 128, 158)  # chroma 30 -> untouched
        polluted = np.full((1, 3, 3), 0, np.uint8)
        polluted[0, :] = (60, 140, 200)
        out = guard(polluted, source)
        c = chroma(out)[0]
        assert c[0] == 0
        assert 0 < c[1] < c[2], f'sem transicao suave: {c}'


class TestFormatsItRefusesToTouch:
    def test_sixteen_bit_output_is_returned_unchanged(self):
        source = np.full((4, 4, 3), 128, np.uint8)
        deep = np.full((4, 4, 3), 30000, np.uint16)
        assert guard(deep, source) is deep

    def test_four_channel_output_is_returned_unchanged(self):
        source = np.full((4, 4, 3), 128, np.uint8)
        rgba = np.full((4, 4, 4), 128, np.uint8)
        assert guard(rgba, source) is rgba

    def test_a_greyscale_source_is_not_used_as_a_reference(self):
        grey_source = np.full((4, 4), 128, np.uint8)
        out = np.full((4, 4, 3), 128, np.uint8)
        assert guard(out, grey_source) is out


class TestThePipelineActuallyAppliesIt:
    """The tests above pin the function's promise; this one pins that process()
    still calls it. Without this, deleting the one line from the pipeline leaves
    every test above passing — verified by doing exactly that."""

    def test_process_strips_colour_the_model_invented(self, tmp_path, monkeypatch):
        source = np.full((8, 8, 3), 128, np.uint8)
        source_path = tmp_path / 'cinza.png'
        cv2.imwrite(str(source_path), source)

        class FakeModel:
            tile_size = 0
            tile_progress_callback = None

            def enhance(self, img, outscale):
                out = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
                out[4:12, 4:12] = (40, 200, 180)  # a invencao do modelo
                return out, None

        upscaler = object.__new__(Upscaler)
        upscaler._model = FakeModel()
        upscaler._model_dir = str(tmp_path)
        upscaler._tile_threshold = 10_000
        upscaler._tile_size = 0

        master = tmp_path / 'master.png'
        upscaler.process(str(source_path), scale=2, custom_size=None, master_path=str(master))

        written = cv2.imread(str(master), cv2.IMREAD_COLOR)
        assert chroma(written).max() == 0, 'a cor inventada chegou ao arquivo final'
