from fastapi import APIRouter

from astros_upscale.core import DEFAULT_IMAGE_MODEL, DEFAULT_VIDEO_MODEL, MODELS, model_download_status

from ..config import settings

router = APIRouter()


@router.get('')
def list_models():
    models = []
    for name, info in sorted(MODELS.items()):
        downloaded, size_bytes = model_download_status(name, model_dir=settings.models_dir)
        models.append({
            'name': name,
            'category': info['category'],
            'scale': info['scale'],
            'description': info['description'],
            # Real, sourced from the official repo/model card for each weight file
            # (see astros_upscale/core.py) — never inferred or guessed.
            'architecture': info.get('architecture'),
            'file_count': len(info['urls']),
            'downloaded': downloaded,
            'size_bytes': size_bytes if downloaded else None,
        })
    return {
        'models': models,
        'devices': ['auto', 'cpu', 'cuda', 'mps'],
        'default_image_model': DEFAULT_IMAGE_MODEL,
        'default_video_model': DEFAULT_VIDEO_MODEL,
    }
