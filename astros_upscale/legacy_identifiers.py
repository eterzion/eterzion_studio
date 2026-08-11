"""Identifiers that used to be valid entries in ``core.MODELS`` and were removed —
either for a rejected commercial licence (docs/models/MODEL_LICENSES.md) or because
the registry was reduced to one implementation per content type (FR-095).

Existing job history — persisted client-side in the desktop app's localStorage, not
in this process's memory — can still reference these. FR-048 requires that old
history not break when its identifier no longer resolves. This module is the single
place both the API (graceful error instead of a raw KeyError) and any future
migration tooling look up "was this a real, known identifier that got removed" vs.
"this was never valid at all".
"""
from __future__ import annotations

# key: the old astros_upscale.core.MODELS identifier. value: why it's gone, in
# plain language — never re-exposes the rejected model's own name/architecture,
# per Constitution Principle V.
REMOVED_MODEL_IDENTIFIERS: dict[str, str] = {
    'ultrasharp': 'Licença não permite uso comercial',
    'animesharp': 'Licença não permite uso comercial',
    'nmkd-siax': 'Licença não verificada por fonte oficial',
    'nmkd-superscale': 'Licença não verificada por fonte oficial',
    'liveaction-span': 'Licença não permite uso comercial',
    # T023/T024: registro reduzido a uma implementação por content_type (FR-095)
    # com base no benchmark real (docs/models/BENCHMARK_RESULTS.md) — estes
    # tinham licença válida, mas perderam para nomos-webphoto/hfa2k-span.
    'realesrgan-x4': 'Substituído pelo resultado do benchmark de perfis',
    'realesrgan-x2': 'Substituído pelo resultado do benchmark de perfis',
    'realesr-general': 'Substituído pelo resultado do benchmark de perfis',
    'realesrnet-x4': 'Substituído pelo resultado do benchmark de perfis',
    'nomos2-dat2': 'Substituído pelo resultado do benchmark de perfis',
    'realesrgan-anime': 'Substituído pelo resultado do benchmark de perfis',
}


def is_removed_identifier(identifier: str) -> bool:
    return identifier in REMOVED_MODEL_IDENTIFIERS


def removal_reason(identifier: str) -> str | None:
    return REMOVED_MODEL_IDENTIFIERS.get(identifier)
