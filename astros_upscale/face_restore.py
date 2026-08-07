"""Real face restoration using the GFPGAN network (official TencentARC weights).

Loaded through spandrel — the same auto-detecting loader used for every other
model in this project — instead of the `gfpgan` PyPI package. `gfpgan` pulls in
`basicsr`, which is unmaintained and fails to even build on Python 3.12+ (its
setup.py's version parsing breaks under newer CPython). Detection, alignment and
paste-back (the rest of what `gfpgan.GFPGANer` normally wraps) use `facexlib`
directly, which has no such dependency and installs cleanly.
"""
from __future__ import annotations

import cv2
import numpy as np
import torch
from spandrel import ModelLoader

from .utils.download import load_file_from_url

# Official release, same file GFPGANer downloads by default.
_GFPGAN_URL = 'https://github.com/TencentARC/GFPGAN/releases/download/v1.3.4/GFPGANv1.4.pth'
_GFPGAN_SHA256 = 'e2cd4703ab14f4d01fd1383a8a8b266f9a5833dacee8e6a79d3bf21a1b6be5ad'


def _bgr_to_tensor(face_bgr: np.ndarray, device: str) -> torch.Tensor:
    face_rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    t = torch.from_numpy(np.ascontiguousarray(face_rgb.transpose(2, 0, 1)))
    t = (t - 0.5) / 0.5  # GFPGAN's expected [-1, 1] input range
    return t.unsqueeze(0).to(device)


def _tensor_to_bgr(t: torch.Tensor) -> np.ndarray:
    img = t.clamp(-1, 1)
    img = (img + 1) / 2  # back to [0, 1]
    img = img.permute(1, 2, 0).cpu().numpy()
    img = (img * 255.0).round().clip(0, 255).astype(np.uint8)
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


class FaceRestorer:
    """Detects faces in a BGR image, restores each one with GFPGAN, and pastes
    the result back into the original frame. Faces are processed at their own
    (independent of the main upscale model's) fixed 512x512 working size, then
    warped back — the same approach the official GFPGANer pipeline uses."""

    def __init__(self, model_dir: str = 'models', device: str | None = None):
        from facexlib.utils.face_restoration_helper import FaceRestoreHelper

        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')

        weights_path = load_file_from_url(_GFPGAN_URL, model_dir=model_dir, sha256=_GFPGAN_SHA256)
        state = torch.load(weights_path, map_location='cpu', weights_only=True)
        state_dict = state.get('params_ema', state.get('params', state))
        descriptor = ModelLoader().load_from_state_dict(state_dict)
        descriptor.eval()
        self.model = descriptor.model.to(self.device)

        self.helper = FaceRestoreHelper(
            upscale_factor=1,
            face_size=512,
            crop_ratio=(1, 1),
            det_model='retinaface_resnet50',
            save_ext='png',
            use_parse=False,
            device=self.device,
            model_rootpath=model_dir,
        )

    def restore(self, img_bgr: np.ndarray, strength: float = 1.0) -> tuple[np.ndarray, int]:
        """Returns (result_image, faces_found). If no face is detected the
        original image is returned unchanged — never silently no-ops without
        saying so, the caller surfaces `faces_found` to the user."""
        self.helper.clean_all()
        self.helper.read_image(img_bgr)
        num_faces = self.helper.get_face_landmarks_5(only_center_face=False, resize=640, eye_dist_threshold=5)
        if num_faces == 0:
            return img_bgr, 0
        self.helper.align_warp_face()

        for cropped_face in self.helper.cropped_faces:
            face_t = _bgr_to_tensor(cropped_face, self.device)
            with torch.inference_mode():
                out = self.model(face_t)
            restored_t = out[0] if isinstance(out, (tuple, list)) else out
            restored_face = _tensor_to_bgr(restored_t[0])
            if strength < 1.0:
                restored_face = cv2.addWeighted(restored_face, strength, cropped_face, 1 - strength, 0)
            self.helper.add_restored_face(restored_face)

        self.helper.get_inverse_affine(None)
        result = self.helper.paste_faces_to_input_image()
        return result, num_faces
