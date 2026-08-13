"""Single/full-song inference for SonicMaster — adapted from the upstream
repository's `infer_single.py` (github.com/AMAAI-Lab/SonicMaster, commit
c4c0869c14bada6c5cb7d3decbcdc00e6a3050f5 — see NOTICE.md), the only script in
that repository with a generic, non-hardcoded CLI.

Exposes `run_single_inference()` as a plain function (not just a CLI `main`)
so `worker_main.py` can call it directly over IPC, in addition to keeping the
original `python infer.py --ckpt ... --input ...` entry point for manual use.

Chunking/crossfade/carry-conditioning logic is unchanged from upstream — see
specs/006-audio-engine-masterizacao/research.md for what this reproduces and
why. One real fix versus upstream: the final output is now trimmed back to
the original input duration — upstream always padded the last chunk to a
full `chunk_duration` and never trimmed it back, so short/uneven-length
inputs came out longer than they went in.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from time import time

import torch
import torchaudio
import soundfile as sf
import yaml
from safetensors.torch import load_file
from diffusers import AutoencoderOobleck

from model import TangoFlux
from stitching import split_into_chunks, stitch_chunks_with_crossfade

hf_token = (
    os.getenv("HF_TOKEN")
    or os.getenv("HUGGINGFACE_TOKEN")
    or os.getenv("HUGGINGFACEHUB_API_TOKEN")
)

_DEFAULT_CONFIG = str(Path(__file__).parent / "configs" / "tangoflux_config.yaml")

_model_cache: dict[str, TangoFlux] = {}
_vae_cache: dict[str, AutoencoderOobleck] = {}


def _load_model(ckpt_path: Path, config_path: str, device: str) -> TangoFlux:
    """Cached by checkpoint path — FR-019 (lazy load, reused across calls
    within the same worker process, never reloaded per operation)."""
    key = str(ckpt_path)
    if key in _model_cache:
        return _model_cache[key]
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)
    model = TangoFlux(config=cfg["model"])
    weights = load_file(str(ckpt_path))
    model.load_state_dict(weights, strict=False)
    model.to(device).eval()
    for p in model.text_encoder.parameters():
        p.requires_grad = False
    model.text_encoder.eval()
    _model_cache[key] = model
    return model


def _load_vae(device: str) -> AutoencoderOobleck:
    if device in _vae_cache:
        return _vae_cache[device]
    vae = AutoencoderOobleck.from_pretrained(
        "stabilityai/stable-audio-open-1.0", subfolder="vae", use_auth_token=hf_token,
    ).to(device)
    vae.eval()
    _vae_cache[device] = vae
    return vae


def _resolve_ckpt(ckpt: str) -> Path:
    ckpt_path = Path(ckpt)
    if ckpt_path.is_dir():
        candidate = ckpt_path / "model.safetensors"
        if not candidate.exists():
            raise FileNotFoundError(f"Could not find model.safetensors in {ckpt_path}")
        return candidate
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")
    return ckpt_path


@torch.no_grad()
def run_single_inference(
    ckpt: str,
    input_path: str,
    prompt: str,
    output_path: str,
    config: str = _DEFAULT_CONFIG,
    fs: int = 44100,
    chunk_duration: int = 30,
    overlap_duration: int = 10,
    vae_batch_size: int = 10,
    num_inference_steps: int = 10,
    guidance_scale: float = 1.0,
    solver: str = "Euler",
    seed: int = 0,
) -> str:
    """Restores `input_path` with SonicMaster, guided by `prompt`, and writes
    the result to `output_path`. Handles both a short clip (single chunk, no
    crossfade needed) and a full song (multiple chunks, overlap + crossfade +
    carried latent conditioning) with the same code path — a clip shorter
    than `chunk_duration` naturally produces exactly one chunk (FR-016)."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True

    ckpt_path = _resolve_ckpt(ckpt)
    model = _load_model(ckpt_path, config, device)
    vae = _load_vae(device)

    in_path = Path(input_path)
    if not in_path.exists():
        raise FileNotFoundError(f"Input audio not found: {in_path}")

    audio, sr = torchaudio.load(str(in_path))  # [C, T]
    if audio.shape[0] == 1:
        audio = audio.repeat(2, 1)
    elif audio.shape[0] > 2:
        audio = audio[:2, :]
    if sr != fs:
        audio = torchaudio.functional.resample(audio, sr, fs)
        sr = fs
    original_length = audio.shape[1]  # FR-014/FR-016 — trimmed back to this at the end
    audio = audio.to(device)

    chunk_size = chunk_duration * fs
    overlap = overlap_duration * fs
    if overlap <= 0 or overlap >= chunk_size:
        raise ValueError("overlap_duration must be >0 and smaller than chunk_duration.")
    stride = chunk_size - overlap

    chunks = split_into_chunks(audio, chunk_size, stride)
    if not chunks:
        raise RuntimeError("No audio content to process.")

    chunk_tensor = torch.stack(chunks)  # [N, 2, T]
    latents = []
    for b in range(0, chunk_tensor.shape[0], vae_batch_size):
        batch = chunk_tensor[b:b + vae_batch_size].to(device)
        z = vae.encode(batch).latent_dist.mode()  # [B, C, T']
        latents.append(z)
    degraded_latents = torch.cat(latents, dim=0)  # [N, C, T']

    decoded_chunks = []
    prev_cond = None
    for i in range(degraded_latents.shape[0]):
        z_in = degraded_latents[i].unsqueeze(0).transpose(1, 2)  # [1, T', C]
        result_latent = model.inference_flow(
            z_in, prompt,
            audiocond_latents=prev_cond,  # None for the first chunk — carried conditioning after
            num_inference_steps=num_inference_steps,
            timesteps=None,
            guidance_scale=guidance_scale,
            duration=chunk_duration,
            seed=seed,
            disable_progress=True,
            num_samples_per_prompt=1,
            callback_on_step_end=None,
            solver=solver,
        )
        wav = vae.decode(result_latent.transpose(2, 1)).sample.cpu()  # [1, 2, T]
        wav = torch.clamp(wav, -1.0, 1.0)
        decoded_chunks.append(wav)
        last = wav[:, :, -overlap:].to(device)
        prev_cond = vae.encode(last).latent_dist.mode().transpose(1, 2)  # [1, T', C]

    final = stitch_chunks_with_crossfade(decoded_chunks, overlap)
    final = final[:, :, :original_length]  # trim padding — fix vs. upstream, see module docstring

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = final.squeeze(0).numpy().T  # [T, 2]
    fmt = 'FLAC' if out_path.suffix.lower() == '.flac' else 'WAV'
    sf.write(out_path.as_posix(), data, fs, format=fmt)
    return str(out_path)


