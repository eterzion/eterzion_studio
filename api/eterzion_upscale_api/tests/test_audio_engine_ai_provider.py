"""Tests for app.audio_engine.ai_provider — SonicMasterProvider, with a fake
worker supervisor (no real GPU/checkpoint/torch — those require the isolated
audio-worker venv, exercised manually per quickstart.md, not in CI)."""
from __future__ import annotations

import pytest

from app.audio_engine import ai_provider
from app.audio_engine.ai_provider import SonicMasterProvider, build_prompt
from app.audio_engine.analyzer import ProblemDetection
from app.config import settings


class _FakeSupervisor:
    def __init__(self):
        self.ensure_started_calls = 0
        self.restore_calls = []
        self.terminated = False

    def ensure_started(self):
        self.ensure_started_calls += 1

    def restore_audio(self, **payload):
        self.restore_calls.append(payload)
        return payload['output_path']

    def terminate(self):
        self.terminated = True


class TestBuildPrompt:
    def test_maps_dominant_problems_to_phrases(self):
        problems = ProblemDetection(
            reverb_severity=0.0, clipping_severity=0.9, distortion_severity=0.9,
            tonal_imbalance_severity=0.0, stereo_imbalance_severity=0.0, noise_severity=0.0,
            hum_60hz_detected=False, requires_ai_restoration=True,
            dominant_problems=['clipping_severity', 'distortion_severity'],
        )
        prompt = build_prompt(problems)
        assert 'clipping' in prompt
        assert 'preserving' in prompt  # FR-009 suffix always present

    def test_falls_back_to_general_restoration_when_no_dominant_problem(self):
        problems = ProblemDetection(
            reverb_severity=0.0, clipping_severity=0.0, distortion_severity=0.0,
            tonal_imbalance_severity=0.0, stereo_imbalance_severity=0.0, noise_severity=0.0,
            hum_60hz_detected=False, requires_ai_restoration=False, dominant_problems=[],
        )
        assert 'general music restoration' in build_prompt(problems)


class TestIsAvailable:
    def test_false_when_audio_worker_python_unset(self, monkeypatch):
        monkeypatch.setattr(settings, 'audio_worker_python', '')
        assert SonicMasterProvider().is_available() is False

    def test_false_when_interpreter_path_does_not_exist(self, monkeypatch):
        monkeypatch.setattr(settings, 'audio_worker_python', 'C:/definitely/not/real/python.exe')
        assert SonicMasterProvider().is_available() is False

    def test_false_when_checkpoint_missing(self, monkeypatch, tmp_path):
        fake_python = tmp_path / 'python.exe'
        fake_python.write_bytes(b'')
        monkeypatch.setattr(settings, 'audio_worker_python', str(fake_python))
        monkeypatch.setattr(settings, 'audio_worker_checkpoint', str(tmp_path / 'missing.safetensors'))
        assert SonicMasterProvider().is_available() is False

    def test_true_when_files_present_and_gpu_has_enough_vram(self, monkeypatch, tmp_path):
        """FR-017 — reuses eterzion_upscale.processing.detect_hardware() (Princípio
        VII) rather than duplicating GPU detection; this test's own environment
        may or may not have a real GPU, so the hardware check itself is faked
        here (real hardware detection is already covered by eterzion_upscale's
        own test suite, not re-tested by this module)."""
        import app.audio_engine.ai_provider as ai_provider_module
        from eterzion_upscale.processing import HardwareCapability

        fake_python = tmp_path / 'python.exe'
        fake_python.write_bytes(b'')
        ckpt = tmp_path / 'model.safetensors'
        ckpt.write_bytes(b'')
        monkeypatch.setattr(settings, 'audio_worker_python', str(fake_python))
        monkeypatch.setattr(settings, 'audio_worker_checkpoint', str(ckpt))

        fake_hw = HardwareCapability(
            cpu_cores=8, ram_total_mb=16000, ram_available_mb=8000,
            gpu_present=True, gpu_vendor='nvidia', vram_total_mb=8000, vram_available_mb=6000,
        )
        import eterzion_upscale.processing as processing_module
        monkeypatch.setattr(processing_module, 'detect_hardware', lambda: fake_hw)

        assert SonicMasterProvider().is_available() is True

    def test_false_when_gpu_absent(self, monkeypatch, tmp_path):
        from eterzion_upscale.processing import HardwareCapability
        import eterzion_upscale.processing as processing_module

        fake_python = tmp_path / 'python.exe'
        fake_python.write_bytes(b'')
        ckpt = tmp_path / 'model.safetensors'
        ckpt.write_bytes(b'')
        monkeypatch.setattr(settings, 'audio_worker_python', str(fake_python))
        monkeypatch.setattr(settings, 'audio_worker_checkpoint', str(ckpt))
        no_gpu = HardwareCapability(
            cpu_cores=8, ram_total_mb=16000, ram_available_mb=8000,
            gpu_present=False, gpu_vendor='unknown', vram_total_mb=None, vram_available_mb=None,
        )
        monkeypatch.setattr(processing_module, 'detect_hardware', lambda: no_gpu)
        assert SonicMasterProvider().is_available() is False

    def test_false_when_vram_insufficient(self, monkeypatch, tmp_path):
        from eterzion_upscale.processing import HardwareCapability
        import eterzion_upscale.processing as processing_module

        fake_python = tmp_path / 'python.exe'
        fake_python.write_bytes(b'')
        ckpt = tmp_path / 'model.safetensors'
        ckpt.write_bytes(b'')
        monkeypatch.setattr(settings, 'audio_worker_python', str(fake_python))
        monkeypatch.setattr(settings, 'audio_worker_checkpoint', str(ckpt))
        low_vram = HardwareCapability(
            cpu_cores=8, ram_total_mb=16000, ram_available_mb=8000,
            gpu_present=True, gpu_vendor='nvidia', vram_total_mb=2000, vram_available_mb=1500,
        )
        monkeypatch.setattr(processing_module, 'detect_hardware', lambda: low_vram)
        assert SonicMasterProvider().is_available() is False


