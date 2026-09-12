"""Image/video/audio job execution (thin wrappers around eterzion_upscale),
hardware-derived capacity estimation, and on-demand component management.
Consolidates what were `upscaler.py`, `video_upscaler.py`, `audio_processor.py`,
`component_manager.py` and `capacity.py` (Constitution Princípio XI).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, replace
from typing import Callable, TypedDict
from urllib.parse import urlparse

from app import security

import cv2
import numpy as np

from eterzion_upscale.media import (ImageOpenError, VideoReader, VideoWriter, apply_atadenoise,
                                  apply_deflicker, compute_tile_grid, copy_audio, even,
                                  ffprobe_json, has_ffmpeg, imread, imwrite, run_ffmpeg)
from eterzion_upscale.processing import FaceEnhancer, HardwareCapability, load_model

from app.config import APP_DIR, settings
from app.licensing import _CONTENT_TYPE_IMPLEMENTATIONS, get_model_license

# ------------------------------- capacity estimation ------------------------------- #
#
# Real capacity estimation derived from eterzion_upscale.processing's
# HardwareCapability (T061/T062, FR-031 to FR-035, FR-076 to FR-080) — every
# figure below is computed from the machine's actually-available memory,
# never a fixed constant independent of it (FR-035).
#
# Two things live here:
# 1. `compute_tile_params()` — replaces the old fixed `_TILE_THRESHOLD=1600`/
#    `_TILE_SIZE=512` constants Upscaler/VideoUpscaler below used to hardcode:
#    more free memory -> larger tiles (fewer seams, faster); less -> smaller
#    tiles.
# 2. `check_capacity()` — the pre-flight gate FR-076/FR-077/FR-079 require:
#    image/video always "fits" (tiling makes arbitrarily large inputs
#    processable, just slower) unless the machine genuinely cannot hold even
#    the smallest usable tile; the estimated-duration figure (FR-078) is an
#    explicitly labelled order-of-magnitude estimate, not a benchmarked
#    guarantee — this codebase has no per-machine benchmark harness to derive
#    real throughput numbers from.

# Conservative bytes-per-megapixel budget for one tile's fp32 activations
# (a handful of conv layers, no tiling) — deliberately generous so a real
# OOM stays rare, not a measured per-model figure.
_BYTES_PER_MEGAPIXEL_FP32 = 350 * 1024 * 1024
_MIN_TILE_SIZE = 192
_MAX_TILE_SIZE = 1024
# Below this, not even one _MIN_TILE_SIZE tile's worth of memory is free —
# genuinely nothing can proceed (FR-079).
_MIN_VIABLE_MEMORY_MB = 64

# Order-of-magnitude throughput assumptions (FR-078: "an estimate", not a
# benchmarked guarantee) — GPU figures assume a mid-range consumer card,
# CPU figures assume the tiled fp32 fallback. Deliberately conservative:
# better to over-warn about a long job than under-warn.
_GPU_PIXELS_PER_SECOND = 2_000_000
_CPU_PIXELS_PER_SECOND = 150_000
_AUDIO_REALTIME_FACTOR_GPU = 8.0
_AUDIO_REALTIME_FACTOR_CPU = 1.5


@dataclass
class CapacityCheck:
    fits: bool
    estimated_duration: float | None
    limiting_resource: str | None


def _available_memory_mb(hardware: HardwareCapability) -> tuple[int, str]:
    """FR-080 — always the currently AVAILABLE figure, never total. Prefers
    VRAM when a GPU is present and its VRAM is actually queryable; CPU/RAM
    is the real fallback otherwise (FR-033)."""
    if hardware.gpu_present and hardware.vram_available_mb is not None:
        return hardware.vram_available_mb, 'vram'
    return hardware.ram_available_mb, 'ram'


def compute_tile_params(hardware: HardwareCapability) -> tuple[int, int]:
    """Returns (tile_threshold, tile_size) — images/frames at or under
    tile_threshold px on the long side skip tiling entirely."""
    available_mb, _ = _available_memory_mb(hardware)
    megapixels_that_fit = max(available_mb, 1) / (_BYTES_PER_MEGAPIXEL_FP32 / (1024 * 1024))
    tile_side = int((max(megapixels_that_fit, 0.01) * 1_000_000) ** 0.5)
    tile_size = max(_MIN_TILE_SIZE, min(_MAX_TILE_SIZE, tile_side))
    tile_threshold = tile_size * 3  # a handful of tiles' worth before tiling is worth it at all
    return tile_threshold, tile_size


def estimate_duration_seconds(
        hardware: HardwareCapability, media_type: str,
        pixel_count: int | None, duration_seconds: float | None) -> float | None:
    if media_type in ('image', 'video') and pixel_count:
        rate = _GPU_PIXELS_PER_SECOND if hardware.gpu_present else _CPU_PIXELS_PER_SECOND
        return pixel_count / rate
    if media_type == 'audio' and duration_seconds:
        factor = _AUDIO_REALTIME_FACTOR_GPU if hardware.gpu_present else _AUDIO_REALTIME_FACTOR_CPU
        return duration_seconds / factor
    return None


def check_capacity(
        hardware: HardwareCapability, media_type: str,
        width: int | None = None, height: int | None = None,
        duration_seconds: float | None = None) -> CapacityCheck:
    """FR-076/FR-077/FR-079 — image/video refuses only when the machine
    can't even hold the smallest usable tile (tiling handles everything
    above that, just more slowly); audio has no tiling equivalent, so it
    refuses on the same bare memory floor. Never a fixed byte/pixel/second
    ceiling independent of what `hardware` actually reports (FR-035)."""
    available_mb, limiting = _available_memory_mb(hardware)
    pixel_count = (width * height) if (width and height) else None
    estimated = estimate_duration_seconds(hardware, media_type, pixel_count, duration_seconds)

    if available_mb < _MIN_VIABLE_MEMORY_MB:
        return CapacityCheck(fits=False, estimated_duration=None, limiting_resource=limiting)
    return CapacityCheck(fits=True, estimated_duration=estimated, limiting_resource=None)


# ------------------------------- image upscale ------------------------------- #
#
# Thin wrapper around eterzion_upscale.processing — the same load_model()/enhance()
# the old GUI and CLI use. No PyTorch/RealESRGAN logic is duplicated here.
#
# process() runs the model once and writes a lossless master PNG; export() only
# re-encodes that master to whatever format/quality/destination is requested — never
# re-runs the model, so re-exporting after a job is done is always fast (see
# jobs.py and routes.py's POST /jobs/{id}/export).

# Lazily built and cached per model_dir — YuNet is small (~230KB) and fast, but there's
# no reason to reload the ONNX graph on every job.
_face_enhancer_cache: dict[str, FaceEnhancer] = {}


def _get_face_enhancer(model_dir: str) -> FaceEnhancer:
    cached = _face_enhancer_cache.get(model_dir)
    if cached is None:
        cached = FaceEnhancer(model_dir=model_dir)
        _face_enhancer_cache[model_dir] = cached
    return cached

_QUALITY_EXTENSIONS = {
    '.jpg': cv2.IMWRITE_JPEG_QUALITY,
    '.jpeg': cv2.IMWRITE_JPEG_QUALITY,
    '.webp': cv2.IMWRITE_WEBP_QUALITY,
}


class ProcessResult(TypedDict):
    source_size: tuple[int, int]  # (width, height)
    output_size: tuple[int, int]


class Upscaler:
    """`model_name` here is always an internal `engine_ref` resolved by
    app.licensing's profile resolver (T012/T020) — never a raw identifier chosen
    by a caller outside this process (FR-009/FR-011). `half` comes from the
    resolved profile's execution_params (see app.licensing._IMAGE_PROFILE_PARAMS)."""

    # Hardware-derived fallback (T061/FR-035): only used when a caller doesn't
    # pass tile_threshold/tile_size explicitly (e.g. code outside jobs.py's
    # profile-resolver-driven path) — never the value actually used for a real
    # job, which always carries compute_tile_params()'s fresh figures.
    _FALLBACK_TILE_THRESHOLD = 1600
    _FALLBACK_TILE_SIZE = 512

    def __init__(self, model_name: str, model_dir: str, device: str | None = None,
                 denoise_strength: float = 0.5, half: bool = True,
                 tile_threshold: int | None = None, tile_size: int | None = None):
        resolved_device = None if device in (None, 'auto', 'Automático') else device
        self._model = load_model(
            model_name, model_dir=model_dir, denoise_strength=denoise_strength,
            tile=0, tile_pad=10, pre_pad=0, half=half, device=resolved_device,
        )
        self._model_dir = model_dir
        self._tile_threshold = tile_threshold or self._FALLBACK_TILE_THRESHOLD
        self._tile_size = tile_size or self._FALLBACK_TILE_SIZE

    @staticmethod
    def _sharpen(img, strength: int):
        """Unsharp mask on luminance only: blur, then push the original away
        from the blur by `strength`. 0 is a no-op; the amount scales up to a
        clearly visible (but not oversharpened) edge boost at 100.

        Sharpening each colour channel on its own moves them by different
        amounts at an edge, and the difference between them IS colour — so the
        filter invented chroma exactly where there was none. Measured on a
        black-and-white icon: chroma came back from 8 to 22 at strength 100,
        undoing what _suppress_invented_chroma had just taken out.

        Separating luminance from chroma and sharpening only the first is the
        standard answer, and it is not a compromise: the impression of
        sharpness comes from the luminance edge. The colour planes are carried
        through untouched, so a sharpened photo keeps its colours exactly.
        """
        if strength <= 0:
            return img

        amount = strength / 100 * 1.5

        # Alpha is not colour and not luminance — it is set aside and put back.
        alpha = img[:, :, 3:] if img.ndim == 3 and img.shape[2] == 4 else None
        colour = img[:, :, :3] if alpha is not None else img

        if colour.ndim == 3 and colour.shape[2] == 3 and colour.dtype == np.uint8:
            ycrcb = cv2.cvtColor(colour, cv2.COLOR_BGR2YCrCb)
            luma = ycrcb[:, :, 0]
            blurred = cv2.GaussianBlur(luma, (0, 0), sigmaX=3)
            ycrcb[:, :, 0] = cv2.addWeighted(luma, 1 + amount, blurred, -amount, 0)
            sharpened = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)
        else:
            # Greyscale or 16-bit: there are no separate chroma planes to
            # protect, so the plain unsharp mask is already the right thing.
            blurred = cv2.GaussianBlur(colour, (0, 0), sigmaX=3)
            sharpened = cv2.addWeighted(colour, 1 + amount, blurred, -amount, 0)

        if alpha is None:
            return sharpened
        return np.concatenate((sharpened, alpha), axis=2)

    # Max OpenCV filter strength ("h" in fastNlMeansDenoisingColored) at strength=100.
    # Non-local means specifically targets grain/compression noise while comparing
    # patches across the whole neighborhood — it holds onto edges much better than a
    # plain blur, which is why it's the right tool here instead of GaussianBlur.
    _DENOISE_MAX_H = 20.0

    @classmethod
    def denoise_filter(cls, img, strength: int):
        """Real non-local-means denoise (cv2.fastNlMeansDenoisingColored), independent
        of any model's own built-in denoise (that one — the "Reduzir ruído" slider tied
        to realesr-general — blends two DNI weight sets at load time; this is a plain
        post-processing filter that works with any model). 0 is a no-op."""
        if strength <= 0:
            return img
        if img.dtype != np.uint8 or img.ndim != 3 or img.shape[2] != 3:
            # fastNlMeansDenoisingColored only supports 8-bit 3-channel BGR — same
            # honest fallback as face recovery for 16-bit/RGBA/grayscale outputs.
            return img
        h = max(1.0, strength / 100 * cls._DENOISE_MAX_H)
        return cv2.fastNlMeansDenoisingColored(img, None, h=h, hColor=h, templateWindowSize=7, searchWindowSize=21)

    @staticmethod
    def _suppress_invented_chroma(result, source, headroom: float = 1.25, floor: int = 8):
        """Cap the output's colour at what the source had in the same place.

        Measured on 2xHFA2kSPAN (the anime/illustration model) with a UI icon:
        21% of flat-area pixels and 82% of edge pixels came out coloured, chroma
        up to 140 — the pink and green fringing in white shapes. The photo model
        reaches 24 on the same picture and a plain nearest-neighbour enlargement
        18, so ~140 is invention, not detail.

        The rule is local, not global. An earlier version only corrected pixels
        whose source was neutral, and it missed exactly the case that prompted
        this: an icon on a dark blue background (chroma 18) counted as "coloured"
        everywhere, so the fringing where white meets that background went
        untouched. Comparing each pixel against the strongest colour actually
        present in its own neighbourhood handles both — a flat white area allows
        nothing, that blue background allows its own 18, and neither allows 140.

        `headroom` lets real colour intensify a little, which is legitimate
        upscaling; `floor` keeps very slight tints from being clamped to nothing
        by rounding. Luminance is never touched: that is where the actual
        upscaling work lives, and only chroma is pulled back.
        """
        if result.dtype != np.uint8 or result.ndim != 3 or result.shape[2] not in (3, 4):
            return result  # 16-bit and greyscale go through untouched
        if source.ndim != 3 or source.shape[2] not in (3, 4):
            return result

        # Transparency is the normal case for the material this was written
        # for: game and UI icons ship as RGBA with no background at all. An
        # earlier version bailed out on any 4-channel image, which meant the
        # correction never ran on precisely the files that motivated it.
        #
        # The alpha channel is carried through untouched — it is not colour and
        # has no chroma to cap. Only the three colour channels are compared and
        # corrected, and they are put back alongside the original alpha.
        alpha = result[:, :, 3:] if result.shape[2] == 4 else None
        colour = result[:, :, :3]
        source_colour = source[:, :, :3]
        corrected = Upscaler._cap_chroma(colour, source_colour, headroom, floor)
        if alpha is None:
            return corrected
        return np.concatenate((corrected, alpha), axis=2)

    @staticmethod
    def _cap_chroma(result, source, headroom: float, floor: int):
        """The cap itself, on three colour channels. Split out so the RGBA path
        and the RGB path cannot drift apart."""

        source_chroma = (
            source.max(axis=2).astype(np.int16) - source.min(axis=2).astype(np.int16)
        ).astype(np.uint8)

        # The strongest colour in the neighbourhood, not in the single pixel:
        # the model legitimately spreads a colour a little past where it started,
        # and a per-pixel comparison would claw that back and leave halos.
        local_max = cv2.dilate(source_chroma, np.ones((3, 3), np.uint8))
        if (source.shape[0], source.shape[1]) != (result.shape[0], result.shape[1]):
            local_max = cv2.resize(
                local_max, (result.shape[1], result.shape[0]), interpolation=cv2.INTER_LINEAR
            )

        # The floor applies only where there was some colour to begin with:
        # it exists so rounding cannot clamp a faint tint to nothing. Where the
        # neighbourhood was strictly neutral, nothing is allowed at all — a
        # white icon has no colour to spread, however faint.
        local_f = local_max.astype(np.float32)
        allowed = np.where(local_f > 0, np.maximum(local_f * headroom, float(floor)), 0.0)

        out_chroma = (
            result.max(axis=2).astype(np.int16) - result.min(axis=2).astype(np.int16)
        ).astype(np.float32)

        over = out_chroma > allowed
        if not over.any():
            return result

        # Scale each offending pixel's colour back toward its own grey, which
        # keeps its hue and its luminance and only reduces how saturated it is.
        rows, cols = np.nonzero(over)
        picked = result[rows, cols].astype(np.float32)
        grey = picked @ np.array([0.114, 0.587, 0.299], np.float32)  # BGR luma
        keep = (allowed[rows, cols] / np.maximum(out_chroma[rows, cols], 1e-6))[:, None]

        pulled = grey[:, None] + (picked - grey[:, None]) * keep
        result = result.copy()
        result[rows, cols] = np.clip(pulled, 0, 255).astype(np.uint8)
        return result

    def process(
        self,
        image_path: str,
        scale: int,
        custom_size: tuple[int, int] | None,
        master_path: str,
        on_progress: Callable[[int], None] | None = None,
        on_stage: Callable[[str], None] | None = None,
        sharpen_strength: int = 0,
        face_recovery: bool = False,
        face_recovery_strength: int = 80,
        denoise_filter_strength: int = 0,
    ) -> ProcessResult:
        if on_stage:
            on_stage('Lendo imagem')
        if on_progress:
            on_progress(5)

        img = imread(image_path)
        h_input, w_input = img.shape[0:2]

        target_w, target_h = custom_size if custom_size else (None, None)
        outscale = max(target_w / w_input, target_h / h_input) if target_w and target_h else scale

        if on_stage:
            on_stage('Aplicando modelo de IA')
        if on_progress:
            on_progress(10)

        self._model.tile_size = self._tile_size if max(h_input, w_input) > self._tile_threshold else 0
        if on_progress and self._model.tile_size:
            # map tile 1..N onto 10..90% of the bar
            self._model.tile_progress_callback = (
                lambda idx, total: on_progress(10 + int(80 * idx / total))
            )
        try:
            result, _img_mode = self._model.enhance(img, outscale=outscale)
        finally:
            self._model.tile_progress_callback = None

        if target_w and target_h and (result.shape[1], result.shape[0]) != (target_w, target_h):
            result = cv2.resize(result, (int(target_w), int(target_h)), interpolation=cv2.INTER_LANCZOS4)

        # Before the optional filters, so that sharpening cannot go on to
        # emphasise colour the model invented.
        result = self._suppress_invented_chroma(result, img)

        if face_recovery:
            # YuNet detection + local enhancement only operates on plain 3-channel 8-bit
            # BGR — the common case for photos. 16-bit and RGBA/grayscale outputs (rarer
            # inputs) are left as-is rather than silently mangled or crashed.
            if result.dtype == np.uint8 and result.ndim == 3 and result.shape[2] == 3:
                if on_stage:
                    on_stage('Realçando rostos')
                enhancer = _get_face_enhancer(self._model_dir)
                result, _faces_found = enhancer.restore(result, strength=face_recovery_strength / 100)
            elif on_stage:
                on_stage('Realce de rostos não suportado para este formato de imagem')

        if denoise_filter_strength > 0:
            if on_stage:
                on_stage('Reduzindo ruído')
            result = self.denoise_filter(result, denoise_filter_strength)

        if sharpen_strength > 0:
            if on_stage:
                on_stage('Aplicando nitidez')
            result = self._sharpen(result, sharpen_strength)

        if on_stage:
            on_stage('Salvando resultado')
        if on_progress:
            on_progress(92)

        os.makedirs(os.path.dirname(os.path.abspath(master_path)) or '.', exist_ok=True)
        imwrite(master_path, result)

        if on_progress:
            on_progress(100)

        return {'source_size': (w_input, h_input), 'output_size': (result.shape[1], result.shape[0])}

    @classmethod
    def process_without_model(
        cls,
        image_path: str,
        master_path: str,
        model_dir: str,
        resize: tuple[int, int] | None = None,
        on_progress: Callable[[int], None] | None = None,
        on_stage: Callable[[str], None] | None = None,
        sharpen_strength: int = 0,
        face_recovery: bool = False,
        face_recovery_strength: int = 80,
        denoise_filter_strength: int = 0,
    ) -> ProcessResult:
        """Everything process() does except the model pass — the Imagem screen's
        Original mode (scale '1x'). Running the model with outscale <= 1 would
        upscale 4x internally only to throw the result away, which is slow enough
        to look like the job hung; the filters below never needed it. `resize` may
        shrink, and may also enlarge -- see the interpolation choice below for
        why enlarging here is a real answer and not a shortcut past the model."""
        if on_stage:
            on_stage('Lendo imagem')
        if on_progress:
            on_progress(10)

        img = imread(image_path)
        h_input, w_input = img.shape[0:2]
        result = img

        if resize is not None:
            target_w, target_h = int(resize[0]), int(resize[1])
            if (target_w, target_h) != (w_input, h_input):
                if on_stage:
                    on_stage('Redimensionando')
                # Shrinking and enlarging want opposite things.
                #
                # INTER_AREA averages the pixels it discards, which is what
                # makes a reduction look clean.
                #
                # Enlarging uses INTER_NEAREST, and that is the whole point
                # of this path for pixel art. Every super-resolution model
                # here is trained on photographs and drawings, where
                # softening an edge is correct; on a 32x32 icon it is not.
                # Measured against a nearest enlargement of a real icon, the
                # models shifted the shape by 2.4 to 6.5 mean luma levels and
                # rounded the corners, while nearest reproduces every pixel
                # exactly as it was authored. For art drawn pixel by pixel,
                # inventing nothing beats any amount of clever.
                #
                # Pixel-art scalers were tried here and dropped: EPX and a
                # no-blend xBR both work (each output pixel is copied, so
                # a 39-colour icon stays 39 colours), but shown side by
                # side against plain nearest on real icons, plain nearest
                # was preferred. They round diagonals, and on artwork built
                # from deliberate blocks that reads as the filter second-
                # guessing the artist. Worth re-testing only with material
                # that is mostly diagonals and curves.
                enlarging = target_w > w_input or target_h > h_input
                interpolation = cv2.INTER_NEAREST if enlarging else cv2.INTER_AREA
                result = cv2.resize(
                    result, (target_w, target_h), interpolation=interpolation
                )
        if on_progress:
            on_progress(35)

        if face_recovery and result.dtype == np.uint8 and result.ndim == 3 and result.shape[2] == 3:
            if on_stage:
                on_stage('Realçando rostos')
            enhancer = _get_face_enhancer(model_dir)
            result, _faces_found = enhancer.restore(result, strength=face_recovery_strength / 100)
        if on_progress:
            on_progress(60)

        if denoise_filter_strength > 0:
            if on_stage:
                on_stage('Reduzindo ruído')
            result = cls.denoise_filter(result, denoise_filter_strength)

        if sharpen_strength > 0:
            if on_stage:
                on_stage('Aplicando nitidez')
            result = cls._sharpen(result, sharpen_strength)

        if on_stage:
            on_stage('Salvando resultado')
        if on_progress:
            on_progress(92)

        os.makedirs(os.path.dirname(os.path.abspath(master_path)) or '.', exist_ok=True)
        imwrite(master_path, result)

        if on_progress:
            on_progress(100)

        return {'source_size': (w_input, h_input), 'output_size': (result.shape[1], result.shape[0])}

    @staticmethod
    def export(master_path: str, output_path: str, quality: int | None) -> None:
        """Re-encodes the cached master to output_path's format — no model inference."""
        result = imread(master_path)
        ext = os.path.splitext(output_path)[1].lower()
        param_key = _QUALITY_EXTENSIONS.get(ext)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
        if quality is not None and param_key is not None:
            ok, buffer = cv2.imencode(ext, result, [param_key, int(quality)])
            if not ok:
                raise ImageOpenError(f'Falha ao codificar imagem: {output_path}')
            buffer.tofile(output_path)
        else:
            imwrite(output_path, result)


