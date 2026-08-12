"""Video super-resolution job execution (T042) — the same astros_upscale.core
frame-by-frame model pipeline `astros_upscale/cli.py`'s `run_video` uses,
wrapped so job_manager.py can dispatch it through the isolated worker process
(T014) instead of running it as a bare in-process call. Reuses VideoReader/
VideoWriter (astros_upscale/utils/video_io.py) and the tiling/stabilization
primitives from astros_upscale/media_engine/temporal.py (T043/T044).

Unlike the image path (upscaler.py), there is no separate "master" step here —
export_job()/Upscaler.export only exist to cheaply re-encode a lossless PNG,
and a video's real output IS the final muxed file process() writes directly.
"""
from __future__ import annotations

import os
from typing import Callable, TypedDict

import cv2

from astros_upscale.core import load_model
from astros_upscale.media_engine.temporal import apply_atadenoise, apply_deflicker, compute_tile_grid
from astros_upscale.utils.video_io import VideoReader, VideoWriter, copy_audio, even, has_ffmpeg


class VideoProcessResult(TypedDict):
    source_size: tuple[int, int]
    output_size: tuple[int, int]


class VideoUpscaler:
    """`model_name` is always an internal engine_ref resolved by
    profile_resolver.py (FR-009/FR-011), same contract as upscaler.Upscaler."""

    # Hardware-derived fallback (T061/FR-035) — same reasoning as
    # upscaler.py's Upscaler: a real job always carries fresh figures from
    # capacity.compute_tile_params(), this is only the default when a caller
    # doesn't pass them explicitly.
    _FALLBACK_TILE_THRESHOLD = 1600
    _FALLBACK_TILE_SIZE = 512

    def __init__(self, model_name: str, model_dir: str, device: str | None = None,
                 denoise_strength: float = 0.5, half: bool = True,
                 tile_threshold: int | None = None, tile_size: int | None = None):
        resolved_device = None if device in (None, 'auto', 'Automático') else device
        self._model = load_model(
            model_name, model_dir=model_dir, denoise_strength=denoise_strength,
            tile=0, tile_pad=10, pre_pad=0, half=half, device=resolved_device,
        )
        self._tile_threshold = tile_threshold or self._FALLBACK_TILE_THRESHOLD
        self._tile_size = tile_size or self._FALLBACK_TILE_SIZE

    def process(
        self,
        video_path: str,
        scale: int,
        output_path: str,
        on_progress: Callable[[int], None] | None = None,
        on_stage: Callable[[str], None] | None = None,
        stabilize: bool = False,
    ) -> VideoProcessResult:
        """Writes the final (audio-muxed) video straight to `output_path` —
        `stabilize` (FR-102) is an opt-in extra pass, never mandatory, and
        only actually runs when a real ffmpeg binary is available."""
        do_stabilize = stabilize and has_ffmpeg()

        if on_stage:
            on_stage('Lendo vídeo')
        read_path = video_path
        pre_denoised_path = None
        if do_stabilize:
            pre_denoised_path = output_path + '.pre_denoise.mp4'
            apply_atadenoise(video_path, pre_denoised_path)
            read_path = pre_denoised_path

        reader = VideoReader(read_path)
        source_w, source_h = reader.width, reader.height
        # FR-101: computed once, from the source frame size, reused unchanged
        # for every frame below — never recomputed mid-video.
        grid = compute_tile_grid(
            reader.width, reader.height,
            self._tile_size if max(reader.width, reader.height) > self._tile_threshold else 0,
        )
        self._model.tile_size = grid.tile_size
        self._model.tile_pad = grid.tile_pad

        out_width, out_height = even(int(reader.width * scale)), even(int(reader.height * scale))
        tmp_noaudio = output_path + '.noaudio.mp4'
        writer = VideoWriter(tmp_noaudio, fps=reader.fps, width=out_width, height=out_height)

        try:
            if on_stage:
                on_stage('Aplicando modelo de IA')
            total = len(reader)
            for idx, frame in enumerate(reader):
                result, _ = self._model.enhance(frame, outscale=scale)
                if result.shape[1] != out_width or result.shape[0] != out_height:
                    result = cv2.resize(result, (out_width, out_height), interpolation=cv2.INTER_LANCZOS4)
                writer.write(result)
                if on_progress and total:
                    on_progress(5 + int(75 * (idx + 1) / total))
        finally:
            reader.close()
            writer.close()
            if pre_denoised_path and os.path.exists(pre_denoised_path):
                os.remove(pre_denoised_path)

        final_video = tmp_noaudio
        if do_stabilize:
            if on_stage:
                on_stage('Estabilizando')
            deflickered = output_path + '.deflickered.mp4'
            apply_deflicker(tmp_noaudio, deflickered)
            os.remove(tmp_noaudio)
            final_video = deflickered

        if on_stage:
            on_stage('Remontando áudio')
        if on_progress:
            on_progress(90)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
        if copy_audio(video_path, final_video, output_path):
            os.remove(final_video)
        else:
            os.replace(final_video, output_path)

        if on_progress:
            on_progress(100)
        return {'source_size': (source_w, source_h), 'output_size': (out_width, out_height)}
