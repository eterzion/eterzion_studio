"""Identifier registry for media the editor operates on.

Constitution Princípio XIII requires that clients reference media by an
identifier the API issued, never by a filesystem path. Its v3.0.0 bounded
exception permits exactly one route — `POST /media/handles` — to accept a path,
under four cumulative conditions. Three of them are this module's job:

  1. the path comes from the OS file dialog (enforced at the route/main-process
     boundary, not here — this module cannot see where a string came from);
  2. validate before anything else, and never return the path;
  3. no other route accepts a path;
  4. the identifier is not a reversible encoding of the path.

Existence of this module is justified under Princípio XI by conditions (a) and
(b): it is exercised directly by test_media_handles.py without going through
routes or jobs, and it is imported from outside its own domain — by routes.py
and by jobs.py, which are separate domains.

Registrations live for the life of the process. The editor is a session
surface, and a handle that outlived a restart would point at a file whose
content may have changed underneath it — which FR-017 would then have to
detect anyway. Nothing here is persisted.
"""
from __future__ import annotations

import os
import re
import secrets
import threading
from typing import Any

from astros_upscale.media import ProbeError, content_key, probe_streams

# Mirrors what the Electron file dialog offers for video (interface/src/main).
# Kept here rather than imported from the interface layer: Princípio IX forbids
# api/ reading anything specific to interface/.
VIDEO_EXTENSIONS = frozenset({'.mp4', '.m4v', '.mov', '.mkv', '.webm', '.avi', '.wmv', '.flv', '.mpg', '.mpeg'})

_HANDLE_PREFIX = 'vh_'
# 32 bytes of urandom. The point is not entropy against guessing — the API is
# loopback-only — but that the identifier carries no information about the path
# it maps to (fourth condition of the exception).
_HANDLE_ENTROPY_BYTES = 32


class HandleError(ValueError):
    """Raised when a path cannot be registered. Carries a `reason` key rather
    than a sentence so the interface can translate it (Princípio XIV)."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


_registry: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def register(path: str) -> str:
    """Validate `path` and return the identifier every other route will use.

    Validation happens before anything else is done with the string, and the
    path never leaves this module afterwards.
    """
    if not os.path.isfile(path):
        raise HandleError('not_found', f'Arquivo não encontrado: {path!r}')
    if os.path.splitext(path)[1].lower() not in VIDEO_EXTENSIONS:
        raise HandleError('unsupported_media', 'O arquivo não é um vídeo que o produto saiba abrir.')

    try:
        probe = probe_streams(path)
    except ProbeError as error:
        raise HandleError('unreadable', 'Não foi possível ler o arquivo de vídeo.') from error
    if not probe['video_stream_count']:
        raise HandleError('unsupported_media', 'O arquivo não contém trilha de vídeo.')

    handle_id = _HANDLE_PREFIX + secrets.token_urlsafe(_HANDLE_ENTROPY_BYTES)
    with _lock:
        _registry[handle_id] = {
            'path': path,
            'display_name': sanitise_display_name(os.path.basename(path)),
            'content_key': content_key(path),
            'duration_seconds': probe['duration_seconds'],
            'width': probe['width'],
            'height': probe['height'],
            'frame_rate': probe['frame_rate'],
            'frame_rate_is_variable': probe['frame_rate_is_variable'],
            'has_audio': probe['audio_stream_count'] > 0,
            'size_bytes': os.path.getsize(path),
        }
    return handle_id


def resolve(handle_id: str) -> str | None:
    """The path behind an identifier. **API-internal only** — the result MUST
    NOT reach a response body. Returns None for an unknown identifier."""
    with _lock:
        entry = _registry.get(handle_id)
    return entry['path'] if entry else None


def describe(handle_id: str) -> dict[str, Any]:
    """The metadata a client may see. The path is excluded here, once, rather
    than at each call site — a caller cannot forget what it never receives."""
    with _lock:
        entry = _registry.get(handle_id)
    if entry is None:
        raise HandleError('not_found', 'Identificador desconhecido.')
    return {k: v for k, v in entry.items() if k != 'path'}


def has_content_changed(handle_id: str) -> bool:
    """True when the file changed since registration, or vanished (FR-017).

    An unknown identifier also counts as changed: a caller asking this question
    wants to know whether its derived artefacts are still valid, and for an
    identifier the registry has never heard of, the answer is no.
    """
    with _lock:
        entry = _registry.get(handle_id)
    if entry is None or not os.path.isfile(entry['path']):
        return True
    return content_key(entry['path']) != entry['content_key']


def refresh(handle_id: str) -> dict[str, Any]:
    """Re-probe a registered file and return current metadata. Used by
    `GET /media/handles/{id}` so a client can discover that its cached
    thumbnails belong to content that no longer exists."""
    path = resolve(handle_id)
    if path is None:
        raise HandleError('not_found', 'Identificador desconhecido.')
    if not os.path.isfile(path):
        raise HandleError('source_changed', 'O arquivo de origem não está mais disponível.')
    with _lock:
        entry = _registry[handle_id]
        try:
            probe = probe_streams(path)
        except ProbeError as error:
            raise HandleError('unreadable', 'Não foi possível reler o arquivo de vídeo.') from error
        entry.update({
            'content_key': content_key(path),
            'duration_seconds': probe['duration_seconds'],
            'width': probe['width'],
            'height': probe['height'],
            'frame_rate': probe['frame_rate'],
            'frame_rate_is_variable': probe['frame_rate_is_variable'],
            'has_audio': probe['audio_stream_count'] > 0,
            'size_bytes': os.path.getsize(path),
        })
    return describe(handle_id)


def clear() -> None:
    """Drop every registration. For tests and for application shutdown."""
    with _lock:
        _registry.clear()


# Anything that could steer path construction, plus the control characters that
# terminate a path early on Windows. Spaces, accents and ordinary punctuation
# survive — this sanitises, it does not transliterate.
_UNSAFE_NAME_CHARS = re.compile(r'[/\\:*?"<>|\x00-\x1f]')


def sanitise_display_name(name: str) -> str:
    """Reduce a client-supplied filename to display text safe to build a path
    from (Princípio XIII).

    Never returns an empty string: a caller that joined `''` into a directory
    would silently target the directory itself.
    """
    safe = _UNSAFE_NAME_CHARS.sub('_', name)
    safe = safe.replace('..', '_')
    # A leading dot hides the file on POSIX and confuses extension handling;
    # trailing dots and spaces are silently stripped by Windows, which makes a
    # name the caller checked differ from the name that lands on disk.
    safe = safe.strip().strip('.').strip()
    return safe or 'arquivo'
