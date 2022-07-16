#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytest
from ..funcs import datetimefuncs


def test_correct_date_converting():
    short_assertion = '2022-05-17T00:00:00+02:00'
    long_assertion = '2022-05-17T11:22:00+02:00'
    assert str(datetimefuncs.make_dt('17.05.22')) == short_assertion
    assert str(datetimefuncs.make_dt('17.05.20 22')) == short_assertion
    assert str(datetimefuncs.make_dt('17.05.2022 1122')) == long_assertion
    assert str(datetimefuncs.make_dt('17.05.2022, 11.22')) == long_assertion
    assert str(datetimefuncs.make_dt('17.05.2022, 1122')) == long_assertion
    assert str(datetimefuncs.make_dt('17.05.20 22, 11.22')) == long_assertion