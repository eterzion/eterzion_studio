"""Image reading/writing and tensor conversion helpers (torch/numpy/cv2 only)."""
from __future__ import annotations

import os

import cv2
import numpy as np
import torch


class ImageOpenError(ValueError):
    """Raised when an image cannot be read or encoded."""


def imread(path: str) -> np.ndarray:
    """Read an image keeping alpha channel and bit depth (unicode-safe on Windows).

    Returns a numpy array in BGR/BGRA/grayscale layout, dtype uint8 or uint16.
    """
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except OSError as error:
        raise ImageOpenError(f'Could not read image: {path} ({error})') from error
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ImageOpenError(f'Could not read image: {path}')
    return img


def imwrite(path: str, img: np.ndarray) -> None:
    """Write an image, creating parent directories as needed (unicode-safe on Windows)."""
    dirname = os.path.dirname(os.path.abspath(path))
    os.makedirs(dirname, exist_ok=True)
    ext = os.path.splitext(path)[1] or '.png'
    ok, buffer = cv2.imencode(ext, img)
    if not ok:
        raise ImageOpenError(f'Could not encode image with extension {ext}')
    buffer.tofile(path)


def img2tensor(img: np.ndarray, bgr2rgb: bool = True, add_batch: bool = True) -> torch.Tensor:
    """Convert an HWC numpy image (uint8/uint16/float) to a float32 CHW tensor in [0, 1]."""
    img = img.astype(np.float32)
    if img.max() > 256:  # 16-bit image
        img = img / 65535.0
    elif img.max() > 1.5:  # 8-bit image
        img = img / 255.0
    if img.ndim == 2:
        img = img[:, :, None]
    if bgr2rgb and img.shape[2] >= 3:
        img = img[:, :, [2, 1, 0]] if img.shape[2] == 3 else np.concatenate(
            (img[:, :, [2, 1, 0]], img[:, :, 3:]), axis=2)
    tensor = torch.from_numpy(np.ascontiguousarray(np.transpose(img, (2, 0, 1)))).float()
    return tensor.unsqueeze(0) if add_batch else tensor


def tensor2img(tensor: torch.Tensor, rgb2bgr: bool = True, out_dtype: type = np.uint8) -> np.ndarray:
    """Convert a CHW/BCHW float tensor in [0, 1] back to an HWC numpy image."""
    img = tensor.detach().squeeze().float().cpu().clamp_(0, 1).numpy()
    if img.ndim == 3:
        img = np.transpose(img, (1, 2, 0))
        if rgb2bgr and img.shape[2] >= 3:
            img = img[:, :, [2, 1, 0]] if img.shape[2] == 3 else np.concatenate(
                (img[:, :, [2, 1, 0]], img[:, :, 3:]), axis=2)
    if out_dtype == np.uint16:
        return (img * 65535.0).round().astype(np.uint16)
    return (img * 255.0).round().astype(np.uint8)
