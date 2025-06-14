#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import pytest
from pendulum.datetime import DateTime

from sausage_bot.util import net_io, envs


async def test_make_event_start_stop():
    date_yes, time_yes = ('17.05.2022', '21:00')
    date_yes, time_no = ('17.05.2022', '671:00')

    assert type(await net_io.make_event_start_stop(date_yes, time_yes)) is dict
    assert await net_io.make_event_start_stop(date_yes, time_no) is None


async def test_parse_nifs_OK():
    '''
    Getting this link from file:
    https://www.nifs.no/kampfakta.php?matchId=2372733&land=1&t=6&u=694962
    '''
    parse_out = await net_io.parse_nifs(mock_in=envs.test_nifs_json_good)
    assert parse_out['teams']['home'] == 'Vålerenga'
    assert type(parse_out['datetime']['end_dt']) is DateTime
    assert type(parse_out['datetime']['start_dt']) is DateTime


async def test_parse_vglive_OK():
    '''
    Getting this link from file:
    https://vglive.vg.no/kamp/v%C3%A5lerenga-sandnes-ulf/633696/rapport
    '''
    parse_out = await net_io.parse_vglive(
        mock_in=envs.test_vglive_json_good,
        mock_in_tv=envs.test_vglive_tv_json_good
    )

    assert type(parse_out) is dict
    assert parse_out['teams']['home'] == 'Vålerenga'
    assert type(parse_out['datetime']['end_dt']) is DateTime
    assert type(parse_out['datetime']['start_dt']) is DateTime


async def test_parse_tv2livesport_url():
    '''
    Getting this link from file:
    https://www.tv2.no/livesport/fotball/kamper/valerenga-vs-sandnes-ulf/0cfb246c-215f-475a-846c-070109bbbe42/oversikt'
    '''
    parse_out = await net_io.parse_tv2livesport(
        mock_in=envs.test_tv2livesport_json_good
    )

    assert type(parse_out) is dict
    assert parse_out['teams']['home'] == 'Vålerenga'
    assert type(parse_out['datetime']['end_dt']) is DateTime
    assert type(parse_out['datetime']['start_dt']) is DateTime
