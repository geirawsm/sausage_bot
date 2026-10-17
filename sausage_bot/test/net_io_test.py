#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import pendulum

from sausage_bot.util import net_io, envs


async def test_make_event_start_stop():
    date_yes, time_yes = ('17.05.2022', '21:00')
    date_yes, time_no = ('17.05.2022', '671:00')

    result = await net_io.make_event_start_stop(date_yes, time_yes)
    assert result == {
        "start_date": "17.05.2022",
        "start_time": "21:00",
        "start_dt": pendulum.datetime(2022, 5, 17, 21, 0, 0, tz="UTC"),
        "start_event": pendulum.datetime(2022, 5, 17, 20, 30, 0, tz="UTC"),
        "event_start_epoch": 1652819400,
        "event_end_epoch": 1652828400,
        "rel_start": "<t:1652821200:R>",
        "event_rel_start": "<t:1652819400:R>",
        "end_dt": pendulum.datetime(2022, 5, 17, 23, 0, 0, tz="UTC"),
    }
    assert await net_io.make_event_start_stop(date_yes, time_no) is None


# Every `parse_*` function below is fed the same fixture match (Vålerenga
# vs Sandnes Ulf, kickoff 23.06.2024 15:00 UTC) from a different source
# site, so they share the same expected `datetime` block.
_EXPECTED_DATETIME = {
    "date": "23.06.2024",
    "time": "15:00",
    "start_dt": pendulum.datetime(2024, 6, 23, 15, 0, 0, tz="UTC"),
    "start_event": pendulum.datetime(2024, 6, 23, 14, 30, 0, tz="UTC"),
    "end_dt": pendulum.datetime(2024, 6, 23, 17, 0, 0, tz="UTC"),
    "event_start_epoch": 1719153000,
    "rel_start": "<t:1719154800:R>",
    "event_rel_start": "<t:1719153000:R>",
}


async def test_parse_nifs_OK():
    '''
    Getting this link from file:
    https://www.nifs.no/kampfakta.php?matchId=2372733&land=1&t=6&u=694962
    '''
    parse_out = await net_io.parse_nifs(mock_in=envs.test_nifs_json_good)
    assert parse_out['teams'] == {'home': 'Vålerenga', 'away': 'Sandnes Ulf'}
    assert parse_out['datetime'] == _EXPECTED_DATETIME


async def test_parse_vglive_OK():
    '''
    Getting this link from file:
    https://vglive.vg.no/kamp/v%C3%A5lerenga-sandnes-ulf/633696/rapport
    '''
    parse_out = await net_io.parse_vglive(
        mock_in=envs.test_vglive_json_good,
        mock_in_tv=envs.test_vglive_tv_json_good
    )

    assert parse_out['teams'] == {'home': 'Vålerenga', 'away': 'Sandnes Ulf'}
    assert parse_out['datetime'] == _EXPECTED_DATETIME


async def test_parse_tv2livesport_url():
    '''
    Getting this link from file:
    https://www.tv2.no/livesport/fotball/kamper/valerenga-vs-sandnes-ulf/0cfb246c-215f-475a-846c-070109bbbe42/oversikt'
    '''
    parse_out = await net_io.parse_tv2livesport(
        mock_in=envs.test_tv2livesport_json_good
    )

    assert parse_out['teams'] == {'home': 'Vålerenga', 'away': 'Sandnes Ulf'}
    assert parse_out['datetime'] == _EXPECTED_DATETIME
