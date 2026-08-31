"""Tests for the isolated worker's self-integrity check (integrity.py) — the
mechanism that makes the .exe refuse to start its worker process if its own
protected files were tampered with on disk since the manifest was generated."""
from __future__ import annotations

import json

import pytest

from app import security as integrity


@pytest.fixture(autouse=True)
def isolated_manifest(tmp_path, monkeypatch):
    """Redirect PROTECTED_FILES lookups and the manifest path at a scratch
    copy of the real protected files, so tests never touch (or depend on the
    current state of) the real integrity_manifest.json checked into the repo."""
    manifest_path = tmp_path / 'integrity_manifest.json'
    monkeypatch.setattr(integrity, '_APP_DIR', tmp_path)
    monkeypatch.setattr(integrity, '_MANIFEST_PATH', manifest_path)
    monkeypatch.setattr(integrity, 'PROTECTED_FILES', ('a.py', 'b.py'))
    (tmp_path / 'a.py').write_text('print("a")\n', encoding='utf-8')
    (tmp_path / 'b.py').write_text('print("b")\n', encoding='utf-8')
    yield tmp_path


class TestGenerateAndVerify:
    def test_verify_fails_when_no_manifest_exists_yet(self):
        ok, problems = integrity.verify_integrity()
        assert ok is False
        assert any('ausente' in p for p in problems)

    def test_generate_then_verify_passes_on_untouched_files(self):
        integrity.generate_manifest()
        ok, problems = integrity.verify_integrity()
        assert ok is True
        assert problems == []

    def test_verify_fails_after_a_protected_file_is_modified(self, isolated_manifest):
        integrity.generate_manifest()
        (isolated_manifest / 'a.py').write_text('print("TAMPERED")\n', encoding='utf-8')
        ok, problems = integrity.verify_integrity()
        assert ok is False
        assert any('a.py' in p and 'modificado' in p for p in problems)

    def test_verify_fails_when_a_protected_file_is_deleted(self, isolated_manifest):
        integrity.generate_manifest()
        (isolated_manifest / 'a.py').unlink()
        ok, problems = integrity.verify_integrity()
        assert ok is False
        assert any('a.py' in p and 'ausente' in p for p in problems)

    def test_verify_fails_when_an_unlisted_file_is_added_after_manifest_generation(self, isolated_manifest, monkeypatch):
        """A file added to PROTECTED_FILES' scope after the manifest was
        generated (e.g. a new module added without regenerating the
        manifest) must be flagged, not silently trusted."""
        integrity.generate_manifest()
        (isolated_manifest / 'c.py').write_text('print("new")\n', encoding='utf-8')
        monkeypatch.setattr(integrity, 'PROTECTED_FILES', ('a.py', 'b.py', 'c.py'))
        ok, problems = integrity.verify_integrity()
        assert ok is False
        assert any('c.py' in p and 'não está no manifesto' in p for p in problems)

    def test_verify_passes_when_manifest_regenerated_after_a_legitimate_change(self, isolated_manifest):
        integrity.generate_manifest()
        (isolated_manifest / 'a.py').write_text('print("a new legitimate version")\n', encoding='utf-8')
        integrity.generate_manifest()  # the documented "how to update" step
        ok, problems = integrity.verify_integrity()
        assert ok is True

    def test_manifest_is_valid_json_mapping_filenames_to_sha256_hex(self):
        hashes = integrity.generate_manifest()
        assert set(hashes.keys()) == {'a.py', 'b.py'}
        for digest in hashes.values():
            assert len(digest) == 64
            int(digest, 16)  # raises ValueError if not valid hex

    def test_verify_fails_on_corrupted_manifest_json(self, isolated_manifest):
        integrity.generate_manifest()
        integrity._MANIFEST_PATH.write_text('{not valid json', encoding='utf-8')
        ok, problems = integrity.verify_integrity()
        assert ok is False

    def test_compute_hashes_ignores_files_not_present_on_disk(self, isolated_manifest, monkeypatch):
        monkeypatch.setattr(integrity, 'PROTECTED_FILES', ('a.py', 'does-not-exist.py'))
        hashes = integrity.compute_hashes()
        assert 'a.py' in hashes
        assert 'does-not-exist.py' not in hashes
