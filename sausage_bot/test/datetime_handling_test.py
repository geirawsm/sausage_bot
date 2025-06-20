#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytest
import pytest_asyncio

from sausage_bot.util import datetime_handling as dt


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
