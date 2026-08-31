"""Job timestamps carry enough precision to describe a fast job.

_now_iso() formatted to whole seconds, so a job that takes half a second
started and ended inside the same second and its duration came out as zero.
The panel that reports "tempo de processamento" then showed its 1ms floor —
for exactly the jobs people run most, the stat could not do the one thing it
existed for.
"""
from __future__ import annotations

import datetime
import re

from app.jobs import _now_iso


def test_includes_milliseconds():
    assert re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z', _now_iso())


def test_two_stamps_taken_within_the_same_second_are_not_equal():
    """The exact case that broke the duration: both ends of a sub-second job."""
    import time

    first = _now_iso()
    time.sleep(0.05)
    second = _now_iso()
    assert first != second, 'dois instantes no mesmo segundo ficaram indistinguiveis'


def test_the_difference_is_readable_as_a_real_duration():
    import time

    def parse(stamp: str) -> datetime.datetime:
        return datetime.datetime.fromisoformat(stamp.replace('Z', '+00:00'))

    start = _now_iso()
    time.sleep(0.12)
    end = _now_iso()
    elapsed_ms = (parse(end) - parse(start)).total_seconds() * 1000
    assert 60 < elapsed_ms < 600, f'duracao implausivel: {elapsed_ms}ms'


def test_stays_parseable_the_way_the_renderer_parses_it():
    """store/jobs.ts uses Date.parse(), which needs a form JS accepts."""
    stamp = _now_iso()
    assert datetime.datetime.fromisoformat(stamp.replace('Z', '+00:00')).tzinfo is not None
