"""Model loading (via spandrel) and tiled inference for astros_upscale."""
from __future__ import annotations

import json
import math
import os
from urllib.parse import urlparse

import cv2
import numpy as np
import torch
from spandrel import ModelLoader
from torch.nn import functional as F

from .utils.download import download_with_fallback, load_file_from_url, local_file_status, sha256_of_file

# Registry of bundled models: friendly name -> download urls, sha256 checksums,
# scale, category and description. The weight files keep their original upstream
# names (they are external release artifacts); the architecture is auto-detected
# from the weights by spandrel. A sha256 of None means "not pinned yet": the
# computed hash is logged on download instead of failing.
MODELS = {
    # -------------------------- Fotos -------------------------- #
    'realesrgan-x4': {
        'urls': ['https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth'],
        'sha256': ['4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1'],
        'scale': 4,
        'category': 'Fotos',
        'description': 'Padrão para fotos reais, equilíbrio nitidez/naturalidade',
    },
    'realesrgan-x2': {
        'urls': ['https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth'],
        'sha256': ['49fafd45f8fd7aa8d31ab2a22d14d91b536c34494a5cfe31eb5d89c2fa266abb'],
        'scale': 2,
        'category': 'Fotos',
        'description': 'Quando 4x é exagero; só dobra a resolução',
    },
    'realesr-general': {
        'urls': [
            'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth',
            'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-wdn-x4v3.pth',
        ],
        'sha256': [
            '8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292',
            '1641f8c4464b9f097c9fdda5589273713f67cf59f3d909e0bd688f0cee269dca',
        ],
        'scale': 4,
        'category': 'Fotos',
        'description': 'Leve e rápido, bom default geral (suporta --denoise)',
    },
    'realesrnet-x4': {
        'urls': ['https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.1/RealESRNet_x4plus.pth'],
        'sha256': ['a820b9bde89a874d7599d545567308ce6c128fc8754a53208eda016d40aa81df'],
        'scale': 4,
        'category': 'Fotos',
        'description': 'Resultado mais suave e com menos artefatos',
    },
    'ultrasharp': {
        'urls': ['https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x-UltraSharp.pth'],
        'sha256': ['a5812231fc936b42af08a5edba784195495d303d5b3248c24489ef0c4021fe01'],
        'scale': 4,
        'category': 'Fotos',
        'description': 'Muito nítido; ótimo em JPEG comprimido',
    },
    # -------------------------- Anime -------------------------- #
    'realesrgan-anime': {
        'urls': ['https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth'],
        'sha256': ['f872d837d3c90ed2e05227bed711af5671a6fd1c9f7d7e91c911a61f155e99da'],
        'scale': 4,
        'category': 'Anime',
        'description': 'Modelo leve otimizado para anime/ilustração',
    },
    'animesharp': {
        'urls': ['https://huggingface.co/Kim2091/AnimeSharp/resolve/main/4x-AnimeSharp.pth'],
        'sha256': ['e7a7de2dafd7331c1992862bbbcd9e9712a9f9f8e6303f0aaa59b4341d359bab'],
        'scale': 4,
        'category': 'Anime',
        'description': 'Linhas limpas em ilustrações e texto',
    },
    # -------------------------- Vídeo/Anime -------------------------- #
    'realesr-animevideo': {
        'urls': ['https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth'],
        'sha256': ['b8a8376811077954d82ca3fcf476f1ac3da3e8a68a4f4d71363008000a18b75d'],
        'scale': 4,
        'category': 'Vídeo/Anime',
        'description': 'Oficial Real-ESRGAN, leve, feito para vídeo de anime',
    },
    'hfa2k-avc': {
        'urls': ['https://huggingface.co/Phips/2xHFA2kAVCCompact/resolve/main/2xHFA2kAVCCompact.safetensors'],
        'sha256': ['2a4bedce982752395a16e5fd29961d62783385018158e5db9e63864077a5973e'],
        'scale': 2,
        'category': 'Vídeo/Anime',
        'description': 'Compact que trata degradação h264 (streaming/web)',
    },
    # ----------------------- Restauração ----------------------- #
    'nmkd-siax': {
        'urls': ['https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_NMKD-Siax_200k.pth'],
        'sha256': ['560424d9f68625713fc47e9e7289a98aabe1d744e1cd6a9ae5a35e9957fd127e'],
        'scale': 4,
        'category': 'Restauração',
        'description': 'Universal p/ imagens limpas ou pouco comprimidas',
    },
    'nmkd-superscale': {
        'urls': ['https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_NMKD-Superscale-SP_178000_G.pth'],
        'sha256': ['1d1b0078fe71446e0469d8d4df59e96baa80d83cda600d68237d655830821bcc'],
        'scale': 4,
        'category': 'Restauração',
        'description': 'Fotos reais com ruído e artefatos',
    },
    # ------------------ Limpeza (1x, sem upscale) ------------------ #
    'denoise': {
        'urls': ['https://github.com/Phhofm/models/releases/download/1xDeNoise_realplksr_otf/'
                 '1xDeNoise_realplksr_otf.pth'],
        'sha256': ['f4774fbe13ceaa9df390343c2baaa980061458ef27292fa6aca6740d87608a8e'],
        'scale': 1,
        'category': 'Limpeza',
        'description': 'Remove ruído fotográfico; trata leve compressão JPEG',
    },
    'dejpg': {
        'urls': ['https://github.com/Phhofm/models/releases/download/1xDeJPG_realplksr_otf/'
                 '1xDeJPG_realplksr_otf.pth'],
        'sha256': ['3bf4959fbd4b39b8877e73ea97a54d4280755371fe4bd64a2836c707d7fd485b'],
        'scale': 1,
        'category': 'Limpeza',
        'description': 'Remove artefatos JPEG (treinado até qualidade 40)',
    },
}

