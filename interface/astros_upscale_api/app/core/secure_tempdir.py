"""Private scratch directories for the isolated worker (Fase 1 — isolamento de
processo). Each directory gets a random, unguessable name and, on Windows, an
ACL restricted to the current user only (inheritance stripped, no group/Everyone
grant). Not a substitute for real sandboxing (Job Objects/AppContainer are a
Fase 5/6 concern) — this only keeps casual/other-user access off artifacts that
briefly touch disk.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import uuid

_ROOT_DIRNAME = 'astros-upscale-worker'


def _base_root() -> str:
    """%LOCALAPPDATA%\\Temp on Windows (per-user already), a generic temp dir
    elsewhere — always under a private, user-owned parent, never a shared
    system-wide temp root."""
    base = os.environ.get('LOCALAPPDATA') or os.environ.get('TEMP') or os.environ.get('TMP')
    if not base:
        import tempfile
        base = tempfile.gettempdir()
    root = os.path.join(base, _ROOT_DIRNAME)
    os.makedirs(root, exist_ok=True)
    return root


def restrict_to_current_user(path: str) -> None:
    """Strip inherited permissions and grant full control only to the current
    user. Best-effort: a failure here shouldn't crash the caller, it just means
    the directory keeps default (less restrictive) permissions. Shared with
    install_identity.py — any private, per-user directory uses this same rule."""
    if sys.platform != 'win32':
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass
        return
    username = os.environ.get('USERNAME')
    domain = os.environ.get('USERDOMAIN')
    account = f'{domain}\\{username}' if domain and username else username
    if not account:
        return
    try:
        subprocess.run(
            ['icacls', path, '/inheritance:r', '/grant:r', f'{account}:(OI)(CI)F'],
            capture_output=True, timeout=10, check=False, shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def create_private_dir() -> str:
    """Creates and returns a fresh, randomly-named, ACL-restricted directory."""
    root = _base_root()
    name = uuid.uuid4().hex
    path = os.path.join(root, name)
    os.makedirs(path, exist_ok=False)
    restrict_to_current_user(path)
    return path


def remove_dir(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)


def cleanup_stale(max_age_seconds: int = 24 * 60 * 60) -> int:
    """Removes leftover directories from crashed/killed previous runs. Meant to
    run once at API startup. Returns how many were removed."""
    root = _base_root()
    removed = 0
    now = time.time()
    try:
        entries = os.listdir(root)
    except OSError:
        return 0
    for name in entries:
        path = os.path.join(root, name)
        try:
            age = now - os.path.getmtime(path)
        except OSError:
            continue
        if age >= max_age_seconds or _is_locked_stale(path):
            remove_dir(path)
            removed += 1
    return removed


def _is_locked_stale(path: str) -> bool:
    """A leftover directory containing a pidfile whose process no longer exists
    is stale regardless of age — it's a crash residue, not a live job."""
    pidfile = os.path.join(path, 'worker.pid')
    if not os.path.isfile(pidfile):
        return False
    try:
        with open(pidfile, encoding='utf-8') as fh:
            pid = int(fh.read().strip())
    except (OSError, ValueError):
        return True
    return not _pid_alive(pid)


def _pid_alive(pid: int) -> bool:
    if sys.platform != 'win32':
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    try:
        result = subprocess.run(
            ['tasklist', '/FI', f'PID eq {pid}'], capture_output=True, timeout=5, text=True, check=False,
        )
        return str(pid) in result.stdout
    except (OSError, subprocess.SubprocessError):
        return True  # unknown -> assume alive, don't delete a possibly-live job's dir