# ------------------------------- video upscale ------------------------------- #
#
# Video super-resolution job execution (T042) — the same eterzion_upscale
# frame-by-frame model pipeline the old CLI's `run_video` used, wrapped so
# jobs.py can dispatch it through the isolated worker process (T014) instead
# of running it as a bare in-process call. Reuses VideoReader/VideoWriter and
# the tiling/stabilization primitives from eterzion_upscale.media (T043/T044).
#
# Unlike the image path (Upscaler above), there is no separate "master" step
# here — export_job()/Upscaler.export only exist to cheaply re-encode a
# lossless PNG, and a video's real output IS the final muxed file process()
# writes directly.


class VideoProcessResult(TypedDict):
    source_size: tuple[int, int]
    output_size: tuple[int, int]


class VideoUpscaler:
    """`model_name` is always an internal engine_ref resolved by app.licensing's
    profile resolver (FR-009/FR-011), same contract as Upscaler above."""

    # Hardware-derived fallback (T061/FR-035) — same reasoning as Upscaler's:
    # a real job always carries fresh figures from compute_tile_params(),
    # this is only the default when a caller doesn't pass them explicitly.
    _FALLBACK_TILE_THRESHOLD = 1600
    _FALLBACK_TILE_SIZE = 512

    def __init__(self, model_name: str, model_dir: str, device: str | None = None,
                 denoise_strength: float = 0.5, half: bool = True,
                 tile_threshold: int | None = None, tile_size: int | None = None):
        resolved_device = None if device in (None, 'auto', 'Automático') else device
        self._model = load_model(
            model_name, model_dir=model_dir, denoise_strength=denoise_strength,
            tile=0, tile_pad=10, pre_pad=0, half=half, device=resolved_device,
        )
        self._tile_threshold = tile_threshold or self._FALLBACK_TILE_THRESHOLD
        self._tile_size = tile_size or self._FALLBACK_TILE_SIZE

    def process(
        self,
        video_path: str,
        scale: int,
        output_path: str,
        on_progress: Callable[[int], None] | None = None,
        on_stage: Callable[[str], None] | None = None,
        stabilize: bool = False,
        custom_size: tuple[int, int] | None = None,
    ) -> VideoProcessResult:
        """Writes the final (audio-muxed) video straight to `output_path` —
        `stabilize` (FR-102) is an opt-in extra pass, never mandatory, and
        only actually runs when a real ffmpeg binary is available.

        `custom_size` names an exact output resolution (the Vídeo screen's
        Customizado presets: 1080p, 1440p, 4K...). It replaces `scale`, which
        then only decides how hard the model works — exactly how the image path
        already treats the pair."""
        do_stabilize = stabilize and has_ffmpeg()

        if on_stage:
            on_stage('Lendo vídeo')
        read_path = video_path
        pre_denoised_path = None
        if do_stabilize:
            pre_denoised_path = output_path + '.pre_denoise.mp4'
            apply_atadenoise(video_path, pre_denoised_path)
            read_path = pre_denoised_path

        reader = VideoReader(read_path)
        source_w, source_h = reader.width, reader.height
        # FR-101: computed once, from the source frame size, reused unchanged
        # for every frame below — never recomputed mid-video.
        grid = compute_tile_grid(
            reader.width, reader.height,
            self._tile_size if max(reader.width, reader.height) > self._tile_threshold else 0,
        )
        self._model.tile_size = grid.tile_size
        self._model.tile_pad = grid.tile_pad

        if custom_size is not None:
            # Even dimensions because H.264 requires them; the per-frame resize
            # below then lands every frame exactly on the target.
            out_width, out_height = even(int(custom_size[0])), even(int(custom_size[1]))
            scale = max(out_width / reader.width, out_height / reader.height)
        else:
            out_width, out_height = even(int(reader.width * scale)), even(int(reader.height * scale))
        tmp_noaudio = output_path + '.noaudio.mp4'
        writer = VideoWriter(tmp_noaudio, fps=reader.fps, width=out_width, height=out_height)

        try:
            if on_stage:
                on_stage('Aplicando modelo de IA')
            total = len(reader)
            for idx, frame in enumerate(reader):
                result, _ = self._model.enhance(frame, outscale=scale)
                if result.shape[1] != out_width or result.shape[0] != out_height:
                    result = cv2.resize(result, (out_width, out_height), interpolation=cv2.INTER_LANCZOS4)
                writer.write(result)
                if on_progress and total:
                    on_progress(5 + int(75 * (idx + 1) / total))
        finally:
            reader.close()
            writer.close()
            if pre_denoised_path and os.path.exists(pre_denoised_path):
                os.remove(pre_denoised_path)

        final_video = tmp_noaudio
        if do_stabilize:
            if on_stage:
                on_stage('Estabilizando')
            deflickered = output_path + '.deflickered.mp4'
            apply_deflicker(tmp_noaudio, deflickered)
            os.remove(tmp_noaudio)
            final_video = deflickered

        if on_stage:
            on_stage('Remontando áudio')
        if on_progress:
            on_progress(90)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
        if copy_audio(video_path, final_video, output_path):
            os.remove(final_video)
        else:
            os.replace(final_video, output_path)

        if on_progress:
            on_progress(100)
        return {'source_size': (source_w, source_h), 'output_size': (out_width, out_height)}


