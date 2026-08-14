"""T068 — real coverage of processing.py. list_components()/
get_component_details() run against the real models/ directory (no mocking
of file presence or license lookups) — the install round trip uses a real,
temporary models_dir so it can perform a genuine download + SHA-256 verify
without touching the shared models/ cache other tests rely on."""
from __future__ import annotations

import pytest

from app import processing
from app.config import settings
from app.processing import (
    CAPABILITY_LABELS,
    ComponentActionUnsupportedError,
    ComponentNotFoundError,
)


class TestListComponents:
    def test_returns_exactly_the_six_content_type_components(self):
        components = processing.list_components()
        assert {c.id for c in components} == set(CAPABILITY_LABELS)

    def test_never_exposes_a_raw_model_identifier_as_the_capability_label(self):
        """FR-009/FR-063 — capability_label must be a human sentence, never
        an internal engine_ref like 'nomos-webphoto' or 'super-voz'."""
        from app.licensing import _CONTENT_TYPE_IMPLEMENTATIONS

        components = processing.list_components()
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
        details = processing.get_component_details('photo')
        assert details.install_state in ('installed', 'update_available')
        assert details.size_mb > 0
        assert details.technical_name == 'nomos-webphoto'
        assert details.license  # real license string, not empty

    def test_music_reports_a_real_conditional_license_string(self):
        details = processing.get_component_details('music')
        assert 'condicional' in details.license.lower()

    def test_unknown_component_raises(self):
        with pytest.raises(ComponentNotFoundError):
            processing.get_component_details('not-a-real-component')


class TestAudioComponentsInstallViaRealPip:
    """speech/music share one pyproject.toml [audio] extra — install/update
    run a real `pip install <repo>[audio]` (subprocess.run is the only
    thing worth mocking here: actually invoking pip/git in a unit test
    would be slow and network-dependent, same reasoning as the `slow`
    marker on the image/video download round trip below)."""

    @pytest.fixture(autouse=True)
    def plenty_of_disk_space(self, monkeypatch):
        # Real disk_usage() would make these tests flaky depending on how
        # full the machine running them happens to be — the low-space path
        # itself is covered separately below with a real mock.
        class Usage:
            free = 100 * 1024 * 1024 * 1024

        monkeypatch.setattr(processing.shutil, 'disk_usage', lambda path: Usage())

    def test_install_refuses_when_disk_space_is_low(self, monkeypatch):
        """A real incident: an unmocked audio install once filled a dev
        machine's C: drive to 0 bytes free mid-session. This is the guard
        that must stop that from happening again."""

        class LowUsage:
            free = 500 * 1024 * 1024  # 500 MiB, below the 3 GiB floor

        monkeypatch.setattr(processing.shutil, 'disk_usage', lambda path: LowUsage())
        with pytest.raises(ComponentActionUnsupportedError, match='[Ee]spaço em disco'):
            processing.install_component('speech')

    def test_install_speech_runs_pip_install_of_the_shared_extra(self, monkeypatch):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)

            class Result:
                returncode = 0
                stdout = ''
                stderr = ''

            return Result()

        monkeypatch.setattr(processing.subprocess, 'run', fake_run)

        result = processing.install_component('speech')

        assert len(calls) == 1
        cmd = calls[0]
        assert cmd[0] == processing.sys.executable
        assert cmd[1:4] == ['-m', 'pip', 'install']
        assert cmd[-1].endswith('[audio]')
        assert result.id == 'speech'

    def test_update_speech_runs_pip_install_with_upgrade_flag(self, monkeypatch):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)

            class Result:
                returncode = 0
                stdout = ''
                stderr = ''

            return Result()

        monkeypatch.setattr(processing.subprocess, 'run', fake_run)

        processing.update_component('speech')

        assert '--upgrade' in calls[0]

    def test_install_music_refuses_no_pip_involved(self, monkeypatch):
        """specs/006-audio-engine-masterizacao: SonicMaster runs from an
        isolated venv the operator sets up manually (api/README.md), never
        pip-installed into this process — unlike speech, which still shares
        the [audio] extra. Regression test for a real bug: this used to run
        `_pip_install_audio_extra()` (a no-op for SonicMaster, which was
        never in that extra) and then re-check the stale
        `shutil.which('inference_fullsong.py')` — always False, so the
        Components screen showed "not installed" forever even with a fully
        configured, working audio-worker."""
        calls = []
        monkeypatch.setattr(processing.subprocess, 'run', lambda *a, **k: calls.append(a))
        with pytest.raises(ComponentActionUnsupportedError, match='SonicMaster'):
            processing.install_component('music')
        assert not calls, 'install_component("music") must never shell out to pip'

    def test_update_music_refuses_no_pip_involved(self, monkeypatch):
        calls = []
        monkeypatch.setattr(processing.subprocess, 'run', lambda *a, **k: calls.append(a))
        with pytest.raises(ComponentActionUnsupportedError, match='SonicMaster'):
            processing.update_component('music')
        assert not calls

    def test_install_raises_with_real_pip_output_on_failure(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            class Result:
                returncode = 1
                stdout = ''
                stderr = 'ERROR: could not find a version that satisfies sonicmaster'

            return Result()

        monkeypatch.setattr(processing.subprocess, 'run', fake_run)

        with pytest.raises(ComponentActionUnsupportedError, match='sonicmaster'):
            processing.install_component('speech')

    def test_install_refuses_when_no_source_checkout_present(self, tmp_path, monkeypatch):
        """A packaged build has neither pip nor this repo's pyproject.toml
        next to it — must fail with an actionable message, not a raw
        FileNotFoundError from pip itself. `speech` (not `music`): only
        speech still installs via this pip path."""
        monkeypatch.setattr(processing, '_REPO_ROOT', tmp_path)
        with pytest.raises(ComponentActionUnsupportedError, match='pip install astros_upscale'):
            processing.install_component('speech')

@pytest.mark.slow
class TestInstallRoundTrip:
    """Real network download + real SHA-256 verify, isolated to a temp
    models_dir so the shared models/ cache other tests depend on is never
    touched."""

    def test_install_a_real_small_model(self, tmp_path, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, 'models_dir', str(tmp_path))

        before = processing.get_component_details('anime_image')
        assert before.install_state == 'not_installed'
        assert before.size_mb == 0

        installed = processing.install_component('anime_image')
        assert installed.install_state == 'installed'
        assert installed.size_mb > 0
