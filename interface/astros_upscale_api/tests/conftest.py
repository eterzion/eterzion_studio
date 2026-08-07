from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# astros_upscale (the core package, imported by app.core.upscaler) lives three
# levels above this service, same layout app/config.py itself relies on.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest


@pytest.fixture(autouse=True)
def isolated_identity_dir(tmp_path, monkeypatch):
    """install_identity.py reads %LOCALAPPDATA%/%APPDATA% directly (it's a
    real per-machine path, not something app.config exposes) — point it at a
    temp dir per test and clear the in-process identity cache so no test sees
    another test's generated keys."""
    from app.core import install_identity

    def _fake_identity_dir():
        path = tmp_path / 'identity'
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    monkeypatch.setattr(install_identity, '_identity_dir', _fake_identity_dir)
    monkeypatch.setattr(install_identity, '_cached', None)
    yield
    monkeypatch.setattr(install_identity, '_cached', None)
