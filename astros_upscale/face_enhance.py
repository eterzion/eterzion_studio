"""Deterministic, licence-clean replacement for GFPGAN-based face restoration.

GFPGAN was removed (docs/models/MODEL_LICENSES.md §2): its top-level Apache-2.0
licence does not cover the StyleGAN2 prior it embeds (NVIDIA Source Code
License, non-commercial) or the DFDNet component (CC-BY-NC-SA-4.0). `facexlib`,
which the old `face_restore.py` used for detection/alignment, was removed too —
its own `__init__.py` imports a `tracking` submodule that pulls in SORT
(abewley/sort), GPL-3.0, which would contaminate the entire application if
linked into a distributed binary.

This module does not reconstruct faces the way GFPGAN did — it cannot invent
detail that was never captured. What it does: detect faces with YuNet (MIT,
opencv_zoo — code and weights both, no dataset-provenance ambiguity), then
apply a local, deterministic sharpen/contrast pass restricted to the face
region and its eyes/mouth sub-regions, feathered into the rest of the image so
there's no visible seam. Same input always produces the same output.
"""
from __future__ import annotations

import cv2
import numpy as np

from .utils.download import load_file_from_url

_YUNET_URL = 'https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx'
_YUNET_SHA256 = '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4'


class FaceEnhancer:
    """Detects faces with YuNet and sharpens each face region in place.

    Unlike the GFPGAN-based restorer this replaces, there is no per-face working
    resolution or warp/unwarp step: the enhancement is applied directly on the
    face's own pixels in the full-resolution image, so there's nothing to paste
    back and no chance of a misaligned seam from an affine warp.
    """

    def __init__(self, model_dir: str = 'models'):
        weights_path = load_file_from_url(_YUNET_URL, model_dir=model_dir,
                                           file_name='face_detection_yunet_2023mar.onnx', sha256=_YUNET_SHA256)
        self._model_path = weights_path
        self._detector = None  # built lazily, once the first image's size is known

    def _detector_for_size(self, width: int, height: int) -> cv2.FaceDetectorYN:
        if self._detector is None:
            self._detector = cv2.FaceDetectorYN.create(
                self._model_path, '', (width, height), score_threshold=0.7,
            )
        else:
            self._detector.setInputSize((width, height))
        return self._detector

    def restore(self, img_bgr: np.ndarray, strength: float = 1.0) -> tuple[np.ndarray, int]:
        """Returns (result_image, faces_found). Mirrors the old FaceRestorer's
        signature so callers (upscaler.py) don't need to change their call site —
        only what happens to each detected face changed, not the contract."""
        if img_bgr.dtype != np.uint8 or img_bgr.ndim != 3 or img_bgr.shape[2] != 3:
            return img_bgr, 0

        height, width = img_bgr.shape[:2]
        detector = self._detector_for_size(width, height)
        _, faces = detector.detect(img_bgr)
        if faces is None or len(faces) == 0:
            return img_bgr, 0

        result = img_bgr.copy()
        for face in faces:
            x, y, w, h = face[0:4].astype(int)
            landmarks = face[4:14].reshape(5, 2).astype(int)  # right eye, left eye, nose, mouth corners
            x, y = max(x, 0), max(y, 0)
            w, h = max(w, 1), max(h, 1)
            if x >= width or y >= height:
                continue
            w = min(w, width - x)
            h = min(h, height - y)
            _enhance_face_region(result, x, y, w, h, landmarks, strength)

        return result, len(faces)


def _enhance_face_region(img: np.ndarray, x: int, y: int, w: int, h: int,
                          landmarks: np.ndarray, strength: float) -> None:
    """Mutates `img` in place: unsharp mask + CLAHE within the face box, extra
    sharpen on eye/mouth sub-regions (where perceived sharpness matters most),
    blended back with an elliptical feathered mask so the box edge never shows.
    """
    roi = img[y:y + h, x:x + w]
    if roi.size == 0:
        return

    blurred = cv2.GaussianBlur(roi, (0, 0), sigmaX=2)
    amount = 0.6 * strength
    sharpened = cv2.addWeighted(roi, 1 + amount, blurred, -amount, 0)

    lab = cv2.cvtColor(sharpened, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.5 * strength + 0.5, tileGridSize=(4, 4))
    l_channel = clahe.apply(l_channel)
    enhanced = cv2.cvtColor(cv2.merge((l_channel, a_channel, b_channel)), cv2.COLOR_LAB2BGR)

    for lx, ly in landmarks:
        rx, ry = lx - x, ly - y
        radius = max(w, h) // 10
        x0, x1 = max(rx - radius, 0), min(rx + radius, w)
        y0, y1 = max(ry - radius, 0), min(ry + radius, h)
        if x1 <= x0 or y1 <= y0:
            continue
        sub = enhanced[y0:y1, x0:x1]
        sub_blur = cv2.GaussianBlur(sub, (0, 0), sigmaX=1)
        enhanced[y0:y1, x0:x1] = cv2.addWeighted(sub, 1 + 0.4 * strength, sub_blur, -0.4 * strength, 0)

    mask = np.zeros((h, w), dtype=np.float32)
    cv2.ellipse(mask, (w // 2, h // 2), (max(w // 2 - 2, 1), max(h // 2 - 2, 1)), 0, 0, 360, 1.0, -1)
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=max(w, h) * 0.06)
    mask3 = mask[:, :, None]

    blended = (enhanced.astype(np.float32) * mask3 + roi.astype(np.float32) * (1 - mask3))
    img[y:y + h, x:x + w] = blended.clip(0, 255).astype(np.uint8)
