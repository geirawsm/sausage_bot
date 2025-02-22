#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import pytest
from pendulum.datetime import DateTime

from sausage_bot.util import net_io, file_io, envs
from sausage_bot.util import dl_parse_file


def test_make_event_start_stop():
    date_yes, time_yes = ('17.05.2022', '21:00')
    date_yes, time_no = ('17.05.2022', '671:00')

    assert type(net_io.make_event_start_stop(date_yes, time_yes)) is dict
    assert net_io.make_event_start_stop(date_yes, time_no) is None


async def test_parse_nifs_OK():
    '''
    Getting this link from file:
    https://www.nifs.no/kampfakta.php?matchId=2372733&land=1&t=6&u=694962
    '''
    if file_io.file_age(envs.test_nifs_json_good) > 60 * 60 * 24 * 30 or\
            not file_io.file_exist(envs.test_nifs_json_good):
        await dl_parse_file.get_nifs_file()

    parse_out = await net_io.parse_nifs(mock_in=envs.test_nifs_json_good)
    assert parse_out['teams']['home'] == 'Vålerenga'
    assert type(parse_out['datetime']['end_dt']) is DateTime
    assert type(parse_out['datetime']['start_dt']) is DateTime


async def test_parse_vglive_OK():
    '''
    Getting this link from file:
    https://vglive.vg.no/kamp/v%C3%A5lerenga-sandnes-ulf/633696/rapport
    '''
    for file in [envs.test_vglive_json_good, envs.test_vglive_tv_json_good]:
        if file_io.file_age(file) > \
                60 * 60 * 24 * 30 or\
                not file_io.file_exist(file):
            await dl_parse_file.get_vglive_file()
            break

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

    if file_io.file_age(
        envs.test_tv2livesport_json_good) > 60 * 60 * 24 * 30 or\
            not file_io.file_exist(envs.test_tv2livesport_json_good):
        await dl_parse_file.get_tv2livesport_file()

    parse_out = await net_io.parse_tv2livesport(
        mock_in=envs.test_tv2livesport_json_good
    )

    assert type(parse_out) is dict
    assert parse_out['teams']['home'] == 'Vålerenga'
    assert type(parse_out['datetime']['end_dt']) is DateTime
    assert type(parse_out['datetime']['start_dt']) is DateTime
