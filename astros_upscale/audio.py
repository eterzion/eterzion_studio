"""Optional audio-enhancement pipeline (denoise / restoration / super-resolution).

These engines are NOT spandrel .pth models — each is a separate PyTorch project
with its own checkpoint management (downloaded by the library itself on first
use, not tracked in astros_upscale's ``models/`` folder). They are an optional
extra: ``pip install astros_upscale[audio]``.

``denoise-voz`` (facebookresearch/denoiser), ``enhance-voz`` (voicefixer) and
``universr`` (woongzip1/UniverSR) are all pure-Python PyTorch packages with no
upper-bound numpy pin and no native build step (no Rust, no deepspeed) — they
install cleanly alongside the modern torch/numpy the rest of astros_upscale
uses. ``universr`` is not published on PyPI (installed straight from its git
repo) and pulls in ``torchcodec``, which on Windows needs an FFmpeg "shared"
build to load correctly — see the README troubleshooting section.

NOTE: unlike the rest of astros_upscale, these three integrations were written
against each library's documented public API but could not be exercised
end-to-end in this environment (large model downloads / GPU-oriented
dependency trees). Please treat this module as implemented-but-unverified
until you run it once against real weights.
"""
from __future__ import annotations

import os
import tempfile

from .utils.video_io import has_ffmpeg

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
    'universr': {
        'category': 'Áudio/Geral',
        'description': 'Super-resolução de áudio (fala e música) para 48kHz',
        'package': 'universr',
        'reference': 'https://github.com/woongzip1/UniverSR',
    },
}


class MissingAudioDependency(ImportError):
    """Raised when an audio engine's optional package is not installed."""

    def __init__(self, engine: str, package: str, original: Exception) -> None:
        super().__init__(
            f"O motor de áudio '{engine}' precisa do pacote opcional '{package}', que não está instalado.\n"
            f"Instale com: pip install astros_upscale[audio]\n(erro original: {original})")


def _run_ffmpeg(args_builder) -> None:
    from ffmpeg import FFmpeg, FFmpegError
    try:
        args_builder(FFmpeg().option('y')).execute()
    except (FFmpegError, OSError) as error:
        raise RuntimeError(f'Falha ao converter áudio com ffmpeg: {error}') from error


def _to_wav(input_path: str) -> str:
    """Convert any audio/video input to a temporary 16-bit PCM WAV via ffmpeg."""
    if not has_ffmpeg():
        raise RuntimeError('ffmpeg não encontrado no sistema; instale-o para processar áudio.')
    tmp_wav = tempfile.mktemp(suffix='.wav')
    _run_ffmpeg(lambda f: f.input(input_path).output(tmp_wav, {'vn': None, 'acodec': 'pcm_s16le'}))
    return tmp_wav


def _convert_format(wav_path: str, output_path: str) -> None:
    fmt = os.path.splitext(output_path)[1].lstrip('.').lower() or 'wav'
    if fmt == 'wav':
        os.replace(wav_path, output_path)
        return
    _run_ffmpeg(lambda f: f.input(wav_path).output(output_path))
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


def _enhance_universr(input_wav: str, output_wav: str) -> None:
    try:
        import torch
        import torchaudio
        from universr import UniverSR
    except ImportError as error:
        raise MissingAudioDependency('universr', 'universr', error) from error
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    info = torchaudio.info(input_wav)
    model = UniverSR.from_pretrained('woongzip1/universr-audio', device=device)
    waveform = model.enhance(input_wav, input_sr=info.sample_rate)
    torchaudio.save(output_wav, waveform.cpu(), 48000)


_ENGINE_FUNCS = {
    'denoise-voz': _enhance_denoise_voz,
    'enhance-voz': _enhance_enhance_voz,
    'universr': _enhance_universr,
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
    module_name = {'denoiser': 'denoiser', 'voicefixer': 'voicefixer', 'universr': 'universr'}[package]
    return importlib.util.find_spec(module_name) is not None
