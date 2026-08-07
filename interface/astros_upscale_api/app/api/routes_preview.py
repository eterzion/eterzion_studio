import base64
import os

import cv2
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.upscaler import Upscaler
from astros_upscale.utils.image_io import imread

router = APIRouter()

# Keeps the preview fast enough to feel interactive on slider release — the actual
# job always runs the filter on the real, full-resolution upscaled output; this is
# only a representative before/after, not the final result.
_PREVIEW_MAX_DIM = 480


class DenoisePreviewRequest(BaseModel):
    input_path: str
    strength: int = Field(ge=0, le=100)


def _encode_png(img) -> str:
    ok, buffer = cv2.imencode('.png', img)
    if not ok:
        raise HTTPException(500, 'Falha ao codificar prévia.')
    return base64.b64encode(buffer.tobytes()).decode('ascii')


@router.post('/denoise')
def preview_denoise(payload: DenoisePreviewRequest):
    if not os.path.isfile(payload.input_path):
        raise HTTPException(404, 'Arquivo não encontrado no caminho informado.')

    img = imread(payload.input_path)
    h, w = img.shape[0:2]
    scale = min(1.0, _PREVIEW_MAX_DIM / max(h, w))
    if scale < 1.0:
        img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)

    after = Upscaler.denoise_filter(img, payload.strength)
    return {
        'before': _encode_png(img),
        'after': _encode_png(after),
        'width': img.shape[1],
        'height': img.shape[0],
    }
