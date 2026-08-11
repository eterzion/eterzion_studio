"""Real hardware capability detection — CPU, RAM, GPU/VRAM, and the encoders/decoders
FFmpeg actually has available on this machine. Nothing here is a fixed constant standing
in for detection: every field is either measured, or explicitly None when it can't be
measured on this hardware (see HardwareCapability.gpu_vendor for the honest-unknown case).

Only NVIDIA VRAM is queryable today, via pynvml (research.md R4) — there is no mature,
widely-adopted equivalent for AMD/Intel in the Python ecosystem. That's a real limitation,
not an oversight: callers must treat vram_total_mb/vram_available_mb as None-able and
degrade gracefully (see profile_resolver.py), not assume every GPU reports VRAM.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field

import psutil
import torch


@dataclass
class HardwareCapability:
    cpu_cores: int
    ram_total_mb: int
    ram_available_mb: int
    gpu_present: bool
    gpu_vendor: str  # 'nvidia' | 'unknown'
    vram_total_mb: int | None
    vram_available_mb: int | None
    ffmpeg_encoders: list[str] = field(default_factory=list)
    ffmpeg_decoders: list[str] = field(default_factory=list)


def _detect_nvidia_vram() -> tuple[int | None, int | None]:
    """Returns (total_mb, available_mb) for the first NVIDIA GPU, or (None, None) if
    pynvml is unavailable or no NVIDIA device is present. Falls back to torch.cuda's
    total-memory figure (no "available" breakdown) when pynvml itself can't be used —
    still better than nothing, since torch is already a hard dependency."""
    try:
        import pynvml

        pynvml.nvmlInit()
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            return int(info.total / (1024 * 1024)), int(info.free / (1024 * 1024))
        finally:
            pynvml.nvmlShutdown()
    except Exception:
        if torch.cuda.is_available():
            total = torch.cuda.get_device_properties(0).total_memory
            return int(total / (1024 * 1024)), None
        return None, None


def _detect_gpu() -> tuple[bool, str, int | None, int | None]:
    if not torch.cuda.is_available():
        return False, 'unknown', None, None
    total_mb, available_mb = _detect_nvidia_vram()
    vendor = 'nvidia' if total_mb is not None else 'unknown'
    return True, vendor, total_mb, available_mb


def _list_ffmpeg_codecs(flag: str) -> list[str]:
    """Parses `ffmpeg -encoders`/`-decoders` output. Returns an empty list — never raises —
    when ffmpeg isn't on PATH; callers already have to handle "no ffmpeg" as a real
    possibility (see media_engine.transcode)."""
    ffmpeg_bin = shutil.which('ffmpeg')
    if not ffmpeg_bin:
        return []
    try:
        result = subprocess.run(
            [ffmpeg_bin, '-hide_banner', flag], capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    codecs = []
    flag_re = re.compile(r'^[VAS][F.][S.][X.][B.][D.]$')
    for line in result.stdout.splitlines():
        line = line.strip()
        # Real rows look like "V....D libx264   description". The legend rows above them
        # (e.g. "V..... = Video") have an IDENTICAL flag-field shape — an all-dots flag
        # field is a legitimate "no special capabilities" codec too — so the flag regex
        # alone can't tell them apart. What does: legend rows are always exactly
        # "<flags> = <word>", i.e. their second token is the literal "=".
        parts = line.split(None, 2)
        if len(parts) >= 2 and flag_re.match(parts[0]) and parts[1] != '=':
            codecs.append(parts[1])
    return codecs


def detect_hardware() -> HardwareCapability:
    """The single entry point profile_resolver.py and the capacity-check path call.
    Always returns a real, freshly-measured snapshot — never cached across calls, since
    available RAM/VRAM genuinely changes between jobs."""
    gpu_present, gpu_vendor, vram_total_mb, vram_available_mb = _detect_gpu()
    vmem = psutil.virtual_memory()
    return HardwareCapability(
        cpu_cores=psutil.cpu_count(logical=True) or 1,
        ram_total_mb=int(vmem.total / (1024 * 1024)),
        ram_available_mb=int(vmem.available / (1024 * 1024)),
        gpu_present=gpu_present,
        gpu_vendor=gpu_vendor,
        vram_total_mb=vram_total_mb,
        vram_available_mb=vram_available_mb,
        ffmpeg_encoders=_list_ffmpeg_codecs('-encoders'),
        ffmpeg_decoders=_list_ffmpeg_codecs('-decoders'),
    )
