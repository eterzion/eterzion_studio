"""Tests for the pure, model-free parts of vendor/sonicmaster/infer.py —
split_into_chunks/stitch_chunks_with_crossfade. These only need torch (already
a main-venv dependency for image/video), never the TangoFlux model or the
Stable Audio Open VAE, so they're testable here without the isolated
audio-worker environment (specs/006-audio-engine-masterizacao FR-015/FR-016,
SC-002 — objective continuity, not subjective).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

torch = pytest.importorskip('torch')

_VENDOR_DIR = Path(__file__).resolve().parent.parent / 'vendor' / 'sonicmaster'
sys.path.insert(0, str(_VENDOR_DIR))

from stitching import split_into_chunks, stitch_chunks_with_crossfade  # noqa: E402


class TestSplitIntoChunks:
    def test_audio_shorter_than_one_chunk_produces_exactly_one_padded_chunk(self):
        """FR-016 — no artificial splitting for short clips."""
        audio = torch.randn(2, 5_000)  # far shorter than any real chunk_size
        chunks = split_into_chunks(audio, chunk_size=44100 * 30, stride=44100 * 20)
        assert len(chunks) == 1
        assert chunks[0].shape == (2, 44100 * 30)

    def test_audio_longer_than_one_chunk_produces_multiple_overlapping_chunks(self):
        chunk_size, stride = 1000, 600
        audio = torch.randn(2, 2500)
        chunks = split_into_chunks(audio, chunk_size=chunk_size, stride=stride)
        # starts at 0, 600, 1200, 1800, 2400 (last one padded) -> 5 chunks
        assert len(chunks) == 5
        for chunk in chunks:
            assert chunk.shape == (2, chunk_size)

    def test_consecutive_chunks_share_the_expected_overlap_content(self):
        chunk_size, stride = 1000, 600
        overlap = chunk_size - stride
        audio = torch.arange(2500, dtype=torch.float32).unsqueeze(0).repeat(2, 1)
        chunks = split_into_chunks(audio, chunk_size=chunk_size, stride=stride)
        # The tail of chunk 0 and the head of chunk 1 both come from the same
        # source samples (the overlap region) — must match exactly pre-crossfade.
        assert torch.equal(chunks[0][:, -overlap:], chunks[1][:, :overlap])


class TestStitchChunksWithCrossfade:
    def test_single_chunk_is_returned_unchanged(self):
        chunk = torch.randn(1, 2, 1000)
        result = stitch_chunks_with_crossfade([chunk], overlap=200)
        assert torch.equal(result, chunk)

    def test_output_length_matches_stride_accumulation(self):
        overlap = 200
        chunk_a = torch.ones(1, 2, 1000)
        chunk_b = torch.ones(1, 2, 1000) * 2
        result = stitch_chunks_with_crossfade([chunk_a, chunk_b], overlap=overlap)
        expected_length = 1000 + (1000 - overlap)
        assert result.shape == (1, 2, expected_length)

    def test_no_discontinuity_at_the_crossfade_boundary(self):
        """SC-002 — objective measure: the sample-to-sample step size at and
        around the crossfade region must stay within the same order of
        magnitude as steps elsewhere in constant-level input, not spike."""
        overlap = 500
        chunk_a = torch.full((1, 2, 2000), 0.3)
        chunk_b = torch.full((1, 2, 2000), 0.3)  # same level -> a perfect stitch is flat
        result = stitch_chunks_with_crossfade([chunk_a, chunk_b], overlap=overlap)
        diffs = (result[:, :, 1:] - result[:, :, :-1]).abs()
        assert float(diffs.max()) < 1e-5  # no audible click: level is constant throughout

    def test_crossfade_blends_toward_the_next_chunks_level(self):
        overlap = 100
        chunk_a = torch.full((1, 2, 1000), 1.0)
        chunk_b = torch.full((1, 2, 1000), 0.0)
        result = stitch_chunks_with_crossfade([chunk_a, chunk_b], overlap=overlap)
        overlap_region = result[0, 0, 900:1000]  # single channel of the blended overlap window
        # Monotonically decreasing from ~1.0 toward ~0.0, not an abrupt jump.
        assert float(overlap_region[0]) > float(overlap_region[-1])
        assert float(overlap_region[0]) == pytest.approx(1.0, abs=0.05)
        assert float(overlap_region[-1]) == pytest.approx(0.0, abs=0.05)

    def test_three_chunks_stitch_without_discontinuity(self):
        overlap = 300
        chunks = [torch.full((1, 2, 1500), level) for level in (0.2, 0.2, 0.2)]
        result = stitch_chunks_with_crossfade(chunks, overlap=overlap)
        diffs = (result[:, :, 1:] - result[:, :, :-1]).abs()
        assert float(diffs.max()) < 1e-5
