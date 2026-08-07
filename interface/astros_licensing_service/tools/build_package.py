"""Builds the encrypted, signed "orchestration logic" package (Fase 4).

Honest scope note: this packages the orchestration module's Python SOURCE,
encrypted and signed — it does NOT compile it to a native binary. Real native
compilation (Nuitka / a Rust rewrite behind FFI) is a separate, much larger
tooling investment noted as future work in docs/processing-protection-
architecture.md; what this buys today is that the module never sits on disk
in the clear and is checked for tampering (signature) and origin (installation
binding) before it's ever executed — see app/core/protected_loader.py on the
astros_upscale_api side for how it's consumed.

Usage: python tools/build_package.py
Run from interface/astros_licensing_service, with astros_upscale_api as a
sibling directory (the default repo layout).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import init_db  # noqa: E402
from app.package_crypto import build_package  # noqa: E402
from app.packages import save_package  # noqa: E402

PACKAGE_NAME = 'orchestration-logic'
_SOURCE_PATH = Path(__file__).resolve().parent.parent.parent / 'astros_upscale_api' / 'app' / 'core' / 'upscaler.py'


def main() -> None:
    if not _SOURCE_PATH.is_file():
        print(f'Fonte não encontrada: {_SOURCE_PATH}', file=sys.stderr)
        sys.exit(1)
    source_bytes = _SOURCE_PATH.read_bytes()
    version = hashlib.sha256(source_bytes).hexdigest()[:16]  # conteúdo determina a versão

    init_db()
    built = build_package(source_bytes)
    save_package(PACKAGE_NAME, version, built)
    print(f'Pacote "{PACKAGE_NAME}" versão {version} construído a partir de {_SOURCE_PATH}')
    print(f'{len(source_bytes)} bytes de origem -> {len(built["ciphertext_b64"])} bytes de ciphertext (base64)')


if __name__ == '__main__':
    main()
