import os

import numpy as np
import pytest
import torch
from spandrel.architectures.Compact import Compact

from eterzion_upscale import EterzionUpscaler
from eterzion_upscale.processing import ALIASES, MODELS, model_needs_update, resolve_model, update_model
from eterzion_upscale.media import DownloadError, load_file_from_url, sha256_of_file


def test_registry_integrity():
    for name, entry in MODELS.items():
        assert entry['urls'], name
        assert len(entry['sha256']) == len(entry['urls']), name
        assert all(isinstance(h, str) and len(h) == 64 for h in entry['sha256']), name
        assert entry['scale'] in (1, 2, 4), name
        assert entry['category'] in ('Fotos', 'Anime', 'Restauração', 'Limpeza', 'Vídeo/Anime', 'Vídeo Real'), name
        assert entry['description'], name


def test_aliases_resolve_to_registry():
    for old, new in ALIASES.items():
        assert new in MODELS, f'alias {old} aponta para modelo inexistente {new}'


def test_download_sha256_ok_and_mismatch(tmp_path):
    source = tmp_path / 'weights.bin'
    source.write_bytes(b'astros' * 1000)
    url = source.as_uri()  # file:// URL
    good = sha256_of_file(str(source))

    # correct checksum -> file cached
    model_dir = tmp_path / 'ok'
    path = load_file_from_url(url, model_dir=str(model_dir), progress=False, sha256=good)
    assert sha256_of_file(path) == good

    # wrong checksum -> DownloadError and nothing left behind
    model_dir_bad = tmp_path / 'bad'
    with pytest.raises(DownloadError, match='SHA256'):
        load_file_from_url(url, model_dir=str(model_dir_bad), progress=False, sha256='0' * 64)
    assert list(model_dir_bad.iterdir()) == []


def test_download_unpinned_hash_warns(tmp_path, caplog):
    source = tmp_path / 'weights.bin'
    source.write_bytes(b'astros')
    with caplog.at_level('WARNING', logger='eterzion_upscale.media'):
        load_file_from_url(source.as_uri(), model_dir=str(tmp_path / 'out'), progress=False, sha256=None)
    assert any('sha256' in record.message for record in caplog.records)


def test_download_error_mentions_url(tmp_path):
    url = (tmp_path / 'nao_existe.pth').as_uri()
    with pytest.raises(DownloadError, match='nao_existe'):
        load_file_from_url(url, model_dir=str(tmp_path / 'out'), progress=False)


def _toy_upscaler(tmp_path, scale, name):
    net = Compact(num_in_ch=3, num_out_ch=3, num_feat=8, num_conv=2, upscale=scale)
    path = str(tmp_path / f'{name}.pth')
    torch.save({'params': net.state_dict()}, path)
    return EterzionUpscaler(model_path=path, device='cpu')


def test_model_update_redownloads_stale_or_missing_file(tmp_path, monkeypatch):
    import eterzion_upscale.processing as core

    official_source = tmp_path / 'official' / 'toy-weights.pth'
    official_source.parent.mkdir(parents=True, exist_ok=True)
    official_source.write_bytes(b'weights-v1')
    digest = sha256_of_file(str(official_source))

    monkeypatch.setitem(core.MODELS, 'toy-model',
                        {'urls': [official_source.as_uri()], 'sha256': [digest], 'scale': 4,
                         'category': 'Fotos', 'description': 'toy'})
    model_dir = str(tmp_path / 'models')

    # missing locally -> needs update, and update() downloads it from the official URL
    assert model_needs_update('toy-model', model_dir=model_dir) is True
    changed = update_model('toy-model', model_dir=model_dir)
    assert changed is True
    assert model_needs_update('toy-model', model_dir=model_dir) is False

    # up to date -> no-op
    assert update_model('toy-model', model_dir=model_dir) is False

    # corrupt the cached file -> detected as stale and refreshed from the same official URL
    cached_path = os.path.join(model_dir, 'toy-weights.pth')
    with open(cached_path, 'wb') as f:
        f.write(b'corrupted-garbage')
    assert model_needs_update('toy-model', model_dir=model_dir) is True
    assert update_model('toy-model', model_dir=model_dir) is True
    with open(cached_path, 'rb') as f:
        assert f.read() == b'weights-v1'


def test_resolve_model_downloads_from_official_url_by_default(tmp_path, monkeypatch):
    """With no models.json present, resolve_model must use the registry's official URL."""
    import eterzion_upscale.processing as core

    official_source = tmp_path / 'official2' / 'toy2.pth'
    official_source.parent.mkdir(parents=True, exist_ok=True)
    official_source.write_bytes(b'official-bytes')
    digest = sha256_of_file(str(official_source))

    monkeypatch.setitem(core.MODELS, 'toy-model-2',
                        {'urls': [official_source.as_uri()], 'sha256': [digest], 'scale': 4,
                         'category': 'Fotos', 'description': 'toy2'})
    model_dir = str(tmp_path / 'models2')
    path, _ = resolve_model('toy-model-2', model_dir=model_dir, models_json=str(tmp_path / 'no-such-models.json'))
    with open(path, 'rb') as f:
        assert f.read() == b'official-bytes'


def test_1x_model_keeps_size_and_chains(tmp_path):
    cleaner = _toy_upscaler(tmp_path, scale=1, name='toy1x')
    upscaler = _toy_upscaler(tmp_path, scale=2, name='toy2x')
    assert cleaner.scale == 1

    img = (np.random.random((20, 16, 3)) * 255).astype(np.uint8)
    # 1x alone: same size, no resize applied
    cleaned, mode = cleaner.enhance(img)
    assert cleaned.shape == (20, 16, 3) and mode == 'RGB'
    # chained: 1x output feeds the 2x model (--pre behaviour)
    result, _ = upscaler.enhance(cleaned)
    assert result.shape == (40, 32, 3)
