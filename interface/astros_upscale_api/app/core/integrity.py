"""Self-integrity check for the isolated worker's own shipped code (Fase 5 —
proteção em runtime e anti-adulteração). The package signature (Fase 4)
protects content fetched at runtime from the licensing service; it says
nothing about whether the FILES ALREADY ON DISK — the worker's own loader,
its IPC handling, its identity module — have been tampered with locally
before the worker even starts. This closes that gap for the files that matter
most: anything that decides what to trust or how to load it.

The manifest (integrity_manifest.json) pins expected SHA-256 hashes. Run this
module directly to (re)generate it after an intentional code change — same
idea as a lockfile, not something meant to auto-update silently.

Honest limits, stated plainly rather than glossed over:
- This only checks files on disk at worker startup. It can't detect in-memory
  patching after the process is already running (a debugger attached to a
  live process bypasses this entirely, as it does most local anti-tamper
  measures — see the architecture doc's "Regra de arquitetura").
- This module checks itself is a well-known weak point of any local
  self-verification scheme: a sufficiently capable attacker can edit
  integrity.py to make verify() always return True. Including this file in
  its own manifest (below) doesn't eliminate that, but it does mean a naive
  edit-the-target-file tamper attempt gets caught, which is most of the real
  threat this defends against. A hard guarantee here would require OS-level
  code signing of a real compiled executable, which is the same "native
  compilation" gap already noted as future work in Fase 4.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_CORE_DIR = Path(__file__).resolve().parent
_MANIFEST_PATH = _CORE_DIR / 'integrity_manifest.json'

# The files that decide what this process trusts or executes — not everything
# in app/core/, just the ones a local tamperer would actually want to alter.
PROTECTED_FILES = (
    'isolated_worker.py',
    'upscaler.py',
    # T042/T053 — video_upscaler.py/audio_processor.py are dispatched from the
    # same isolated_worker.py _MODULE_REGISTRY as upscaler.py and run in the
    # same trust boundary; leaving them out of this list would mean a local
    # tamperer could alter what those handlers actually run undetected.
    'video_upscaler.py',
    'audio_processor.py',
    'capacity.py',
    'worker_supervisor.py',
    'protected_loader.py',
    'install_identity.py',
    'secure_tempdir.py',
    'dpapi.py',
    'integrity.py',
)


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_hashes() -> dict[str, str]:
    return {name: _hash_file(_CORE_DIR / name) for name in PROTECTED_FILES if (_CORE_DIR / name).is_file()}


def generate_manifest() -> dict[str, str]:
    hashes = compute_hashes()
    _MANIFEST_PATH.write_text(json.dumps(hashes, indent=2, sort_keys=True), encoding='utf-8')
    return hashes


def _load_manifest() -> dict[str, str] | None:
    if not _MANIFEST_PATH.is_file():
        return None
    try:
        return json.loads(_MANIFEST_PATH.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None


def verify() -> tuple[bool, list[str]]:
    """Returns (ok, problems). problems lists which files are missing,
    modified, or unexpectedly present relative to the pinned manifest."""
    manifest = _load_manifest()
    if manifest is None:
        return False, ['integrity_manifest.json ausente ou ilegível']
    current = compute_hashes()
    problems: list[str] = []
    for name, expected_hash in manifest.items():
        actual_hash = current.get(name)
        if actual_hash is None:
            problems.append(f'{name}: ausente')
        elif actual_hash != expected_hash:
            problems.append(f'{name}: hash não confere (modificado)')
    for name in current:
        if name not in manifest:
            problems.append(f'{name}: presente mas não está no manifesto')
    return not problems, problems


if __name__ == '__main__':
    if '--verify' in sys.argv:
        ok, problems = verify()
        if ok:
            print('OK — todos os arquivos protegidos conferem com o manifesto.')
            sys.exit(0)
        print('FALHA de integridade:', file=sys.stderr)
        for problem in problems:
            print(f'  - {problem}', file=sys.stderr)
        sys.exit(1)
    hashes = generate_manifest()
    print(f'Manifesto gerado em {_MANIFEST_PATH} com {len(hashes)} arquivo(s).')
