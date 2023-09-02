#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytest
from ..util import datetime_handling as dt


def test_correct_date_converting():
    short_assertion = '2022-05-17T00:00:00+02:00'
    long_assertion = '2022-05-17T11:22:00+02:00'
    assert str(dt.make_dt('17.05.22')) == short_assertion
    assert str(dt.make_dt('17.05.20 22')) == short_assertion
    assert str(dt.make_dt('17.05.2022 1122')) == long_assertion
    assert str(dt.make_dt('17.05.2022, 11.22')) == long_assertion
    assert str(dt.make_dt('17.05.2022, 1122')) == long_assertion
    assert str(dt.make_dt('17.05.20 22, 11.22')) == long_assertion


def test_change_dt():
    orig_date = dt.make_dt('2022-05-17T11:22:00+02:00Z')
    # All OK
    plus_nineteen_years = dt.make_dt('2041-05-17T11:22:00+02:00Z')
    minus_four_months = dt.make_dt('2022-01-17T11:22:00+02:00Z')
    plus_two_days = dt.make_dt('2022-05-19T11:22:00+02:00Z')
    minus_three_hours = dt.make_dt('2022-05-17T08:22:00+02:00Z')
    plus_thirty_minutes = dt.make_dt('2022-05-17T11:52:00+02:00Z')
    plus_two_and_half_hours = dt.make_dt('2022-05-17T13:52:00+02:00Z')

    # All OK
    assert dt.change_dt(orig_date, 'add', 19, 'years') == plus_nineteen_years
    assert dt.change_dt(orig_date, 'remove', 4, 'months') == minus_four_months
    assert dt.change_dt(orig_date, 'add', 2, 'days') == plus_two_days
    assert dt.change_dt(orig_date, 'remove', 3, 'hours') == minus_three_hours
    assert dt.change_dt(orig_date, 'add', 30, 'minutes') == plus_thirty_minutes
    assert dt.change_dt(
        orig_date, 'add', 2.5, 'hours'
    ) == plus_two_and_half_hours
    # Fails
    assert dt.change_dt(orig_date, 'add', 'two', 'days') is None