# ------------------------------- audio enhancement job ------------------------------- #
#
# Real audio-enhance pipeline (T053) — jobs.py's isolated-worker dispatch
# target for media_type='audio'/operation='enhance'.
#
# Two stages, always in this order:
# 1. DSP chain (always runs, LGPL-safe ffmpeg filters only, per
#    docs/models/MODEL_LICENSES.md §4): `afftdn` (FFT noise reduction),
#    `deesser`/`acompressor` (voice-clarity shaping), `loudnorm` (EBU R128
#    loudness normalization). Fully verifiable with just ffmpeg — no ML
#    dependency, no network, no GPU.
# 2. Content-type model pass — `speech` gets audiosronnx's bandwidth extension
#    (Apache-2.0, package `audiosronnx`); `music` gets SonicMaster's
#    restoration model (Apache-2.0 code/weights, `license_status=
#    approved_conditional` — see app.licensing's profile resolver and
#    docs/models/MODEL_LICENSES.md §3-bis for the Stable Audio Open VAE
#    dependency this carries). Neither package is installed in every
#    environment (`[audio]` extra) — a missing one raises
#    MissingAudioDependency rather than silently skipping the step.
#
# SonicMaster ships as inference *scripts* (`inference_fullsong.py` et al.).
# There is no documented stable importable Python API — this integration calls
# its confirmed real CLI entry point via subprocess. It has not been run
# end-to-end in this environment (no checkpoint downloaded, package not
# installed here) — same "implemented but unverified until run once against
# real weights" status eterzion_upscale.processing already documents for its own
# less-common engines.