class TestRestore:
    def test_restore_sends_the_expected_payload(self, monkeypatch, tmp_path):
        fake = _FakeSupervisor()
        monkeypatch.setattr(ai_provider, 'get_audio_worker_supervisor', lambda: fake, raising=False)
        import app.jobs as jobs_module
        monkeypatch.setattr(jobs_module, 'get_audio_worker_supervisor', lambda: fake)
        ckpt = tmp_path / 'model.safetensors'
        ckpt.write_bytes(b'')
        monkeypatch.setattr(settings, 'audio_worker_checkpoint', str(ckpt))

        provider = SonicMasterProvider()
        out = provider.restore(str(tmp_path / 'in.wav'), 'restore clipping', strength=75)

        assert fake.restore_calls, 'restore_audio was never called'
        payload = fake.restore_calls[0]
        assert payload['prompt'] == 'restore clipping'
        assert payload['ckpt'] == str(ckpt)
        assert payload['num_inference_steps'] == 14  # strength=75 profile
        assert out == payload['output_path']

    def test_restore_sends_hf_token_from_settings_explicitly(self, monkeypatch, tmp_path):
        """Regression test: HF_TOKEN reaching the audio-worker via subprocess
        environment inheritance proved unreliable in real operator testing
        (Windows terminal/session quirks) — the token is now read once by the
        main process (Settings, HF_TOKEN unprefixed) and passed explicitly in
        the IPC payload, same as ckpt/prompt/output_path."""
        fake = _FakeSupervisor()
        import app.jobs as jobs_module
        monkeypatch.setattr(jobs_module, 'get_audio_worker_supervisor', lambda: fake)
        ckpt = tmp_path / 'model.safetensors'
        ckpt.write_bytes(b'')
        monkeypatch.setattr(settings, 'audio_worker_checkpoint', str(ckpt))
        monkeypatch.setattr(settings, 'hf_token', 'hf_fake_token_value')

        provider = SonicMasterProvider()
        provider.restore(str(tmp_path / 'in.wav'), 'restore clipping', strength=50)

        assert fake.restore_calls[0]['hf_token'] == 'hf_fake_token_value'

    def test_strength_zero_uses_minimal_inference_profile(self, monkeypatch, tmp_path):
        fake = _FakeSupervisor()
        import app.jobs as jobs_module
        monkeypatch.setattr(jobs_module, 'get_audio_worker_supervisor', lambda: fake)
        ckpt = tmp_path / 'model.safetensors'
        ckpt.write_bytes(b'')
        monkeypatch.setattr(settings, 'audio_worker_checkpoint', str(ckpt))

        provider = SonicMasterProvider()
        provider.restore(str(tmp_path / 'in.wav'), 'x', strength=0)
        assert fake.restore_calls[0]['num_inference_steps'] == 0


class TestLazyLoadingAndReuse:
    """FR-019 — the worker isn't spawned until first real use, and reused
    (not re-spawned) across subsequent operations."""

    def test_initialize_is_not_called_by_the_constructor(self, monkeypatch):
        calls = []

        def fake_get_supervisor():
            calls.append(1)
            return _FakeSupervisor()

        import app.jobs as jobs_module
        monkeypatch.setattr(jobs_module, 'get_audio_worker_supervisor', fake_get_supervisor)
        SonicMasterProvider()
        assert calls == []

    def test_two_restores_reuse_the_worker_without_respawning(self, monkeypatch, tmp_path):
        fake = _FakeSupervisor()
        import app.jobs as jobs_module
        monkeypatch.setattr(jobs_module, 'get_audio_worker_supervisor', lambda: fake)
        ckpt = tmp_path / 'model.safetensors'
        ckpt.write_bytes(b'')
        monkeypatch.setattr(settings, 'audio_worker_checkpoint', str(ckpt))

        provider = SonicMasterProvider()
        provider.restore(str(tmp_path / 'in.wav'), 'a', strength=50)
        provider.restore(str(tmp_path / 'in2.wav'), 'b', strength=50)

        assert fake.ensure_started_calls == 1  # WorkerSupervisor.ensure_started() is itself
        # idempotent, but initialize() must only be invoked once from this provider's side.
        assert len(fake.restore_calls) == 2
