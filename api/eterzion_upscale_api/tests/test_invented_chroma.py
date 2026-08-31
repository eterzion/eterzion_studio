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

    def test_the_cap_follows_the_neighbourhood_not_the_single_pixel(self):
        """A colour is allowed to spread slightly past where it started — the
        model legitimately does that when it sharpens an edge. Comparing each
        pixel only against itself would claw that back and leave a halo, so the
        cap comes from a 3x3 neighbourhood."""
        source = np.zeros((1, 5, 3), np.uint8)
        source[0, :] = (128, 128, 128)
        source[0, 2] = (128, 128, 188)   # chroma 60, isolado no meio
        polluted = np.zeros((1, 5, 3), np.uint8)
        polluted[0, :] = (60, 140, 200)  # o modelo colore tudo
        out = guard(polluted, source)
        c = chroma(out)[0]
        assert c[0] == 0, 'longe da cor, nada e permitido'
        assert c[1] > 0, 'o vizinho imediato herda o teto'
        assert c[4] == 0, 'o outro extremo tambem fica limpo'

    def test_the_reported_case_an_icon_on_a_tinted_background(self):
        """The case an earlier version of this guard missed entirely.

        White shapes on a dark blue background: the background's own chroma is
        about 18, so a rule of "only correct pixels whose source was neutral"
        treated the whole picture as legitimately coloured and left the
        fringing where white meets blue untouched — chroma 78 in what should be
        a white edge. Measured on the real model, the local cap brings that to
        23, next to 18 for a plain nearest enlargement.
        """
        source = np.zeros((16, 16, 3), np.uint8)
        source[:, :] = (30, 20, 12)      # fundo azulado, croma 18
        source[4:12, 4:12] = (255, 255, 255)

        polluted = source.copy()
        polluted[5, 5] = (255, 120, 200)  # franja rosa dentro do branco
        out = guard(polluted, source)

        assert chroma(out)[5, 5] <= 23, 'a franja sobreviveu ao teto local'
        assert np.array_equal(out[0, 0], source[0, 0]), 'o fundo legitimo mudou'

class TestTransparency:
    """Icons ship as RGBA with no background at all — the material this whole
    guard was written for. An earlier version bailed out on any 4-channel
    image, so the correction never ran on exactly those files: measured on a
    transparent icon, the anime model reached chroma 204 across 63% of the
    visible pixels and nothing touched it."""

    @staticmethod
    def _icon_with_alpha():
        source = np.zeros((16, 16, 4), np.uint8)
        source[..., 3] = 0                       # tudo transparente
        source[4:12, 4:12] = (255, 255, 255, 255)  # um quadrado branco opaco
        return source

    def test_invented_colour_is_removed_from_the_visible_part(self):
        source = self._icon_with_alpha()
        polluted = source.copy()
        polluted[6, 6, :3] = (40, 200, 180)
        out = guard(polluted, source)
        visible = out[..., 3] > 128
        assert chroma(out[..., :3])[visible].max() == 0

    def test_the_alpha_channel_is_carried_through_untouched(self):
        source = self._icon_with_alpha()
        polluted = source.copy()
        polluted[6, 6, :3] = (40, 200, 180)
        out = guard(polluted, source)
        assert np.array_equal(out[..., 3], polluted[..., 3]), 'a transparencia foi alterada'

    def test_the_result_keeps_its_four_channels(self):
        source = self._icon_with_alpha()
        assert guard(source.copy(), source).shape[2] == 4

    def test_an_rgb_result_from_an_rgba_source_still_works(self):
        """cv2 can hand back three channels even when the source had four."""
        source = self._icon_with_alpha()
        rgb_result = np.full((16, 16, 3), 128, np.uint8)
        rgb_result[6, 6] = (40, 200, 180)
        out = guard(rgb_result, source)
        assert out.shape[2] == 3
        assert chroma(out).max() == 0


class TestFormatsItRefusesToTouch:
    def test_sixteen_bit_output_is_returned_unchanged(self):
        source = np.full((4, 4, 3), 128, np.uint8)
        deep = np.full((4, 4, 3), 30000, np.uint16)
        assert guard(deep, source) is deep

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
