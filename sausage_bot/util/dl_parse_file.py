# -*- coding: utf-8 -*-
'dl_parse_file: Download and parse files for testing'
import asyncio
from sausage_bot.util import config, file_io, envs, net_io
from bs4 import BeautifulSoup
import json
import re

logger = config.logger

async def get_nifs_file():
    nifs_in = 'https://www.nifs.no/kampfakta.php?matchId=2372733&land=1&t=6&u=694962'
    base_url = 'https://api.nifs.no/matches/{}'
    # Get info relevant for the event
    _id = re.match(r'.*matchId=(\d+)\b', nifs_in).group(1)
    logger.debug(f'Getting: {base_url.format(_id)}')
    match_json = await net_io.get_link(
        url=base_url.format(_id)
    )
    match_json = json.loads(match_json)
    file_io.write_json(
        envs.test_nifs_json_good,
        match_json
    )


async def get_vglive_file():
    vglive_in = 'https://vglive.vg.no/kamp/v%C3%A5lerenga-sandnes-ulf/633696/rapport'
    base_url = 'https://vglive.vg.no/bff/vg/events/{}'
    # Get info relevant for the event
    _id = re.match(r'.*/kamp/.*/(\d+)/.*', vglive_in).group(1)
    logger.debug(f'Getting: {base_url.format(_id)}')
    match_json = await net_io.get_link(base_url.format(_id))
    match_json = json.loads(match_json)
    file_io.write_json(
        envs.test_vglive_json_good,
        match_json
    )
    # Get tv info
    tv_url = 'https://vglive.vg.no/bff/vg/events/tv-channels?eventIds={}'
    _tv_info = await net_io.get_link(tv_url.format(_id))
    logger.debug(f'Getting: {tv_url.format(_id)}')
    tv_json = json.loads(_tv_info)
    file_io.write_json(
        envs.test_vglive_tv_json_good,
        tv_json
    )


async def get_tv2livesport_file():
    tv2livesport_in = 'https://www.tv2.no/livesport/fotball/kamper/'\
        'valerenga-vs-sandnes-ulf/0cfb246c-215f-475a-846c-070109bbbe42'\
        '/oversikt'
    base_url = 'https://livesport-api.alpha.tv2.no/v3/football/'\
        'matches/{}/result'
    # Get info relevant for the event
    _id = re.match(
        r'.*tv2.no/livesport/.*/kamper/.*/([a-f0-9\-]+)', tv2livesport_in
    ).group(1)
    logger.debug(f'Getting: {base_url.format(_id)}')
    match_json = await net_io.get_link(
        url=base_url.format(_id)
    )
    match_json = json.loads(match_json)
    file_io.write_json(
        envs.test_tv2livesport_json_good,
        match_json
    )


async def write_generic_rss_to_file(url_in, filename, force=False):
    if (file_io.file_age(
        envs.TESTPARSE_DIR / filename
    ) > 60 * 60 * 24) or file_io.file_exist(
        envs.TESTPARSE_DIR / filename
    ) is False or force:
        feed_info = await net_io.get_link(url=url_in)
        soup = BeautifulSoup(feed_info, features='xml')
        file_io.write_file(
            envs.TESTPARSE_DIR / filename,
            soup
        )
    else:
        logger.debug(f'File {filename} is younger than 24 hours')
