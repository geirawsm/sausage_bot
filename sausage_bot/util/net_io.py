#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import discord
import re
import httpx
from datetime import datetime
from bs4 import BeautifulSoup
from sausage_bot.util import envs, datetime_handling
from sausage_bot.util.args import args
from .log import log
import json


if args.local_parsing:
    from ..test.modules.requests_local import requests_session as requests
    from ..test.modules import mod_vars_test
else:
    import requests


async def get_link(url, cookies=None):
    'Get a requests object from a `url`'
    if type(url) is not str:
        log.debug('`url` is not string')
        log.log(envs.RSS_INVALID_URL.format(url))
        return None
    if args.local_parsing:
        log.debug('Using local parsing')
        if cookies:
            req = await requests.get(url, cookies)
        else:
            req = await requests.get(url)
    else:
        if re.search(r'^http(s)?', url):
            log.debug('Found scheme in url')
        elif re.match(r'^((http:\/\/|^https:\/\/))?((www\.))?', url) is not None:
            log.debug('Did not found scheme, adding')
            url = f'https://{url}'
        try:
            log.debug(f'Trying `url`: {url}')
            async with httpx.AsyncClient() as client:
                try:
                    req = await client.get(url)
                except httpx.ReadTimeout as e:
                    # TODO vars msg
                    log.log(
                        envs.NET_IO_TIMEOUT.format(url, e),
                        color='red'
                    )
                    req = None
                except httpx.ConnectError as e:
                    # TODO vars msg
                    log.log(
                        envs.NET_IO_CONNECTION_ERROR.format(url, e),
                        color='red'
                    )
                    req = None
        except httpx.HTTPStatusError as e:
            log.log(
                envs.NET_IO_CONNECTION_ERROR.format(url, e),
                color='red'
            )
            req = None
    if req is None:
        return None
    log.log_more('Got a {} when fetching {}'.format(req.status_code, url))
    if 399 < req.status_code > 599:
        log.log_to_bot_channel('Got a {} when fetching {}'.format(req.status_code, url))
        return None
    else:
        return req


def scrape_page(url, cookies=None):
    'Get a bs4 object from `url`'
    if cookies:
        scrape = get_link(url, cookies)
    else:
        scrape = get_link(url)
    try:
        soup = BeautifulSoup(scrape.content, features='html5lib')
        return soup
    except Exception as e:
        log.log(envs.RSS_NOT_ABLE_TO_SCRAPE.format(url, e))
        return None


def make_event_start_stop(date, time=None):
    '''
    Make datetime objects for the event based on the start date and time.
    The event will start 30 minutes prior to the match, and it will end 2
    hours and 30 minutes after

    `date`: The match date or a datetime-object
    `time`: The match start time (optional)
    '''
    try:
        # Make the original startdate an object
        if time is None:
            start_dt = datetime_handling.make_dt(date)
        else:
            start_dt = datetime_handling.make_dt(f'{date} {time}')
        start_date = datetime_handling.get_dt('date', dt=start_dt)
        start_time = datetime_handling.get_dt('time', sep=':', dt=start_dt)
        # Make a startdate for the event that starts 30 minutes before
        # the match
        start_event = datetime_handling.change_dt(
            start_dt, 'remove', 30, 'minutes'
        )
        # Make an enddate for the event that should stop approximately
        # 30 minutes after the match is over
        end_dt = datetime_handling.change_dt(start_dt, 'add', 2.5, 'hours')
        # Make the epochs that the event will use
        start_epoch = datetime_handling.get_dt(dt=start_event)
        end_epoch = datetime_handling.get_dt(dt=end_dt)
        # Make a relative start object for discord
        rel_start = discord.utils.format_dt(
            datetime.fromtimestamp(start_epoch).astimezone(),
            'R'
        )
        return {
            'start_date': start_date,
            'start_time': start_time,
            'start_dt': start_dt,
            'start_epoch': start_epoch,
            'rel_start': rel_start,
            'end_dt': end_dt,
            'end_epoch': end_epoch
        }
    except Exception as e:
        log.log(envs.ERROR_WITH_ERROR_MSG.format(e))
        return None