class MissingAudioDependency(ImportError):
    def __init__(self, engine: str, package: str, original: Exception) -> None:
        super().__init__(
            f"O motor de áudio '{engine}' precisa do pacote opcional '{package}', que não está instalado.\n"
            f"Instale com: pip install eterzion_upscale[audio]\n(erro original: {original})")


class AudioProcessResult(TypedDict):
    duration_seconds: float
    channels: int


# LGPL-only (never GPL) — noise reduction, then voice-clarity shaping, then
# loudness normalization last so the model pass below (if any) sees
# already-normalized input. -16 LUFS / -1.5 dBTP / LRA 11 mirrors ffmpeg's
# own loudnorm documentation defaults for streaming-style content.
_DSP_FILTER_CHAIN = 'afftdn,deesser,acompressor,loudnorm=I=-16:TP=-1.5:LRA=11'


def apply_dsp_chain(input_path: str, output_path: str) -> None:
    """Always runs, regardless of content_type — real ffmpeg filters, no
    Python ML dependency. Verified in test_audio_processor.py by measuring
    actual noise-floor reduction and the real integrated loudness of the
    output via a second ffmpeg loudnorm measurement pass."""
    run_ffmpeg(lambda f: f.input(input_path).output(output_path, {'af': _DSP_FILTER_CHAIN}))