def _parse_args():
    p = argparse.ArgumentParser("Single-sample inference for SonicMaster")
    p.add_argument("--ckpt", type=str, required=True)
    p.add_argument("--input", type=str, required=True)
    p.add_argument("--prompt", type=str, required=True)
    p.add_argument("--output", type=str, required=True)
    p.add_argument("--config", type=str, default=_DEFAULT_CONFIG)
    p.add_argument("--fs", type=int, default=44100)
    p.add_argument("--chunk_duration", type=int, default=30)
    p.add_argument("--overlap_duration", type=int, default=10)
    p.add_argument("--vae_batch_size", type=int, default=10)
    p.add_argument("--num_inference_steps", type=int, default=10)
    p.add_argument("--guidance_scale", type=float, default=1.0)
    p.add_argument("--solver", type=str, default="Euler")
    p.add_argument("--seed", type=int, default=0)
    return p.parse_args()


def main() -> None:
    t0 = time()
    args = _parse_args()
    out = run_single_inference(
        ckpt=args.ckpt, input_path=args.input, prompt=args.prompt, output_path=args.output,
        config=args.config, fs=args.fs, chunk_duration=args.chunk_duration,
        overlap_duration=args.overlap_duration, vae_batch_size=args.vae_batch_size,
        num_inference_steps=args.num_inference_steps, guidance_scale=args.guidance_scale,
        solver=args.solver, seed=args.seed,
    )
    print(f"Saved: {out}")
    print(f"Elapsed: {time() - t0:.2f}s")


if __name__ == "__main__":
    main()
