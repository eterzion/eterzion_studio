import os

import numpy as np
import pytest

from astros_upscale.optimize import (EncoderUnavailableError, UnsupportedFormatError,
                                      _CONTAINER_AUDIO_ENCODERS, _CONTAINER_VIDEO_ENCODERS,
                                      _audio_options, _quality_to_audio_bitrate_kbps, _quality_to_crf,
                                      _resolve_video_encoder, _video_quality_options,
                                      optimize_file, optimize_image, optimize_video)
from astros_upscale.media import GPL_ENCODERS, imwrite


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
    from astros_upscale.media import imread
    assert np.array_equal(imread(src), imread(out))


def test_optimize_image_rejects_unsupported_extension(tmp_path):
    src = _write_toy_image(tmp_path / 'in.png')
    with pytest.raises(UnsupportedFormatError):
        optimize_image(src, str(tmp_path / 'out.tiff'), quality=80)


def test_optimize_file_converts_between_extensions_of_the_same_media_type(tmp_path):
    """T025/T027 — FR-028: conversion (different extension, same media type)
    is now a real, supported path, not the same-extension restriction that
    used to reject this outright."""
    src = _write_toy_image(tmp_path / 'in.jpg')
    out = str(tmp_path / 'out.png')
    optimize_file(src, out, quality=80)
    assert os.path.exists(out)
    from astros_upscale.media import imread
    assert imread(out).shape == imread(src).shape


def test_optimize_file_rejects_cross_media_type_conversion(tmp_path):
    """FR-030: image -> audio (or any cross-media-type request) must be
    refused with a clear reason, never silently attempted."""
    src = _write_toy_image(tmp_path / 'in.jpg')
    with pytest.raises(UnsupportedFormatError, match='imagem.*áudio|mesmo tipo de mídia'):
        optimize_file(src, str(tmp_path / 'out.mp3'), quality=80)


def test_optimize_file_rejects_unknown_extension(tmp_path):
    bogus = tmp_path / 'in.xyz'
    bogus.write_bytes(b'not a real media file')
    with pytest.raises(UnsupportedFormatError):
        optimize_file(str(bogus), str(tmp_path / 'out.xyz'), quality=80)


def test_optimize_image_converts_to_avif_via_ffmpeg(tmp_path):
    src = _write_toy_image(tmp_path / 'in.png')
    out = str(tmp_path / 'out.avif')
    optimize_image(src, out, quality=60)
    assert os.path.exists(out)
    assert os.path.getsize(out) > 0


def test_optimize_image_converts_from_avif_via_ffmpeg(tmp_path):
    src = _write_toy_image(tmp_path / 'in.png')
    avif_path = str(tmp_path / 'mid.avif')
    optimize_image(src, avif_path, quality=60)

    out = str(tmp_path / 'out.jpg')
    optimize_image(avif_path, out, quality=80)
    assert os.path.exists(out)
    assert os.path.getsize(out) > 0


def test_optimize_image_resizes_to_the_requested_dimensions(tmp_path):
    """Resize on the compress/convert path is a plain resample — it must
    actually change the written file's dimensions, not just be accepted."""
    from astros_upscale.media import imread

    src = _write_toy_image(tmp_path / 'in.png', width=64, height=48)
    out = str(tmp_path / 'out.png')
    optimize_image(src, out, resize=(32, 24))
    written = imread(out)
    assert (written.shape[1], written.shape[0]) == (32, 24)


def test_optimize_image_without_resize_keeps_original_dimensions(tmp_path):
    from astros_upscale.media import imread

    src = _write_toy_image(tmp_path / 'in.png', width=64, height=48)
    out = str(tmp_path / 'out.png')
    optimize_image(src, out)
    written = imread(out)
    assert (written.shape[1], written.shape[0]) == (64, 48)


def test_optimize_file_passes_resize_through_for_images(tmp_path):
    from astros_upscale.media import imread

    src = _write_toy_image(tmp_path / 'in.png', width=64, height=48)
    out = str(tmp_path / 'out.jpg')
    optimize_file(src, out, quality=80, resize=(16, 12))
    written = imread(out)
    assert (written.shape[1], written.shape[0]) == (16, 12)


def test_quality_to_crf_bounds():
    assert _quality_to_crf(100) == 18
    assert _quality_to_crf(0) == 40
    assert _quality_to_crf(150) == _quality_to_crf(100)  # clipped
    assert _quality_to_crf(-10) == _quality_to_crf(0)  # clipped


