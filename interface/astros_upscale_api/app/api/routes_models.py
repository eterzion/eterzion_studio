from fastapi import APIRouter

from astros_upscale.core import DEFAULT_IMAGE_MODEL, DEFAULT_VIDEO_MODEL, MODELS

router = APIRouter()


@router.get('')
def list_models():
    return {
        'models': [
            {'name': name, 'category': info['category'], 'scale': info['scale'], 'description': info['description']}
            for name, info in sorted(MODELS.items())
        ],
        'devices': ['auto', 'cpu', 'cuda', 'mps'],
        'default_image_model': DEFAULT_IMAGE_MODEL,
        'default_video_model': DEFAULT_VIDEO_MODEL,
    }
