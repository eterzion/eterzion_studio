"""T068 — real coverage of component_manager.py. list_components()/
get_component_details() run against the real models/ directory (no mocking
of file presence or license lookups) — the install/update/delete round trip
uses a real, temporary models_dir so it can perform a genuine download +
SHA-256 verify + delete without touching the shared models/ cache other
tests rely on."""
from __future__ import annotations

import pytest

from app.core import component_manager
from app.core.component_manager import (
    CAPABILITY_LABELS,
    ComponentActionUnsupportedError,
    ComponentNotFoundError,
)


class TestListComponents:
    def test_returns_exactly_the_six_content_type_components(self):
        components = component_manager.list_components()
        assert {c.id for c in components} == set(CAPABILITY_LABELS)

    def test_never_exposes_a_raw_model_identifier_as_the_capability_label(self):
        """FR-009/FR-063 — capability_label must be a human sentence, never
        an internal engine_ref like 'nomos-webphoto' or 'super-voz'."""
        from app.core.profile_resolver import _CONTENT_TYPE_IMPLEMENTATIONS

        components = component_manager.list_components()
        raw_refs = {
            impl.engine_ref for impl in _CONTENT_TYPE_IMPLEMENTATIONS.values() if impl.engine_ref
        }
        for c in components:
            assert c.capability_label not in raw_refs
            assert c.id in CAPABILITY_LABELS  # id is a content_type slug, not an engine_ref

    def test_photo_reflects_real_download_state(self):
        """The real photo model (nomos-webphoto) is already downloaded on
        this dev machine (used throughout this session's other real tests)
        — list_components() must report that truthfully."""
        details = component_manager.get_component_details('photo')
        assert details.install_state in ('installed', 'update_available')
        assert details.size_mb > 0
        assert details.technical_name == 'nomos-webphoto'
        assert details.license  # real license string, not empty

    def test_music_reports_a_real_conditional_license_string(self):
        details = component_manager.get_component_details('music')
        assert 'condicional' in details.license.lower()

    def test_unknown_component_raises(self):
        with pytest.raises(ComponentNotFoundError):
            component_manager.get_component_details('not-a-real-component')


class TestAudioComponentsRefuseAutomatedActions:
    def test_install_speech_refuses_with_an_actionable_message(self):
        with pytest.raises(ComponentActionUnsupportedError, match='pip install'):
            component_manager.install_component('speech')

    def test_delete_music_refuses(self):
        with pytest.raises(ComponentActionUnsupportedError):
            component_manager.delete_component('music')


@pytest.mark.slow
class TestInstallUpdateDeleteRoundTrip:
    """Real network download + real SHA-256 verify + real file deletion,
    isolated to a temp models_dir so the shared models/ cache other tests
    depend on is never touched."""

    def test_install_then_delete_a_real_small_model(self, tmp_path, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, 'models_dir', str(tmp_path))

        before = component_manager.get_component_details('anime_image')
        assert before.install_state == 'not_installed'
        assert before.size_mb == 0

        installed = component_manager.install_component('anime_image')
        assert installed.install_state == 'installed'
        assert installed.size_mb > 0

        deleted = component_manager.delete_component('anime_image')
        assert deleted.install_state == 'not_installed'