def _enhance_speech(input_wav: str, output_wav: str, models_dir: str) -> None:
    """speech content_type — audiosronnx (Apache-2.0), the same engine
    eterzion_upscale.processing registers as 'super-voz'. Os pesos vem de
    `models_dir` (baixados sob demanda, espelho primeiro, SHA-256 conferido)."""
    from eterzion_upscale.processing import enhance_speech_file

    enhance_speech_file(input_wav, output_wav, models_dir)


_VENDOR_SONICMASTER_INFER = str(APP_DIR.parent / 'vendor' / 'sonicmaster' / 'infer.py')


def _enhance_music(input_wav: str, output_wav: str, models_dir: str | None = None) -> None:
    """music content_type — SonicMaster (approved_conditional, see
    app.licensing's _CONTENT_TYPE_IMPLEMENTATIONS and
    docs/models/MODEL_LICENSES.md §3-bis). Fixed in specs/006-audio-engine-
    masterizacao (T003): the previous version called `inference_fullsong.py`,
    which does not accept `--input`/`--output`/`--prompt` at all (it is
    dataset/JSONL-driven, confirmed against the real upstream source) — this
    never actually worked. Calls the vendored, adapted single-clip script
    (`vendor/sonicmaster/infer.py`, based on upstream's own `infer_single.py`,
    the only script there with a generic CLI) in the isolated audio-worker
    interpreter. This is the minimal, default-profile ('enhance') path —
    app.audio_engine.ai_provider.SonicMasterProvider (US1+) is the richer
    entry point used by the auto_master/restore/restore_master modes."""
    if not settings.audio_worker_python:
        raise MissingAudioDependency(
            'music (SonicMaster)', 'audio-worker',
            ImportError('ASTROS_AUDIO_WORKER_PYTHON não configurado — veja api/README.md'))
    if not os.path.isfile(settings.audio_worker_checkpoint):
        raise MissingAudioDependency(
            'music (SonicMaster)', 'sonicmaster-checkpoint',
            FileNotFoundError(f'Checkpoint não encontrado em {settings.audio_worker_checkpoint}'))
    result = subprocess.run(
        [settings.audio_worker_python, _VENDOR_SONICMASTER_INFER,
         '--ckpt', settings.audio_worker_checkpoint, '--input', input_wav, '--output', output_wav,
         '--prompt', 'Perform general music restoration and mastering', '--fs', '44100'],
        capture_output=True, text=True, timeout=600, check=False,
        **security.no_window_kwargs(),
    )
    if result.returncode != 0 or not os.path.isfile(output_wav):
        raise RuntimeError(f'SonicMaster falhou: {result.stderr.strip()}')


