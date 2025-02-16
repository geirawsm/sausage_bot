#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import discord
import re
import aiohttp
import aiofiles
from datetime import datetime
from sausage_bot.util import config, envs, datetime_handling, db_helper
from sausage_bot.util import file_io, discord_commands
from sausage_bot.util.args import args
from .log import log

import json
import colorgram

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOauthError
from requests.exceptions import ConnectionError
try:
    _spotipy = spotipy.Spotify(
        auth_manager=SpotifyClientCredentials(
            client_id=config.SPOTIFY_ID,
            client_secret=config.SPOTIFY_SECRET
        ),
        requests_timeout=6
    )
except (SpotifyOauthError, ConnectionError) as _error:
    _spotipy = None
    log.error(f'Error when connecting to Spotify: {_error}')


async def get_link(url):
    'Get contents of requests object from a `url`'
    content_out = None
    url_status = 0
    if type(url) is not str:
        log.error('Input `{url}`is not a proper URL. Check spelling.')
        return None
    if re.search(r'^http(s)?\:', url):
        log.debug('Found scheme in url')
    elif re.match(r'^((http\:\/\/|^https\:\/\/))?((www\.))?', url) is not None:
        log.debug('Did not found scheme, adding')
        url = f'https://{url}'
    try:
        log.debug(f'Trying `url`: {url}')
        session = aiohttp.ClientSession()
        async with session.get(url) as resp:
            url_status = resp.status
            log.debug(f'Got status: {url_status}')
            content_out = await resp.text()
            log.verbose(f'Got content_out: {content_out[0:500]}...')
        await session.close()
    except Exception as e:
        log.error(f'Error when getting `url`:({url_status}) {e}')
        return None
    if 399 < int(url_status) < 600:
        log.error(f'Got error code {url_status}')
        file_io.ensure_folder(envs.TEMP_DIR / 'HTTP_errors')
        await file_io.write_file(
            envs.TEMP_DIR / 'HTTP_errors' / '{}.log'.format(
                datetime_handling.get_dt(
                    format='revdatetimefull',
                    sep='-'
                )
            ),
            content_out
        )
        return int(url_status)
    if content_out is None:
        return None
    else:
        return content_out


async def check_spotify_podcast(url):
    log.verbose('Checking podcast...')
    if _spotipy is None:
        _spotipy_error = 'Spotipy has no credentials. Check README'
        log.error(_spotipy_error)
        await discord_commands.log_to_bot_channel(_spotipy_error)
        return None
    try:
        log.verbose(f'Looking up show ({url})...')
        _show = _spotipy.show(url)
        return _show['total_episodes']
    except Exception as e:
        log.error(f'ERROR: {e}')
        return False


async def check_spotify_podcast_episodes():
    log.verbose('Getting num of episodes...')
    if _spotipy is None:
        _spotipy_error = 'Spotipy has no credentials. Check README'
        log.error(_spotipy_error)
        await discord_commands.log_to_bot_channel(_spotipy_error)
        return None
    spotify_feeds = await db_helper.get_output(
        template_info=envs.rss_db_schema,
        select=('uuid', 'feed_name', 'url', 'channel', 'num_episodes'),
        order_by=[
            ('feed_name', 'DESC')
        ],
        where=[
            ('status_url', envs.FEEDS_URL_SUCCESS),
            ('status_channel', envs.CHANNEL_STATUS_SUCCESS),
            ('feed_type', 'spotify')
        ]
    )
    checklist = {}
    if len(spotify_feeds) == 0:
        return checklist
    for feed in spotify_feeds:
        pod_id = re.search(r'.*/show/([a-zA-Z0-9]+).*', feed['url']).group(1)
        checklist[pod_id] = {
            'name': feed['feed_name'],
            'num_episodes_old': feed['num_episodes'] if
            isinstance(feed['num_episodes'], int) else 0,
            'num_episodes_new': None,
            'uuid': feed['uuid'],
            'channel': feed['channel']
        }
    try:
        show_ids = [feed for feed in checklist]
        _shows = _spotipy.shows(show_ids)['shows']
        log.verbose(f'Got ({len(_shows)}) shows')
    except Exception as e:
        log.error(f'ERROR: {e}')
        return False
    for show in _shows:
        checklist[show['id']]['num_episodes_new'] = show['total_episodes']
        _old_eps = checklist[show['id']]['num_episodes_old']
        _new_eps = checklist[show['id']]['num_episodes_new']
        if _new_eps > _old_eps:
            _old_eps = _new_eps
        else:
            checklist.pop(show['id'])
    return checklist


