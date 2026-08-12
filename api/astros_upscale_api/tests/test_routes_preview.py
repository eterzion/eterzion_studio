"""HTTP-layer tests for routes_preview.py — POST /preview/denoise. Exercises
the real cv2.fastNlMeansDenoisingColored path (no mocking of the algorithm
itself) against real generated test images, the same way the manual
verification during development measured it."""
from __future__ import annotations

import base64

import cv2
import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_preview


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes_preview.router, prefix='/preview')
    return TestClient(app)


@pytest.fixture
def noisy_image_path(tmp_path):
    rng = np.random.default_rng(0)
    base = np.full((120, 120, 3), 180, dtype=np.float64)
    noise = rng.normal(0, 25, base.shape)
    noisy = np.clip(base + noise, 0, 255).astype(np.uint8)
    path = tmp_path / 'noisy.png'
    cv2.imwrite(str(path), noisy)
    return str(path)


def _decode(b64_png: str):
    data = base64.b64decode(b64_png)
    return cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)


class TestPreviewDenoise:
    def test_returns_404_for_missing_file(self, client, tmp_path):
        res = client.post('/preview/denoise', json={
            'input_path': str(tmp_path / 'nope.png'), 'strength': 50,
        })
        assert res.status_code == 404

    def test_rejects_strength_out_of_range(self, client, noisy_image_path):
        res = client.post('/preview/denoise', json={'input_path': noisy_image_path, 'strength': 150})
        assert res.status_code == 422

    def test_rejects_negative_strength(self, client, noisy_image_path):
        res = client.post('/preview/denoise', json={'input_path': noisy_image_path, 'strength': -1})
        assert res.status_code == 422

    def test_returns_decodable_before_and_after_images(self, client, noisy_image_path):
        res = client.post('/preview/denoise', json={'input_path': noisy_image_path, 'strength': 60})
        assert res.status_code == 200
        body = res.json()
        before = _decode(body['before'])
        after = _decode(body['after'])
        assert before is not None
        assert after is not None
        assert before.shape == after.shape
        assert body['width'] == before.shape[1]
        assert body['height'] == before.shape[0]

    def test_strength_zero_is_a_no_op(self, client, noisy_image_path):
        res = client.post('/preview/denoise', json={'input_path': noisy_image_path, 'strength': 0})
        body = res.json()
        before = _decode(body['before'])
        after = _decode(body['after'])
        assert np.array_equal(before, after)

    def test_higher_strength_measurably_reduces_noise(self, client, noisy_image_path):
        """Same real assertion used during manual verification: standard
        deviation in the (uniformly noisy, no edges) test image must drop."""
        res = client.post('/preview/denoise', json={'input_path': noisy_image_path, 'strength': 80})
        body = res.json()
        before = _decode(body['before'])
        after = _decode(body['after'])
        assert after.std() < before.std() * 0.5

    def test_large_image_is_downscaled_to_the_preview_cap(self, client, tmp_path):
        big = np.full((900, 1200, 3), 128, dtype=np.uint8)
        path = tmp_path / 'big.png'
        cv2.imwrite(str(path), big)

        res = client.post('/preview/denoise', json={'input_path': str(path), 'strength': 30})
        body = res.json()
        assert max(body['width'], body['height']) == routes_preview._PREVIEW_MAX_DIM

    def test_small_image_is_not_upscaled(self, client, noisy_image_path):
        res = client.post('/preview/denoise', json={'input_path': noisy_image_path, 'strength': 30})
        body = res.json()
        assert body['width'] == 120
        assert body['height'] == 120

    def test_rejects_malformed_body(self, client):
        res = client.post('/preview/denoise', json={'strength': 50})  # missing input_path
        assert res.status_code == 422
