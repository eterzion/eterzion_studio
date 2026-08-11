"""T033: offline tolerance window — 30 days since last successful
revalidation, warn from day 23, block after, and clock manipulation must not
extend it (FR-056 to FR-058). Real file I/O against a temp cache dir, real
day-boundary math — no mocking of the two functions under test."""
from __future__ import annotations

import pytest

from app.core import license_cache, offline_tolerance


@pytest.fixture(autouse=True)
def isolated_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.delenv('APPDATA', raising=False)


DAY = 86400.0


class TestComputeOfflineState:
    def test_none_days_is_blocked_not_a_silent_pass(self):
        state, remaining = offline_tolerance.compute_offline_state(None)
        assert state == 'blocked'
        assert remaining == 0

    def test_day_zero_is_within_tolerance(self):
        state, remaining = offline_tolerance.compute_offline_state(0)
        assert state == 'offline_tolerance'
        assert remaining == 30

    def test_day_22_is_still_within_tolerance_no_warning_yet(self):
        state, _ = offline_tolerance.compute_offline_state(22)
        assert state == 'offline_tolerance'

    def test_day_23_starts_the_warning(self):
        state, remaining = offline_tolerance.compute_offline_state(23)
        assert state == 'offline_expiring'
        assert remaining == 7

    def test_day_30_is_the_last_day_still_allowed(self):
        state, remaining = offline_tolerance.compute_offline_state(30)
        assert state == 'offline_expiring'
        assert remaining == 0

    def test_day_31_is_blocked(self):
        state, remaining = offline_tolerance.compute_offline_state(31)
        assert state == 'blocked'
        assert remaining == 0

    def test_never_blocks_mid_processing_boundary_is_inclusive(self):
        """FR-057: must not block in the middle of ongoing work — the
        threshold itself (exactly day 30) still allows, only day 31 blocks."""
        state, _ = offline_tolerance.compute_offline_state(30.0)
        assert state != 'blocked'


class TestLicenseCache:
    def test_no_cache_file_yet_reports_none(self):
        assert license_cache.days_since_last_success(now_epoch=1000.0) is None

    def test_records_and_reads_back_a_successful_check(self):
        license_cache.record_successful_check(now_epoch=1_000_000.0)
        days = license_cache.days_since_last_success(now_epoch=1_000_000.0 + 5 * DAY)
        assert days == pytest.approx(5.0)

    def test_full_offline_tolerance_pipeline_across_real_days(self):
        license_cache.record_successful_check(now_epoch=0.0)
        days = license_cache.days_since_last_success(now_epoch=25 * DAY)
        state, remaining = offline_tolerance.compute_offline_state(days)
        assert state == 'offline_expiring'
        assert remaining == 5

    def test_rolling_the_system_clock_backward_does_not_extend_tolerance(self):
        """FR-058 — the actual mechanism under test: max_observed_epoch never
        goes down, so a rolled-back clock reading later can't look like a
        fresher check-in than one that's already been observed."""
        license_cache.record_successful_check(now_epoch=100 * DAY)
        # attacker (or a buggy NTP sync) rolls the clock back to day 50 and
        # asks again — a naive "now - last_success" would report negative
        # days (i.e. "fully fresh"), resetting the tolerance clock
        license_cache.record_successful_check(now_epoch=50 * DAY)
        days = license_cache.days_since_last_success(now_epoch=50 * DAY)
        # effective_now is clamped to the max ever observed (100 days), so
        # the gap from the real last_success_epoch (100 days) is still ~0,
        # never negative, and a later honest reading past day 100 keeps
        # counting from the true last success, not the rolled-back one
        assert days == pytest.approx(0.0, abs=0.01)

    def test_rolling_clock_backward_then_forward_again_still_counts_from_true_success(self):
        license_cache.record_successful_check(now_epoch=100 * DAY)
        license_cache.record_successful_check(now_epoch=50 * DAY)  # rollback attempt, ignored
        days = license_cache.days_since_last_success(now_epoch=110 * DAY)
        assert days == pytest.approx(10.0, abs=0.01)
