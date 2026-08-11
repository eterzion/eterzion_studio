"""Optional audio-enhancement pipeline (denoise / restoration / super-resolution).

These engines are NOT spandrel .pth models — each is a separate PyTorch project
with its own checkpoint management (downloaded by the library itself on first
use, not tracked in astros_upscale's ``models/`` folder). They are an optional
extra: ``pip install astros_upscale[audio]``.

``denoise-voz`` (facebookresearch/denoiser), ``enhance-voz`` (voicefixer) and
``super-voz`` (TigreGotico/audiosronnx, wrapping the LavaSR model as ONNX —
doesn't even need torch at runtime) are pure-Python packages with no
upper-bound numpy pin and no native build step (no Rust, no deepspeed). All
three install cleanly alongside the modern torch/numpy the rest of
astros_upscale uses, and are published on PyPI as part of the ``[audio]``
extra.

``audio-enhance`` uses `astros_audio_enhance
<https://github.com/ericinacio/astros_audio_enhance>`_ — this project's own
maintained fork of AudioSR (Liu et al., arXiv:2309.07314), rebuilt against
modern ``torch>=2.6``/``numpy>=2.1`` instead of upstream ``audiosr``'s
``numpy<=1.23.5`` pin (which has no wheels for Python 3.12+ and directly
conflicted with astros_upscale's own ``numpy>=1.26``). It's installed from
its git repository (not on PyPI) as part of the ``[audio]`` extra like
everything else here — no special-cased manual install needed anymore.

NOTE: ``audio-enhance`` has been exercised end-to-end (real weights, a real
10.24s wav, CPU inference) — 48kHz/correct-duration output confirmed. The
other three engines were written against each library's documented public
API but not run end-to-end in this environment (large model downloads /
GPU-oriented dependency trees); treat those three as implemented-but-unverified
until run once against real weights.
"""
from __future__ import annotations

import os
import shutil
import tempfile

from .media_engine import has_ffmpeg, run_ffmpeg

AUDIO_ENGINES = {
    'denoise-voz': {
        'category': 'Áudio/Voz',
        'description': 'Remoção de ruído em fala, rápido (roda em CPU)',
        'package': 'denoiser',
        'reference': 'https://github.com/facebookresearch/denoiser',
    },
    'enhance-voz': {
        'category': 'Áudio/Voz',
        'description': 'Denoise + restauração de fala degradada',
        'package': 'voicefixer',
        'reference': 'https://github.com/haoheliu/voicefixer',
    },
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
            f"Instale com: pip install astros_upscale[audio]\n(erro original: {original})")


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


def _enhance_denoise_voz(input_wav: str, output_wav: str) -> None:
    try:
        import torch
        import torchaudio
        from denoiser import pretrained
        from denoiser.dsp import convert_audio
    except ImportError as error:
        raise MissingAudioDependency('denoise-voz', 'denoiser', error) from error
    model = pretrained.dns64()
    wav, sr = torchaudio.load(input_wav)
    wav = convert_audio(wav, sr, model.sample_rate, model.chin)
    with torch.no_grad():
        denoised = model(wav[None])[0]
    torchaudio.save(output_wav, denoised.cpu(), model.sample_rate)


def _enhance_enhance_voz(input_wav: str, output_wav: str, denoise_only: bool = False) -> None:
    try:
        import torch
        from voicefixer import VoiceFixer
    except ImportError as error:
        raise MissingAudioDependency('enhance-voz', 'voicefixer', error) from error
    vf = VoiceFixer()
    # VoiceFixer has no dedicated denoise-only entry point; mode=1 (adds a
    # pre-processing step that trims high frequencies) is the closest
    # approximation to a lighter/denoise-leaning pass than the mode=0 default.
    mode = 1 if denoise_only else 0
    vf.restore(input=input_wav, output=output_wav, cuda=torch.cuda.is_available(), mode=mode)


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
    'denoise-voz': _enhance_denoise_voz,
    'enhance-voz': _enhance_enhance_voz,
    'audio-enhance': _enhance_audio_enhance,
    'super-voz': _enhance_super_voz,
}


def enhance_audio_file(input_path: str, output_path: str, engine: str, denoise_only: bool = False) -> None:
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
        if engine == 'enhance-voz':
            _enhance_enhance_voz(tmp_in, tmp_out, denoise_only=denoise_only)
        else:
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
        'denoiser': 'denoiser',
        'voicefixer': 'voicefixer',
        'astros-audio-enhance': 'astros_audio_enhance',
        'audiosronnx': 'audiosronnx',
    }[package]
    return importlib.util.find_spec(module_name) is not None
