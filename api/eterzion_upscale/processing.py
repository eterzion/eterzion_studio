"""Model registry, tiled inference, content-type classification, face enhancement,
hardware detection and audio-enhancement engines. Consolidates what were
`core.py`, `audio.py`, `content_type.py`, `face_enhance.py`, `hardware.py` and
`legacy_identifiers.py` (Constitution Princípio XI).
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from urllib.parse import urlparse

import cv2
import numpy as np
import psutil
import torch
from spandrel import ModelLoader
from torch.nn import functional as F

from .media import (download_with_fallback, has_ffmpeg, load_file_from_url,
                    local_file_status, run_ffmpeg, sha256_of_file)

# ------------------------------- removed model identifiers ------------------------------- #
#
# Identifiers that used to be valid entries in ``MODELS`` and were removed —
# either for a rejected commercial licence (docs/models/MODEL_LICENSES.md) or because
# the registry was reduced to one implementation per content type (FR-095).
#
# Existing job history — persisted client-side in the desktop app's localStorage, not
# in this process's memory — can still reference these. FR-048 requires that old
# history not break when its identifier no longer resolves. This is the single
# place both the API (graceful error instead of a raw KeyError) and any future
# migration tooling look up "was this a real, known identifier that got removed" vs.
# "this was never valid at all".

# key: the old MODELS identifier. value: why it's gone, in plain language —
# never re-exposes the rejected model's own name/architecture, per Constitution
# Principle V.
REMOVED_MODEL_IDENTIFIERS: dict[str, str] = {
    'ultrasharp': 'Licença não permite uso comercial',
    'animesharp': 'Licença não permite uso comercial',
    'nmkd-siax': 'Licença não verificada por fonte oficial',
    'nmkd-superscale': 'Licença não verificada por fonte oficial',
    'liveaction-span': 'Licença não permite uso comercial',
    # T023/T024: registro reduzido a uma implementação por content_type (FR-095)
    # com base no benchmark real (docs/models/BENCHMARK_RESULTS.md) — estes
    # tinham licença válida, mas perderam para nomos-webphoto/hfa2k-span.
    'realesrgan-x4': 'Substituído pelo resultado do benchmark de perfis',
    'realesrgan-x2': 'Substituído pelo resultado do benchmark de perfis',
    'realesr-general': 'Substituído pelo resultado do benchmark de perfis',
    'realesrnet-x4': 'Substituído pelo resultado do benchmark de perfis',
    'nomos2-dat2': 'Substituído pelo resultado do benchmark de perfis',
    'realesrgan-anime': 'Substituído pelo resultado do benchmark de perfis',
    # Resíduo da mesma redução: continuaram em MODELS depois do T023/T024, mas
    # nenhum content_type os aponta, e o nome que chega ao load_model é sempre
    # `pipeline.engine_ref` (jobs.py) — vindo de _CONTENT_TYPE_IMPLEMENTATIONS.
    # Ou seja: estavam no catálogo, tinham licença registrada, e nenhum caminho
    # de execução chegava neles. Dois dos quatro arquivos ainda iam embarcados
    # no instalador (66 MB) sem nunca serem carregados.
    'hfa2k-avc': 'Substituído pelo resultado do benchmark de perfis',
    'nomosuni-span': 'Substituído pelo resultado do benchmark de perfis',
    'denoise': 'A limpeza 1x saiu do registro: nenhum content_type a seleciona',
    'dejpg': 'A limpeza 1x saiu do registro: nenhum content_type a seleciona',
    'deh264': 'A limpeza 1x saiu do registro: nenhum content_type a seleciona',
}


def is_removed_identifier(identifier: str) -> bool:
    return identifier in REMOVED_MODEL_IDENTIFIERS


def removal_reason(identifier: str) -> str | None:
    return REMOVED_MODEL_IDENTIFIERS.get(identifier)


# ------------------------------- hardware detection ------------------------------- #
#
# Real hardware capability detection — CPU, RAM, GPU/VRAM, and the encoders/decoders
# FFmpeg actually has available on this machine. Nothing here is a fixed constant standing
# in for detection: every field is either measured, or explicitly None when it can't be
# measured on this hardware (see HardwareCapability.gpu_vendor for the honest-unknown case).
#
# Only NVIDIA VRAM is queryable today, via pynvml (research.md R4) — there is no mature,
# widely-adopted equivalent for AMD/Intel in the Python ecosystem. That's a real limitation,
# not an oversight: callers must treat vram_total_mb/vram_available_mb as None-able and
# degrade gracefully (see profile resolution in eterzion_upscale_api), not assume every GPU
# reports VRAM.


@dataclass
class HardwareCapability:
    cpu_cores: int
    ram_total_mb: int
    ram_available_mb: int
    gpu_present: bool
    gpu_vendor: str  # 'nvidia' | 'unknown'
    vram_total_mb: int | None
    vram_available_mb: int | None
    ffmpeg_encoders: list[str] = field(default_factory=list)
    ffmpeg_decoders: list[str] = field(default_factory=list)


def _detect_nvidia_vram() -> tuple[int | None, int | None]:
    """Returns (total_mb, available_mb) for the first NVIDIA GPU, or (None, None) if
    pynvml is unavailable or no NVIDIA device is present. Falls back to torch.cuda's
    total-memory figure (no "available" breakdown) when pynvml itself can't be used —
    still better than nothing, since torch is already a hard dependency."""
    try:
        import pynvml

        pynvml.nvmlInit()
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            return int(info.total / (1024 * 1024)), int(info.free / (1024 * 1024))
        finally:
            pynvml.nvmlShutdown()
    except Exception:
        if torch.cuda.is_available():
            total = torch.cuda.get_device_properties(0).total_memory
            return int(total / (1024 * 1024)), None
        return None, None


def _detect_gpu() -> tuple[bool, str, int | None, int | None]:
    if not torch.cuda.is_available():
        return False, 'unknown', None, None
    total_mb, available_mb = _detect_nvidia_vram()
    vendor = 'nvidia' if total_mb is not None else 'unknown'
    return True, vendor, total_mb, available_mb


def _list_ffmpeg_codecs(flag: str) -> list[str]:
    """Parses `ffmpeg -encoders`/`-decoders` output. Returns an empty list — never raises —
    when ffmpeg isn't on PATH; callers already have to handle "no ffmpeg" as a real
    possibility (see media.py)."""
    ffmpeg_bin = shutil.which('ffmpeg')
    if not ffmpeg_bin:
        return []
    try:
        result = subprocess.run(
            [ffmpeg_bin, '-hide_banner', flag], capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    codecs = []
    flag_re = re.compile(r'^[VAS][F.][S.][X.][B.][D.]$')
    for line in result.stdout.splitlines():
        line = line.strip()
        # Real rows look like "V....D libx264   description". The legend rows above them
        # (e.g. "V..... = Video") have an IDENTICAL flag-field shape — an all-dots flag
        # field is a legitimate "no special capabilities" codec too — so the flag regex
        # alone can't tell them apart. What does: legend rows are always exactly
        # "<flags> = <word>", i.e. their second token is the literal "=".
        parts = line.split(None, 2)
        if len(parts) >= 2 and flag_re.match(parts[0]) and parts[1] != '=':
            codecs.append(parts[1])
    return codecs


def detect_hardware() -> HardwareCapability:
    """The single entry point profile resolution and the capacity-check path call.
    Always returns a real, freshly-measured snapshot — never cached across calls, since
    available RAM/VRAM genuinely changes between jobs."""
    gpu_present, gpu_vendor, vram_total_mb, vram_available_mb = _detect_gpu()
    vmem = psutil.virtual_memory()
    return HardwareCapability(
        cpu_cores=psutil.cpu_count(logical=True) or 1,
        ram_total_mb=int(vmem.total / (1024 * 1024)),
        ram_available_mb=int(vmem.available / (1024 * 1024)),
        gpu_present=gpu_present,
        gpu_vendor=gpu_vendor,
        vram_total_mb=vram_total_mb,
        vram_available_mb=vram_available_mb,
        ffmpeg_encoders=_list_ffmpeg_codecs('-encoders'),
        ffmpeg_decoders=_list_ffmpeg_codecs('-decoders'),
    )


# ------------------------------- content-type classification ------------------------------- #
#
# Automatic content-type classification — DSP only for images (research.md R1), a small
# VAD model plus DSP for audio (research.md R2). Neither uses a learned image classifier:
# the Constitution's "No AI Without Benefit" principle ruled that out once the DSP heuristic
# proved sufficient in practice, and it also sidesteps every licence question a trained
# classifier's weights would raise.
#
# Classification is a starting point the person can always override (FR-096) — it does not
# need to be perfect, only good enough that most people never have to correct it.

ImageContentType = str  # 'photo' | 'pixel_art' | 'anime_image'
AudioContentType = str  # 'speech' | 'music'


@dataclass
class ImageClassification:
    content_type: ImageContentType
    confidence: float  # 0..1, informational only — never surfaced as a raw number to the user


# Threshold for _pixel_run_length(). 0.08 was picked from the measurement
# described in that function: it is the point where recall is still useful and
# false positives are zero on the control set, including UI icons.
_PIXEL_ART_RUN_LENGTH = 0.08


def _pixel_run_length(image: np.ndarray) -> float:
    """Mean length of runs of identical pixels along a row, over the width.

    This is what separates art drawn on a grid from everything else. In pixel
    art a colour is repeated across whole blocks, so runs are long relative to
    the picture. Anything with antialiasing — a photograph, a rasterised vector
    icon — changes value almost every pixel, so runs are near 1 and the ratio
    collapses.

    Measured over 200 of the owner's real icons against a control set that
    deliberately included modern UI icons (small, few colours, with alpha — a
    naive detector's worst case): a threshold of 0.08 catches 69% of the pixel
    art and none of the controls. Recall is deliberately the side that gives:
    when this fires it is right, and when it does not the normal photo/anime
    classification still runs.
    """
    if image.ndim == 3:
        grey = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
    else:
        grey = image
    if grey.size == 0 or grey.shape[1] < 2:
        return 0.0

    # Every 16th row is plenty and keeps this O(1) in picture height.
    step = max(1, grey.shape[0] // 16)
    ratios = []
    for row in grey[::step]:
        changes = np.nonzero(np.diff(row.astype(np.int16)))[0]
        if len(changes) == 0:
            ratios.append(1.0)
            continue
        runs = np.diff(np.concatenate(([0], changes + 1, [len(row)])))
        ratios.append(float(runs.mean()) / len(row))
    return float(np.mean(ratios)) if ratios else 0.0


def classify_image(image: np.ndarray) -> ImageClassification:
    """Anime/illustration art has three telltale signals real photos rarely share all of:
    high saturation, large flat colour regions, and sparse-but-sharp edges (flat shading +
    clean linework, vs. a photo's continuous tonal gradients and sensor/lens noise).
    """
    # 16-bit input reached cvtColor(BGR2HSV) and raised: that conversion only
    # accepts 8-bit and 32-bit float. A 16-bit PNG is a normal thing to be
    # handed, and detection crashing on it took the whole job down.
    if image.dtype == np.uint16:
        image = (image >> 8).astype(np.uint8)
    elif image.dtype != np.uint8:
        image = np.clip(image, 0, 255).astype(np.uint8)

    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

    # Pixel art first, and it short-circuits: it is not a kind of illustration
    # to be scored against photography, it is the case where no model should
    # run at all (see licensing.MODEL_FREE_CONTENT_TYPES). Checking it after
    # the anime score would mean asking "how anime is this icon" — the wrong
    # question, and the one that had these files landing on the model that
    # measured worst for them.
    run_length = _pixel_run_length(image)
    if run_length > _PIXEL_ART_RUN_LENGTH:
        return ImageClassification('pixel_art', confidence=min(run_length / 0.2, 1.0))

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mean_saturation = float(hsv[:, :, 1].mean()) / 255.0

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 160)
    edge_density = float(np.count_nonzero(edges)) / edges.size

    # LAB color-block ratio: quantize to 16 buckets per channel and measure how much of the
    # image falls into its single most common colour — flat-shaded art scores high here.
    #
    # Each channel quantizes to 0..15, so the three fit losslessly in one 12-bit
    # code and the histogram is a plain bincount over 4096 buckets. The obvious
    # `np.unique(pixels, axis=0, return_counts=True)` computes the identical
    # counts but has to lexicographically sort every pixel row: ~11s for a 12 MP
    # photo, which is most of what made content-type detection feel slow.
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    quantized = (lab // 16).astype(np.uint32)
    codes = (quantized[:, :, 0] << 8) | (quantized[:, :, 1] << 4) | quantized[:, :, 2]
    counts = np.bincount(codes.ravel(), minlength=1 << 12)
    dominant_block_ratio = float(counts.max()) / codes.size

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


# How much audio classify_audio() actually looks at. 30s is far more than the
# classifier needs to separate speech from music, and bounds the cost for a
# full-length track.
_CLASSIFY_WINDOW_SECONDS = 30


def _harmonic_energy_ratio(
    samples: np.ndarray,
    n_fft: int = 2048,
    hop_length: int = 512,
    kernel_size: int = 31,
    power: float = 2.0,
) -> float:
    """Fracao da energia que e' harmonica, pela separacao harmonico/percussivo.

    Mesmo metodo de Fitzgerald (2010) que o `librosa.effects.hpss` implementa, e
    com os mesmos parametros: som harmonico e' estavel ao longo do TEMPO (uma
    nota sustentada ocupa a mesma raia por varios frames), som percussivo e'
    estavel ao longo da FREQUENCIA (um transiente espalha energia por todo o
    espectro num frame so). Filtro de mediana em cada eixo separa os dois, e as
    mascaras de Wiener repartem a energia.

    Substituiu o `librosa.effects.hpss` pelo peso que o librosa 1.0 arrasta:
    `numba` (e com ele o `llvmlite`, 117 MB num unico DLL), `scikit-learn`
    (44 MB) e `joblib`, nenhum deles usado em lugar nenhum daqui. Eram ~195 MB
    liquidos de instalador para dois chamados; o outro (`resample`) o `soxr`
    atende, e este o `scipy`, que ja estava no pacote.

    Fica no dominio da frequencia de proposito: quem chama usa apenas a RAZAO
    de energia, nunca os sinais separados, entao a ISTFT -- a parte mais
    delicada de reimplementar -- nao precisa existir. Medido contra o librosa
    em fala real, musica, senoide, ruido branco e cliques: a maior divergencia
    na razao foi 0,013 (em cliques puros, onde ambos dao ~0,01 e a
    classificacao nao chega perto do limiar); nos dois casos que decidem
    alguma coisa, fala e musica, ficou em 0,0006.
    """
    from scipy.ndimage import median_filter
    from scipy.signal import stft

    n_samples = int(np.asarray(samples).size)
    # Menos de duas amostras nao tem espectro. O librosa devolvia arrays vazios
    # aqui e a soma das energias dava zero, caindo no mesmo neutro.
    if n_samples < 2:
        return 0.5

    # Um arquivo mais curto que a janela e' raro mas alcancavel: 2048 amostras
    # sao 46 ms a 44,1 kHz. O scipy encolhe o `nperseg` sozinho nesse caso e
    # NAO mexe no `noverlap`, o que estoura com "noverlap must be less than
    # nperseg" -- o librosa nao tinha esse problema porque fazia padding. Os
    # dois precisam encolher juntos.
    if n_samples < n_fft:
        n_fft = n_samples
        hop_length = max(1, n_fft // 4)

    _, _, spectrum = stft(
        samples,
        nperseg=n_fft,
        noverlap=n_fft - hop_length,
        window='hann',
        boundary='zeros',
        padded=True,
    )
    magnitude = np.abs(spectrum)

    harmonic = median_filter(magnitude, size=(1, kernel_size), mode='reflect')
    percussive = median_filter(magnitude, size=(kernel_size, 1), mode='reflect')

    harmonic_p = harmonic ** power
    percussive_p = percussive ** power
    total = harmonic_p + percussive_p
    # Onde nao ha energia nenhuma a divisao seria 0/0; 0.5 e' o valor neutro,
    # o mesmo que o ramo `else` do calculo anterior usava.
    with np.errstate(invalid='ignore', divide='ignore'):
        mask_harmonic = np.where(total > 0, harmonic_p / total, 0.5)

    harmonic_energy = float(np.sum((magnitude * mask_harmonic) ** 2))
    percussive_energy = float(np.sum((magnitude * (1.0 - mask_harmonic)) ** 2))
    total_energy = harmonic_energy + percussive_energy
    return (harmonic_energy / total_energy) if total_energy > 0 else 0.5


def classify_audio(samples: np.ndarray, sample_rate: int) -> AudioClassification:
    """Speech has continuous voice-activity and a strongly harmonic-dominant spectrum from
    vowel sounds; music has more percussive/broadband energy on average and voice activity
    that comes and goes with vocal lines rather than filling the whole clip. Combines a
    real VAD (fraction of the clip with detected speech) with harmonic/percussive
    source separation — neither signal alone is reliable, together they are.
    """
    import soxr
    import torch

    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    samples = samples.astype(np.float32)

    # Analyse a bounded window rather than the whole file. Both halves of this
    # classifier scale linearly with duration — the VAD runs one forward pass
    # per 512-sample frame, and the HPSS is an STFT plus median filtering
    # over every frame — so a full song used to cost ~10s for an answer that a
    # representative excerpt gives just as well. Taken from the middle: intros
    # are often silence or a lone instrument and misrepresent the track.
    if len(samples) > _CLASSIFY_WINDOW_SECONDS * sample_rate:
        window = int(_CLASSIFY_WINDOW_SECONDS * sample_rate)
        start = (len(samples) - window) // 2
        samples = samples[start:start + window]

    target_sr = 16000
    if sample_rate != target_sr:
        # soxr diretamente, e nao via librosa: `librosa.resample` ja usa
        # `res_type='soxr_hq'` por padrao, entao chamar soxr e' o mesmo
        # algoritmo com a mesma qualidade, sem o librosa no meio.
        vad_samples = soxr.resample(samples, sample_rate, target_sr, quality='HQ')
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

    harmonic_ratio = _harmonic_energy_ratio(samples)

    speech_score = 0.6 * speech_ratio + 0.4 * min(harmonic_ratio / 0.7, 1.0)
    if speech_score >= 0.5:
        return AudioClassification('speech', confidence=min(speech_score, 1.0))
    return AudioClassification('music', confidence=1.0 - speech_score)


# ------------------------------- audio enhancement engines ------------------------------- #
#
# Optional audio-enhancement pipeline (restoration / super-resolution).
#
# These engines are NOT spandrel .pth models — each is a separate PyTorch project
# with its own checkpoint management (downloaded by the library itself on first
# use, not tracked in this project's ``models/`` folder). They are an optional
# extra: ``pip install eterzion_upscale[audio]``.
#
# ``super-voz`` (TigreGotico/audiosronnx, wrapping the LavaSR model as ONNX —
# doesn't even need torch at runtime) is a pure-Python package with no
# upper-bound numpy pin and no native build step (no Rust, no deepspeed). It
# installs cleanly alongside the modern torch/numpy the rest of this project
# uses, and is published on PyPI as part of the ``[audio]`` extra.
#
# ``audio-enhance`` uses `astros_audio_enhance
# <https://github.com/ericinacio/astros_audio_enhance>`_ — this project's own
# maintained fork of AudioSR (Liu et al., arXiv:2309.07314), rebuilt against
# modern ``torch>=2.6``/``numpy>=2.1`` instead of upstream ``audiosr``'s
# ``numpy<=1.23.5`` pin (which has no wheels for Python 3.12+ and directly
# conflicted with this project's own ``numpy>=1.26``). It's installed from
# its git repository (not on PyPI) as part of the ``[audio]`` extra like
# everything else here — no special-cased manual install needed anymore.
#
# NOTE: ``audio-enhance`` has been exercised end-to-end (real weights, a real
# 10.24s wav, CPU inference) — 48kHz/correct-duration output confirmed.
# ``super-voz`` was written against its library's documented public API but not
# run end-to-end in this environment (large model download); treat it as
# implemented-but-unverified until run once against real weights.
#
# The ``denoiser`` (CC-BY-NC-4.0) and ``voicefixer`` (unlicensed vocoder
# checkpoint) engines were removed — see pyproject.toml's ``[audio]`` extra.

AUDIO_ENGINES = {
    'audio-enhance': {
        'category': 'Áudio/Música',
        'description': 'Super-resolução de áudio geral (música) para 48kHz',
        'package': 'astros-audio-enhance',
        'reference': 'https://github.com/ericinacio/astros_audio_enhance',
    },
    'super-voz': {
        'category': 'Áudio/Voz',
        'description': 'Super-resolução de fala (bandwidth extension) para 48kHz',
        'package': 'audiosronnx',
        'reference': 'https://github.com/TigreGotico/audiosronnx',
    },
}


class MissingAudioDependency(ImportError):
    """Raised when an audio engine's optional package is not installed."""

    def __init__(self, engine: str, package: str, original: Exception) -> None:
        super().__init__(
            f"O motor de áudio '{engine}' precisa do pacote opcional '{package}', que não está instalado.\n"
            f"Instale com: pip install eterzion_upscale[audio]\n(erro original: {original})")


def _to_wav(input_path: str) -> str:
    """Convert any audio/video input to a temporary 16-bit PCM WAV via ffmpeg."""
    if not has_ffmpeg():
        raise RuntimeError('ffmpeg não encontrado no sistema; instale-o para processar áudio.')
    tmp_wav = tempfile.mktemp(suffix='.wav')
    run_ffmpeg(lambda f: f.input(input_path).output(tmp_wav, {'vn': None, 'acodec': 'pcm_s16le'}))
    return tmp_wav


def _convert_format(wav_path: str, output_path: str) -> None:
    fmt = os.path.splitext(output_path)[1].lstrip('.').lower() or 'wav'
    if fmt == 'wav':
        # os.replace() raises WinError 17 when wav_path (tempfile, usually on the
        # system drive) and output_path land on different drives; shutil.move()
        # falls back to a copy+delete in that case instead of requiring a rename.
        shutil.move(wav_path, output_path)
        return
    run_ffmpeg(lambda f: f.input(wav_path).output(output_path))
    os.remove(wav_path)


def _enhance_audio_enhance(input_wav: str, output_wav: str) -> None:
    try:
        import soundfile as sf
        import torch
        from astros_audio_enhance import build_model, super_resolution
    except ImportError as error:
        raise MissingAudioDependency('audio-enhance', 'astros-audio-enhance', error) from error
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = build_model(device=device, model_name='basic')
    # super_resolution()'s own default is ddim_steps=200; astros_audio_enhance's CLI
    # defaults to 50 (good quality/speed tradeoff per its README) — match that instead
    # of silently taking the much slower 200-step default.
    waveform = super_resolution(model, input_wav, ddim_steps=50)
    # (batch, channels, samples) -> (samples, channels), matching astros_audio_enhance's
    # own save_wave(). generate_batch() returns a plain numpy array in practice (despite
    # save_wave() defensively calling .cpu() on it, which only applies to torch tensors).
    data = waveform[0].T
    if torch.is_tensor(data):
        data = data.cpu().numpy()
    sf.write(output_wav, data, 48000)


def _enhance_super_voz(input_wav: str, output_wav: str) -> None:
    try:
        import soundfile as sf
        from audiosronnx import load_sr
    except ImportError as error:
        raise MissingAudioDependency('super-voz', 'audiosronnx', error) from error
    model = load_sr(engine='lavasr')
    waveform = model.upscale(input_wav)
    sf.write(output_wav, waveform, 48000)


_ENGINE_FUNCS = {
    'audio-enhance': _enhance_audio_enhance,
    'super-voz': _enhance_super_voz,
}


def enhance_audio_file(input_path: str, output_path: str, engine: str) -> None:
    """Enhance the audio track/file at ``input_path`` and write the result to ``output_path``.

    ``input_path`` may be any format ffmpeg understands (wav/mp3/flac/a video file
    with an audio track...); ``output_path``'s extension picks the output format.

    Raises:
        ValueError: unknown engine name.
        MissingAudioDependency: the engine's package is not installed.
        RuntimeError: ffmpeg is missing, or conversion/processing failed.
    """
    if engine not in AUDIO_ENGINES:
        raise ValueError(f"Motor de áudio desconhecido: {engine!r}. Opções: {', '.join(AUDIO_ENGINES)}")
    if not is_engine_available(engine):
        package = AUDIO_ENGINES[engine]['package']
        raise MissingAudioDependency(engine, package, ImportError(f'package {package!r} not found'))

    tmp_in = _to_wav(input_path)
    tmp_out = tempfile.mktemp(suffix='.wav')
    try:
        _ENGINE_FUNCS[engine](tmp_in, tmp_out)
        _convert_format(tmp_out, output_path)
    finally:
        for tmp in (tmp_in, tmp_out):
            if os.path.exists(tmp):
                os.remove(tmp)


def is_engine_available(engine: str) -> bool:
    """Check whether an audio engine's optional package is importable, without importing it fully."""
    import importlib.util
    package = AUDIO_ENGINES[engine]['package']
    module_name = {
        'astros-audio-enhance': 'astros_audio_enhance',
        'audiosronnx': 'audiosronnx',
    }[package]
    return importlib.util.find_spec(module_name) is not None


# ------------------------------- face enhancement ------------------------------- #
#
# Deterministic, licence-clean replacement for GFPGAN-based face restoration.
#
# GFPGAN was removed (docs/models/MODEL_LICENSES.md §2): its top-level Apache-2.0
# licence does not cover the StyleGAN2 prior it embeds (NVIDIA Source Code
# License, non-commercial) or the DFDNet component (CC-BY-NC-SA-4.0). `facexlib`,
# which the old `face_restore.py` used for detection/alignment, was removed too —
# its own `__init__.py` imports a `tracking` submodule that pulls in SORT
# (abewley/sort), GPL-3.0, which would contaminate the entire application if
# linked into a distributed binary.
#
# This module does not reconstruct faces the way GFPGAN did — it cannot invent
# detail that was never captured. What it does: detect faces with YuNet (MIT,
# opencv_zoo — code and weights both, no dataset-provenance ambiguity), then
# apply a local, deterministic sharpen/contrast pass restricted to the face
# region and its eyes/mouth sub-regions, feathered into the rest of the image so
# there's no visible seam. Same input always produces the same output.

_YUNET_URL = 'https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx'
_YUNET_SHA256 = '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4'


class FaceEnhancer:
    """Detects faces with YuNet and sharpens each face region in place.

    Unlike the GFPGAN-based restorer this replaces, there is no per-face working
    resolution or warp/unwarp step: the enhancement is applied directly on the
    face's own pixels in the full-resolution image, so there's nothing to paste
    back and no chance of a misaligned seam from an affine warp.
    """

    def __init__(self, model_dir: str = 'models'):
        weights_path = load_file_from_url(_YUNET_URL, model_dir=model_dir,
                                           file_name='face_detection_yunet_2023mar.onnx', sha256=_YUNET_SHA256)
        self._model_path = weights_path
        self._detector = None  # built lazily, once the first image's size is known

    def _detector_for_size(self, width: int, height: int) -> cv2.FaceDetectorYN:
        if self._detector is None:
            self._detector = cv2.FaceDetectorYN.create(
                self._model_path, '', (width, height), score_threshold=0.7,
            )
        else:
            self._detector.setInputSize((width, height))
        return self._detector

    def restore(self, img_bgr: np.ndarray, strength: float = 1.0) -> tuple[np.ndarray, int]:
        """Returns (result_image, faces_found). Mirrors the old FaceRestorer's
        signature so callers (Upscaler/EterzionUpscaler) don't need to change their
        call site — only what happens to each detected face changed, not the
        contract."""
        if img_bgr.dtype != np.uint8 or img_bgr.ndim != 3 or img_bgr.shape[2] != 3:
            return img_bgr, 0

        height, width = img_bgr.shape[:2]
        detector = self._detector_for_size(width, height)
        _, faces = detector.detect(img_bgr)
        if faces is None or len(faces) == 0:
            return img_bgr, 0

        result = img_bgr.copy()
        for face in faces:
            x, y, w, h = face[0:4].astype(int)
            landmarks = face[4:14].reshape(5, 2).astype(int)  # right eye, left eye, nose, mouth corners
            x, y = max(x, 0), max(y, 0)
            w, h = max(w, 1), max(h, 1)
            if x >= width or y >= height:
                continue
            w = min(w, width - x)
            h = min(h, height - y)
            _enhance_face_region(result, x, y, w, h, landmarks, strength)

        return result, len(faces)


def _enhance_face_region(img: np.ndarray, x: int, y: int, w: int, h: int,
                          landmarks: np.ndarray, strength: float) -> None:
    """Mutates `img` in place: unsharp mask + CLAHE within the face box, extra
    sharpen on eye/mouth sub-regions (where perceived sharpness matters most),
    blended back with an elliptical feathered mask so the box edge never shows.
    """
    roi = img[y:y + h, x:x + w]
    if roi.size == 0:
        return

    blurred = cv2.GaussianBlur(roi, (0, 0), sigmaX=2)
    amount = 0.6 * strength
    sharpened = cv2.addWeighted(roi, 1 + amount, blurred, -amount, 0)

    lab = cv2.cvtColor(sharpened, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.5 * strength + 0.5, tileGridSize=(4, 4))
    l_channel = clahe.apply(l_channel)
    enhanced = cv2.cvtColor(cv2.merge((l_channel, a_channel, b_channel)), cv2.COLOR_LAB2BGR)

    for lx, ly in landmarks:
        rx, ry = lx - x, ly - y
        radius = max(w, h) // 10
        x0, x1 = max(rx - radius, 0), min(rx + radius, w)
        y0, y1 = max(ry - radius, 0), min(ry + radius, h)
        if x1 <= x0 or y1 <= y0:
            continue
        sub = enhanced[y0:y1, x0:x1]
        sub_blur = cv2.GaussianBlur(sub, (0, 0), sigmaX=1)
        enhanced[y0:y1, x0:x1] = cv2.addWeighted(sub, 1 + 0.4 * strength, sub_blur, -0.4 * strength, 0)

    mask = np.zeros((h, w), dtype=np.float32)
    cv2.ellipse(mask, (w // 2, h // 2), (max(w // 2 - 2, 1), max(h // 2 - 2, 1)), 0, 0, 360, 1.0, -1)
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=max(w, h) * 0.06)
    mask3 = mask[:, :, None]

    blended = (enhanced.astype(np.float32) * mask3 + roi.astype(np.float32) * (1 - mask3))
    img[y:y + h, x:x + w] = blended.clip(0, 255).astype(np.uint8)


# ------------------------------- model registry + upscale inference ------------------------------- #
#
# Model loading (via spandrel) and tiled inference.

# Registry of bundled models: friendly name -> download urls, sha256 checksums,
# scale, category and description. The weight files keep their original upstream
# names (they are external release artifacts); the architecture is auto-detected
# from the weights by spandrel. A sha256 of None means "not pinned yet": the
# computed hash is logged on download instead of failing.
MODELS = {
    # -------------------------- Fotos -------------------------- #
    # T023/T024: benchmark real (docs/models/BENCHMARK_RESULTS.md) elegeu este
    # como única implementação para content_type=photo (FR-095) — os outros
    # cinco candidatos que disputaram (realesrgan-x4/x2, realesr-general,
    # realesrnet-x4, nomos2-dat2) foram removidos; ver REMOVED_MODEL_IDENTIFIERS.
    'nomos-webphoto': {
        'urls': ['https://huggingface.co/Phips/4xNomosWebPhoto_RealPLKSR/resolve/main/4xNomosWebPhoto_RealPLKSR.safetensors'],
        'sha256': ['9be0228f98156a100d6636d99b373ed2785b999723f9adc4cca504329ab157f2'],
        'scale': 4,
        'category': 'Fotos',
        'description': 'Padrão para fotos reais — vencedor do benchmark de perfis (LPIPS)',
        'architecture': 'RealPLKSR',
    },
    # -------------------------- Anime -------------------------- #
    # T023/T024: vencedor do benchmark para content_type=anime_image;
    # realesrgan-anime (o outro candidato) foi removido — ver REMOVED_MODEL_IDENTIFIERS.
    'hfa2k-span': {
        'urls': ['https://huggingface.co/Phips/2xHFA2kSPAN/resolve/main/2xHFA2kSPAN.safetensors'],
        'sha256': ['616666ffaa9ccdf604e3d6b98bf1ec32c6ed08c4d36da7fed1d013843e5a45e9'],
        'scale': 2,
        'category': 'Anime',
        'description': 'SPAN — qualidade parecida ao realesrgan-anime, muito mais rápido',
        'architecture': 'SPAN',
    },
    # -------------------------- Vídeo/Anime -------------------------- #
    'realesr-animevideo': {
        'urls': ['https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth'],
        'sha256': ['b8a8376811077954d82ca3fcf476f1ac3da3e8a68a4f4d71363008000a18b75d'],
        'scale': 4,
        'category': 'Vídeo/Anime',
        'description': 'Oficial Real-ESRGAN, leve, feito para vídeo de anime',
        'architecture': 'SRVGGNetCompact',
    },
    # T045: docs/models/MODEL_LICENSES.md §3-ter — Apache-2.0 em código e
    # pesos, dataset 100% domínio público (CC0), sem ressalva de licença.
    # Variante sem denoise (mais estável entre quadros que a alternativa com
    # denoise agressivo, que não foi lançada por Phhofm neste release).
    'realplksr-video-real': {
        'urls': ['https://github.com/Phhofm/models/releases/download/'
                 '2xPublic_realplksr_dysample_layernorm_real/2xPublic_realplksr_dysample_layernorm_real.safetensors'],
        'sha256': ['5eb81e8c3e21d57b0ea2aa7931910c97c263c1f23ef9b35fabbd46e98471cd44'],
        'scale': 2,
        'category': 'Vídeo Real',
        'description': 'Padrão para vídeo real — estável entre quadros, sem denoise agressivo',
        'architecture': 'RealPLKSR (dysample, layernorm)',
    },
    # Nota: a categoria "Restauração" tinha modelos aqui
    # (nmkd-siax, nmkd-superscale) removidos por licença —
    # ver docs/models/MODEL_LICENSES.md §1/§6. `real_video` é reintroduzido
    # com um modelo aprovado em uma fase posterior (ver tasks.md T045).
}

# Old model names kept as aliases for backward compatibility. The photo/anime
# aliases that pointed at models T024 removed are gone too — REMOVED_MODEL_IDENTIFIERS
# is what gives those old names a friendly "archived" message now.
ALIASES = {
    'anime-video': 'realesr-animevideo',
    'anime-video-x4': 'realesr-animevideo',
}

DEFAULT_IMAGE_MODEL = 'nomos-webphoto'
DEFAULT_VIDEO_MODEL = 'realesr-animevideo'


def canonical_name(name_or_alias: str) -> str:
    """Resolve an alias (or already-canonical name) to its canonical registry name."""
    return ALIASES.get(name_or_alias, name_or_alias)


def _load_mirror_map(models_json: str = 'models.json') -> dict:
    """Load the mirror map generated by ``scripts/mirror_models.py``, if present.

    Returns an empty dict (no mirrors) when the file does not exist or is invalid —
    this is the normal state until someone runs the mirroring script, and downloads
    simply fall back to the original upstream URLs.
    """
    if not os.path.isfile(models_json):
        return {}
    try:
        with open(models_json, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return {entry['name']: entry for entry in data.get('models', []) if 'name' in entry}


def _urls_with_mirror(name: str, entry: dict, models_json: str) -> list[list[str]]:
    """For each file of ``entry``, return the candidate URL list: [mirror_url?, original_url]."""
    mirror_entry = _load_mirror_map(models_json).get(name)
    mirror_by_filename = {}
    if mirror_entry:
        mirror_by_filename = {f['filename']: f.get('mirror_url') for f in mirror_entry.get('files', [])}
    candidates = []
    for url in entry['urls']:
        filename = os.path.basename(urlparse(url).path)
        mirror_url = mirror_by_filename.get(filename)
        candidates.append([mirror_url, url] if mirror_url else [url])
    return candidates


def model_local_paths(name_or_path: str, model_dir: str = 'models') -> list[str]:
    """Return the local file path(s) a registered model would be cached as (no download)."""
    name = canonical_name(name_or_path)
    entry = MODELS[name]
    return [os.path.join(model_dir, os.path.basename(urlparse(u).path)) for u in entry['urls']]


def model_download_status(name_or_path: str, model_dir: str = 'models') -> tuple[bool, int]:
    """Return (fully_downloaded, total_size_in_bytes) for a registered model, without downloading."""
    name = canonical_name(name_or_path)
    entry = MODELS[name]
    total = 0
    for url in entry['urls']:
        downloaded, size = local_file_status(url, model_dir=model_dir)
        if not downloaded:
            return False, 0
        total += size
    return True, total


def model_needs_update(name_or_path: str, model_dir: str = 'models') -> bool:
    """True if the model is missing locally, or a cached file no longer matches the
    checksum currently pinned in the registry (e.g. after the registry was bumped
    to point at a newer/corrected weight file)."""
    name = canonical_name(name_or_path)
    entry = MODELS[name]
    for url, pinned_sha in zip(entry['urls'], entry['sha256']):
        path = os.path.join(model_dir, os.path.basename(urlparse(url).path))
        if not os.path.isfile(path):
            return True
        if sha256_of_file(path).lower() != pinned_sha.lower():
            return True
    return False


def update_model(name_or_path: str, model_dir: str = 'models', models_json: str = 'models.json') -> bool:
    """Bring a model's local file(s) in line with the registry: download if missing,
    or re-download if the cached file no longer matches the pinned checksum.

    Returns:
        bool: True if anything was (re)downloaded, False if it was already up to date.
    """
    name = canonical_name(name_or_path)
    entry = MODELS[name]
    changed = False
    for url, pinned_sha in zip(entry['urls'], entry['sha256']):
        path = os.path.join(model_dir, os.path.basename(urlparse(url).path))
        if os.path.isfile(path):
            if sha256_of_file(path).lower() == pinned_sha.lower():
                continue
            os.remove(path)  # stale: force a fresh download below
        changed = True
    if changed:
        resolve_model(name, model_dir=model_dir, models_json=models_json)
    return changed


def resolve_model(
        name_or_path: str,
        model_dir: str = 'models',
        denoise_strength: float | None = None,
        models_json: str = 'models.json') -> tuple[str | list[str], list[float] | None]:
    """Resolve a model name (from MODELS) or a local .pth path into loader arguments.

    When a ``models.json`` mirror map (generated by ``scripts/mirror_models.py``) is
    present, each file is downloaded from its mirror first, automatically falling
    back to the original upstream URL if the mirror is unreachable.

    Returns:
        tuple: (model_path, dni_weight) ready for EterzionUpscaler. ``model_path`` is a
        list of two paths when denoise interpolation applies.
    """
    if os.path.isfile(name_or_path):
        return name_or_path, None
    name = canonical_name(name_or_path)
    if name not in MODELS:
        reason = removal_reason(name)
        if reason is not None:
            raise ValueError(f'Modelo {name_or_path!r} não está mais disponível: {reason}. '
                             f'Reprocesse com um perfil atual (Rápido/Equilibrado/Qualidade).')
        raise ValueError(f'Modelo desconhecido: {name_or_path!r}. '
                         f'Veja os modelos disponíveis na tela de Modelos do app.')
    entry = MODELS[name]
    url_candidates = _urls_with_mirror(name, entry, models_json)
    paths = [
        download_with_fallback(candidates, model_dir=model_dir, sha256=digest)
        for candidates, digest in zip(url_candidates, entry['sha256'])
    ]
    if name == 'realesr-general' and denoise_strength is not None and denoise_strength != 1:
        # interpolate between the normal and the strong-denoise weights
        return [paths[0], paths[1]], [denoise_strength, 1 - denoise_strength]
    return paths[0], None


def load_model(name_or_path: str, model_dir: str = 'models', **kwargs) -> 'EterzionUpscaler':
    """Convenience helper: resolve a model name/path and return a ready EterzionUpscaler."""
    model_path, dni_weight = resolve_model(name_or_path, model_dir=model_dir,
                                           denoise_strength=kwargs.pop('denoise_strength', None))
    return EterzionUpscaler(model_path=model_path, dni_weight=dni_weight, **kwargs)


def _pick_device(gpu_id: int | None = None) -> torch.device:
    """Pick the best available device: CUDA > MPS (Apple Silicon) > CPU."""
    if torch.cuda.is_available():
        return torch.device(f'cuda:{gpu_id}' if gpu_id is not None else 'cuda')
    if getattr(torch.backends, 'mps', None) is not None and torch.backends.mps.is_available():
        return torch.device('mps')
    return torch.device('cpu')


class EterzionUpscaler():
    """Upscales images with a super-resolution model loaded through spandrel.

    Args:
        model_path (str | list[str]): Path to the pretrained weights (or a URL). A list of two
            paths enables deep-network interpolation controlled by ``dni_weight``.
            The architecture is auto-detected from the weights by spandrel.
        scale (int): Upsampling scale of the network. If None, the scale detected by spandrel is used.
        tile (int): Crop the input into tiles of this size to bound GPU memory use; the results
            are seamlessly merged. 0 disables tiling. Default: 0.
        tile_pad (int): Padding around each tile to remove border artifacts. Default: 10.
        pre_pad (int): Pad the input borders to avoid edge artifacts. Default: 10.
        half (bool): Use half precision. Only applied on CUDA/MPS and when the model supports it.
        compile_model (bool): Compile the network with ``torch.compile`` for faster repeated
            inference (pays a warm-up cost on the first call). Default: False.
    """

    def __init__(self,
                 model_path: str | list[str] | None = None,
                 scale: int | None = None,
                 dni_weight: list[float] | None = None,
                 tile: int = 0,
                 tile_pad: int = 10,
                 pre_pad: int = 10,
                 half: bool = False,
                 device: str | torch.device | None = None,
                 gpu_id: int | None = None,
                 compile_model: bool = False) -> None:
        self.tile_size = tile
        self.tile_pad = tile_pad
        self.pre_pad = pre_pad
        self.mod_scale = None

        self.device = _pick_device(gpu_id) if device is None else torch.device(device)

        if self.device.type == 'cuda':
            # convolution-heavy, fixed-ish shapes: let cuDNN autotune and use TF32 on Ampere+
            torch.backends.cudnn.benchmark = True
            torch.set_float32_matmul_precision('high')

        if isinstance(model_path, list):
            # deep network interpolation
            assert len(model_path) == len(dni_weight), 'model_path and dni_weight should have the same length.'
            loadnet = self.dni(model_path[0], model_path[1], dni_weight)
        else:
            if model_path.startswith('https://'):
                model_path = load_file_from_url(url=model_path)
            loadnet = torch.load(model_path, map_location=torch.device('cpu'), weights_only=True)

        # prefer to use params_ema
        if 'params_ema' in loadnet:
            loadnet = loadnet['params_ema']
        elif 'params' in loadnet:
            loadnet = loadnet['params']

        # spandrel auto-detects the architecture from the state dict
        descriptor = ModelLoader().load_from_state_dict(loadnet)
        self.descriptor = descriptor
        self.scale = scale if scale is not None else descriptor.scale

        # half precision only makes sense on GPU backends and on models that support it
        self.half = half and self.device.type in ('cuda', 'mps') and descriptor.supports_half

        descriptor.eval()
        model = descriptor.model.to(self.device, memory_format=torch.channels_last)
        if self.half:
            model = model.half()
        if compile_model and hasattr(torch, 'compile'):
            model = torch.compile(model)
        self.model = model

    def dni(self, net_a, net_b, dni_weight, key='params', loc='cpu'):
        """Deep network interpolation.

        ``Paper: Deep Network Interpolation for Continuous Imagery Effect Transition``
        """
        net_a = torch.load(net_a, map_location=torch.device(loc), weights_only=True)
        net_b = torch.load(net_b, map_location=torch.device(loc), weights_only=True)
        for k, v_a in net_a[key].items():
            net_a[key][k] = dni_weight[0] * v_a + dni_weight[1] * net_b[key][k]
        return net_a

    def pre_process(self, img):
        """Pre-process, such as pre-pad and mod pad, so that the images can be divisible
        """
        img = torch.from_numpy(np.ascontiguousarray(np.transpose(img, (2, 0, 1)))).float()
        img = img.unsqueeze(0)
        if self.device.type == 'cuda':
            img = img.pin_memory()
        self.img = img.to(self.device, non_blocking=True).to(memory_format=torch.channels_last)
        if self.half:
            self.img = self.img.half()

        # pre_pad
        if self.pre_pad != 0:
            self.img = F.pad(self.img, (0, self.pre_pad, 0, self.pre_pad), 'reflect')
        # mod pad for divisible borders
        if self.scale == 2:
            self.mod_scale = 2
        elif self.scale == 1:
            self.mod_scale = 4
        if self.mod_scale is not None:
            self.mod_pad_h, self.mod_pad_w = 0, 0
            _, _, h, w = self.img.size()
            if (h % self.mod_scale != 0):
                self.mod_pad_h = (self.mod_scale - h % self.mod_scale)
            if (w % self.mod_scale != 0):
                self.mod_pad_w = (self.mod_scale - w % self.mod_scale)
            self.img = F.pad(self.img, (0, self.mod_pad_w, 0, self.mod_pad_h), 'reflect')

    def process(self):
        # model inference
        self.output = self.model(self.img)

    def tile_process(self):
        """It will first crop input images to tiles, and then process each tile.
        Finally, all the processed tiles are merged into one images.

        Modified from: https://github.com/ata4/esrgan-launcher
        """
        batch, channel, height, width = self.img.shape
        output_height = height * self.scale
        output_width = width * self.scale
        output_shape = (batch, channel, output_height, output_width)

        # start with black image
        self.output = self.img.new_zeros(output_shape)
        tiles_x = math.ceil(width / self.tile_size)
        tiles_y = math.ceil(height / self.tile_size)

        # loop over all tiles
        for y in range(tiles_y):
            for x in range(tiles_x):
                # extract tile from input image
                ofs_x = x * self.tile_size
                ofs_y = y * self.tile_size
                # input tile area on total image
                input_start_x = ofs_x
                input_end_x = min(ofs_x + self.tile_size, width)
                input_start_y = ofs_y
                input_end_y = min(ofs_y + self.tile_size, height)

                # input tile area on total image with padding
                input_start_x_pad = max(input_start_x - self.tile_pad, 0)
                input_end_x_pad = min(input_end_x + self.tile_pad, width)
                input_start_y_pad = max(input_start_y - self.tile_pad, 0)
                input_end_y_pad = min(input_end_y + self.tile_pad, height)

                # input tile dimensions
                input_tile_width = input_end_x - input_start_x
                input_tile_height = input_end_y - input_start_y
                tile_idx = y * tiles_x + x + 1
                input_tile = self.img[:, :, input_start_y_pad:input_end_y_pad, input_start_x_pad:input_end_x_pad]

                # upscale tile
                try:
                    with torch.inference_mode():
                        output_tile = self.model(input_tile)
                except RuntimeError as error:
                    print('Error', error)
                print(f'\tTile {tile_idx}/{tiles_x * tiles_y}')
                # optional per-tile progress hook (used by the desktop API for live progress)
                tile_callback = getattr(self, 'tile_progress_callback', None)
                if tile_callback is not None:
                    tile_callback(tile_idx, tiles_x * tiles_y)

                # output tile area on total image
                output_start_x = input_start_x * self.scale
                output_end_x = input_end_x * self.scale
                output_start_y = input_start_y * self.scale
                output_end_y = input_end_y * self.scale

                # output tile area without padding
                output_start_x_tile = (input_start_x - input_start_x_pad) * self.scale
                output_end_x_tile = output_start_x_tile + input_tile_width * self.scale
                output_start_y_tile = (input_start_y - input_start_y_pad) * self.scale
                output_end_y_tile = output_start_y_tile + input_tile_height * self.scale

                # put tile into output image
                self.output[:, :, output_start_y:output_end_y,
                            output_start_x:output_end_x] = output_tile[:, :, output_start_y_tile:output_end_y_tile,
                                                                       output_start_x_tile:output_end_x_tile]

    def post_process(self):
        # remove extra pad
        if self.mod_scale is not None:
            _, _, h, w = self.output.size()
            self.output = self.output[:, :, 0:h - self.mod_pad_h * self.scale, 0:w - self.mod_pad_w * self.scale]
        # remove prepad
        if self.pre_pad != 0:
            _, _, h, w = self.output.size()
            self.output = self.output[:, :, 0:h - self.pre_pad * self.scale, 0:w - self.pre_pad * self.scale]
        return self.output

    @torch.inference_mode()
    def enhance(self,
                img: np.ndarray,
                outscale: float | None = None,
                alpha_upsampler: str = 'model') -> tuple[np.ndarray, str]:
        h_input, w_input = img.shape[0:2]
        # img: numpy
        img = img.astype(np.float32)
        if np.max(img) > 256:  # 16-bit image
            max_range = 65535
            print('\tInput is a 16-bit image')
        else:
            max_range = 255
        img = img / max_range
        if len(img.shape) == 2:  # gray image
            img_mode = 'L'
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        elif img.shape[2] == 4:  # RGBA image with alpha channel
            img_mode = 'RGBA'
            alpha = img[:, :, 3]
            img = img[:, :, 0:3]
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            if alpha_upsampler == 'model':
                alpha = cv2.cvtColor(alpha, cv2.COLOR_GRAY2RGB)
        else:
            img_mode = 'RGB'
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # ------------------- process image (without the alpha channel) ------------------- #
        self.pre_process(img)
        if self.tile_size > 0:
            self.tile_process()
        else:
            self.process()
        output_img = self.post_process()
        output_img = output_img.data.squeeze().float().cpu().clamp_(0, 1).numpy()
        output_img = np.transpose(output_img[[2, 1, 0], :, :], (1, 2, 0))
        if img_mode == 'L':
            output_img = cv2.cvtColor(output_img, cv2.COLOR_BGR2GRAY)

        # ------------------- process the alpha channel if necessary ------------------- #
        if img_mode == 'RGBA':
            if alpha_upsampler == 'model':
                self.pre_process(alpha)
                if self.tile_size > 0:
                    self.tile_process()
                else:
                    self.process()
                output_alpha = self.post_process()
                output_alpha = output_alpha.data.squeeze().float().cpu().clamp_(0, 1).numpy()
                output_alpha = np.transpose(output_alpha[[2, 1, 0], :, :], (1, 2, 0))
                output_alpha = cv2.cvtColor(output_alpha, cv2.COLOR_BGR2GRAY)
            else:  # use the cv2 resize for alpha channel
                h, w = alpha.shape[0:2]
                output_alpha = cv2.resize(alpha, (w * self.scale, h * self.scale), interpolation=cv2.INTER_LINEAR)

            # merge the alpha channel
            output_img = cv2.cvtColor(output_img, cv2.COLOR_BGR2BGRA)
            output_img[:, :, 3] = output_alpha

        # ------------------------------ return ------------------------------ #
        if max_range == 65535:  # 16-bit image
            output = (output_img * 65535.0).round().astype(np.uint16)
        else:
            output = (output_img * 255.0).round().astype(np.uint8)

        if outscale is not None and outscale != float(self.scale):
            output = cv2.resize(
                output, (
                    int(w_input * outscale),
                    int(h_input * outscale),
                ), interpolation=cv2.INTER_LANCZOS4)

        return output, img_mode