def parse(url: str):
    '''
    Parse `url` to get info about a football match.

    Returns a dict with information about the match given.
    '''
    def parse_nifs(soup):
        'Parse content from matchpages from nifs.no'
        info_tbl = soup.find('table', attrs={'class': 'nifs_table_l_nb'})
        rows = info_tbl.find_all('tr')
        # Get info relevant for the event
        info0 = rows[0].find_all('a', attrs={'class': 'nifs_link_style'})
        team_home = info0[0].text.strip()
        team_away = info0[1].text.strip()
        info1 = rows[1].find_all('td')
        tournament = info1[1].text.strip().replace('\t', '').replace('\n', ' ')
        date = info1[3].text.strip()
        time = rows[2].find_all('td')[3].text.strip()
        dt_in = make_event_start_stop(date, time)
        if dt_in is None:
            return None
        start_dt = dt_in['start_dt']
        end_dt = dt_in['end_dt']
        start_epoch = dt_in['start_epoch']
        rel_start = f'<t:{start_epoch}:R>'
        stadium = rows[3].find_all('td')[3].text.strip()
        return {
            'teams': {
                'home': team_home,
                'away': team_away
            },
            'tournament': tournament,
            'datetime': {
                'date': date,
                'time': time,
                'start_dt': start_dt,
                'start_epoch': start_epoch,
                'end_dt': end_dt,
                'rel_start': rel_start
            },
            'stadium': stadium
        }

    def parse_vglive(url):
        'Parse content from matchpages from vglive.no'
        # https://vglive.no/kamp/v%C3%A5lerenga-str%C3%B8msgodset/528898/rapport
        match_id = re.search(r'.*/(\d+)/rapport', url)
        # https://vglive.no/api/vg/events/528898
        json_url = 'https://vglive.no/api/vg/events/{}'.format(
            match_id.group(1)
        )
        match_json = json.loads(get_link(json_url).content)
        # Get info relevant for the event
        home_id = match_json['event']['participantIds'][0]
        away_id = match_json['event']['participantIds'][1]
        team_home = match_json['participants'][home_id]['name']
        team_away = match_json['participants'][away_id]['name']
        tournament = match_json['tournamentSeason']['name']
        datetime = match_json['event']['startDate']
        dt_in = make_event_start_stop(datetime)
        if dt_in is None:
            return None
        date = dt_in['start_date']
        time = dt_in['start_time']
        start_dt = dt_in['start_dt']
        end_dt = dt_in['end_dt']
        start_epoch = dt_in['start_epoch']
        rel_start = dt_in['rel_start']
        stadium = match_json['event']['details']['venue']['name']
        return {
            'teams': {
                'home': team_home,
                'away': team_away
            },
            'tournament': tournament,
            'datetime': {
                'date': date,
                'time': time,
                'start_dt': start_dt,
                'start_epoch': start_epoch,
                'end_dt': end_dt,
                'rel_start': rel_start
            },
            'stadium': stadium
        }

    PARSER = None
    if 'nifs.no' in url:
        PARSER = 'nifs'
    elif 'vglive.no' in url:
        PARSER = 'vglive'
    elif args.force_parser:
        PARSER = args.force_parser
    log.log_more(f'Got parser `{PARSER}`')
    if PARSER == 'nifs':
        soup = scrape_page(url)
        try:
            parse = parse_nifs(soup)
            return parse
        except Exception as e:
            error_msg = envs.AUTOEVENT_PARSE_ERROR.format(url, e)
            log.log(error_msg)
            return None
    elif PARSER == 'vglive':
        try:
            parse = parse_vglive(url)
            return parse
        except Exception as e:
            error_msg = envs.AUTOEVENT_PARSE_ERROR.format(url, e)
            log.log(error_msg)
            return None
    else:
        log.log('Linken er ikke kjent')
        return None


if __name__ == "__main__":
    pass
