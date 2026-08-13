"""Model-free chunk splitting/crossfade-stitching for full-song inference —
factored out of `infer.py` so it depends only on `torch` (already a main-venv
dependency for image/video), never `diffusers`/`transformers`/`safetensors`
(audio-worker-only). This is what makes FR-015/FR-016/SC-002 (full-song
continuity, no artificial splitting of short clips) testable without the
isolated audio-worker environment — see
specs/006-audio-engine-masterizacao/tests/test_vendor_sonicmaster_infer.py.
"""
from __future__ import annotations

import torch


def split_into_chunks(audio: torch.Tensor, chunk_size: int, stride: int) -> list[torch.Tensor]:
    """Splits `audio` ([2, T]) into overlapping, zero-padded `chunk_size`-long
    windows advancing by `stride`. Audio shorter than `chunk_size` naturally
    produces exactly one, padded chunk (FR-016) — no special-casing needed
    by the caller."""
    chunks = []
    start = 0
    total = audio.shape[1]
    while start < total:
        end = min(start + chunk_size, total)
        chunk = audio[:, start:end]
        if chunk.shape[1] < chunk_size:
            chunk = torch.nn.functional.pad(chunk, (0, chunk_size - chunk.shape[1]))
        chunks.append(chunk)
        start += stride
    return chunks


def stitch_chunks_with_crossfade(chunks: list[torch.Tensor], overlap: int) -> torch.Tensor:
    """Reconstructs a full waveform from decoded, per-chunk model output via
    linear crossfade over `overlap` samples (FR-015 — no clicks/volume jumps
    at chunk boundaries). `chunks` are `[1, 2, T]` tensors; a single-element
    list (audio shorter than one chunk) returns unchanged, no crossfade math
    applied at all."""
    final = chunks[0]
    for i in range(1, len(chunks)):
        prev = final[:, :, -overlap:]
        curr = chunks[i][:, :, :overlap]
        alpha = torch.linspace(1.0, 0.0, steps=overlap).view(1, 1, -1)
        beta = 1.0 - alpha
        blended = prev * alpha + curr * beta
        final = torch.cat(
            [final[:, :, :-overlap], blended, chunks[i][:, :, overlap:]], dim=2,
        )
    return final
