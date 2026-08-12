import json
import os

import numpy as np
import pytest
import torch
from spandrel.architectures.Compact import Compact

from astros_upscale.processing import AUDIO_ENGINES, MissingAudioDependency, enhance_audio_file, is_engine_available
from astros_upscale.processing import canonical_name, model_download_status, model_local_paths, resolve_model
from astros_upscale.media import DownloadError, download_with_fallback
from astros_upscale.media import VideoWriter, even, extract_audio, has_ffmpeg, mux_audio_file


def _write_source(tmp_path, name, content=b'weights'):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_mirror_url_used_before_fallback(tmp_path, monkeypatch):
    # a working "mirror" file wins over a broken "original" URL
    mirror = _write_source(tmp_path / 'mirror', 'w.pth', b'mirror-bytes')
    from astros_upscale.media import sha256_of_file
    digest = sha256_of_file(str(mirror))

    result = download_with_fallback(
        [mirror.as_uri(), (tmp_path / 'does-not-exist.pth').as_uri()],
        model_dir=str(tmp_path / 'out'), progress=False, file_name='w.pth', sha256=digest)
    assert os.path.basename(result) == 'w.pth'


def test_fallback_to_original_when_mirror_fails(tmp_path):
    original = _write_source(tmp_path / 'original', 'w2.pth', b'original-bytes')
    from astros_upscale.media import sha256_of_file
    digest = sha256_of_file(str(original))

    broken_mirror = (tmp_path / 'nao-existe.pth').as_uri()
    result = download_with_fallback(
        [broken_mirror, original.as_uri()], model_dir=str(tmp_path / 'out'), progress=False,
        file_name='w2.pth', sha256=digest)
    assert os.path.basename(result) == 'w2.pth'


def test_all_sources_fail_raises_aggregated_error(tmp_path):
    with pytest.raises(DownloadError, match='Todas as fontes'):
        download_with_fallback(
            [(tmp_path / 'a.pth').as_uri(), (tmp_path / 'b.pth').as_uri()],
            model_dir=str(tmp_path / 'out'), progress=False, file_name='x.pth')


def test_resolve_model_uses_mirror_json(tmp_path, monkeypatch):
    # build a fake models.json pointing 'hfa2k-span' at a local mirror file
    mirror_file = _write_source(tmp_path, '2xHFA2kSPAN.safetensors', b'fake-mirror-weights')
    from astros_upscale.media import sha256_of_file
    digest = sha256_of_file(str(mirror_file))

    manifest = {
        'models': [{
            'name': 'hfa2k-span',
            'files': [{'filename': '2xHFA2kSPAN.safetensors', 'sha256': digest, 'mirror_url': mirror_file.as_uri()}],
        }]
    }
    models_json = tmp_path / 'models.json'
    models_json.write_text(json.dumps(manifest), encoding='utf-8')

    # the registry's pinned sha256 differs from our fake mirror content, so pass sha256=None
    # indirectly by monkeypatching MODELS' pinned hash for this one test to match our fake file.
    import astros_upscale.processing as core
    monkeypatch.setitem(core.MODELS['hfa2k-span'], 'sha256', [digest])

    path, _ = resolve_model('hfa2k-span', model_dir=str(tmp_path / 'out'), models_json=str(models_json))
    assert os.path.isfile(path)
    with open(path, 'rb') as f:
        assert f.read() == b'fake-mirror-weights'


def test_model_download_status_and_paths(tmp_path):
    downloaded, size = model_download_status('nomos-webphoto', model_dir=str(tmp_path))
    assert downloaded is False and size == 0
    paths = model_local_paths('nomos-webphoto', model_dir=str(tmp_path))
    os.makedirs(tmp_path, exist_ok=True)
    for p in paths:
        with open(p, 'wb') as f:
            f.write(b'x' * 10)
    downloaded, size = model_download_status('nomos-webphoto', model_dir=str(tmp_path))
    assert downloaded is True and size == 10 * len(paths)


def test_canonical_name_aliases():
    assert canonical_name('anime-video') == 'realesr-animevideo'
    assert canonical_name('nomos-webphoto') == 'nomos-webphoto'


def test_even_dimension_rounding():
    assert even(640) == 640
    assert even(641) == 642
    assert even(0) == 0


@pytest.mark.skipif(not has_ffmpeg(), reason='ffmpeg binary not available')
def test_extract_and_mux_audio_roundtrip(tmp_path):
    from ffmpeg import FFmpeg

    silent = str(tmp_path / 'silent.mp4')
    writer = VideoWriter(silent, fps=10.0, width=16, height=16)
    for _ in range(5):
        writer.write(np.zeros((16, 16, 3), dtype=np.uint8))
    writer.close()

    source_with_audio = str(tmp_path / 'with_audio.mp4')
    (FFmpeg().option('y')
     .input(silent)
     .input('sine=frequency=440:duration=1', f='lavfi')
     .output(source_with_audio, {'c:v': 'copy', 'c:a': 'aac'}, shortest=None)
     .execute())

    extracted_wav = str(tmp_path / 'extracted.wav')
    assert extract_audio(source_with_audio, extracted_wav) is True
    assert os.path.getsize(extracted_wav) > 0

    output = str(tmp_path / 'muxed.mp4')
    assert mux_audio_file(silent, extracted_wav, output) is True
    assert os.path.isfile(output)


def test_extract_audio_no_stream_returns_false(tmp_path):
    silent = str(tmp_path / 'silent2.mp4')
    writer = VideoWriter(silent, fps=10.0, width=16, height=16)
    writer.write(np.zeros((16, 16, 3), dtype=np.uint8))
    writer.close()
    if not has_ffmpeg():
        pytest.skip('ffmpeg binary not available')
    ok = extract_audio(silent, str(tmp_path / 'out.wav'))
    assert ok is False


def test_1x_video_frame_chaining_offline(tmp_path):
    # mirrors the CLI's --pre behaviour on a single frame, without touching disk/network
    net1x = Compact(num_in_ch=3, num_out_ch=3, num_feat=8, num_conv=2, upscale=1)
    net2x = Compact(num_in_ch=3, num_out_ch=3, num_feat=8, num_conv=2, upscale=2)
    from astros_upscale import AstrosUpscaler
    p1 = str(tmp_path / 'a.pth')
    p2 = str(tmp_path / 'b.pth')
    torch.save({'params': net1x.state_dict()}, p1)
    torch.save({'params': net2x.state_dict()}, p2)
    pre = AstrosUpscaler(model_path=p1, device='cpu')
    main = AstrosUpscaler(model_path=p2, device='cpu')
    frame = (np.random.random((18, 14, 3)) * 255).astype(np.uint8)
    cleaned, _ = pre.enhance(frame)
    assert cleaned.shape == frame.shape
    result, _ = main.enhance(cleaned)
    assert result.shape == (36, 28, 3)


def test_audio_engine_missing_dependency_message(tmp_path):
    if is_engine_available('super-voz'):
        pytest.skip('audiosronnx is installed in this environment')
    with pytest.raises(MissingAudioDependency, match='astros_upscale\\[audio\\]'):
        enhance_audio_file(str(tmp_path / 'in.wav'), str(tmp_path / 'out.wav'), engine='super-voz')


def test_audio_engines_registry():
    for name, info in AUDIO_ENGINES.items():
        assert info['category'] in ('Áudio/Voz', 'Áudio/Geral', 'Áudio/Música'), name
        assert info['description'], name
        assert info['reference'].startswith('https://'), name
