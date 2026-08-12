"""Pure offline-tolerance state math (FR-056 to FR-058) — no I/O, no clock
reads. The local API only ever calls this once it already knows it CAN'T
reach astros_licensing_service right now (see license_gate.py); while
reachable, the service's own answer is authoritative and this module doesn't
apply at all.

Assumption from spec.md: 30 days since the last successful revalidation,
warning from day 23 — "valor adotado como padrão razoável de mercado, não
especificado pelo dono do projeto — confirmar antes do lançamento."
"""
from __future__ import annotations

TOLERANCE_DAYS = 30
WARN_FROM_DAY = 23

OfflineState = str  # 'offline_tolerance' | 'offline_expiring' | 'blocked'


def compute_offline_state(days_since_last_success: float | None) -> tuple[OfflineState, int]:
    """Returns (state, offline_days_remaining).

    `days_since_last_success=None` means there is no cached successful
    check-in at all (e.g. never activated while online, or the cache was
    lost) — nothing to extend tolerance from, so this is `blocked` same as
    exceeding the window, never a silent pass."""
    if days_since_last_success is None:
        return 'blocked', 0
    if days_since_last_success < WARN_FROM_DAY:
        return 'offline_tolerance', max(0, round(TOLERANCE_DAYS - days_since_last_success))
    if days_since_last_success <= TOLERANCE_DAYS:
        return 'offline_expiring', max(0, round(TOLERANCE_DAYS - days_since_last_success))
    return 'blocked', 0
