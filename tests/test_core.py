import numpy as np
import torch
from spandrel import ImageModelDescriptor, ModelLoader
from spandrel.architectures.Compact import Compact

from astros_upscale import AstrosUpscaler


def _save_toy_checkpoint(tmp_path, scale=2):
    """Save a tiny Compact (SRVGGNet) checkpoint in the upstream .pth format."""
    net = Compact(num_in_ch=3, num_out_ch=3, num_feat=8, num_conv=2, upscale=scale)
    path = str(tmp_path / f'toy_x{scale}.pth')
    torch.save({'params': net.state_dict()}, path)
    return path


def test_load_from_file_and_upscale(tmp_path):
    scale = 2
    path = _save_toy_checkpoint(tmp_path, scale=scale)

    model = ModelLoader().load_from_file(path)
    assert isinstance(model, ImageModelDescriptor)
    assert model.architecture.id == 'Compact'
    assert model.scale == scale
    assert model.input_channels == 3
    assert model.output_channels == 3

    model.eval()
    x = torch.rand(1, 3, 16, 16)
    with torch.no_grad():
        y = model(x)
    assert y.shape == (1, 3, 16 * scale, 16 * scale)


def test_astros_upscaler(tmp_path):
    path = _save_toy_checkpoint(tmp_path, scale=2)

    upscaler = AstrosUpscaler(model_path=path, tile=0, pre_pad=2, half=False, device='cpu')
    assert upscaler.scale == 2
    assert upscaler.descriptor.architecture.id == 'Compact'

    img = (np.random.random((16, 16, 3)) * 255).astype(np.uint8)
    output, img_mode = upscaler.enhance(img, outscale=2)
    assert output.shape == (32, 32, 3)
    assert img_mode == 'RGB'

    # tiled path must produce the same output shape
    upscaler_tiled = AstrosUpscaler(model_path=path, tile=8, tile_pad=4, half=False, device='cpu')
    output_tiled, _ = upscaler_tiled.enhance(img, outscale=2)
    assert output_tiled.shape == (32, 32, 3)

    # RGBA and grayscale inputs
    rgba = (np.random.random((12, 12, 4)) * 255).astype(np.uint8)
    output_rgba, mode = upscaler.enhance(rgba, outscale=2)
    assert output_rgba.shape == (24, 24, 4) and mode == 'RGBA'
    gray = (np.random.random((12, 12)) * 255).astype(np.uint8)
    output_gray, mode = upscaler.enhance(gray, outscale=2)
    assert output_gray.shape == (24, 24) and mode == 'L'


def test_image_io_roundtrip(tmp_path):
    from astros_upscale import imread, imwrite, img2tensor, tensor2img

    img = (np.random.random((8, 10, 3)) * 255).astype(np.uint8)
    path = str(tmp_path / 'roundtrip.png')
    imwrite(path, img)
    loaded = imread(path)
    assert (loaded == img).all()

    tensor = img2tensor(img)
    assert tensor.shape == (1, 3, 8, 10)
    assert 0.0 <= float(tensor.min()) and float(tensor.max()) <= 1.0
    back = tensor2img(tensor)
    assert back.shape == (8, 10, 3)
    assert np.abs(back.astype(int) - img.astype(int)).max() <= 1