# Old model names kept as aliases for backward compatibility.
ALIASES = {
    'photo-x4': 'realesrgan-x4',
    'photo-x2': 'realesrgan-x2',
    'photo-soft-x4': 'realesrnet-x4',
    'anime-x4': 'realesrgan-anime',
    'anime-video': 'realesr-animevideo',
    'anime-video-x4': 'realesr-animevideo',
    'fast-x4': 'realesr-general',
}

DEFAULT_IMAGE_MODEL = 'realesrgan-x4'
DEFAULT_VIDEO_MODEL = 'realesr-animevideo'


def canonical_name(name_or_alias: str) -> str:
    """Resolve an alias (or already-canonical name) to its canonical registry name."""
    return ALIASES.get(name_or_alias, name_or_alias)


def _load_mirror_map(models_json: str = 'models.json') -> dict:
    """Load the mirror map generated by ``scripts/mirror_models.py``, if present.

    Returns an empty dict (no mirrors) when the file does not exist or is invalid —
    this is the normal state until someone runs the mirroring script, and downloads
    simply fall back to the original upstream URLs.
    """
    if not os.path.isfile(models_json):
        return {}
    try:
        with open(models_json, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return {entry['name']: entry for entry in data.get('models', []) if 'name' in entry}


def _urls_with_mirror(name: str, entry: dict, models_json: str) -> list[list[str]]:
    """For each file of ``entry``, return the candidate URL list: [mirror_url?, original_url]."""
    mirror_entry = _load_mirror_map(models_json).get(name)
    mirror_by_filename = {}
    if mirror_entry:
        mirror_by_filename = {f['filename']: f.get('mirror_url') for f in mirror_entry.get('files', [])}
    candidates = []
    for url in entry['urls']:
        filename = os.path.basename(urlparse(url).path)
        mirror_url = mirror_by_filename.get(filename)
        candidates.append([mirror_url, url] if mirror_url else [url])
    return candidates


def model_local_paths(name_or_path: str, model_dir: str = 'models') -> list[str]:
    """Return the local file path(s) a registered model would be cached as (no download)."""
    name = canonical_name(name_or_path)
    entry = MODELS[name]
    return [os.path.join(model_dir, os.path.basename(urlparse(u).path)) for u in entry['urls']]


def model_download_status(name_or_path: str, model_dir: str = 'models') -> tuple[bool, int]:
    """Return (fully_downloaded, total_size_in_bytes) for a registered model, without downloading."""
    name = canonical_name(name_or_path)
    entry = MODELS[name]
    total = 0
    for url in entry['urls']:
        downloaded, size = local_file_status(url, model_dir=model_dir)
        if not downloaded:
            return False, 0
        total += size
    return True, total


def model_needs_update(name_or_path: str, model_dir: str = 'models') -> bool:
    """True if the model is missing locally, or a cached file no longer matches the
    checksum currently pinned in the registry (e.g. after the registry was bumped
    to point at a newer/corrected weight file)."""
    name = canonical_name(name_or_path)
    entry = MODELS[name]
    for url, pinned_sha in zip(entry['urls'], entry['sha256']):
        path = os.path.join(model_dir, os.path.basename(urlparse(url).path))
        if not os.path.isfile(path):
            return True
        if sha256_of_file(path).lower() != pinned_sha.lower():
            return True
    return False


def update_model(name_or_path: str, model_dir: str = 'models', models_json: str = 'models.json') -> bool:
    """Bring a model's local file(s) in line with the registry: download if missing,
    or re-download if the cached file no longer matches the pinned checksum.

    Returns:
        bool: True if anything was (re)downloaded, False if it was already up to date.
    """
    name = canonical_name(name_or_path)
    entry = MODELS[name]
    changed = False
    for url, pinned_sha in zip(entry['urls'], entry['sha256']):
        path = os.path.join(model_dir, os.path.basename(urlparse(url).path))
        if os.path.isfile(path):
            if sha256_of_file(path).lower() == pinned_sha.lower():
                continue
            os.remove(path)  # stale: force a fresh download below
        changed = True
    if changed:
        resolve_model(name, model_dir=model_dir, models_json=models_json)
    return changed


def resolve_model(
        name_or_path: str,
        model_dir: str = 'models',
        denoise_strength: float | None = None,
        models_json: str = 'models.json') -> tuple[str | list[str], list[float] | None]:
    """Resolve a model name (from MODELS) or a local .pth path into loader arguments.

    When a ``models.json`` mirror map (generated by ``scripts/mirror_models.py``) is
    present, each file is downloaded from its mirror first, automatically falling
    back to the original upstream URL if the mirror is unreachable.

    Returns:
        tuple: (model_path, dni_weight) ready for AstrosUpscaler. ``model_path`` is a
        list of two paths when denoise interpolation applies.
    """
    if os.path.isfile(name_or_path):
        return name_or_path, None
    name = canonical_name(name_or_path)
    if name not in MODELS:
        raise ValueError(f'Modelo desconhecido: {name_or_path!r}. '
                         f'Veja as opções com: astros-upscale models')
    entry = MODELS[name]
    url_candidates = _urls_with_mirror(name, entry, models_json)
    paths = [
        download_with_fallback(candidates, model_dir=model_dir, sha256=digest)
        for candidates, digest in zip(url_candidates, entry['sha256'])
    ]
    if name == 'realesr-general' and denoise_strength is not None and denoise_strength != 1:
        # interpolate between the normal and the strong-denoise weights
        return [paths[0], paths[1]], [denoise_strength, 1 - denoise_strength]
    return paths[0], None


def load_model(name_or_path: str, model_dir: str = 'models', **kwargs) -> 'AstrosUpscaler':
    """Convenience helper: resolve a model name/path and return a ready AstrosUpscaler."""
    model_path, dni_weight = resolve_model(name_or_path, model_dir=model_dir,
                                           denoise_strength=kwargs.pop('denoise_strength', None))
    return AstrosUpscaler(model_path=model_path, dni_weight=dni_weight, **kwargs)


def _pick_device(gpu_id: int | None = None) -> torch.device:
    """Pick the best available device: CUDA > MPS (Apple Silicon) > CPU."""
    if torch.cuda.is_available():
        return torch.device(f'cuda:{gpu_id}' if gpu_id is not None else 'cuda')
    if getattr(torch.backends, 'mps', None) is not None and torch.backends.mps.is_available():
        return torch.device('mps')
    return torch.device('cpu')


class AstrosUpscaler():
    """Upscales images with a super-resolution model loaded through spandrel.

    Args:
        model_path (str | list[str]): Path to the pretrained weights (or a URL). A list of two
            paths enables deep-network interpolation controlled by ``dni_weight``.
            The architecture is auto-detected from the weights by spandrel.
        scale (int): Upsampling scale of the network. If None, the scale detected by spandrel is used.
        tile (int): Crop the input into tiles of this size to bound GPU memory use; the results
            are seamlessly merged. 0 disables tiling. Default: 0.
        tile_pad (int): Padding around each tile to remove border artifacts. Default: 10.
        pre_pad (int): Pad the input borders to avoid edge artifacts. Default: 10.
        half (bool): Use half precision. Only applied on CUDA/MPS and when the model supports it.
        compile_model (bool): Compile the network with ``torch.compile`` for faster repeated
            inference (pays a warm-up cost on the first call). Default: False.
    """

    def __init__(self,
                 model_path: str | list[str] | None = None,
                 scale: int | None = None,
                 dni_weight: list[float] | None = None,
                 tile: int = 0,
                 tile_pad: int = 10,
                 pre_pad: int = 10,
                 half: bool = False,
                 device: str | torch.device | None = None,
                 gpu_id: int | None = None,
                 compile_model: bool = False) -> None:
        self.tile_size = tile
        self.tile_pad = tile_pad
        self.pre_pad = pre_pad
        self.mod_scale = None

        self.device = _pick_device(gpu_id) if device is None else torch.device(device)

        if self.device.type == 'cuda':
            # convolution-heavy, fixed-ish shapes: let cuDNN autotune and use TF32 on Ampere+
            torch.backends.cudnn.benchmark = True
            torch.set_float32_matmul_precision('high')

        if isinstance(model_path, list):
            # deep network interpolation
            assert len(model_path) == len(dni_weight), 'model_path and dni_weight should have the same length.'
            loadnet = self.dni(model_path[0], model_path[1], dni_weight)
        else:
            if model_path.startswith('https://'):
                model_path = load_file_from_url(url=model_path)
            loadnet = torch.load(model_path, map_location=torch.device('cpu'), weights_only=True)

        # prefer to use params_ema
        if 'params_ema' in loadnet:
            loadnet = loadnet['params_ema']
        elif 'params' in loadnet:
            loadnet = loadnet['params']

        # spandrel auto-detects the architecture from the state dict
        descriptor = ModelLoader().load_from_state_dict(loadnet)
        self.descriptor = descriptor
        self.scale = scale if scale is not None else descriptor.scale

        # half precision only makes sense on GPU backends and on models that support it
        self.half = half and self.device.type in ('cuda', 'mps') and descriptor.supports_half

        descriptor.eval()
        model = descriptor.model.to(self.device, memory_format=torch.channels_last)
        if self.half:
            model = model.half()
        if compile_model and hasattr(torch, 'compile'):
            model = torch.compile(model)
        self.model = model

    def dni(self, net_a, net_b, dni_weight, key='params', loc='cpu'):
        """Deep network interpolation.

        ``Paper: Deep Network Interpolation for Continuous Imagery Effect Transition``
        """
        net_a = torch.load(net_a, map_location=torch.device(loc), weights_only=True)
        net_b = torch.load(net_b, map_location=torch.device(loc), weights_only=True)
        for k, v_a in net_a[key].items():
            net_a[key][k] = dni_weight[0] * v_a + dni_weight[1] * net_b[key][k]
        return net_a

    def pre_process(self, img):
        """Pre-process, such as pre-pad and mod pad, so that the images can be divisible
        """
        img = torch.from_numpy(np.ascontiguousarray(np.transpose(img, (2, 0, 1)))).float()
        img = img.unsqueeze(0)
        if self.device.type == 'cuda':
            img = img.pin_memory()
        self.img = img.to(self.device, non_blocking=True).to(memory_format=torch.channels_last)
        if self.half:
            self.img = self.img.half()

        # pre_pad
        if self.pre_pad != 0:
            self.img = F.pad(self.img, (0, self.pre_pad, 0, self.pre_pad), 'reflect')
        # mod pad for divisible borders
        if self.scale == 2:
            self.mod_scale = 2
        elif self.scale == 1:
            self.mod_scale = 4
        if self.mod_scale is not None:
            self.mod_pad_h, self.mod_pad_w = 0, 0
            _, _, h, w = self.img.size()
            if (h % self.mod_scale != 0):
                self.mod_pad_h = (self.mod_scale - h % self.mod_scale)
            if (w % self.mod_scale != 0):
                self.mod_pad_w = (self.mod_scale - w % self.mod_scale)
            self.img = F.pad(self.img, (0, self.mod_pad_w, 0, self.mod_pad_h), 'reflect')

    def process(self):
        # model inference
        self.output = self.model(self.img)

    def tile_process(self):
        """It will first crop input images to tiles, and then process each tile.
        Finally, all the processed tiles are merged into one images.

        Modified from: https://github.com/ata4/esrgan-launcher
        """
        batch, channel, height, width = self.img.shape
        output_height = height * self.scale
        output_width = width * self.scale
        output_shape = (batch, channel, output_height, output_width)

        # start with black image
        self.output = self.img.new_zeros(output_shape)
        tiles_x = math.ceil(width / self.tile_size)
        tiles_y = math.ceil(height / self.tile_size)

        # loop over all tiles
        for y in range(tiles_y):
            for x in range(tiles_x):
                # extract tile from input image
                ofs_x = x * self.tile_size
                ofs_y = y * self.tile_size
                # input tile area on total image
                input_start_x = ofs_x
                input_end_x = min(ofs_x + self.tile_size, width)
                input_start_y = ofs_y
                input_end_y = min(ofs_y + self.tile_size, height)

                # input tile area on total image with padding
                input_start_x_pad = max(input_start_x - self.tile_pad, 0)
                input_end_x_pad = min(input_end_x + self.tile_pad, width)
                input_start_y_pad = max(input_start_y - self.tile_pad, 0)
                input_end_y_pad = min(input_end_y + self.tile_pad, height)

                # input tile dimensions
                input_tile_width = input_end_x - input_start_x
                input_tile_height = input_end_y - input_start_y
                tile_idx = y * tiles_x + x + 1
                input_tile = self.img[:, :, input_start_y_pad:input_end_y_pad, input_start_x_pad:input_end_x_pad]

                # upscale tile
                try:
                    with torch.inference_mode():
                        output_tile = self.model(input_tile)
                except RuntimeError as error:
                    print('Error', error)
                print(f'\tTile {tile_idx}/{tiles_x * tiles_y}')

                # output tile area on total image
                output_start_x = input_start_x * self.scale
                output_end_x = input_end_x * self.scale
                output_start_y = input_start_y * self.scale
                output_end_y = input_end_y * self.scale

                # output tile area without padding
                output_start_x_tile = (input_start_x - input_start_x_pad) * self.scale
                output_end_x_tile = output_start_x_tile + input_tile_width * self.scale
                output_start_y_tile = (input_start_y - input_start_y_pad) * self.scale
                output_end_y_tile = output_start_y_tile + input_tile_height * self.scale

                # put tile into output image
                self.output[:, :, output_start_y:output_end_y,
                            output_start_x:output_end_x] = output_tile[:, :, output_start_y_tile:output_end_y_tile,
                                                                       output_start_x_tile:output_end_x_tile]

    def post_process(self):
        # remove extra pad
        if self.mod_scale is not None:
            _, _, h, w = self.output.size()
            self.output = self.output[:, :, 0:h - self.mod_pad_h * self.scale, 0:w - self.mod_pad_w * self.scale]
        # remove prepad
        if self.pre_pad != 0:
            _, _, h, w = self.output.size()
            self.output = self.output[:, :, 0:h - self.pre_pad * self.scale, 0:w - self.pre_pad * self.scale]
        return self.output

    @torch.inference_mode()
    def enhance(self,
                img: np.ndarray,
                outscale: float | None = None,
                alpha_upsampler: str = 'model') -> tuple[np.ndarray, str]:
        h_input, w_input = img.shape[0:2]
        # img: numpy
        img = img.astype(np.float32)
        if np.max(img) > 256:  # 16-bit image
            max_range = 65535
            print('\tInput is a 16-bit image')
        else:
            max_range = 255
        img = img / max_range
        if len(img.shape) == 2:  # gray image
            img_mode = 'L'
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        elif img.shape[2] == 4:  # RGBA image with alpha channel
            img_mode = 'RGBA'
            alpha = img[:, :, 3]
            img = img[:, :, 0:3]
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            if alpha_upsampler == 'model':
                alpha = cv2.cvtColor(alpha, cv2.COLOR_GRAY2RGB)
        else:
            img_mode = 'RGB'
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # ------------------- process image (without the alpha channel) ------------------- #
        self.pre_process(img)
        if self.tile_size > 0:
            self.tile_process()
        else:
            self.process()
        output_img = self.post_process()
        output_img = output_img.data.squeeze().float().cpu().clamp_(0, 1).numpy()
        output_img = np.transpose(output_img[[2, 1, 0], :, :], (1, 2, 0))
        if img_mode == 'L':
            output_img = cv2.cvtColor(output_img, cv2.COLOR_BGR2GRAY)

        # ------------------- process the alpha channel if necessary ------------------- #
        if img_mode == 'RGBA':
            if alpha_upsampler == 'model':
                self.pre_process(alpha)
                if self.tile_size > 0:
                    self.tile_process()
                else:
                    self.process()
                output_alpha = self.post_process()
                output_alpha = output_alpha.data.squeeze().float().cpu().clamp_(0, 1).numpy()
                output_alpha = np.transpose(output_alpha[[2, 1, 0], :, :], (1, 2, 0))
                output_alpha = cv2.cvtColor(output_alpha, cv2.COLOR_BGR2GRAY)
            else:  # use the cv2 resize for alpha channel
                h, w = alpha.shape[0:2]
                output_alpha = cv2.resize(alpha, (w * self.scale, h * self.scale), interpolation=cv2.INTER_LINEAR)

            # merge the alpha channel
            output_img = cv2.cvtColor(output_img, cv2.COLOR_BGR2BGRA)
            output_img[:, :, 3] = output_alpha

        # ------------------------------ return ------------------------------ #
        if max_range == 65535:  # 16-bit image
            output = (output_img * 65535.0).round().astype(np.uint16)
        else:
            output = (output_img * 255.0).round().astype(np.uint8)

        if outscale is not None and outscale != float(self.scale):
            output = cv2.resize(
                output, (
                    int(w_input * outscale),
                    int(h_input * outscale),
                ), interpolation=cv2.INTER_LANCZOS4)

        return output, img_mode