def test_quality_to_audio_bitrate_bounds():
    assert _quality_to_audio_bitrate_kbps(0) == 64
    assert _quality_to_audio_bitrate_kbps(100) == 320


# ------------------------- encoder choice (GPL debt) ------------------------- #
#
# `optimize_video`/`optimize_file` defaulted to `codec='libx264'` until
# docs/technical-debt/gpl-encoder-default.md was closed. libx264 is GPL, and the
# Constitution forbids shipping a GPL encoder. These fix the new behaviour so the
# default cannot quietly come back.


def test_no_container_offers_a_gpl_encoder():
    for container, encoders in _CONTAINER_VIDEO_ENCODERS.items():
        assert not GPL_ENCODERS.intersection(encoders), container
    for container, encoders in _CONTAINER_AUDIO_ENCODERS.items():
        assert not GPL_ENCODERS.intersection(encoders), container


def test_every_video_extension_has_an_encoder_list():
    """A container `optimize_file` accepts but `_CONTAINER_VIDEO_ENCODERS` does
    not know would raise UnsupportedFormatError after the job already started."""
    from astros_upscale.optimize import VIDEO_EXTENSIONS

    assert set(VIDEO_EXTENSIONS) == set(_CONTAINER_VIDEO_ENCODERS) == set(_CONTAINER_AUDIO_ENCODERS)


def test_an_explicitly_named_gpl_codec_is_refused():
    """The refusal is a property of `encoder_works()`, not of this call site —
    it holds even on a developer machine whose ffmpeg does have libx264."""
    for gpl in GPL_ENCODERS:
        with pytest.raises(EncoderUnavailableError):
            _resolve_video_encoder('out.mp4', gpl)


def test_the_refusal_message_never_names_an_encoder():
    """These surface through the job error field; Princípio V keeps encoder
    names off that wire."""
    with pytest.raises(EncoderUnavailableError) as refused:
        _resolve_video_encoder('out.mp4', 'libx264')
    assert 'libx264' not in str(refused.value)


def test_an_unknown_container_is_refused_by_extension():
    with pytest.raises(UnsupportedFormatError):
        _resolve_video_encoder('out.ogv', None)


def test_optimize_video_refuses_before_transcoding_when_nothing_works(tmp_path, monkeypatch):
    """Princípio XIII: fail with a named reason before starting, never partway
    through. The machine's actual hardware decides which encoders work, so the
    absence has to be simulated — the refusal itself is real."""
    from astros_upscale import optimize as optimize_module

    monkeypatch.setattr(optimize_module, 'has_ffmpeg', lambda: True)
    monkeypatch.setattr(optimize_module, 'first_available_encoder', lambda candidates: None)
    monkeypatch.setattr(optimize_module, 'run_ffmpeg', _never_called)

    with pytest.raises(EncoderUnavailableError):
        optimize_video('in.mp4', str(tmp_path / 'out.mp4'), quality=75)


def _never_called(*args, **kwargs):
    raise AssertionError('ffmpeg was invoked after the encoder check should have refused')


@pytest.mark.parametrize('encoder,option', [
    ('h264_nvenc', 'cq'),
    ('h264_qsv', 'global_quality'),
    ('h264_amf', 'qp_i'),
    ('libvpx-vp9', 'crf'),
    ('libaom-av1', 'crf'),
])
def test_each_encoder_gets_the_quantizer_option_it_understands(encoder, option):
    """One number, five spellings. `crf` passed to nvenc is silently ignored and
    the export comes out at the encoder's default quality — the kind of bug that
    only shows up as "why is this file so big"."""
    options = _video_quality_options(encoder, quality=75)
    assert options[option] == _quality_to_crf(75)


def test_the_two_crf_encoders_pin_the_bitrate_target_to_zero():
    for encoder in ('libvpx-vp9', 'libaom-av1'):
        assert _video_quality_options(encoder, quality=75)['b:v'] == '0'


def test_audio_is_copied_only_when_the_container_stays_the_same(monkeypatch):
    from astros_upscale import optimize as optimize_module

    assert _audio_options('in.mp4', 'out.mp4') == {'c:a': 'copy'}

    monkeypatch.setattr(optimize_module, 'first_available_encoder', lambda candidates: candidates[0])
    assert _audio_options('in.mp4', 'out.webm') == {'c:a': 'libopus'}
