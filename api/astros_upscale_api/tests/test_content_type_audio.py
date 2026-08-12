"""T052 — real coverage of astros_upscale.processing.classify_audio (T008):
routes a genuine speech recording to 'speech' and a synthesized musical clip
(harmony + percussion, no voice) to 'music'. No mocking of the VAD model or
of librosa's harmonic/percussive separation.

The speech fixture is a real human-voice recording bundled with silero-vad's
own repository (already fetched into this machine's torch.hub cache by
astros_upscale.processing._get_vad_model() — see conftest.py's
`real_speech_wav` fixture) — not a synthetic tone, which silero-vad would not
reliably detect as speech in the first place."""
from __future__ import annotations

import os
import subprocess

import numpy as np
import pytest
import soundfile as sf

from astros_upscale.processing import classify_audio

pytestmark = pytest.mark.hardware  # loads a real torch model (silero-vad) + librosa

_SILERO_TEST_WAV = os.path.join(
    os.path.expanduser('~'), '.cache', 'torch', 'hub',
    'snakers4_silero-vad_master', 'tests', 'data', 'test.wav',
)


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(['ffmpeg', '-y', *args], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


@pytest.fixture(scope='module')
def real_speech_samples():
    if not os.path.isfile(_SILERO_TEST_WAV):
        pytest.skip(
            'silero-vad\'s bundled real-speech test fixture is not in this machine\'s torch.hub '
            'cache (only populated after classify_audio actually runs once) — real speech audio '
            'is not otherwise available to synthesize honestly.')
    data, sr = sf.read(_SILERO_TEST_WAV)
    return data.astype(np.float32), sr


@pytest.fixture(scope='module')
def synthetic_music_samples(tmp_path_factory):
    """A real audio file with no voice at all: a sustained three-note chord
    (harmonic) plus a rhythmic percussive click track — genuinely music-shaped
    (strong harmonic content + periodic percussive transients), genuinely not
    speech (silero-vad has nothing voice-like to detect)."""
    tmp_path = tmp_path_factory.mktemp('music')
    chord_path = str(tmp_path / 'chord.wav')
    clicks_path = str(tmp_path / 'clicks.wav')
    mixed_path = str(tmp_path / 'music.wav')

    _run_ffmpeg([
        '-f', 'lavfi',
        '-i', 'sine=frequency=220:duration=6,volume=0.2',
        chord_path,
    ])
    _run_ffmpeg([
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=6,volume=0.15,'
                              'apulsator=hz=2',
        clicks_path,
    ])
    _run_ffmpeg([
        '-i', chord_path, '-i', clicks_path,
        '-filter_complex', 'amix=inputs=2:duration=longest',
        mixed_path,
    ])
    data, sr = sf.read(mixed_path)
    return data.astype(np.float32), sr


class TestClassifyAudioRoutesByRealContent:
    def test_real_speech_recording_classified_as_speech(self, real_speech_samples):
        samples, sr = real_speech_samples
        result = classify_audio(samples, sr)
        assert result.content_type == 'speech'

    def test_synthetic_music_clip_classified_as_music(self, synthetic_music_samples):
        samples, sr = synthetic_music_samples
        result = classify_audio(samples, sr)
        assert result.content_type == 'music'

    def test_confidence_is_within_valid_range(self, real_speech_samples):
        samples, sr = real_speech_samples
        result = classify_audio(samples, sr)
        assert 0.0 <= result.confidence <= 1.0