# Keyed by engine_ref (app.licensing's resolved identifier, e.g.
# 'super-voz'/'sonicmaster') — not content_type. The isolated worker's IPC
# message never carries content_type (FR-009/FR-011: only the already-resolved
# engine_ref crosses that boundary), same contract image/video handlers use.
_ENGINE_ENHANCERS: dict[str, Callable[[str, str, str], None]] = {
    'super-voz': _enhance_speech,
    'sonicmaster': _enhance_music,
}


def process(
    input_path: str,
    engine_ref: str,
    output_path: str,
    on_progress: Callable[[int], None] | None = None,
    on_stage: Callable[[str], None] | None = None,
    models_dir: str | None = None,
) -> AudioProcessResult:
    """Full pipeline: convert to WAV -> DSP chain -> content-type model pass
    -> re-encode to output_path's real format. Raises MissingAudioDependency
    if the resolved engine's package isn't installed (never silently skips
    the model step and calls it done)."""
    if engine_ref not in _ENGINE_ENHANCERS:
        raise ValueError(f'engine_ref sem implementação de áudio: {engine_ref!r}')

    if on_stage:
        on_stage('Lendo áudio')
    if on_progress:
        on_progress(5)
    tmp_in = tempfile.mktemp(suffix='.wav')
    run_ffmpeg(lambda f: f.input(input_path).output(tmp_in, {'vn': None, 'acodec': 'pcm_s16le'}))
    source_probe = ffprobe_json(tmp_in)
    source_audio = next(s for s in source_probe['streams'] if s['codec_type'] == 'audio')

    tmp_dsp = tempfile.mktemp(suffix='.wav')
    tmp_model = tempfile.mktemp(suffix='.wav')
    try:
        if on_stage:
            on_stage('Reduzindo ruído e normalizando volume')
        if on_progress:
            on_progress(25)
        apply_dsp_chain(tmp_in, tmp_dsp)

        if on_stage:
            on_stage('Aplicando modelo de IA')
        if on_progress:
            on_progress(50)
        # `models_dir` chega pela mensagem do job: o worker isolado nao recebe
        # ASTROS_MODELS_DIR no ambiente, e sem isto os pesos iriam para a pasta
        # padrao -- dentro da instalacao, possivelmente sem permissao de escrita.
        _ENGINE_ENHANCERS[engine_ref](tmp_dsp, tmp_model, models_dir or _model_dir())

        if on_stage:
            on_stage('Salvando resultado')
        if on_progress:
            on_progress(90)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
        fmt = os.path.splitext(output_path)[1].lstrip('.').lower() or 'wav'
        if fmt == 'wav':
            shutil.move(tmp_model, output_path)
        else:
            run_ffmpeg(lambda f: f.input(tmp_model).output(output_path))
    finally:
        for tmp in (tmp_in, tmp_dsp, tmp_model):
            if os.path.exists(tmp):
                os.remove(tmp)

    output_probe = ffprobe_json(output_path)
    duration = float(output_probe.get('format', {}).get('duration', 0.0) or 0.0)
    if on_progress:
        on_progress(100)
    return {'duration_seconds': duration, 'channels': int(source_audio.get('channels', 1))}


# ------------------------------- component management ------------------------------- #
#
# T068 — on-demand component download/verification/cache/eviction
# (FR-041/FR-042/FR-067 to FR-069). A "Component" is the installable unit the
# FR-063 to FR-069 screen lists — never a raw model identifier (FR-009/FR-063):
# each one maps 1:1 to a content-type implementation (app.licensing's
# _CONTENT_TYPE_IMPLEMENTATIONS), so there are exactly the 6 entries FR-095
# allows, not one per file in eterzion_upscale.processing.MODELS.
#
# Two real backends, one per kind of implementation:
# - image/video content types: eterzion_upscale.processing.MODELS — real
#   downloads, real SHA-256 verification (already implemented by
#   resolve_model()/model_needs_update()), real local cache (models_dir), real
#   eviction (delete the cached weight file(s)).
# - `speech`: o motor (audiosronnx + onnxruntime) vem no instalador; o botao
#   Instalar baixa os pesos do LavaSR pelo mesmo caminho dos de imagem
#   (espelho primeiro, SHA-256 fixado), e Remover apaga esses pesos. Ate'
#   2026-09-12 isto era um `pip install` do extra [audio] -- impossivel no app
#   empacotado, que nao tem pip, e a tela so' podia pedir para rodar o codigo-
#   fonte.
# - `music` (SonicMaster): nao instalavel pelo app; ver _MUSIC_NOT_AVAILABLE.