async def get_spotify_podcast_links(pod_id=str, uuid=str):
    if _spotipy is None:
        _spotipy_error = 'Spotipy has no credentials. Check README'
        log.log(_spotipy_error)
        await discord_commands.log_to_bot_channel(_spotipy_error)
        return None
    log.verbose('Getting show info...')
    _show = _spotipy.show(pod_id)
    log.verbose('Getting DB filters')
    filters_db = await db_helper.get_output(
        template_info=envs.rss_db_filter_schema,
        select=('allow_or_deny', 'filter'),
        where=[('uuid', uuid)]
    )
    log.verbose('Getting DB log')
    log_db = await db_helper.get_output(
        template_info=envs.rss_db_log_schema,
        where=[('uuid', uuid)]
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
    log.verbose('Processing episodes')
    try:
        for ep in episodes:
            if ep is None:
                continue
            temp_info = items_info.copy()
            temp_info['title'] = ep['name']
            temp_info['description'] = ep['description']
            temp_info['link'] = ep['external_urls']['spotify']
            temp_info['img'] = ep['images'][0]['url']
            temp_info['id'] = ep['id']
            temp_info['duration'] = ep['duration_ms'] * 1000
            log.verbose('Populated `temp_info`: ', pretty=temp_info)
            items_out['items'].append(temp_info)
        items_out = filter_links(items_out)
        return items_out
    except TypeError as e:
        _msg = 'Error processing episodes from {}: {}'.format(
            items_info['pod_name'], e
        )
        log.error(_msg)
        await discord_commands.log_to_bot_channel(_msg)


def filter_links(items):
    '''
    Filter incoming links based on active filters
    '''

    def post_based_on_filter(item, filters_in):
        allow = []
        deny = []
        for filter_in in filters_in:
            if filter_in['allow_or_deny'].lower() == 'allow':
                allow.append(filter_in['filter'])
            elif filter_in['allow_or_deny'].lower() == 'deny':
                deny.append(filter_in['filter'])
        filter_priority = eval(config.env(
            'RSS_FILTER_PRIORITY', default='deny'))
        for filter_out in filter_priority:
            log.verbose(f'Using filter: {filter_out}')
            try:
                if item['title'] is not None:
                    log.verbose(
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
                            'description ({}) - not posting!'.format(
                                item['description']
                            )
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
            items['items'][0]['title']
        )
    )
    links_out = []
    for item in items['items']:
        log.verbose('Checking item: {}'.format(
            item['title']
        ))
        if item['type'] == 'youtube':
            log.verbose('Checking Youtube item')
            if not config.env('YT_INCLUDE_SHORTS', default='true'):
                shorts_keywords = ['#shorts', '(shorts)']
                if any(kw in str(item['title']).lower()
                        for kw in shorts_keywords) or\
                        any(kw in str(item['description']).lower()
                            for kw in shorts_keywords):
                    log.verbose(
                        'Skipped {} because of `#Shorts` '
                        'or `(shorts)`'.format(
                            item['title']
                        )
                    )
                    continue
        log.verbose('Filters: {}'.format(items['filters']))
        if items['filters'] is not None and len(items['filters']) > 0:
            log.verbose('Found active filters, checking...')
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
        start_time = datetime_handling.get_dt(
            'time', sep=':', dt=start_dt
        )
        log.debug(f'Making `start_time` {start_time}')
        # Make a startdate for the event that starts 30 minutes before
        # the match
        start_event = datetime_handling.change_dt(
            start_dt, 'remove', 30, 'minutes'
        )
        log.debug(f'`start_event` is {start_event}')
        # Make an enddate for the event that should stop approximately
        # 30 minutes after the match is over
        end_dt = datetime_handling.change_dt(
            start_dt, 'add', 2.5, 'hours'
        )
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
        log.error('Error: {}'.format(e))
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
            log.error('The NIFS url is not from a match page')
            return None
        try:
            parse = await parse_nifs(url)
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
        try:
            parse = await parse_vglive(url)
            if parse is None:
                return None
            else:
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
        parse = await parse_tv2livesport(url)
        return parse
    else:
        log.error('Linken er ikke kjent')
        return None


