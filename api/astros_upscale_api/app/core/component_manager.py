"""T068 — on-demand component download/verification/cache/eviction
(FR-041/FR-042/FR-067 to FR-069). A "Component" is the installable unit the
FR-063 to FR-069 screen lists — never a raw model identifier (FR-009/FR-063):
each one maps 1:1 to a content-type implementation (profile_resolver.py's
_CONTENT_TYPE_IMPLEMENTATIONS), so there are exactly the 6 entries FR-095
allows, not one per file in astros_upscale.core.MODELS.

Two real backends, one per kind of implementation:
- image/video content types: astros_upscale.core.MODELS — real downloads,
  real SHA-256 verification (already implemented by resolve_model()/
  model_needs_update()), real local cache (models_dir), real eviction
  (delete the cached weight file(s)).
- audio content types: no per-file weight download in the same sense —
  `speech` (audiosronnx) and `music` (SonicMaster) are Python
  packages/scripts, both declared under this repo's own `[audio]` extra
  (pyproject.toml) rather than downloaded weight files. "install"/"update"
  run a real `pip install <repo>[audio]` in this process's own
  interpreter (sys.executable) — the two share one extras group, so
  installing/updating either one installs both. Only works when this
  process is running from a source checkout with pyproject.toml (true in
  dev; a packaged build has neither pip nor the repo tree, so this would
  fail with pip's own real error — never silently no-ops). Deletion still
  refuses: uninstalling a shared dependency (e.g. torch) from under a
  running interpreter has no safe undo.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from urllib.parse import urlparse

from app.config import APP_DIR, settings
from app.core import profile_resolver
from app.core.license_registry import get_model_license

# APP_DIR = <repo>/api/astros_upscale_api/app -> the api/ package root (where
# pyproject.toml and the astros_upscale[audio] extras group live) is 2 levels
# up. This is deliberately NOT the git repo root (contrast with config.py's
# models_dir, which still climbs 3 levels to /models) — pyproject.toml moved
# into api/ during the api/+interface/ reorganisation, so "source checkout
# present" now means "api/ is present", not "the repo root is present".
_REPO_ROOT = APP_DIR.parent.parent

CAPABILITY_LABELS: dict[str, str] = {
    'photo': 'Melhoria de imagem — Foto',
    'anime_image': 'Melhoria de imagem — Anime/Ilustração',
    'anime_video': 'Melhoria de vídeo — Anime/Animação',
    'real_video': 'Melhoria de vídeo — Filmagem real',
    'speech': 'Melhoria de áudio — Voz',
    'music': 'Melhoria de áudio — Música',
}

_AUDIO_CONTENT_TYPES = {'speech', 'music'}


class ComponentNotFoundError(KeyError):
    pass


class ComponentActionUnsupportedError(RuntimeError):
    """Raised when install/update/delete is attempted on a component this
    process cannot safely automate (e.g. a pip-installed audio package) —
    never silently no-ops, always tells the person what to do instead."""


@dataclass
class ComponentInfo:
    id: str
    capability_label: str
    size_mb: int
    install_state: str
    update_available: bool
    technical_name: str
    version: str
    provenance: str
    license: str


def _model_dir() -> str:
    return settings.models_dir


def _image_video_component(content_type: str, engine_ref: str) -> ComponentInfo:
    from astros_upscale.core import MODELS, model_download_status, model_needs_update

    entry = MODELS[engine_ref]
    downloaded, size_bytes = model_download_status(engine_ref, model_dir=_model_dir())
    needs_update = downloaded and model_needs_update(engine_ref, model_dir=_model_dir())
    license_info = get_model_license(engine_ref)
    return ComponentInfo(
        id=content_type,
        capability_label=CAPABILITY_LABELS[content_type],
        # Real size once downloaded; unknown beforehand without a network HEAD
        # request per file, so 0 means "not yet measurable" here, not "0 bytes"
        # (same honest limitation the older GET /models route already had).
        size_mb=int(size_bytes / (1024 * 1024)) if downloaded else 0,
        install_state='update_available' if needs_update else ('installed' if downloaded else 'not_installed'),
        update_available=needs_update,
        technical_name=engine_ref,
        version=(entry['sha256'][0][:12] if entry.get('sha256') else 'desconhecida'),
        provenance=entry['urls'][0] if entry.get('urls') else 'desconhecida',
        license=license_info.license if license_info else 'não verificada',
    )


def _audio_component(content_type: str, engine_ref: str) -> ComponentInfo:
    if engine_ref == 'super-voz':
        from astros_upscale.audio import AUDIO_ENGINES, is_engine_available

        available = is_engine_available('super-voz')
        entry = AUDIO_ENGINES['super-voz']
        return ComponentInfo(
            id=content_type, capability_label=CAPABILITY_LABELS[content_type], size_mb=0,
            install_state='installed' if available else 'not_installed', update_available=False,
            technical_name=engine_ref, version='pacote pip (sem versão fixada)',
            provenance=entry['reference'], license='Apache-2.0',
        )
    # music / sonicmaster — see module docstring: script-based repo, no clean
    # importable API to probe beyond "is the real CLI entry point on PATH".
    script_available = bool(shutil.which('inference_fullsong.py') or shutil.which('inference_fullsong'))
    return ComponentInfo(
        id=content_type, capability_label=CAPABILITY_LABELS[content_type], size_mb=0,
        install_state='installed' if script_available else 'not_installed', update_available=False,
        technical_name=engine_ref, version='pacote pip (sem versão fixada)',
        provenance='https://github.com/AMAAI-Lab/SonicMaster', license='Apache-2.0 (condicional — ver MODEL_LICENSES.md §3-bis)',
    )


def _component_info(content_type: str) -> ComponentInfo:
    implementation = profile_resolver._CONTENT_TYPE_IMPLEMENTATIONS.get(content_type)
    if implementation is None or implementation.engine_ref is None:
        raise ComponentNotFoundError(content_type)
    if content_type in _AUDIO_CONTENT_TYPES:
        return _audio_component(content_type, implementation.engine_ref)
    return _image_video_component(content_type, implementation.engine_ref)


def list_components() -> list[ComponentInfo]:
    return [_component_info(ct) for ct in CAPABILITY_LABELS]


def get_component_details(component_id: str) -> ComponentInfo:
    if component_id not in CAPABILITY_LABELS:
        raise ComponentNotFoundError(component_id)
    return _component_info(component_id)


# pip's download/build cache lives under the user profile (Windows:
# %LOCALAPPDATA%\pip\cache), which is very often on a different, smaller
# drive than this repo — checking free space there, not next to the repo,
# is what actually prevents a real incident: a mid-session audio install
# once filled a dev machine's C: drive to 0 bytes free this way.
_MIN_FREE_BYTES_FOR_AUDIO_INSTALL = 3 * 1024 * 1024 * 1024  # 3 GiB


def _pip_install_audio_extra(*extra_args: str) -> None:
    """Real `pip install` of this repo's `[audio]` extra, run in this
    process's own interpreter (sys.executable) so the result is importable
    immediately — no separate venv, no silent no-op. `speech` and `music`
    share this one extras group (pyproject.toml), so this installs/updates
    both together regardless of which component the person clicked."""
    if not (_REPO_ROOT / 'pyproject.toml').is_file():
        raise ComponentActionUnsupportedError(
            'Não foi possível instalar: esta cópia do aplicativo não tem o código-fonte '
            f'do astros_upscale ao lado ({_REPO_ROOT}). Instale manualmente com '
            '"pip install astros_upscale[audio]".')

    free_bytes = shutil.disk_usage(os.path.expanduser('~')).free
    if free_bytes < _MIN_FREE_BYTES_FOR_AUDIO_INSTALL:
        free_mb = free_bytes / (1024 * 1024)
        raise ComponentActionUnsupportedError(
            f'Espaço em disco insuficiente para instalar os componentes de áudio '
            f'(SonicMaster + dependências): apenas {free_mb:.0f} MB livres, são '
            f'necessários pelo menos {_MIN_FREE_BYTES_FOR_AUDIO_INSTALL // (1024 * 1024)} MB. '
            'Libere espaço e tente novamente.')

    target = f'{_REPO_ROOT}[audio]'
    cmd = [sys.executable, '-m', 'pip', 'install', *extra_args, target]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if result.returncode != 0:
        raise ComponentActionUnsupportedError(
            f'pip falhou (código {result.returncode}) instalando os componentes de áudio:\n'
            f'{result.stderr[-2000:] or result.stdout[-2000:]}')


def install_component(component_id: str) -> ComponentInfo:
    """Real download + real SHA-256 verification (astros_upscale.core.resolve_model)
    for image/video; a real `pip install` of the shared [audio] extra for
    speech/music (see _pip_install_audio_extra)."""
    if component_id in _AUDIO_CONTENT_TYPES:
        _pip_install_audio_extra()
        return _component_info(component_id)
    implementation = profile_resolver._CONTENT_TYPE_IMPLEMENTATIONS.get(component_id)
    if implementation is None or implementation.engine_ref is None:
        raise ComponentNotFoundError(component_id)
    from astros_upscale.core import resolve_model

    resolve_model(implementation.engine_ref, model_dir=_model_dir())
    return _component_info(component_id)


def update_component(component_id: str) -> ComponentInfo:
    if component_id in _AUDIO_CONTENT_TYPES:
        _pip_install_audio_extra('--upgrade')
        return _component_info(component_id)
    implementation = profile_resolver._CONTENT_TYPE_IMPLEMENTATIONS.get(component_id)
    if implementation is None or implementation.engine_ref is None:
        raise ComponentNotFoundError(component_id)
    from astros_upscale.core import update_model

    update_model(implementation.engine_ref, model_dir=_model_dir())
    return _component_info(component_id)


def delete_component(component_id: str) -> ComponentInfo:
    """Real eviction — deletes the cached weight file(s) from models_dir.
    Never touches the pip-installed audio packages (no clean, safe
    "uninstall this one dependency" primitive this process should be
    driving anyway)."""
    if component_id in _AUDIO_CONTENT_TYPES:
        raise ComponentActionUnsupportedError('Componentes de áudio não são removíveis por esta tela.')
    implementation = profile_resolver._CONTENT_TYPE_IMPLEMENTATIONS.get(component_id)
    if implementation is None or implementation.engine_ref is None:
        raise ComponentNotFoundError(component_id)
    from astros_upscale.core import MODELS

    entry = MODELS[implementation.engine_ref]
    for url in entry.get('urls', []):
        path = os.path.join(_model_dir(), os.path.basename(urlparse(url).path))
        if os.path.isfile(path):
            os.remove(path)
    return _component_info(component_id)
