"""Media I/O and transcoding — ffmpeg invocation, ffprobe inspection, temporal
video filters, model/resource download, and image/video read-write. Consolidates
what were `media_engine/{probe,temporal,transcode}.py` and
`utils/{download,image_io,video_io}.py` (Constitution Princípio XI).
"""
from __future__ import annotations

import functools
import hashlib
import json
import logging
import math
import os
import shutil
import subprocess
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from urllib.parse import urlparse

import cv2
import numpy as np
import torch
from torch.hub import download_url_to_file

logger = logging.getLogger(__name__)

# ------------------------------- ffmpeg invocation ------------------------------- #
#
# Central FFmpeg access point — the single place every media domain (video, audio,
# compression, conversion) shells out to FFmpeg from, replacing three previously
# independent implementations (video read/write, audio, optimize each had their own
# inline/`_run_ffmpeg` pattern).
#
# Licence note: this module deliberately does NOT fail at import time when the
# resolved ffmpeg binary is a GPL build (`--enable-gpl`/`--enable-nonfree`) — the
# developer's local ffmpeg is irrelevant to the Constitution's LGPL requirement,
# which is about what gets *bundled in the shipped installer*. A GPL dev machine
# must not block `pytest` or local development. `is_lgpl_build()` below is the
# real check, and it's enforced at packaging time (tasks.md T072), not at import.

# Software encoders that are GPL, not LGPL — must never ship in a bundled build
# without a separately negotiated commercial licence (Constitution, Licensing and
# Distribution Constraints). Hardware encoders (h264_nvenc, hevc_qsv, etc.) and
# AV1 encoders (libsvtav1, librav1e) are not in this set — they're LGPL-safe.
GPL_ENCODERS = frozenset({'libx264', 'libx264rgb', 'libx265', 'libxvid'})

_warned_this_process = False


def _bundled_ffmpeg_path() -> str | None:
    """Path to the ffmpeg binary electron-builder packages alongside the app.

    The Electron main process (interface/src/main/apiProcess.ts)
    sets ASTROS_FFMPEG_DIR to the extraResources 'ffmpeg' folder when a bundled
    LGPL build exists for the current platform (see electron-builder.yml and
    docs/models/MODEL_LICENSES.md §5). Unset in dev or on platforms without one
    (currently macOS), in which case callers fall back to PATH.
    """
    bundled_dir = os.environ.get('ASTROS_FFMPEG_DIR')
    if not bundled_dir:
        return None
    binary_name = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
    bundled_path = os.path.join(bundled_dir, binary_name)
    return bundled_path if os.path.isfile(bundled_path) else None


def ffmpeg_path() -> str | None:
    """Return the ffmpeg binary to use: the bundled build if present, else PATH."""
    return _bundled_ffmpeg_path() or shutil.which('ffmpeg')


def has_ffmpeg() -> bool:
    return ffmpeg_path() is not None