async def parse_nifs(url_in):
    '''
    Parse match ID from matchpage from nifs.no, then use that in an
    api call
    '''
    base_url = 'https://api.nifs.no/matches/{}'

    _id = re.match(r'.*matchId=(\d+)\b', url_in).group(1)
    json_link_in = await get_link(base_url.format(_id))

    # Get info relevant for the event
    match_json = json.loads(json_link_in)
    date_in = match_json['timestamp']
    _date_obj = datetime_handling.make_dt(date_in)
    dt_in = make_event_start_stop(_date_obj)
    if dt_in is None:
        return None
    if 'tvChannels' in match_json:
        tv = match_json['tvChannels'][0]['name']
    else:
        tv = None
    return {
        'teams': {
            'home': match_json['homeTeam']['name'],
            'away': match_json['awayTeam']['name']
        },
        'tournament': match_json['stage']['fullName'],
        'tv': tv,
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
        'stadium': match_json['stadium']['name']
    }


async def parse_vglive(url_in):
    '''
    Parse match ID from matchpage from vglive.no, then use that in an
    api call
    '''
    base_url = 'https://vglive.vg.no/bff/vg/events/{}'
    tv_url = 'https://vglive.vg.no/bff/vg/events/tv-channels?eventIds={}'

    _id = re.match(r'.*/kamp/.*/(\d+)/.*', url_in).group(1)
    _match_info = await get_link(base_url.format(_id))
    if isinstance(_match_info, int):
        # TODO i18n
        error_msg = 'Link received HTTP status code {}'.format(_match_info)
        log.error(error_msg)
        await discord_commands.log_to_bot_channel(error_msg)
        return None
    # Get info relevant for the event
    match_json = json.loads(_match_info)
    log.verbose('Got `match_json`: ', pretty=match_json)
    _tv_info = await get_link(tv_url.format(_id))
    tv_json = json.loads(_tv_info)
    log.verbose('Got `tv_json`: ', pretty=tv_json)
    teams = match_json['event']['participantIds']
    if 'venue' in match_json['event']['details']:
        stadium = match_json['event']['details']['venue']['name']
    else:
        stadium = None
    log.debug(f'Got `stadium`: {stadium}')
    log.debug('Channels ({}): {}'.format(
        len(tv_json['tvChannels']),
        tv_json['tvChannels']
    ))
    if len(tv_json['tvChannels']) > 0:
        tv = tv_json['tvChannels'][_id][0]['name']
    else:
        tv = None
    log.debug(f'Got `tv`: {tv}')
    date_in = match_json['event']['startDate']
    _date_obj = datetime_handling.make_dt(date_in)
    dt_in = make_event_start_stop(_date_obj)
    if dt_in is None:
        log.error('`dt_in` is None')
        return None
    return {
        'teams': {
            'home': match_json['participants'][teams[0]]['name'],
            'away': match_json['participants'][teams[1]]['name']
        },
        'tournament': match_json['tournament']['name'],
        'tv': tv,
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


async def parse_tv2livesport(url_in):
    '''
    Parse match ID from matchpage from tv2.no/livesport, then use that
    in an API call
    '''
    base_url = 'https://livesport-api.alpha.tv2.no/v3/football/'\
        'matches/{}/result'
    _id = re.match(
        r'.*tv2.no/livesport/.*/kamper/.*/([a-f0-9\-]+)', url_in
    ).group(1)
    match_info = await get_link(base_url.format(_id))

    match_json = json.loads(match_info)
    # Get info relevant for the event
    home = match_json['teams'][0]['name']
    away = match_json['teams'][1]['name']
    if 'venue' in match_json:
        stadium = match_json['venue']['name']
    else:
        stadium = None
    if 'broadcast' in match_json:
        tv = match_json['broadcast']['channelName']
    else:
        tv = None
    date_in = match_json['startTime']
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
        'tournament': match_json['competition']['name'],
        'tv': tv,
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


async def extract_color_from_image_url(image_url):
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