CAPABILITY_LABELS: dict[str, str] = {
    'photo': 'Melhoria de imagem — Foto',
    'anime_image': 'Melhoria de imagem — Anime/Ilustração',
    'anime_video': 'Melhoria de vídeo — Anime/Animação',
    'real_video': 'Melhoria de vídeo — Filmagem real',
    'speech': 'Melhoria de áudio — Voz',
    'music': 'Melhoria de áudio — Música',
}

_AUDIO_CONTENT_TYPES = {'speech', 'music'}


class ComponentNotFoundError(KeyError):
    pass


class ComponentActionUnsupportedError(RuntimeError):
    """Raised when install/update/delete is attempted on a component this
    process cannot safely automate — never silently no-ops, always tells the
    person what happened.

    `reason` e' o que a interface usa para escrever a frase na lingua do app;
    a mensagem (so' em portugues) e' a reserva.
    """

    def __init__(self, message: str, reason: str = 'unsupported'):
        super().__init__(message)
        self.reason = reason


# A musica (SonicMaster) precisa de um ambiente Python proprio com torch CUDA
# de varios GB, placa de video com 6-8 GB de VRAM e um download do Hugging Face
# que exige token e aceite dos termos da Stability AI. Nada disso cabe no
# instalador nem num botao desta tela, e a instalacao completa ficou para um
# projeto proprio (decisao de 2026-09-12). Ate' la', a recusa fala com quem usa
# o app -- nao manda ler README, montar venv ou exportar HF_TOKEN.
_MUSIC_NOT_AVAILABLE = ComponentActionUnsupportedError(
    'A restauração de música por IA ainda não está disponível nesta versão do aplicativo.',
    reason='not_available_in_app')


@dataclass
class ComponentInfo:
    id: str
    capability_label: str
    size_mb: int
    install_state: str
    update_available: bool
    technical_name: str
    version: str
    provenance: str
    license: str
    # Preenchido quando a última instalação em segundo plano falhou. Sem isto,
    # o estado voltaria a `not_installed` e a pessoa clicaria de novo sem saber
    # o que houve — que é o modo mais frustrante de um download falhar.
    error: str | None = None
    error_reason: str | None = None


# ------------------------------- instalação em segundo plano ------------------------------- #
#
# `POST /install` respondia só depois do download inteiro. Para o modelo maior
# isso é a tela parada por minutos, sem indicação, que a pessoa lê como app
# travado. O `InstallState` já previa `'installing'` — o que faltava era o
# backend entregar esse estado.
#
# O que NÃO virou assíncrono: a validação. Falta de código-fonte ao lado ou
# disco cheio continuam respondendo 422 na hora, porque são previsíveis antes
# de começar. Só falha de execução — rede caiu, hash não bateu, pip quebrou —
# chega pelo campo `error`, já que essas não dá para saber de antemão.
_INSTALL_LOCK = threading.Lock()
_INSTALLING: set[str] = set()
_INSTALL_ERRORS: dict[str, str] = {}
# Motivo da falha de download (`DownloadError.reason`), quando houver: e' com
# ele que a interface escolhe a frase, na lingua de quem usa o app.
_INSTALL_ERROR_REASONS: dict[str, str] = {}


def _start_background(component_id: str, work: Callable[[], object]) -> None:
    with _INSTALL_LOCK:
        if component_id in _INSTALLING:
            return  # já em curso: pedir de novo não enfileira uma segunda vez
        _INSTALLING.add(component_id)
        _INSTALL_ERRORS.pop(component_id, None)
        _INSTALL_ERROR_REASONS.pop(component_id, None)

    def run() -> None:
        try:
            work()
        except Exception as error:  # noqa: BLE001 - o erro vai para a tela, não some
            with _INSTALL_LOCK:
                _INSTALL_ERRORS[component_id] = str(error)
                reason = getattr(error, 'reason', None)
                if reason:
                    _INSTALL_ERROR_REASONS[component_id] = reason
        finally:
            with _INSTALL_LOCK:
                _INSTALLING.discard(component_id)

    threading.Thread(target=run, name=f'component-install-{component_id}', daemon=True).start()


def _with_background_state(info: ComponentInfo) -> ComponentInfo:
    with _INSTALL_LOCK:
        installing = info.id in _INSTALLING
        error = _INSTALL_ERRORS.get(info.id)
        reason = _INSTALL_ERROR_REASONS.get(info.id)
    if installing:
        return replace(info, install_state='installing', error=None, error_reason=None)
    return replace(info, error=error, error_reason=reason) if error else info


def _model_dir() -> str:
    return settings.models_dir


def _image_video_component(content_type: str, engine_ref: str) -> ComponentInfo:
    from eterzion_upscale.processing import MODELS, model_download_status, model_needs_update

    entry = MODELS[engine_ref]
    downloaded, size_bytes = model_download_status(engine_ref, model_dir=_model_dir())
    needs_update = downloaded and model_needs_update(engine_ref, model_dir=_model_dir())
    license_info = get_model_license(engine_ref)
    return ComponentInfo(
        id=content_type,
        capability_label=CAPABILITY_LABELS[content_type],
        # Real size once downloaded; unknown beforehand without a network HEAD
        # request per file, so 0 means "not yet measurable" here, not "0 bytes"
        # (same honest limitation the older GET /models route already had).
        size_mb=int(size_bytes / (1024 * 1024)) if downloaded else 0,
        install_state='update_available' if needs_update else ('installed' if downloaded else 'not_installed'),
        update_available=needs_update,
        technical_name=engine_ref,
        version=(entry['sha256'][0][:12] if entry.get('sha256') else 'desconhecida'),
        provenance=entry['urls'][0] if entry.get('urls') else 'desconhecida',
        license=license_info.license if license_info else 'não verificada',
    )


