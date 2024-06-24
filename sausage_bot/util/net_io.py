#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import discord
import re
import aiohttp
import aiofiles
from datetime import datetime
from sausage_bot.util import config, envs, datetime_handling, db_helper
from sausage_bot.util.args import args, file_io, discord_commands
from .log import log

import json
import colorgram

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOauthError
try:
    _spotipy = spotipy.Spotify(
        auth_manager=SpotifyClientCredentials(
            client_id=config.SPOTIFY_ID,
            client_secret=config.SPOTIFY_SECRET
        )
    )
except SpotifyOauthError:
    _spotipy = None


async def get_link(url):
    'Get contents of requests object from a `url`'
    content_out = None
    if type(url) is not str:
        log.error(envs.RSS_INVALID_URL.format(url))
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
            url_status = resp.status
            content_out = await resp.text()
            log.debug(f'Got status: {url_status}')
            log.debug(f'Got content_out: {content_out[0:500]}...')
        await session.close()
    except Exception as e:
        log.error(f'Error when getting `url`: {e}')
        return None
    if 399 < int(url_status) < 600:
        log.error(f'Got error code {url_status}')
        return None
    if content_out is None:
        return None
    else:
        return content_out


async def check_spotify_podcast(url):
    if _spotipy is None:
        _spotipy_error = 'Spotipy has no credentials. Check README'
        log.log(_spotipy_error)
        await discord_commands.log_to_bot_channel(_spotipy_error)
        return None
    pod_id = re.search(r'.*/show/([a-zA-Z0-9]+).*', url).group(1)
    try:
        _show = _spotipy.show(pod_id)
        log.debug(f'`_show`: ', pretty=_show)
        return True
    except Exception as e:
        log.error(f'ERROR: {e}')
        return False


async def get_spotify_podcast_links(feed):
    if _spotipy is None:
        _spotipy_error = 'Spotipy has no credentials. Check README'
        log.log(_spotipy_error)
        await discord_commands.log_to_bot_channel(_spotipy_error)
        return None
    UUID = feed[0]
    URL = feed[2]
    pod_id = re.search(r'.*/show/([a-zA-Z0-9]+).*', URL).group(1)
    _show = _spotipy.show(pod_id)
    filters_db = await db_helper.get_output(
        template_info=envs.rss_db_filter_schema,
        select=('allow_or_deny', 'filter'),
        where=[('uuid', UUID)]
    )
    log_db = await db_helper.get_output(
        template_info=envs.rss_db_log_schema,
        where=[('uuid', UUID)]
    )
    episodes = _show['episodes']['items']
    items_out = {
        'filters': filters_db,
        'items': [],
        'log': log_db
    }
    items_info = {
        'pod_name': _show['name'],
        'pod_description': _show['description'],
        'pod_img': _show['images'][0]['url'],
        'title': '',
        'description': '',
        'link': '',
        'img': '',
        'id': '',
        'duration': '',
        'type': 'spotify',
    }
    for ep in episodes:
        temp_info = items_info.copy()
        temp_info['title'] = ep['name']
        temp_info['description'] = ep['description']
        temp_info['link'] = ep['external_urls']['spotify']
        temp_info['img'] = ep['images'][0]['url']
        temp_info['id'] = ep['id']
        temp_info['duration'] = ep['duration_ms'] * 1000
        log.verbose(f'Populated `temp_info`: ', pretty=temp_info)
        items_out['items'].append(temp_info)
        log.debug(
            'len of `items_out[\'items\']` is {}'.format(
                len(items_out['items'])
            )
        )
    items_out = filter_links(items_out)
    return items_out


