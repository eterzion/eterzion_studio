"""Thin wrapper around astros_upscale.core — the same load_model()/enhance() the
old GUI and CLI use. No PyTorch/RealESRGAN logic is duplicated here.

process() runs the model once and writes a lossless master PNG; export() only
re-encodes that master to whatever format/quality/destination is requested — never
re-runs the model, so re-exporting after a job is done is always fast (see
job_manager.py and routes_jobs.py's POST /jobs/{id}/export).
"""
from __future__ import annotations

import os
from typing import Callable, TypedDict

import cv2
import numpy as np

from astros_upscale.core import load_model
from astros_upscale.face_restore import FaceRestorer
from astros_upscale.utils.image_io import ImageOpenError, imread, imwrite

# Lazily built and cached per (model_dir, device) — GFPGAN + its face detector are
# ~350MB combined and slow to load, so this only happens the first time a job
# actually requests face recovery, not on every Upscaler instantiation.
_face_restorer_cache: dict[tuple[str, str], FaceRestorer] = {}


def _get_face_restorer(model_dir: str, device: str) -> FaceRestorer:
    key = (model_dir, device)
    cached = _face_restorer_cache.get(key)
    if cached is None:
        cached = FaceRestorer(model_dir=model_dir, device=device)
        _face_restorer_cache[key] = cached
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
    def __init__(self, model_name: str, model_dir: str, device: str | None = None, denoise_strength: float = 0.5):
        resolved_device = None if device in (None, 'auto', 'Automático') else device
        self._model = load_model(
            model_name, model_dir=model_dir, denoise_strength=denoise_strength,
            tile=0, tile_pad=10, pre_pad=0, half=True, device=resolved_device,
        )
        self._model_dir = model_dir

    # Inputs larger than this (on either side) are processed in tiles: bounds GPU/CPU
    # memory (a 4096x4096 whole-image pass can OOM) and gives real per-tile progress.
    _TILE_THRESHOLD = 1600
    _TILE_SIZE = 512

    @staticmethod
    def _sharpen(img, strength: int):
        """Real OpenCV unsharp mask: blur the image, then push the original away
        from the blur by `strength`. 0 is a no-op; the amount scales up to a
        clearly visible (but not oversharpened) edge boost at 100."""
        if strength <= 0:
            return img
        blurred = cv2.GaussianBlur(img, (0, 0), sigmaX=3)
        amount = strength / 100 * 1.5
        return cv2.addWeighted(img, 1 + amount, blurred, -amount, 0)

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

        self._model.tile_size = self._TILE_SIZE if max(h_input, w_input) > self._TILE_THRESHOLD else 0
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

        if face_recovery:
            # GFPGAN (via facexlib's detector/aligner) only operates on plain 3-channel
            # 8-bit BGR — the common case for photos. 16-bit and RGBA/grayscale outputs
            # (rarer inputs) are left as-is rather than silently mangled or crashed.
            if result.dtype == np.uint8 and result.ndim == 3 and result.shape[2] == 3:
                if on_stage:
                    on_stage('Recuperando rostos')
                restorer = _get_face_restorer(self._model_dir, str(self._model.device))
                result, _faces_found = restorer.restore(result, strength=face_recovery_strength / 100)
            elif on_stage:
                on_stage('Recuperação de faces não suportada para este formato de imagem')

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
