#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytest
import pytest_asyncio

from sausage_bot.util import datetime_handling as dt
from sausage_bot.util import guild_context


async def test_correct_date_converting():
    assert str(await dt.make_dt('17.05.22')) == '2022-05-17 00:00:00+00:00'
    assert str(await dt.make_dt('17.05.20 22')) == '2022-05-17 00:00:00+00:00'
    assert str(await dt.make_dt('17.05.2022 1322')) ==\
        '2022-05-17 13:22:00+00:00'
    assert str(await dt.make_dt('17.05.2022, 13.22')) ==\
        '2022-05-17 13:22:00+00:00'
    assert str(await dt.make_dt('17.05.2022, 1322')) ==\
        '2022-05-17 13:22:00+00:00'
    assert str(await dt.make_dt('17.05.20 22, 13.22')) ==\
        '2022-05-17 13:22:00+00:00'


async def test_change_dt():
    orig_date = await dt.make_dt('17.05.2022, 13.22')
    # All OK
    plus_nineteen_years = await dt.make_dt('17.05.2041, 13:22')
    minus_four_months = await dt.make_dt('17.01.2022, 13.22')
    plus_two_days = await dt.make_dt('19.05.2022, 13:22')
    minus_three_hours = await dt.make_dt('17.05.2022, 10.22')
    plus_thirty_minutes = await dt.make_dt('17.05.2022, 13.52')

    # All OK
    assert dt.change_dt(
        orig_date, 'add', 19, 'years'
    ) == plus_nineteen_years
    assert dt.change_dt(
        orig_date, 'remove', 4, 'months'
    ) == minus_four_months
    assert dt.change_dt(
        orig_date, 'add', 2, 'days'
    ) == plus_two_days
    assert dt.change_dt(
        orig_date, 'remove', 3, 'hours'
    ) == minus_three_hours
    assert dt.change_dt(
        orig_date, 'add', 30, 'minutes'
    ) == plus_thirty_minutes
    # Fails
    assert dt.change_dt(orig_date, 'add', 'two', 'days') is None


# The tests above all run with no guild context set, so `make_dt`/`get_dt`
# fall back to `guild_context`'s defaults (UTC/en). These tests set a
# guild's timezone/locale directly to check that fallback is actually
# guild-aware, not just coincidentally correct.

async def test_get_dt_respects_guild_timezone():
    fixed_instant = '2022-05-17T11:22:00Z'

    token_tz = guild_context.current_timezone.set('Europe/Oslo')
    try:
        local = await dt.get_dt(format='datetime', dt=fixed_instant)
    finally:
        guild_context.current_timezone.reset(token_tz)
    utc = await dt.get_dt(format='datetime', dt=fixed_instant)

    # Europe/Oslo is UTC+2 (CEST) in May
    assert local == '17.05.2022 13.22'
    assert utc == '17.05.2022 11.22'


async def test_get_dt_no_timezone_forces_utc_regardless_of_guild():
    fixed_instant = '2022-05-17T11:22:00Z'

    token_tz = guild_context.current_timezone.set('Europe/Oslo')
    try:
        forced_utc = await dt.get_dt(
            format='datetime', dt=fixed_instant, no_timezone=True
        )
    finally:
        guild_context.current_timezone.reset(token_tz)

    assert forced_utc == '17.05.2022 11.22'


async def test_get_dt_respects_guild_locale():
    fixed_instant = '2022-05-17T11:22:00Z'

    token_locale = guild_context.current_locale.set('nb')
    try:
        text_nb = await dt.get_dt(format='datetext', dt=fixed_instant)
    finally:
        guild_context.current_locale.reset(token_locale)
    text_en = await dt.get_dt(format='datetext', dt=fixed_instant)

    assert text_nb != text_en
    assert 'mai' in text_nb.lower()
    assert 'may' in text_en.lower()
