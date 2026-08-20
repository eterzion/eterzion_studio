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
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.processing import Upscaler
from app.routes import jobs_router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(jobs_router, prefix='/jobs')
    return TestClient(app)


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


class TestScaleWithoutACustomSize:
    """A 2x/4x request with no explicit target must still enlarge.

    This shipped broken and no unit test saw it: the job completed, reported
    done, and handed back the source at its own resolution. Original mode
    always sends an explicit size, so this branch had never had to read
    `scale` — and pixel_art arrives with '4x' and no custom size whenever the
    person picks the Ampliar tab. Completing successfully while doing nothing
    is the worst shape a failure can take.

    Driven through the real route, because the missing step was in jobs.py and
    a unit test of the resize would have passed either way.
    """

    @staticmethod
    def _run(client, tmp_path, scale):
        import asyncio

        from app import jobs as job_manager

        art = np.zeros((8, 8, 3), np.uint8)
        art[2:6, 2:6] = 255
        source = tmp_path / 'icone.png'
        cv2.imwrite(str(source), art)

        job_id = client.post('/jobs/local', json={'media_request': {
            'media_type': 'image', 'operation': 'enhance', 'scale': scale,
            'profile': 'quality', 'content_type_override': 'pixel_art',
            'input_path': str(source),
        }}).json()['id']
        job_manager.jobs[job_id]['status'] = 'queued'
        asyncio.run(job_manager._process_job(job_id))
        return job_manager.get_job(job_id)

    def test_four_x_actually_quadruples(self, client, tmp_path):
        job = self._run(client, tmp_path, '4x')
        assert job['status'] == 'done', job.get('error')
        assert job['output_meta']['width'] == 32, 'saiu do mesmo tamanho da origem'

    def test_two_x_actually_doubles(self, client, tmp_path):
        job = self._run(client, tmp_path, '2x')
        assert job['status'] == 'done', job.get('error')
        assert job['output_meta']['width'] == 16