def filter_links(items):
    '''
    Filter incoming links based on active filters
    '''

    def post_based_on_filter(item, filters_in):
        allow = []
        deny = []
        for filter_in in filters_in:
            if filter_in[0].lower() == 'allow':
                allow.append(filter_in[1])
            elif filter_in[0].lower() == 'deny':
                deny.append(filter_in[1])
        filter_priority = eval(config.env(
            'RSS_FILTER_PRIORITY', default='deny'))
        for filter_out in filter_priority:
            log.debug(f'Using filter: {filter_out}')
            try:
                if item['title'] is not None:
                    log.debug(
                        'Checking filter against title `{}`'.format(
                            item['title'].lower()
                        )
                    )
                    if filter_out.lower() in str(item['title']).lower():
                        log.debug(
                            f'Found filter `{filter_out}` in '
                            'title ({}) - not posting!'.format(item['title'])
                        )
                        return False
            except TypeError:
                log.error(
                    'Title is not correct type: {} ({})'.format(
                        item['title'], type(item['title'])
                    )
                )
            try:
                if item['description']:
                    log.debug(
                        'Checking filter against description`{}`'.format(
                            item['description'].lower()
                        )
                    )
                    if filter_out.lower() in str(item['description']).lower():
                        log.debug(
                            f'Found filter `{filter_out}` in '
                            'description ({}) - not posting!').format(
                                item['description']
                            )
                        return False
            except TypeError:
                log.error(
                    'Description is not correct type: {} ({})'.format(
                        item['description'], type(item['description'])
                    )
                )
            log.debug(
                'Fant ikke noe filter i tittel eller beskrivelse'
            )
            return True

    log.debug(
        'Got {} `items` (sample): {}'.format(
            len(items['items']),
            items['items'][0]
        )
    )
    links_out = []
    for item in items['items']:
        log.verbose(f'Checking item: {item}')
        if item['type'] == 'youtube':
            log.debug('Checking Youtube item')
            if not config.env('YT_INCLUDE_SHORTS', default='true'):
                shorts_keywords = ['#shorts', '(shorts)']
                if any(kw in str(item['title']).lower()
                        for kw in shorts_keywords) or\
                        any(kw in str(item['description']).lower()
                            for kw in shorts_keywords):
                    log.debug(
                        'Skipped {} because of `#Shorts` '
                        'or `(shorts)`'.format(
                            item['title']
                        )
                    )
                    continue
        log.debug('Filters: {}'.format(items['filters']))
        if items['filters'] is not None and len(items['filters']) > 0:
            log.debug('Found active filters, checking...')
            link_filter = post_based_on_filter(item, items['filters'])
            if link_filter:
                links_out.append(item)
        else:
            links_out.append(item)
    return links_out


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
        log.error(f'Got an error: {e}')
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
        log.error(envs.ERROR_WITH_ERROR_MSG.format(e))
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
            log.error('Error with `dt_in`')
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
            log.error('Error with `dt_in`')
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
        log.error('Got None as url')
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
    log.verbose(f'Got parser `{PARSER}`')
    if PARSER == 'nifs':
        if 'matchId=' not in url:
            # todo var msg
            log.error('The NISO url is not from a match page')
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
            log.error(error_msg)
            return None
    elif PARSER == 'vglive':
        if '/kamp/' not in url:
            # todo var msg
            log.error('The vglive url is not from a match page')
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
            log.error(error_msg)
            return None
    elif PARSER == 'tv2livesport':
        if '/kamper/' not in url:
            # todo var msg
            log.error('The tv2 url is not from a match page')
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
            log.error(error_msg)
            return None
    else:
        log.error('Linken er ikke kjent')
        return None


async def download_pod_image(img_url):
    session = aiohttp.ClientSession()
    async with session.get(img_url) as resp:
        if resp.status == 200:
            file_io.ensure_file(f'{envs.TEMP_DIR}/temp_img.png')
            f = await aiofiles.open(
                f'{envs.TEMP_DIR}/temp_img.png', mode='wb'
            )
            await f.write(await resp.read())
            await f.close()
    await session.close()


async def get_main_color_from_image_url(image_url):
    def rgb_to_hex(value1, value2, value3):
        """
        Convert RGB color to hex color
        """
        for value in (value1, value2, value3):
            if not 0 <= value <= 255:
                raise ValueError(
                    'Value each slider must be ranges from 0 to 255'
                )
        return str('{0:02X}{1:02X}{2:02X}'.format(value1, value2, value3))

    log.verbose(f'Downloading image: {image_url}')
    await download_pod_image(image_url)
    log.verbose('Extracting color')
    color = colorgram.extract(f'{envs.TEMP_DIR}/temp_img.png', 1)[0]
    log.verbose('Converting color to hex')
    color_out = rgb_to_hex(color.rgb.r, color.rgb.g, color.rgb.b)
    log.verbose(f'Returning: {color_out}')
    return color_out

if __name__ == "__main__":
    pass
