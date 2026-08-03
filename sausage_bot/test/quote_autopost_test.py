#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for the 5-minute window-match arithmetic that
`cogs/quote.py`'s `task_autopost()` uses to decide whether *this* tick is
the one where a given guild's configured `autopost_time` should fire.

The formula lives inline inside `task_autopost()` (a `@tasks.loop`
closure that also touches Discord/DB), so it isn't independently
importable. It's mirrored here rather than imported - see
`cogs/quote.py`, the block computing `now_minutes`/`target_minutes`
around the `(now_minutes - target_minutes) % (24 * 60) >= 5` check.

Caveat: because the formula is duplicated rather than imported, this
test does not catch a regression if someone edits the inline formula in
quote.py without updating this mirror. If that inline block is ever
extracted into its own function, this file should import it instead.
"""
from datetime import time


def is_within_autopost_window(now_hour, now_minute, target_hour, target_minute):
    "Mirrors the (now_minutes - target_minutes) % (24 * 60) >= 5 check in quote.py"
    now_minutes = now_hour * 60 + now_minute
    target_minutes = target_hour * 60 + target_minute
    return (now_minutes - target_minutes) % (24 * 60) < 5


def test_exact_target_time_matches():
    assert is_within_autopost_window(9, 0, 9, 0) is True


def test_four_minutes_after_target_matches():
    assert is_within_autopost_window(9, 4, 9, 0) is True


def test_five_minutes_after_target_does_not_match():
    # 5 minutes is the loop's own polling interval - the *next* tick
    # should have caught this, not this one
    assert is_within_autopost_window(9, 5, 9, 0) is False


def test_one_minute_before_target_does_not_match():
    assert is_within_autopost_window(8, 59, 9, 0) is False


def test_window_wraps_correctly_around_midnight():
    assert is_within_autopost_window(0, 2, 23, 59) is True
    assert is_within_autopost_window(23, 58, 23, 59) is False


def test_default_autopost_time_of_noon_matches_at_noon():
    # cogs/quote.py falls back to "12:00:00" when a guild has no
    # `autopost_time` set yet
    default_target = time.fromisoformat("12:00:00")
    assert (
        is_within_autopost_window(12, 3, default_target.hour, default_target.minute)
        is True
    )
