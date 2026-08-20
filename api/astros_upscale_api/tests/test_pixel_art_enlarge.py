"""Enlarging with no model: every source pixel repeated, nothing invented.

Every super-resolution model here is trained on photographs and drawings, where
softening an edge is correct. On a 32x32 icon it is not: measured against a
nearest enlargement of a real one, the models moved the shape by 2.4 to 6.5
mean luma levels and rounded corners the artist drew square.

So this path exists to invent nothing at all, and these tests say exactly that
— the output must be reconstructible from the input, not merely close to it.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.processing import Upscaler


def checkerboard(size: int = 8) -> np.ndarray:
    """Worst case for interpolation: every neighbouring pixel differs."""
    board = np.zeros((size, size, 3), np.uint8)
    board[::2, ::2] = 255
    board[1::2, 1::2] = 255
    return board


def enlarge(image, path, tmp_path, factor: int):
    source = tmp_path / 'in.png'
    cv2.imwrite(str(source), image)
    master = tmp_path / 'out.png'
    Upscaler.process_without_model(
        str(source), str(master), str(tmp_path),
        resize=(image.shape[1] * factor, image.shape[0] * factor),
    )
    return cv2.imread(str(master), cv2.IMREAD_UNCHANGED)


class TestItInventsNothing:
    def test_every_pixel_becomes_a_solid_block_of_itself(self, tmp_path):
        source = checkerboard()
        out = enlarge(source, None, tmp_path, 4)
        assert out.shape[:2] == (32, 32)
        for y in range(source.shape[0]):
            for x in range(source.shape[1]):
                block = out[y * 4:(y + 1) * 4, x * 4:(x + 1) * 4]
                assert len(np.unique(block.reshape(-1, block.shape[2]), axis=0)) == 1, (
                    f'bloco ({x},{y}) nao e uniforme — houve interpolacao'
                )

    def test_the_output_holds_no_colour_the_source_did_not_have(self, tmp_path):
        source = checkerboard()
        out = enlarge(source, None, tmp_path, 3)
        source_colours = {tuple(c) for c in np.unique(source.reshape(-1, 3), axis=0)}
        out_colours = {tuple(c) for c in np.unique(out[..., :3].reshape(-1, 3), axis=0)}
        assert out_colours <= source_colours, f'cores novas: {out_colours - source_colours}'

    def test_shrinking_still_averages_instead_of_dropping_pixels(self, tmp_path):
        """The opposite direction keeps INTER_AREA — a reduction that picked
        nearest neighbours would alias badly."""
        source = checkerboard(16)
        out = enlarge(source, None, tmp_path, 1)  # mesmo tamanho, sem resize
        assert out.shape[:2] == (16, 16)

        source_path = tmp_path / 'shrink_in.png'
        cv2.imwrite(str(source_path), source)
        master = tmp_path / 'shrink_out.png'
        Upscaler.process_without_model(
            str(source_path), str(master), str(tmp_path), resize=(4, 4)
        )
        reduced = cv2.imread(str(master), cv2.IMREAD_UNCHANGED)
        greys = np.unique(reduced[..., 0])
        assert not set(greys.tolist()) <= {0, 255}, 'a reducao nao mediou os pixels descartados'


class TestTransparency:
    def test_alpha_survives_the_enlargement(self, tmp_path):
        source = np.zeros((8, 8, 4), np.uint8)
        source[2:6, 2:6] = (255, 255, 255, 255)
        out = enlarge(source, None, tmp_path, 4)
        assert out.shape[2] == 4
        assert int((out[..., 3] == 0).sum()) == int((source[..., 3] == 0).sum()) * 16
