"""Real audio-enhance pipeline (T053) — job_manager's isolated-worker dispatch
target for media_type='audio'/operation='enhance'.

Two stages, always in this order:
1. DSP chain (always runs, LGPL-safe ffmpeg filters only, per
   docs/models/MODEL_LICENSES.md §4): `afftdn` (FFT noise reduction),
   `deesser`/`acompressor` (voice-clarity shaping), `loudnorm` (EBU R128
   loudness normalization). Fully verifiable with just ffmpeg — no ML
   dependency, no network, no GPU.
2. Content-type model pass — `speech` gets audiosronnx's bandwidth extension
   (Apache-2.0, package `audiosronnx`); `music` gets SonicMaster's
   restoration model (Apache-2.0 code/weights, `license_status=
   approved_conditional` — see profile_resolver.py and
   docs/models/MODEL_LICENSES.md §3-bis for the Stable Audio Open VAE
   dependency this carries). Neither package is installed in every
   environment (`[audio]` extra) — a missing one raises
   MissingAudioDependency rather than silently skipping the step.

SonicMaster ships as inference *scripts* (`inference_fullsong.py` et al.).
There is no documented stable importable Python API — this integration calls
its confirmed real CLI entry point via subprocess. It has not been run
end-to-end in this environment (no checkpoint downloaded, package not
installed here) — same "implemented but unverified until run once against
real weights" status astros_upscale/audio.py already documents for its own
less-common engines.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Callable, TypedDict

from astros_upscale.media_engine.probe import ffprobe_json
from astros_upscale.media_engine.transcode import run_ffmpeg


class MissingAudioDependency(ImportError):
    def __init__(self, engine: str, package: str, original: Exception) -> None:
        super().__init__(
            f"O motor de áudio '{engine}' precisa do pacote opcional '{package}', que não está instalado.\n"
            f"Instale com: pip install astros_upscale[audio]\n(erro original: {original})")


class AudioProcessResult(TypedDict):
    duration_seconds: float
    channels: int


# LGPL-only (never GPL) — noise reduction, then voice-clarity shaping, then
# loudness normalization last so the model pass below (if any) sees
# already-normalized input. -16 LUFS / -1.5 dBTP / LRA 11 mirrors ffmpeg's
# own loudnorm documentation defaults for streaming-style content.
_DSP_FILTER_CHAIN = 'afftdn,deesser,acompressor,loudnorm=I=-16:TP=-1.5:LRA=11'


def apply_dsp_chain(input_path: str, output_path: str) -> None:
    """Always runs, regardless of content_type — real ffmpeg filters, no
    Python ML dependency. Verified in test_audio_processor.py by measuring
    actual noise-floor reduction and the real integrated loudness of the
    output via a second ffmpeg loudnorm measurement pass."""
    run_ffmpeg(lambda f: f.input(input_path).output(output_path, {'af': _DSP_FILTER_CHAIN}))


def _enhance_speech(input_wav: str, output_wav: str) -> None:
    """speech content_type — audiosronnx (Apache-2.0), the same engine
    astros_upscale.audio registers as 'super-voz'."""
    try:
        import soundfile as sf
        from audiosronnx import load_sr
    except ImportError as error:
        raise MissingAudioDependency('speech (audiosronnx)', 'audiosronnx', error) from error
    model = load_sr(engine='lavasr')
    waveform = model.upscale(input_wav)
    sf.write(output_wav, waveform, 48000)


def _enhance_music(input_wav: str, output_wav: str) -> None:
    """music content_type — SonicMaster (approved_conditional, see
    profile_resolver.py's _CONTENT_TYPE_IMPLEMENTATIONS and
    docs/models/MODEL_LICENSES.md §3-bis). SonicMaster ships as inference
    scripts, not an importable module with a stable API — this calls its
    real `inference_fullsong.py` entry point (confirmed against the
    project's own repository), the closest thing to a documented interface
    it has today."""
    script = shutil.which('inference_fullsong.py') or shutil.which('inference_fullsong')
    if not script:
        raise MissingAudioDependency(
            'music (SonicMaster)', 'sonicmaster',
            ImportError('inference_fullsong.py not found on PATH — SonicMaster checkpoint/config not set up'))
    result = subprocess.run(
        ['python', script, '--input', input_wav, '--output', output_wav,
         '--prompt', 'Restore and master this music recording', '--fs', '44100'],
        capture_output=True, text=True, timeout=600, check=False,
    )
    if result.returncode != 0 or not os.path.isfile(output_wav):
        raise RuntimeError(f'SonicMaster falhou: {result.stderr.strip()}')


# Keyed by engine_ref (profile_resolver.py's resolved identifier, e.g.
# 'super-voz'/'sonicmaster') — not content_type. The isolated worker's IPC
# message never carries content_type (FR-009/FR-011: only the already-resolved
# engine_ref crosses that boundary), same contract image/video handlers use.
_ENGINE_ENHANCERS: dict[str, Callable[[str, str], None]] = {
    'super-voz': _enhance_speech,
    'sonicmaster': _enhance_music,
}


def process(
    input_path: str,
    engine_ref: str,
    output_path: str,
    on_progress: Callable[[int], None] | None = None,
    on_stage: Callable[[str], None] | None = None,
) -> AudioProcessResult:
    """Full pipeline: convert to WAV -> DSP chain -> content-type model pass
    -> re-encode to output_path's real format. Raises MissingAudioDependency
    if the resolved engine's package isn't installed (never silently skips
    the model step and calls it done)."""
    if engine_ref not in _ENGINE_ENHANCERS:
        raise ValueError(f'engine_ref sem implementação de áudio: {engine_ref!r}')

    if on_stage:
        on_stage('Lendo áudio')
    if on_progress:
        on_progress(5)
    tmp_in = tempfile.mktemp(suffix='.wav')
    run_ffmpeg(lambda f: f.input(input_path).output(tmp_in, {'vn': None, 'acodec': 'pcm_s16le'}))
    source_probe = ffprobe_json(tmp_in)
    source_audio = next(s for s in source_probe['streams'] if s['codec_type'] == 'audio')

    tmp_dsp = tempfile.mktemp(suffix='.wav')
    tmp_model = tempfile.mktemp(suffix='.wav')
    try:
        if on_stage:
            on_stage('Reduzindo ruído e normalizando volume')
        if on_progress:
            on_progress(25)
        apply_dsp_chain(tmp_in, tmp_dsp)

        if on_stage:
            on_stage('Aplicando modelo de IA')
        if on_progress:
            on_progress(50)
        _ENGINE_ENHANCERS[engine_ref](tmp_dsp, tmp_model)

        if on_stage:
            on_stage('Salvando resultado')
        if on_progress:
            on_progress(90)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
        fmt = os.path.splitext(output_path)[1].lstrip('.').lower() or 'wav'
        if fmt == 'wav':
            shutil.move(tmp_model, output_path)
        else:
            run_ffmpeg(lambda f: f.input(tmp_model).output(output_path))
    finally:
        for tmp in (tmp_in, tmp_dsp, tmp_model):
            if os.path.exists(tmp):
                os.remove(tmp)

    output_probe = ffprobe_json(output_path)
    duration = float(output_probe.get('format', {}).get('duration', 0.0) or 0.0)
    if on_progress:
        on_progress(100)
    return {'duration_seconds': duration, 'channels': int(source_audio.get('channels', 1))}
