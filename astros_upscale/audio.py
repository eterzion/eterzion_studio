"""Optional audio-enhancement pipeline (denoise / restoration / super-resolution).

These engines are NOT spandrel .pth models — each is a separate PyTorch project
with its own checkpoint management (downloaded by the library itself on first
use, not tracked in astros_upscale's ``models/`` folder). They are an optional
extra: ``pip install astros_upscale[audio]``.

NOTE: unlike the rest of astros_upscale, these three integrations were written
against each library's documented public API but could not be exercised
end-to-end in this environment (DeepFilterNet requires a Rust toolchain to
build, and resemble-enhance/audiosr pull large GPU-oriented dependency trees).
Please treat this module as implemented-but-unverified until you run it once
against real weights.
"""
from __future__ import annotations

import os
import tempfile

from .utils.video_io import has_ffmpeg

AUDIO_ENGINES = {
    'denoise-voz': {
        'category': 'Áudio/Voz',
        'description': 'Remoção de ruído em fala, rápido (roda em CPU)',
        'package': 'deepfilternet',
        'reference': 'https://github.com/Rikorose/DeepFilterNet',
    },
    'enhance-voz': {
        'category': 'Áudio/Voz',
        'description': 'Denoise + restauração + extensão de banda (44.1kHz)',
        'package': 'resemble-enhance',
        'reference': 'https://github.com/resemble-ai/resemble-enhance',
    },
    'audiosr': {
        'category': 'Áudio/Geral',
        'description': 'Super-resolução de áudio (fala e música) para 48kHz',
        'package': 'audiosr',
        'reference': 'https://github.com/haoheliu/versatile_audio_super_resolution',
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
        from df.enhance import enhance, init_df, load_audio, save_audio
    except ImportError as error:
        raise MissingAudioDependency('denoise-voz', 'deepfilternet', error) from error
    model, df_state, _ = init_df()
    audio, _ = load_audio(input_wav, sr=df_state.sr())
    enhanced = enhance(model, df_state, audio)
    save_audio(output_wav, enhanced, df_state.sr())


def _enhance_enhance_voz(input_wav: str, output_wav: str, denoise_only: bool = False) -> None:
    try:
        import torch
        import torchaudio
        from resemble_enhance.enhancer.inference import denoise, enhance
    except ImportError as error:
        raise MissingAudioDependency('enhance-voz', 'resemble-enhance', error) from error
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    wav, sr = torchaudio.load(input_wav)
    fn = denoise if denoise_only else enhance
    enhanced_wav, new_sr = fn(wav.mean(dim=0), sr, device)
    torchaudio.save(output_wav, enhanced_wav.unsqueeze(0).cpu(), new_sr)


def _enhance_audiosr(input_wav: str, output_wav: str) -> None:
    try:
        import soundfile as sf
        from audiosr import build_model, super_resolution
    except ImportError as error:
        raise MissingAudioDependency('audiosr', 'audiosr', error) from error
    model = build_model(model_name='basic')
    waveform = super_resolution(model, input_wav)
    sf.write(output_wav, waveform.squeeze(), 48000)


_ENGINE_FUNCS = {
    'denoise-voz': _enhance_denoise_voz,
    'enhance-voz': _enhance_enhance_voz,
    'audiosr': _enhance_audiosr,
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
    module_name = {'deepfilternet': 'df', 'resemble-enhance': 'resemble_enhance', 'audiosr': 'audiosr'}[package]
    return importlib.util.find_spec(module_name) is not None
