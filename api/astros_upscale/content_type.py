"""Automatic content-type classification — DSP only for images (research.md R1), a small
VAD model plus DSP for audio (research.md R2). Neither uses a learned image classifier:
the Constitution's "No AI Without Benefit" principle ruled that out once the DSP heuristic
proved sufficient in practice, and it also sidesteps every licence question a trained
classifier's weights would raise.

Classification is a starting point the person can always override (FR-096) — it does not
need to be perfect, only good enough that most people never have to correct it.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

ImageContentType = str  # 'photo' | 'anime_image'
AudioContentType = str  # 'speech' | 'music'


@dataclass
class ImageClassification:
    content_type: ImageContentType
    confidence: float  # 0..1, informational only — never surfaced as a raw number to the user


def classify_image(image: np.ndarray) -> ImageClassification:
    """Anime/illustration art has three telltale signals real photos rarely share all of:
    high saturation, large flat colour regions, and sparse-but-sharp edges (flat shading +
    clean linework, vs. a photo's continuous tonal gradients and sensor/lens noise).
    """
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mean_saturation = float(hsv[:, :, 1].mean()) / 255.0

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 160)
    edge_density = float(np.count_nonzero(edges)) / edges.size

    # LAB color-block ratio: quantize to 16 buckets per channel and measure how much of the
    # image falls into its single most common colour — flat-shaded art scores high here.
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    quantized = (lab // 16).astype(np.uint8)
    flat_view = quantized.reshape(-1, 3)
    _, counts = np.unique(flat_view, axis=0, return_counts=True)
    dominant_block_ratio = float(counts.max()) / flat_view.shape[0]

    anime_score = (
        0.4 * min(mean_saturation / 0.55, 1.0)
        + 0.3 * min(dominant_block_ratio / 0.25, 1.0)
        + 0.3 * (1.0 - min(edge_density / 0.12, 1.0))
    )
    if anime_score >= 0.55:
        return ImageClassification('anime_image', confidence=min(anime_score, 1.0))
    return ImageClassification('photo', confidence=1.0 - anime_score)


@dataclass
class AudioClassification:
    content_type: AudioContentType
    confidence: float


_vad_model = None


def _get_vad_model():
    global _vad_model
    if _vad_model is None:
        import torch

        model, _utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad', model='silero_vad', trust_repo=True,
        )
        _vad_model = model
    return _vad_model


def classify_audio(samples: np.ndarray, sample_rate: int) -> AudioClassification:
    """Speech has continuous voice-activity and a strongly harmonic-dominant spectrum from
    vowel sounds; music has more percussive/broadband energy on average and voice activity
    that comes and goes with vocal lines rather than filling the whole clip. Combines a
    real VAD (fraction of the clip with detected speech) with librosa's harmonic/percussive
    source separation — neither signal alone is reliable, together they are.
    """
    import librosa
    import torch

    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    samples = samples.astype(np.float32)

    target_sr = 16000
    if sample_rate != target_sr:
        vad_samples = librosa.resample(samples, orig_sr=sample_rate, target_sr=target_sr)
    else:
        vad_samples = samples

    model = _get_vad_model()
    with torch.no_grad():
        tensor = torch.from_numpy(vad_samples)
        window = 512
        speech_frames = 0
        total_frames = 0
        for start in range(0, len(tensor) - window, window):
            prob = model(tensor[start:start + window], target_sr).item()
            total_frames += 1
            if prob > 0.5:
                speech_frames += 1
    speech_ratio = (speech_frames / total_frames) if total_frames else 0.0

    harmonic, percussive = librosa.effects.hpss(samples)
    harmonic_energy = float(np.sum(harmonic ** 2))
    percussive_energy = float(np.sum(percussive ** 2))
    total_energy = harmonic_energy + percussive_energy
    harmonic_ratio = (harmonic_energy / total_energy) if total_energy > 0 else 0.5

    speech_score = 0.6 * speech_ratio + 0.4 * min(harmonic_ratio / 0.7, 1.0)
    if speech_score >= 0.5:
        return AudioClassification('speech', confidence=min(speech_score, 1.0))
    return AudioClassification('music', confidence=1.0 - speech_score)
