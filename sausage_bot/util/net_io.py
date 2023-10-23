#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import discord
import re
import aiohttp
from datetime import datetime
from sausage_bot.util import envs, datetime_handling
from sausage_bot.util.args import args
from .log import log
import json


async def get_link(url):
    'Get contents of requests object from a `url`'
    content_out = None
    if type(url) is not str:
        log.debug('`url` is not string')
        log.log(envs.RSS_INVALID_URL.format(url))
        return None
    if re.search(r'^http(s)?', url):
        log.debug('Found scheme in url')
    elif re.match(r'^((http:\/\/|^https:\/\/))?((www\.))?', url) is not None:
        log.debug('Did not found scheme, adding')
        url = f'https://{url}'
    try:
        log.debug(f'Trying `url`: {url}')
        session = aiohttp.ClientSession()
        async with session.get(url) as resp:
            content_out = await resp.text()
        await session.close()
    except Exception as e:
        log.debug(f'Error when getting `url`: {e}')
    if content_out is None:
        return None
    else:
        return content_out


def make_event_start_stop(date, time=None):
    '''
    Make datetime objects for the event based on the start date and time.
    The event will start 30 minutes prior to the match, and it will end 2
    hours and 30 minutes after

    `date`: The match date or a datetime-object
    `time`: The match start time (optional)
    '''
    log.debug(f'Got `date`: {date}')
    try:
        # Make the original startdate an object
        if time is None:
            start_dt = datetime_handling.make_dt(date)
        else:
            start_dt = datetime_handling.make_dt(f'{date} {time}')
        log.debug(f'`start_dt` is {start_dt}')
    except Exception as e:
        log.log(f'Got an error: {e}')
        return None
    try:
        start_date = datetime_handling.get_dt('date', dt=start_dt)
        log.debug(f'Making `start_date` {start_date}')
        start_time = datetime_handling.get_dt('time', sep=':', dt=start_dt)
        log.debug(f'Making `start_time` {start_time}')
        # Make a startdate for the event that starts 30 minutes before
        # the match
        start_event = datetime_handling.change_dt(
            start_dt, 'remove', 30, 'minutes'
        )
        log.debug(f'`start_event` is {start_event}')
        # Make an enddate for the event that should stop approximately
        # 30 minutes after the match is over
        end_dt = datetime_handling.change_dt(start_dt, 'add', 2.5, 'hours')
        log.debug(f'`end_dt` is {end_dt}')
        # Make the epochs that the event will use
        event_start_epoch = datetime_handling.get_dt(dt=start_event)
        event_end_epoch = datetime_handling.get_dt(dt=end_dt)
        # Make a relative start object for the game
        start_epoch = datetime_handling.get_dt(dt=start_dt)
        rel_start = discord.utils.format_dt(
            datetime.fromtimestamp(start_epoch),
            'R'
        )
        # Make a relative start object for the event
        event_rel_start = discord.utils.format_dt(
            datetime.fromtimestamp(event_start_epoch),
            'R'
        )
        return {
            'start_date': start_date,
            'start_time': start_time,
            'start_dt': start_dt,
            'start_event': start_event,
            'event_start_epoch': event_start_epoch,
            'event_end_epoch': event_end_epoch,
            'rel_start': rel_start,
            'event_rel_start': event_rel_start,
            'end_dt': end_dt,
        }
    except Exception as e:
        log.log(envs.ERROR_WITH_ERROR_MSG.format(e))
        return None


