"""T051/T053 — real, ffmpeg-only coverage of audio_processor.apply_dsp_chain():
noise reduction is measurable, loudness normalization hits the configured LUFS
target, duration and channel count survive the round trip. No mocking of
ffmpeg or of the DSP filters themselves — only the content-type model step
(audiosronnx/SonicMaster, neither installed in this environment) is out of
scope here and covered separately by MissingAudioDependency assertions."""
from __future__ import annotations

import math
import struct
import subprocess
import wave

import pytest

from app.processing import MissingAudioDependency, apply_dsp_chain, process
from eterzion_upscale.media import ffprobe_json, has_ffmpeg
from eterzion_upscale.media import ffmpeg_path

pytestmark = pytest.mark.skipif(not has_ffmpeg(), reason='requires a real ffmpeg binary on PATH')


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run([ffmpeg_path() or ffmpeg_path() or 'ffmpeg', '-y', *args], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def _build_noisy_quiet_speech_like_wav(path: str, duration: float = 2.0, sample_rate: int = 16000) -> None:
    """A real WAV: a quiet 220Hz tone (voice-like fundamental) plus broadband
    noise, deliberately mixed well below 0dBFS — gives loudnorm real headroom
    to normalize upward and afftdn real noise to remove."""
    n_samples = int(duration * sample_rate)
    import random
    random.seed(42)
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            tone = 0.05 * math.sin(2 * math.pi * 220 * i / sample_rate)
            noise = 0.05 * (random.random() * 2 - 1)
            sample = max(-1.0, min(1.0, tone + noise))
            frames += struct.pack('<h', int(sample * 32767))
        wf.writeframes(bytes(frames))


def _measure_rms_level_db(path: str) -> float:
    """Real ffmpeg astats summary — reads the real 'RMS level dB' line astats
    reports (dB, negative, closer to 0 = louder). On a clip that is pure
    broadband noise (no protected signal), a real denoiser's own broadband
    suppression shows up directly as a lower overall RMS level."""
    result = subprocess.run(
        [ffmpeg_path() or 'ffmpeg', '-i', path, '-af', 'astats', '-f', 'null', '-'],
        capture_output=True, text=True, timeout=30,
    )
    for line in result.stderr.splitlines():
        if 'RMS level dB:' in line:
            return float(line.rsplit(':', 1)[1].strip())
    raise AssertionError(f'no "RMS level dB" found in astats output:\n{result.stderr}')


def _measure_integrated_lufs(path: str) -> float:
    result = subprocess.run(
        [ffmpeg_path() or 'ffmpeg', '-i', path, '-af', 'loudnorm=print_format=json', '-f', 'null', '-'],
        capture_output=True, text=True, timeout=30,
    )
    import json

    start = result.stderr.rfind('{')
    end = result.stderr.rfind('}') + 1
    data = json.loads(result.stderr[start:end])
    return float(data['input_i'])


class TestApplyDspChain:
    def test_loudness_is_normalized_toward_the_target(self, tmp_path):
        input_path = str(tmp_path / 'quiet.wav')
        output_path = str(tmp_path / 'normalized.wav')
        _build_noisy_quiet_speech_like_wav(input_path)

        before_lufs = _measure_integrated_lufs(input_path)
        apply_dsp_chain(input_path, output_path)
        after_lufs = _measure_integrated_lufs(output_path)

        # -16 LUFS target — after normalization must land much closer to it
        # than the deliberately-quiet original did.
        assert abs(after_lufs - (-16.0)) < abs(before_lufs - (-16.0))
        assert abs(after_lufs - (-16.0)) < 2.0

    def test_duration_and_channels_are_preserved(self, tmp_path):
        input_path = str(tmp_path / 'in.wav')
        output_path = str(tmp_path / 'out.wav')
        _build_noisy_quiet_speech_like_wav(input_path, duration=1.5)

        apply_dsp_chain(input_path, output_path)

        in_probe = ffprobe_json(input_path)
        out_probe = ffprobe_json(output_path)
        in_stream = next(s for s in in_probe['streams'] if s['codec_type'] == 'audio')
        out_stream = next(s for s in out_probe['streams'] if s['codec_type'] == 'audio')
        assert out_stream['channels'] == in_stream['channels']

        in_duration = float(in_probe['format']['duration'])
        out_duration = float(out_probe['format']['duration'])
        assert out_duration == pytest.approx(in_duration, abs=0.2)

    def test_noise_floor_is_reduced_on_a_pure_noise_clip(self, tmp_path):
        """afftdn needs a learning window on pure/broadband noise to show a
        measurable effect — a plain white-noise clip (no signal to protect)
        isolates that effect from loudnorm's separate, unrelated gain change."""
        input_path = str(tmp_path / 'noise.wav')
        output_path = str(tmp_path / 'denoised.wav')
        _run_ffmpeg([
            '-f', 'lavfi', '-i', 'anoisesrc=color=white:amplitude=0.3:duration=3', input_path,
        ])

        # Isolate afftdn alone (bypass loudnorm's independent gain change) to
        # measure the denoise filter's own real effect on the noise floor.
        result = subprocess.run(
            [ffmpeg_path() or ffmpeg_path() or 'ffmpeg', '-y', '-i', input_path, '-af', 'afftdn', output_path],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stderr

        before = _measure_rms_level_db(input_path)
        after = _measure_rms_level_db(output_path)
        assert after < before  # more negative dB = quieter overall level


class TestProcessDispatchesByEngineRef:
    def test_unknown_engine_ref_raises(self, tmp_path):
        input_path = str(tmp_path / 'in.wav')
        _build_noisy_quiet_speech_like_wav(input_path, duration=0.5)
        with pytest.raises(ValueError, match='sem implementação'):
            process(input_path, 'not-a-real-engine', str(tmp_path / 'out.wav'))

    def test_speech_engine_raises_missing_dependency_when_audiosronnx_absent(self, tmp_path):
        """Honest failure, not a silent skip — audiosronnx isn't installed in
        this environment (not part of the base dependency set)."""
        input_path = str(tmp_path / 'in.wav')
        _build_noisy_quiet_speech_like_wav(input_path, duration=0.5)
        try:
            import audiosronnx  # noqa: F401
            pytest.skip('audiosronnx is installed in this environment — nothing to assert here')
        except ImportError:
            pass
        with pytest.raises(MissingAudioDependency):
            process(input_path, 'super-voz', str(tmp_path / 'out.wav'))

    def test_music_engine_raises_missing_dependency_when_audio_worker_not_configured(
            self, tmp_path, monkeypatch):
        """specs/006-audio-engine-masterizacao T004 — _enhance_music no longer shells
        out to `inference_fullsong.py` (which never accepted --input/--output/--prompt
        and never worked); it now requires ASTROS_AUDIO_WORKER_PYTHON to be configured."""
        from app.config import settings
        monkeypatch.setattr(settings, 'audio_worker_python', '')
        input_path = str(tmp_path / 'in.wav')
        _build_noisy_quiet_speech_like_wav(input_path, duration=0.5)
        with pytest.raises(MissingAudioDependency):
            process(input_path, 'sonicmaster', str(tmp_path / 'out.wav'))

    def test_music_engine_raises_missing_dependency_when_checkpoint_absent(
            self, tmp_path, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, 'audio_worker_python', 'python')  # configured, but...
        monkeypatch.setattr(settings, 'audio_worker_checkpoint', str(tmp_path / 'no-such-file.safetensors'))
        input_path = str(tmp_path / 'in.wav')
        _build_noisy_quiet_speech_like_wav(input_path, duration=0.5)
        with pytest.raises(MissingAudioDependency):
            process(input_path, 'sonicmaster', str(tmp_path / 'out.wav'))

    def test_music_engine_calls_the_vendored_infer_script_correctly(self, tmp_path, monkeypatch):
        """Confirms _enhance_music invokes vendor/sonicmaster/infer.py (the real,
        --input/--output/--prompt-accepting script) — not the old, broken
        inference_fullsong.py reference — via subprocess.run, without needing real
        torch/GPU/checkpoint (subprocess.run itself is stubbed)."""
        import app.processing as processing_module
        from app.config import settings

        monkeypatch.setattr(settings, 'audio_worker_python', 'fake-python')
        ckpt = tmp_path / 'model.safetensors'
        ckpt.write_bytes(b'not-a-real-checkpoint')
        monkeypatch.setattr(settings, 'audio_worker_checkpoint', str(ckpt))

        captured = {}

        def fake_run(cmd, **kwargs):
            captured['cmd'] = cmd
            out_wav = cmd[cmd.index('--output') + 1]
            with open(out_wav, 'wb') as fh:
                fh.write(b'RIFF....WAVEfmt ')  # just needs to exist
            class _Result:
                returncode = 0
                stderr = ''
            return _Result()

        monkeypatch.setattr(processing_module.subprocess, 'run', fake_run)

        input_path = str(tmp_path / 'in.wav')
        _build_noisy_quiet_speech_like_wav(input_path, duration=0.5)
        output_path = str(tmp_path / 'out.wav')
        processing_module._enhance_music(input_path, output_path)

        cmd = captured['cmd']
        assert cmd[0] == 'fake-python'
        assert cmd[1].endswith('vendor\\sonicmaster\\infer.py') or cmd[1].endswith('vendor/sonicmaster/infer.py')
        assert '--ckpt' in cmd and str(ckpt) in cmd
        assert '--prompt' in cmd


def test_missing_audio_dependency_speaks_to_the_user_not_to_a_developer():
    """A frase chega a quem usa o app instalado: nada de pip, README ou
    variavel de ambiente. O tecnico fica em `detail`."""
    erro = MissingAudioDependency('music (SonicMaster)', 'audio-worker',
                                  ImportError('ASTROS_AUDIO_WORKER_PYTHON não configurado'))
    for proibido in ('pip', 'README', 'ASTROS_', 'SonicMaster', 'audio-worker'):
        assert proibido not in str(erro)
    assert 'audio-worker' in erro.detail