def _audio_component(content_type: str, engine_ref: str) -> ComponentInfo:
    if engine_ref == 'super-voz':
        from eterzion_upscale.processing import (
            _LAVASR_REVISION, is_engine_available, speech_weight_paths, speech_weights_installed)

        # Instalada = motor no pacote E pesos no disco. O motor vem no
        # instalador; o que o botao Instalar baixa sao os pesos (~56 MB).
        instalada = is_engine_available('super-voz') and speech_weights_installed(_model_dir())
        tamanho = sum(os.path.getsize(p) for p in speech_weight_paths(_model_dir()).values()
                      if os.path.isfile(p))
        return ComponentInfo(
            id=content_type, capability_label=CAPABILITY_LABELS[content_type],
            size_mb=int(tamanho / (1024 * 1024)) if instalada else 0,
            install_state='installed' if instalada else 'not_installed', update_available=False,
            technical_name=engine_ref, version=f'LavaSR {_LAVASR_REVISION[:7]}',
            provenance='https://github.com/TigreGotico/audiosronnx', license='Apache-2.0',
        )
    # music / sonicmaster — specs/006-audio-engine-masterizacao: runs from a
    # vendored inference subset in an isolated venv (audio_worker_requirements.txt),
    # never pip-installed into this process — "installed" means the operator
    # configured ASTROS_AUDIO_WORKER_PYTHON/ASTROS_AUDIO_WORKER_CHECKPOINT and
    # both paths exist (api/README.md's setup section). GPU/VRAM/HF_TOKEN
    # validity are runtime concerns (SonicMasterProvider.is_available()),
    # not "installed" — this screen answers "is the venv+checkpoint set up",
    # not "will an AI job succeed right now".
    checkpoint_present = os.path.isfile(settings.audio_worker_checkpoint)
    checkpoint_ready = bool(settings.audio_worker_python) and os.path.isfile(settings.audio_worker_python) \
        and checkpoint_present
    # Unlike speech, this one DOES own a single file on disk (the ~3.3 GB
    # SonicMaster checkpoint), so its size is real and deleting it is a safe,
    # useful way to reclaim that space.
    size_mb = int(os.path.getsize(settings.audio_worker_checkpoint) / (1024 * 1024)) if checkpoint_present else 0
    return ComponentInfo(
        id=content_type, capability_label=CAPABILITY_LABELS[content_type], size_mb=size_mb,
        install_state='installed' if checkpoint_ready else 'not_installed', update_available=False,
        technical_name=engine_ref, version='não incluída nesta versão do aplicativo',
        provenance='https://github.com/AMAAI-Lab/SonicMaster', license='Apache-2.0',
    )


def _component_info(content_type: str) -> ComponentInfo:
    implementation = _CONTENT_TYPE_IMPLEMENTATIONS.get(content_type)
    if implementation is None or implementation.engine_ref is None:
        raise ComponentNotFoundError(content_type)
    if content_type in _AUDIO_CONTENT_TYPES:
        info = _audio_component(content_type, implementation.engine_ref)
    else:
        info = _image_video_component(content_type, implementation.engine_ref)
    return _with_background_state(info)


def list_components() -> list[ComponentInfo]:
    return [_component_info(ct) for ct in CAPABILITY_LABELS]


def get_component_details(component_id: str) -> ComponentInfo:
    if component_id not in CAPABILITY_LABELS:
        raise ComponentNotFoundError(component_id)
    return _component_info(component_id)


def _install_speech_weights() -> None:
    from eterzion_upscale.processing import ensure_speech_weights, is_engine_available

    # O motor vem no instalador. Faltar aqui so' acontece num ambiente de
    # desenvolvimento montado sem o extra [audio].
    if not is_engine_available('super-voz'):
        raise ComponentActionUnsupportedError(
            'Esta cópia do aplicativo foi montada sem o motor de voz. Reinstale o aplicativo.',
            reason='engine_missing')
    ensure_speech_weights(_model_dir())


def install_component(component_id: str) -> ComponentInfo:
    """Real download + real SHA-256 verification: image/video weights through
    eterzion_upscale.processing.resolve_model, the speech weights through
    ensure_speech_weights — the same mirror-first path for both. `music`
    (SonicMaster) is not installable from the app (see _MUSIC_NOT_AVAILABLE)."""
    if component_id == 'music':
        raise _MUSIC_NOT_AVAILABLE
    if component_id == 'speech':
        _start_background('speech', _install_speech_weights)
        return _component_info('speech')
    implementation = _CONTENT_TYPE_IMPLEMENTATIONS.get(component_id)
    if implementation is None or implementation.engine_ref is None:
        raise ComponentNotFoundError(component_id)
    from eterzion_upscale.processing import resolve_model

    engine_ref = implementation.engine_ref
    _start_background(component_id, lambda: resolve_model(engine_ref, model_dir=_model_dir()))
    return _component_info(component_id)


def update_component(component_id: str) -> ComponentInfo:
    if component_id == 'music':
        raise _MUSIC_NOT_AVAILABLE
    if component_id == 'speech':
        # Os pesos tem revisao e SHA-256 fixados: "atualizar" e' garantir que
        # os arquivos certos estao la', baixando o que faltar.
        _start_background('speech', _install_speech_weights)
        return _component_info('speech')
    implementation = _CONTENT_TYPE_IMPLEMENTATIONS.get(component_id)
    if implementation is None or implementation.engine_ref is None:
        raise ComponentNotFoundError(component_id)
    from eterzion_upscale.processing import update_model

    engine_ref = implementation.engine_ref
    _start_background(component_id, lambda: update_model(engine_ref, model_dir=_model_dir()))
    return _component_info(component_id)


def uninstall_component(component_id: str) -> ComponentInfo:
    """Apaga os arquivos que uma capacidade baixou, devolvendo o espaço.

    Instalar sem poder desinstalar deixa o disco crescer sem que a pessoa
    tenha como reverter — e a tela mostra o tamanho justamente para que ela
    possa decidir. Cada capacidade de imagem/vídeo é um punhado de pesos; a
    música é um checkpoint de ~3,3 GB, o caso em que isto mais importa.

    A voz remove os pesos que baixou; o motor fica, porque vem no instalador.
    """
    if component_id == 'speech':
        from eterzion_upscale.processing import speech_weight_paths

        for caminho in speech_weight_paths(_model_dir()).values():
            if os.path.isfile(caminho):
                os.remove(caminho)
        return _component_info('speech')

    if component_id == 'music':
        if not os.path.isfile(settings.audio_worker_checkpoint):
            return _component_info(component_id)
        os.remove(settings.audio_worker_checkpoint)
        return _component_info(component_id)

    implementation = _CONTENT_TYPE_IMPLEMENTATIONS.get(component_id)
    if implementation is None or implementation.engine_ref is None:
        raise ComponentNotFoundError(component_id)
    from eterzion_upscale.processing import model_local_paths

    for path in model_local_paths(implementation.engine_ref, model_dir=_model_dir()):
        # Remover o que já não está lá é sucesso, não erro: a pessoa pediu que
        # não estivesse, e é assim que remover duas vezes seguidas funciona.
        if os.path.isfile(path):
            os.remove(path)
    return _component_info(component_id)