async def parse(url: str = None):
    '''
    Parse `url` to get info about a football match
    Currently supports the following sites:
    - nifs.no
    - vglive.no
    - tv2.no/livesport

    Parameters
    ------------
    url: str
        The url to parse (default: None)

    Returns
    ------------
    dict with info about the match
    '''
    def parse_nifs(json_in):
        '''
        Parse match ID from matchpage from nifs.no, then use that in an
        api call
        '''
        # Get info relevant for the event
        date_in = json_in['timestamp']
        _date_obj = datetime_handling.make_dt(date_in)
        dt_in = make_event_start_stop(_date_obj)
        if dt_in is None:
            return None
        return {
            'teams': {
                'home': json_in['homeTeam']['name'],
                'away': json_in['awayTeam']['name']
            },
            'tournament': json_in['stage']['fullName'],
            'datetime': {
                'date': dt_in['start_date'],
                'time': dt_in['start_time'],
                'start_dt': dt_in['start_dt'],
                'start_event': dt_in['start_event'],
                'end_dt': dt_in['end_dt'],
                'event_start_epoch': dt_in['event_start_epoch'],
                'rel_start': dt_in['rel_start'],
                'event_rel_start': dt_in['event_rel_start']
            },
            'stadium': json_in['stadium']['name']
        }

    def parse_vglive(json_in):
        '''
        Parse match ID from matchpage from vglive.no, then use that in an
        api call
        '''
        # Get info relevant for the event
        teams = json_in['event']['participantIds']
        if 'venue' in json_in['event']['details']:
            stadium = json_in['event']['details']['venue']['name']
        else:
            stadium = None
        date_in = json_in['event']['startDate']
        _date_obj = datetime_handling.make_dt(date_in)
        dt_in = make_event_start_stop(_date_obj)
        if dt_in is None:
            log.debug('Error with `dt_in`')
            return None
        return {
            'teams': {
                'home': json_in['participants'][teams[0]]['name'],
                'away': json_in['participants'][teams[1]]['name']
            },
            'tournament': json_in['tournament']['name'],
            'datetime': {
                'date': dt_in['start_date'],
                'time': dt_in['start_time'],
                'start_dt': dt_in['start_dt'],
                'start_event': dt_in['start_event'],
                'end_dt': dt_in['end_dt'],
                'event_start_epoch': dt_in['event_start_epoch'],
                'rel_start': dt_in['rel_start'],
                'event_rel_start': dt_in['event_rel_start']
            },
            'stadium': stadium
        }

    def parse_tv2_livesport(json_in):
        '''
        Parse match ID from matchpage from tv2.no/livesport, then use that
        in an API call
        '''
        # Get info relevant for the event
        home = json_in['teams'][0]['name']
        away = json_in['teams'][1]['name']
        if 'venue' in json_in:
            stadium = json_in['venue']['name']
        else:
            stadium = None
        date_in = json_in['startDate']
        _date_obj = datetime_handling.make_dt(date_in)
        dt_in = make_event_start_stop(_date_obj)
        if dt_in is None:
            log.debug('Error with `dt_in`')
            return None
        return {
            'teams': {
                'home': home,
                'away': away
            },
            'tournament': json_in['competition']['name'],
            'datetime': {
                'date': dt_in['start_date'],
                'time': dt_in['start_time'],
                'start_dt': dt_in['start_dt'],
                'start_event': dt_in['start_event'],
                'end_dt': dt_in['end_dt'],
                'event_start_epoch': dt_in['event_start_epoch'],
                'rel_start': dt_in['rel_start'],
                'event_rel_start': dt_in['event_rel_start']
            },
            'stadium': stadium
        }

    if url is None:
        log.debug('Got None as url')
        return None
    PARSER = None
    if 'nifs.no' in url:
        PARSER = 'nifs'
    elif 'vglive.vg.no' in url:
        PARSER = 'vglive'
    elif 'tv2.no/livesport' in url:
        PARSER = 'tv2livesport'
    elif args.force_parser:
        PARSER = args.force_parser
    log.log_more(f'Got parser `{PARSER}`')
    if PARSER == 'nifs':
        if 'matchId=' not in url:
            # todo var msg
            log.log('The NISO url is not from a match page')
            return None
        _id = re.match(r'.*matchId=(\d+)\b', url).group(1)
        base_url = 'https://api.nifs.no/matches/{}'
        try:
            json_in = await get_link(base_url.format(_id))
            json_out = json.loads(json_in)
            parse = parse_nifs(json_out)
            return parse
        except Exception as e:
            error_msg = envs.AUTOEVENT_PARSE_ERROR.format(url, e)
            log.log(error_msg)
            return None
    elif PARSER == 'vglive':
        if '/kamp/' not in url:
            # todo var msg
            log.log('The vglive url is not from a match page')
            return None
        _id = re.match(r'.*/kamp/.*/(\d+)/.*', url).group(1)
        base_url = 'https://vglive.no/api/vg/events/{}'
        try:
            json_in = await get_link(base_url.format(_id))
            json_out = json.loads(json_in)
            parse = parse_vglive(json_out)
            return parse
        except Exception as e:
            error_msg = envs.AUTOEVENT_PARSE_ERROR.format(url, e)
            log.log(error_msg)
            return None
    elif PARSER == 'tv2livesport':
        if '/kamper/' not in url:
            # todo var msg
            log.log('The tv2 url is not from a match page')
            return None
        _id = re.match(
            r'.*tv2.no/livesport/.*/kamper/.*/([a-f0-9\-]+)', url).group(1)
        base_url = 'https://tv2-sport-backend.sumo.tv2.no/football/'\
            'matches/{}/facts'
        try:
            json_in = await get_link(base_url.format(_id))
            json_out = json.loads(json_in)
            parse = parse_tv2_livesport(json_out)
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
