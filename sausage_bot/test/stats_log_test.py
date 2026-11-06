#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exercises `stats.log_guild_stats()`, the once-a-day write to a guild's
`stats_log.sqlite`. The clock is pinned to noon on 2026-10-31, and the
real `datetime_handling.get_dt()` is used.
"""
import sqlite3
from types import SimpleNamespace

import pendulum

from sausage_bot.util import envs, db_helper
from sausage_bot.cogs import stats

GUILD_ID = 444444444444444444


def _set_today(monkeypatch, year, month, day):
    "Pin `pendulum.now()` to noon on the given date"
    fixed = pendulum.datetime(year, month, day, 12, 0, 0, tz="UTC")
    monkeypatch.setattr(
        pendulum, "now", lambda tz=None: fixed.in_timezone(tz) if tz else fixed
    )


def _dates_logged():
    con = sqlite3.connect(envs.resolve_db_file(envs.stats_db_log_schema, GUILD_ID))
    rows = con.execute("SELECT datetime FROM log ORDER BY datetime").fetchall()
    con.close()
    return [row[0][:10] for row in rows]


async def _log(guild_db_root, existing_datetime):
    await db_helper.prep_table(envs.stats_db_log_schema, guild_id=GUILD_ID)
    if existing_datetime:
        await db_helper.insert_many_all(
            envs.stats_db_log_schema,
            inserts=[(existing_datetime, 39, 15900, 950)],
            guild_id=GUILD_ID,
        )
    guild = SimpleNamespace(id=GUILD_ID, name="testguild")
    await stats.log_guild_stats(guild, 40, 16000, 960)


async def test_empty_log_gets_first_row(guild_db_root, monkeypatch):
    _set_today(monkeypatch, 2026, 10, 31)
    await _log(guild_db_root, None)
    assert _dates_logged() == ["2026-10-31"]


async def test_logs_when_last_row_is_from_yesterday(guild_db_root, monkeypatch):
    _set_today(monkeypatch, 2026, 10, 31)
    await _log(guild_db_root, "2026-10-30 00:05:00.000")
    assert _dates_logged() == ["2026-10-30", "2026-10-31"]


async def test_logs_when_last_row_is_31st_of_a_later_month_in_older_year(
    guild_db_root, monkeypatch
):
    _set_today(monkeypatch, 2026, 10, 31)
    # Regression: dates were compared as `DD.MM.YYYY` strings, so
    # "31.10.2026" > "31.12.2025" was False and logging stopped for good
    await _log(guild_db_root, "2025-12-31 00:03:49.454")
    assert _dates_logged() == ["2025-12-31", "2026-10-31"]


async def test_logs_day_after_a_31st(guild_db_root, monkeypatch):
    # Regression: "01.08.2024" > "31.07.2024" was False
    _set_today(monkeypatch, 2024, 8, 1)
    await _log(guild_db_root, "2024-07-31 00:03:02.181")
    assert _dates_logged() == ["2024-07-31", "2024-08-01"]


async def test_does_not_log_twice_on_the_same_day(guild_db_root, monkeypatch):
    _set_today(monkeypatch, 2026, 10, 31)
    await _log(guild_db_root, "2026-10-31 00:01:00.000")
    assert _dates_logged() == ["2026-10-31"]
