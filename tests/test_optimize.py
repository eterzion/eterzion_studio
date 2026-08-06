import os

import numpy as np
import pytest

from astros_upscale.optimize import (UnsupportedFormatError, _quality_to_audio_bitrate_kbps, _quality_to_crf,
                                      optimize_file, optimize_image)
from astros_upscale.utils.image_io import imwrite


def _write_toy_image(path, width=64, height=48):
    rng = np.random.default_rng(0)
    img = rng.integers(0, 255, (height, width, 3), dtype=np.uint8)
    imwrite(str(path), img)
    return str(path)


def test_optimize_image_jpg_reduces_size(tmp_path):
    src = _write_toy_image(tmp_path / 'in.jpg')
    out = str(tmp_path / 'out.jpg')
    optimize_image(src, out, quality=10)
    assert os.path.exists(out)
    assert os.path.getsize(out) < os.path.getsize(src)


def test_optimize_image_png_is_lossless(tmp_path):
    src = _write_toy_image(tmp_path / 'in.png')
    out = str(tmp_path / 'out.png')
    optimize_image(src, out, quality=1)  # quality is ignored for png
    from astros_upscale.utils.image_io import imread
    assert np.array_equal(imread(src), imread(out))


def test_optimize_image_rejects_unsupported_extension(tmp_path):
    src = _write_toy_image(tmp_path / 'in.png')
    with pytest.raises(UnsupportedFormatError):
        optimize_image(src, str(tmp_path / 'out.tiff'), quality=80)


def test_optimize_file_requires_matching_extension(tmp_path):
    src = _write_toy_image(tmp_path / 'in.jpg')
    with pytest.raises(UnsupportedFormatError, match='extensão'):
        optimize_file(src, str(tmp_path / 'out.png'), quality=80)


def test_optimize_file_rejects_unknown_extension(tmp_path):
    bogus = tmp_path / 'in.xyz'
    bogus.write_bytes(b'not a real media file')
    with pytest.raises(UnsupportedFormatError):
        optimize_file(str(bogus), str(tmp_path / 'out.xyz'), quality=80)


def test_quality_to_crf_bounds():
    assert _quality_to_crf(100) == 18
    assert _quality_to_crf(0) == 40
    assert _quality_to_crf(150) == _quality_to_crf(100)  # clipped
    assert _quality_to_crf(-10) == _quality_to_crf(0)  # clipped


def test_quality_to_audio_bitrate_bounds():
    assert _quality_to_audio_bitrate_kbps(0) == 64
    assert _quality_to_audio_bitrate_kbps(100) == 320