def is_lgpl_build() -> bool | None:
    """Returns True/False when determinable, or None when no ffmpeg binary
    (bundled or on PATH) is found. Real check against `ffmpeg -version`'s
    configuration line — not a guess."""
    ffmpeg_bin = ffmpeg_path()
    if not ffmpeg_bin:
        return None
    try:
        result = subprocess.run([ffmpeg_bin, '-version'], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    config_line = next((line for line in result.stdout.splitlines() if line.startswith('configuration:')), '')
    return '--enable-gpl' not in config_line and '--enable-nonfree' not in config_line


@functools.lru_cache(maxsize=1)
def available_encoders() -> frozenset[str]:
    """The encoder names this ffmpeg binary actually exposes, from
    `ffmpeg -hide_banner -encoders`.

    Constitution Princípio XIII: "An allowlist entry means 'permitted', not
    'present'. Before starting work that depends on a codec, encoder, or
    container, the API MUST confirm the runtime actually provides it and MUST
    fail with a clear reason if it does not — never begin processing that will
    die partway through."

    Cached for the process: the answer cannot change without the binary
    changing, and the alternative is a subprocess on every export request.

    Returns an empty set when no binary is found, which callers MUST treat as
    "nothing is available" — never as "unknown, proceed and hope".
    """
    ffmpeg_bin = ffmpeg_path()
    if not ffmpeg_bin:
        return frozenset()
    try:
        result = subprocess.run(
            [ffmpeg_bin, '-hide_banner', '-encoders'],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return frozenset()
    if result.returncode != 0:
        return frozenset()

    # Lines look like " V....D h264_nvenc           NVIDIA NVENC H.264 encoder".
    # The flag column is fixed-width and always precedes the name; splitting on
    # whitespace and taking the second field is what the format guarantees.
    names = set()
    for line in result.stdout.splitlines():
        if not line.startswith(' ') or line.startswith(' -'):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0] and not parts[0].startswith('-'):
            names.add(parts[1])
    return frozenset(names)


@functools.lru_cache(maxsize=64)
def encoder_works(name: str) -> bool:
    """Whether this encoder can actually encode a frame here, right now.

    `available_encoders()` reports what the binary was COMPILED with, which is
    not the same question. Measured on the development machine: ffmpeg lists
    h264_nvenc, h264_qsv and h264_amf, and all three fail at the first frame —
    NVENC driver too old, no Intel MFX session, amfrt64.dll absent. A listing
    check would have offered mp4 and mov and let every export die partway
    through, which is precisely what Princípio XIII forbids: "Before starting
    work that depends on a codec, encoder, or container, the API MUST confirm
    the runtime actually provides it and MUST fail with a clear reason if it
    does not — never begin processing that will die partway through."

    So this encodes one 64×64 frame to null and reports whether that worked.
    ~120 ms per encoder, cached for the process — paid once, against an export
    that would otherwise fail after minutes.
    """
    if name in GPL_ENCODERS:
        return False
    if name not in available_encoders():
        return False
    ffmpeg_bin = ffmpeg_path()
    if not ffmpeg_bin:
        return False
    try:
        result = subprocess.run(
            [ffmpeg_bin, '-hide_banner', '-v', 'error', '-y',
             '-f', 'lavfi', '-i', 'color=c=black:size=64x64:rate=1:duration=0.1',
             '-c:v', name, '-frames:v', '1', '-f', 'null', '-'],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def first_available_encoder(candidates: 'Sequence[str]') -> str | None:
    """First candidate that actually works here, in the caller's preference
    order.

    Rejects GPL encoders unconditionally, even when present and even when a
    caller asks for one: the developer machine's ffmpeg may well have libx264,
    and a shipped build must never depend on it (Constitution, Licensing and
    Distribution Constraints). Making that a property of this function rather
    than of each call site is the point — a caller cannot forget it.
    """
    return next((c for c in candidates if encoder_works(c)), None)


def _warn_once_if_gpl_build() -> None:
    global _warned_this_process
    if _warned_this_process:
        return
    _warned_this_process = True
    lgpl = is_lgpl_build()
    if lgpl is False:
        logger.warning(
            'The ffmpeg on PATH reports --enable-gpl/--enable-nonfree. Fine for local '
            'development; MUST be replaced with an LGPL build before packaging a '
            'distributable installer (see docs/models/MODEL_LICENSES.md §5).'
        )


def run_ffmpeg(args_builder) -> None:
    """Runs one FFmpeg invocation built by `args_builder(FFmpeg().option('y'))`.
    Consolidates what were three near-identical `_run_ffmpeg` helpers in
    video_io.py, audio.py and optimize.py into the one real place.
    Uses the bundled ffmpeg binary (T072) when packaged, falling back to PATH."""
    from ffmpeg import FFmpeg, FFmpegError

    _warn_once_if_gpl_build()
    executable = ffmpeg_path() or 'ffmpeg'
    try:
        args_builder(FFmpeg(executable=executable).option('y')).execute()
    except (FFmpegError, OSError) as error:
        raise RuntimeError(f'Falha ao processar com ffmpeg: {error}') from error


# ------------------------------- ffprobe inspection ------------------------------- #
#
# Real ffprobe wrapper — used for stream inspection (secondary-elements detection,
# duration/fps/channel verification) across video, audio and image domains.


class ProbeError(RuntimeError):
    """Raised when ffprobe is unavailable or the file can't be probed."""


def ffprobe_json(path: str) -> dict:
    """Runs `ffprobe -show_format -show_streams -show_chapters -of json` and
    returns the parsed result. Real subprocess call, no parsing of a
    synthetic/mocked shape."""
    ffprobe_bin = shutil.which('ffprobe')
    if not ffprobe_bin:
        raise ProbeError('ffprobe não encontrado no sistema.')
    try:
        result = subprocess.run(
            [ffprobe_bin, '-v', 'error', '-show_format', '-show_streams', '-show_chapters', '-of', 'json', path],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProbeError(f'Falha ao executar ffprobe em {path!r}: {error}') from error
    if result.returncode != 0:
        raise ProbeError(f'ffprobe falhou em {path!r}: {result.stderr.strip()}')
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ProbeError(f'Saída inválida do ffprobe para {path!r}: {error}') from error


def probe_streams(path: str) -> dict:
    """Summarizes a probed file into what callers actually need: counts of video/
    audio/subtitle streams and whether chapters are present — the exact signals
    the secondary-elements confirmation flow (FR-081) needs, without every caller
    re-parsing the raw ffprobe JSON shape."""
    data = ffprobe_json(path)
    streams = data.get('streams', [])
    video_streams = [s for s in streams if s.get('codec_type') == 'video']
    audio_streams = [s for s in streams if s.get('codec_type') == 'audio']
    subtitle_streams = [s for s in streams if s.get('codec_type') == 'subtitle']
    chapters = data.get('chapters', [])
    # T007 (specs/007-video-editor-player): dimensions and frame rate added for
    # the editor's timeline. The keys above are unchanged — the
    # secondary-elements confirmation flow (FR-081) already reads them and must
    # keep working byte for byte.
    first_video = video_streams[0] if video_streams else {}
    nominal = _parse_rational(first_video.get('r_frame_rate'))
    average = _parse_rational(first_video.get('avg_frame_rate'))

    return {
        'video_stream_count': len(video_streams),
        'audio_stream_count': len(audio_streams),
        'subtitle_stream_count': len(subtitle_streams),
        'has_chapters': len(chapters) > 0,
        'duration_seconds': float(data.get('format', {}).get('duration', 0.0) or 0.0),
        'width': int(first_video['width']) if first_video.get('width') else None,
        'height': int(first_video['height']) if first_video.get('height') else None,
        'frame_rate': average or nominal,
        'frame_rate_is_variable': _is_variable_frame_rate(nominal, average),
    }


def _parse_rational(value: object) -> float | None:
    """ffprobe reports frame rates as 'num/den' ('30000/1001', and '0/0' for a
    stream that has none)."""
    if not isinstance(value, str) or '/' not in value:
        return None
    numerator, _, denominator = value.partition('/')
    try:
        num, den = float(numerator), float(denominator)
    except ValueError:
        return None
    return num / den if den else None


# 1% apart is comfortably outside rounding noise (29.97 vs 30000/1001 differ by
# far less) and comfortably inside what real VFR produces — the project's own
# vfr fixture lands around 17 fps average against a 30 fps nominal rate.
_VFR_RELATIVE_TOLERANCE = 0.01


def _is_variable_frame_rate(nominal: float | None, average: float | None) -> bool:
    """True when the container's nominal rate and the measured average disagree
    enough that "frame number = time × fps" stops being true.

    FR-012 depends on this: when it returns True the editor MUST NOT present a
    frame number as exact. A false negative here is the expensive direction —
    it makes the player display a confident number that does not match the
    picture — so a stream missing either rate is treated as untrustworthy
    rather than assumed constant.
    """
    if not nominal or not average:
        return True
    return abs(nominal - average) / max(nominal, average) > _VFR_RELATIVE_TOLERANCE


# T047, FR-081 to FR-086: the video-enhance pipeline (VideoReader/VideoWriter below)
# only ever carries one video stream and one audio stream through — anything beyond
# that (extra audio tracks, subtitles, chapters) is silently lost unless the person
# explicitly confirms first.
def detect_secondary_elements(path: str) -> dict:
    """Real, ffprobe-backed answer to "will processing this file lose
    anything the person didn't ask to lose". `has_losses=False` when the
    file has at most one audio stream and no subtitles/chapters — FR-085:
    files with nothing to lose never trigger a confirmation prompt."""
    info = probe_streams(path)
    losses = []
    if info['audio_stream_count'] > 1:
        losses.append('extra_audio_tracks')
    if info['subtitle_stream_count'] > 0:
        losses.append('subtitles')
    if info['has_chapters']:
        losses.append('chapters')
    return {**info, 'has_losses': bool(losses), 'losses': losses}


# ------------------------------- temporal video filters ------------------------------- #
#
# Temporal stabilization and deterministic tiling for video upscaling
# (T043/T044, FR-101/FR-102).
#
# Deterministic tiling (FR-101): tile size/offset/overlap fixed for the whole
# video — never varied per frame based on content, memory pressure, or
# anything else. A tile grid that shifts frame-to-frame is a real source of
# visible seams that "move" between frames (temporal flicker at tile
# boundaries), which is worse than a fixed, occasionally-suboptimal tile size.
#
# Temporal stabilization (FR-102): two real ffmpeg filters, both LGPL —
# - `atadenoise` (pre-upscale): adaptive temporal averaging denoise across
#   adjacent frames, so the model sees a less noisy, less frame-to-frame-erratic
#   input than raw sensor/compression noise would give it.
# - `deflicker` (post-upscale): corrects residual per-frame luminance variation
#   after the model's own (necessarily per-frame, since the model itself has no
#   temporal awareness) enhancement pass.
#
# Never `hqdn3d` (GPL) for the same reason — Constitution "Licensing and
# Distribution Constraints": a GPL filter in the filtergraph would GPL-license
# the resulting ffmpeg invocation the same way a GPL codec does.


@dataclass(frozen=True)
class TileGrid:
    """A fixed tiling plan for one video — computed once from the frame size,
    reused unchanged for every single frame (FR-101). Never recomputed
    mid-video, regardless of what an individual frame's content looks like."""
    tile_size: int
    tile_pad: int
    tiles_x: int
    tiles_y: int


def compute_tile_grid(width: int, height: int, tile_size: int, tile_pad: int = 10) -> TileGrid:
    """Deterministic: the same (width, height, tile_size) always produces the
    exact same grid — no randomness, no content-adaptive resizing.
    `tile_size <= 0` means "no tiling" (one tile covering the whole frame)."""
    if tile_size <= 0:
        return TileGrid(tile_size=0, tile_pad=tile_pad, tiles_x=1, tiles_y=1)
    return TileGrid(
        tile_size=tile_size, tile_pad=tile_pad,
        tiles_x=math.ceil(width / tile_size), tiles_y=math.ceil(height / tile_size),
    )


def apply_atadenoise(input_path: str, output_path: str) -> None:
    """Pre-upscale temporal denoise — runs BEFORE the model sees any frame,
    on the original-resolution video. Audio is copied through untouched."""
    run_ffmpeg(lambda f: f.input(input_path).output(output_path, {'vf': 'atadenoise', 'c:a': 'copy'}))


def apply_deflicker(input_path: str, output_path: str) -> None:
    """Post-upscale flicker correction — runs on the already-upscaled frames.
    Audio is copied through untouched."""
    run_ffmpeg(lambda f: f.input(input_path).output(output_path, {'vf': 'deflicker', 'c:a': 'copy'}))


# ------------------------------- download ------------------------------- #
#
# URL-download helper built on torch.hub, with SHA256 validation, atomic writes
# and mirror-with-fallback support.


class DownloadError(RuntimeError):
    """Raised when a model download fails or its checksum does not match."""


def sha256_of_file(path: str, chunk_size: int = 1 << 20) -> str:
    """Compute the SHA256 hex digest of a file, reading in chunks."""
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


# Head and tail sampled for the content key below. Large enough that two
# different videos practically never collide (container headers, moov atoms and
# trailing indexes all live in these regions), small enough to stay constant-cost
# on a 30 GB file.
_CONTENT_KEY_SAMPLE_BYTES = 1 << 20


def content_key(path: str) -> str:
    """A cache key that changes when the file's CONTENT changes, not only its
    path (Constitution Princípio XV: "A cache key MUST include something that
    changes with the file's content, not its path alone").

    Combines size, mtime and a hash of the first and last megabyte. Deliberately
    NOT a full hash: this runs every time a file is opened in the editor, and
    reading 30 GB to draw a thumbnail strip would violate Princípio III for a
    guarantee nothing here needs. Deliberately not size+mtime alone either — a
    copy that preserved mtime would masquerade as the same file.

    This is a cache key, not a security digest. It answers "is this the same
    bytes as when I derived that thumbnail", not "has anyone tampered with
    this file".
    """
    stat = os.stat(path)
    digest = hashlib.sha256()
    digest.update(str(stat.st_size).encode())
    digest.update(str(stat.st_mtime_ns).encode())
    with open(path, 'rb') as f:
        digest.update(f.read(_CONTENT_KEY_SAMPLE_BYTES))
        if stat.st_size > _CONTENT_KEY_SAMPLE_BYTES * 2:
            f.seek(-_CONTENT_KEY_SAMPLE_BYTES, os.SEEK_END)
            digest.update(f.read(_CONTENT_KEY_SAMPLE_BYTES))
    return digest.hexdigest()


def load_file_from_url(url: str,
                       model_dir: str = 'models',
                       progress: bool = True,
                       file_name: str | None = None,
                       sha256: str | None = None) -> str:
    """Download a file from a URL into ``model_dir`` (skipping if already cached).

    The download goes to a ``.partial`` temporary file and is renamed only after
    completing (and, when ``sha256`` is given, after the checksum matches), so an
    interrupted download never leaves a corrupted file behind. When ``sha256`` is
    None, the computed hash is logged so it can be pinned later.

    Returns:
        str: The absolute path to the downloaded file.

    Raises:
        DownloadError: When the download fails or the checksum does not match.
    """
    os.makedirs(model_dir, exist_ok=True)
    filename = file_name if file_name is not None else os.path.basename(urlparse(url).path)
    cached_file = os.path.abspath(os.path.join(model_dir, filename))
    if os.path.exists(cached_file):
        return cached_file

    partial_file = cached_file + '.partial'
    print(f'Baixando "{url}"\n  -> {cached_file}')
    try:
        download_url_to_file(url, partial_file, hash_prefix=None, progress=progress)
    except Exception as error:
        if os.path.exists(partial_file):
            os.remove(partial_file)
        raise DownloadError(f'Falha ao baixar o modelo de {url} ({error}). '
                            'Verifique sua conexão ou se a URL ainda está no ar.') from error

    digest = sha256_of_file(partial_file)
    if sha256 is None:
        logger.warning('no pinned sha256 for %s; computed sha256=%s', filename, digest)
    elif digest.lower() != sha256.lower():
        os.remove(partial_file)
        raise DownloadError(f'Checksum SHA256 inválido para {filename} (baixado de {url}): '
                            f'esperado {sha256}, obtido {digest}. O arquivo foi descartado.')
    os.replace(partial_file, cached_file)
    return cached_file


def download_with_fallback(urls: list[str],
                          model_dir: str = 'models',
                          progress: bool = True,
                          file_name: str | None = None,
                          sha256: str | None = None) -> str:
    """Try each URL in ``urls`` in order (e.g. [mirror_url, original_url]) until one
    succeeds. All candidates share the same cached filename, so once any one of
    them has been downloaded successfully the others are never touched again.

    Raises:
        DownloadError: aggregating every failure, only if ALL urls failed.
    """
    filename = file_name if file_name is not None else os.path.basename(urlparse(urls[0]).path)
    cached_file = os.path.abspath(os.path.join(model_dir, filename))
    if os.path.exists(cached_file):
        return cached_file

    errors = []
    for url in urls:
        try:
            return load_file_from_url(url, model_dir=model_dir, progress=progress, file_name=filename, sha256=sha256)
        except DownloadError as error:
            logger.warning('source failed (%s); trying next mirror if any', url)
            errors.append(str(error))
    raise DownloadError('Todas as fontes de download falharam para ' + filename + ':\n' +
                        '\n'.join(f'  - {e}' for e in errors))


def local_file_status(url: str, model_dir: str = 'models', file_name: str | None = None) -> tuple[bool, int]:
    """Return (downloaded, size_in_bytes) for the file a URL would be cached as, without downloading."""
    filename = file_name if file_name is not None else os.path.basename(urlparse(url).path)
    path = os.path.join(model_dir, filename)
    if os.path.isfile(path):
        return True, os.path.getsize(path)
    return False, 0


# ------------------------------- image I/O ------------------------------- #
#
# Image reading/writing and tensor conversion helpers (torch/numpy/cv2 only).


class ImageOpenError(ValueError):
    """Raised when an image cannot be read or encoded."""


def imread(path: str) -> np.ndarray:
    """Read an image keeping alpha channel and bit depth (unicode-safe on Windows).

    Returns a numpy array in BGR/BGRA/grayscale layout, dtype uint8 or uint16.
    """
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except OSError as error:
        raise ImageOpenError(f'Could not read image: {path} ({error})') from error
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ImageOpenError(f'Could not read image: {path}')
    return img


def imwrite(path: str, img: np.ndarray) -> None:
    """Write an image, creating parent directories as needed (unicode-safe on Windows)."""
    dirname = os.path.dirname(os.path.abspath(path))
    os.makedirs(dirname, exist_ok=True)
    ext = os.path.splitext(path)[1] or '.png'
    ok, buffer = cv2.imencode(ext, img)
    if not ok:
        raise ImageOpenError(f'Could not encode image with extension {ext}')
    buffer.tofile(path)


def img2tensor(img: np.ndarray, bgr2rgb: bool = True, add_batch: bool = True) -> torch.Tensor:
    """Convert an HWC numpy image (uint8/uint16/float) to a float32 CHW tensor in [0, 1]."""
    img = img.astype(np.float32)
    if img.max() > 256:  # 16-bit image
        img = img / 65535.0
    elif img.max() > 1.5:  # 8-bit image
        img = img / 255.0
    if img.ndim == 2:
        img = img[:, :, None]
    if bgr2rgb and img.shape[2] >= 3:
        img = img[:, :, [2, 1, 0]] if img.shape[2] == 3 else np.concatenate(
            (img[:, :, [2, 1, 0]], img[:, :, 3:]), axis=2)
    tensor = torch.from_numpy(np.ascontiguousarray(np.transpose(img, (2, 0, 1)))).float()
    return tensor.unsqueeze(0) if add_batch else tensor


def tensor2img(tensor: torch.Tensor, rgb2bgr: bool = True, out_dtype: type = np.uint8) -> np.ndarray:
    """Convert a CHW/BCHW float tensor in [0, 1] back to an HWC numpy image."""
    img = tensor.detach().squeeze().float().cpu().clamp_(0, 1).numpy()
    if img.ndim == 3:
        img = np.transpose(img, (1, 2, 0))
        if rgb2bgr and img.shape[2] >= 3:
            img = img[:, :, [2, 1, 0]] if img.shape[2] == 3 else np.concatenate(
                (img[:, :, [2, 1, 0]], img[:, :, 3:]), axis=2)
    if out_dtype == np.uint16:
        return (img * 65535.0).round().astype(np.uint16)
    return (img * 255.0).round().astype(np.uint8)


# ------------------------------- video I/O ------------------------------- #
#
# Video reading/writing built on OpenCV, with optional audio remux via python-ffmpeg.
#
# The pipeline is: read frames with cv2.VideoCapture -> upscale frame by frame ->
# write with cv2.VideoWriter -> if the ffmpeg binary is available, copy the
# original audio track into the final file (driven by the python-ffmpeg library).
# Without ffmpeg the video is still produced, only without audio.


class VideoOpenError(ValueError):
    """Raised when a video file cannot be opened for reading or writing."""


class VideoReader:
    """Iterate over the frames of a video file (BGR numpy arrays)."""

    def __init__(self, path: str) -> None:
        self.path = path
        if not os.path.isfile(path):
            raise VideoOpenError(f'Could not open video: {path} (file not found)')
        self.capture = cv2.VideoCapture(path)
        if not self.capture.isOpened():
            raise VideoOpenError(f'Could not open video: {path}')
        self.fps: float = self.capture.get(cv2.CAP_PROP_FPS) or 24.0
        self.width: int = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height: int = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.frame_count: int = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if self.width <= 0 or self.height <= 0:
            self.capture.release()
            raise VideoOpenError(f'Could not read video stream: {path} (invalid or corrupted file)')

    def __len__(self) -> int:
        return max(self.frame_count, 0)

    def __iter__(self) -> Iterator[np.ndarray]:
        return self

    def __next__(self) -> np.ndarray:
        ok, frame = self.capture.read()
        if not ok:
            raise StopIteration
        return frame

    def close(self) -> None:
        self.capture.release()


class VideoWriter:
    """Write BGR frames to a video file."""

    def __init__(self, path: str, fps: float, width: int, height: int, codec: str = 'mp4v') -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*codec)
        self.writer = cv2.VideoWriter(path, fourcc, fps, (width, height))
        if not self.writer.isOpened():
            raise VideoOpenError(f'Could not open video writer for: {path} (codec {codec})')
        self.path = path

    def write(self, frame: np.ndarray) -> None:
        self.writer.write(frame)

    def close(self) -> None:
        self.writer.release()


def even(n: int) -> int:
    """Round a dimension up to the nearest even number (some codecs require it)."""
    return n if n % 2 == 0 else n + 1


def extract_audio(video_path: str, output_wav_path: str) -> bool:
    """Extract the audio track of ``video_path`` into a PCM WAV file.

    Returns False (instead of raising) when ffmpeg is missing or the source has
    no audio track — the caller should treat that as "nothing to enhance".
    """
    if not has_ffmpeg():
        return False
    try:
        run_ffmpeg(lambda f: f.input(video_path).output(output_wav_path, {'vn': None, 'acodec': 'pcm_s16le'}))
    except RuntimeError:
        return False
    return os.path.isfile(output_wav_path) and os.path.getsize(output_wav_path) > 0


def mux_audio_file(video_path: str, audio_path: str, output_path: str) -> bool:
    """Mux an external audio file into a (silent) video, re-encoding audio to AAC."""
    if not has_ffmpeg():
        return False
    try:
        run_ffmpeg(lambda f: f.input(video_path).input(audio_path).output(
            output_path, {'c:v': 'copy', 'c:a': 'aac'}, map=['0:v:0', '1:a:0'], shortest=None))
    except RuntimeError as error:
        logger.warning('audio mux failed (%s)', error)
        if os.path.exists(output_path) and os.path.abspath(output_path) != os.path.abspath(video_path):
            os.remove(output_path)
        return False
    return True


def copy_audio(source_video: str, upscaled_video: str, output_path: str) -> bool:
    """Mux the audio track of ``source_video`` into ``upscaled_video``.

    The video stream is copied as-is (no re-encode); audio is encoded to AAC.
    Returns True on success. Falls back (returns False) when the ffmpeg binary
    is missing, the source has no audio, or the mux fails — the caller is
    expected to keep the audio-less file in that case.
    """
    if not has_ffmpeg():
        logger.info('ffmpeg binary not found (bundled or on PATH); skipping audio remux')
        return False
    try:
        run_ffmpeg(lambda f: f.input(upscaled_video).input(source_video).output(
            output_path, {'c:v': 'copy', 'c:a': 'aac'}, map=['0:v:0', '1:a:0?'], shortest=None))
    except RuntimeError as error:
        logger.warning('audio remux failed (%s); keeping video without audio', error)
        if os.path.exists(output_path) and os.path.abspath(output_path) != os.path.abspath(upscaled_video):
            os.remove(output_path)  # discard partial output
        return False
    return True
