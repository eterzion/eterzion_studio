"""Local, persistent record of the last successful license revalidation
(FR-056) — this is what lets offline_tolerance.py compute a real day count
across app restarts, and what makes FR-058 (clock rollback must not extend
tolerance) enforceable: `max_observed_epoch` only ever moves forward, so a
system clock rolled backward can't manufacture a fresher-looking check-in.

Not secret material (just a timestamp) — no DPAPI, unlike install_identity.py.
Lives in a sibling directory of the install identity for the same reason
that one picked %LOCALAPPDATA%/%APPDATA%: per-user, survives reinstalls of
the app itself.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

_DIRNAME = 'AstrosUpscale'
_CACHE_FILENAME = 'license_cache.json'


def _cache_dir() -> str:
    base = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or str(Path.home())
    path = os.path.join(base, _DIRNAME, 'license')
    os.makedirs(path, exist_ok=True)
    return path


def _cache_path() -> str:
    return os.path.join(_cache_dir(), _CACHE_FILENAME)


def load() -> dict | None:
    try:
        with open(_cache_path(), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def record_successful_check(now_epoch: float | None = None) -> None:
    """Called every time license_gate.py successfully reaches the licensing
    service (any 2xx/404-not-activated response — actual reachability, not
    just 'active' status). FR-058: last_success_epoch tracks the largest
    'now' this process has ever observed, so a rolled-back clock can't undo
    it on the next read."""
    now_epoch = now_epoch if now_epoch is not None else time.time()
    cached = load() or {}
    max_seen = max(cached.get('max_observed_epoch', 0.0), now_epoch)
    with open(_cache_path(), 'w', encoding='utf-8') as f:
        json.dump({'last_success_epoch': max_seen, 'max_observed_epoch': max_seen}, f)


def days_since_last_success(now_epoch: float | None = None) -> float | None:
    """None when there's no cached successful check at all — see
    offline_tolerance.compute_offline_state()'s handling of that case."""
    cached = load()
    if not cached or 'last_success_epoch' not in cached:
        return None
    now_epoch = now_epoch if now_epoch is not None else time.time()
    effective_now = max(now_epoch, cached.get('max_observed_epoch', now_epoch))
    return (effective_now - cached['last_success_epoch']) / 86400.0
