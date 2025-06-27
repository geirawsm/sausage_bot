#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'net_io: Networking functions'
import discord
import re
import aiohttp
from random import choice
import requests
from datetime import datetime
import json
from pprint import pformat
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOauthError
from requests.exceptions import ConnectionError
from bs4 import BeautifulSoup
from bs4 import element as bs4_element
from PIL import Image
from io import BytesIO
import httpx
from numpy import array as np_array
from hashlib import md5
from yt_dlp import YoutubeDL

from sausage_bot.util import config, envs, datetime_handling, db_helper
from sausage_bot.util import file_io, discord_commands
from sausage_bot.util.args import args

logger = config.logger


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
    logger.error(f'Error when connecting to Spotify: {_error}')


async def fetch_random_user_agent():
    # Check if API key is set
    if config.SCRAPEOPS_API_KEY is None:
        logger.error('SCRAPEOPS_API_KEY is not set')
        return
    # Get new headers if the file is older than 6 hours or does not exist
    if file_io.file_age(envs.TEMP_DIR / 'headers.json') > 60 * 60 * 6 or\
            file_io.file_exist(envs.TEMP_DIR / 'headers.json') is False:
        logger.debug('Headers file is older than an hour or does not exist')
        response = requests.get(
            envs.scrapeops_url.format(config.SCRAPEOPS_API_KEY)
        )
        file_io.write_json(envs.TEMP_DIR / 'headers.json', response.json())


async def get_link(url=None, mock_file=None, status_out=None):
    'Get contents of requests object from a `url`'
    def get_random_user_agent():
        headers_file = envs.TEMP_DIR / 'headers.json'
        return choice(
            dict(file_io.read_json(headers_file))['result']
        )['user-agent']

    if mock_file:
        logger.debug('Found mock file, returning it')
        return file_io.read_file(mock_file)
    content_out = None
    url_status = 0
    if type(url) is not str or url == '':
        logger.error(f'Input `{url}`is not a proper URL. Check spelling.')
        return None
    if re.search(r'^http(s)?\:', url):
        logger.debug('Found scheme in url')
    elif re.match(r'^((http\:\/\/|^https\:\/\/))?((www\.))?', url) is not None:
        logger.debug('Did not found scheme, adding')
        url = f'https://{url}'
    try:
        logger.debug(f'Trying `url`: {url}')
        session = aiohttp.ClientSession()
        # Get random user agent
#        rand_user_agent = get_random_user_agent()
#        logger.debug(f'Using user-agent: {rand_user_agent}')
#        headers = {'user-agent': rand_user_agent}
#        async with session.get(url, headers=headers) as resp:
        async with session.get(url) as resp:
            url_status = resp.status
            logger.debug(f'Got status: {url_status}')
            content_out = await resp.text()
            logger.debug(f'Got content_out: {content_out[0:500]}...')
            if 399 < int(url_status) < 600:
                logger.error(f'Got error code {url_status}')
                file_io.ensure_folder(envs.TEMP_DIR / 'HTTP_errors')
                file_io.write_file(
                    envs.LOG_DIR / 'HTTP_errors' / '{}.log'.format(
                        await datetime_handling.get_dt(
                            format='revdatetimefull',
                            sep='-'
                        )
                    ),
                    str(content_out)
                )
        await session.close()
        if status_out:
            return {'status': url_status, 'content': content_out}
        else:
            return content_out
    except Exception as e:
        logger.error(f'Error when getting `url`:({url_status}) {e}')
        if isinstance(url_status, int):
            return int(url_status)
        else:
            return None
        return None
    else:
        return content_out


async def check_spotify_podcast(url, mock_file=None):
    logger.debug('Checking podcast...')
    if mock_file:
        logger.debug('Found mock file, returning it')
        return file_io.read_file(mock_file)
    if _spotipy is None:
        _spotipy_error = 'Spotipy has no credentials. Check README'
        logger.error(_spotipy_error)
        await discord_commands.log_to_bot_channel(_spotipy_error)
        return None
    try:
        logger.debug(f'Looking up show ({url})...')
        _show = _spotipy.show(url)
        return _show['total_episodes']
    except Exception as e:
        logger.error(f'ERROR: {e}')
        return False


async def check_for_new_spotify_podcast_episodes():
    '''
    Create a dict of Spotify podcasts that have more available episodes
    than registered in the db
    '''
    logger.debug('Getting num of episodes...')
    if _spotipy is None:
        _spotipy_error = 'Spotipy has no credentials. Check README'
        logger.error(_spotipy_error)
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
            ('feed_type', 'podcast')
        ],
        like=('url', 'spotify.com/show/')
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
        logger.debug(f'Got ({len(_shows)}) shows')
    except Exception as e:
        logger.error(f'ERROR: {e}')
        return False
    for show in _shows:
        checklist[show['id']]['num_episodes_new'] = show['total_episodes']
        _old_eps = checklist[show['id']]['num_episodes_old']
        _new_eps = checklist[show['id']]['num_episodes_new']
        if all([_old_eps, _new_eps]):
            if _new_eps > _old_eps:
                _old_eps = _new_eps
            else:
                checklist.pop(show['id'])
        else:
            _msg = 'Error when checking for new episodes for {}'.format(
                feed['feed_name']
            )
            logger.error(_msg)
            discord_commands.log_to_bot_channel(_msg)
    return checklist


async def check_other_podcast_episodes():
    podcast_feeds = await db_helper.get_output(
        template_info=envs.rss_db_schema,
        select=('uuid', 'feed_name', 'url', 'channel'),
        order_by=[
            ('feed_name', 'DESC')
        ],
        where=[
            ('status_url', envs.FEEDS_URL_SUCCESS),
            ('status_channel', envs.CHANNEL_STATUS_SUCCESS),
            ('feed_type', 'podcast')
        ],
        not_like=('url', 'spotify.com/show/')
    )
    checklist = {}
    if len(podcast_feeds) == 0:
        return checklist
    for feed in podcast_feeds:
        checklist[feed['uuid']] = {
            'name': feed['feed_name'],
            'uuid': feed['uuid'],
            'url': feed['url'],
            'channel': feed['channel']
        }
    return checklist


async def get_spotify_podcast_links(pod_id=str, uuid=str):
    '''
    Returns a dict with filters_db, log_db and items.
    Items is a list of dicts with the following keys:
    pod_name, pod_description, pod_img, title, description, link, img, id,
    duration, type
    '''
    if _spotipy is None:
        _spotipy_error = 'Spotipy has no credentials. Check README'
        logger.info(_spotipy_error)
        await discord_commands.log_to_bot_channel(_spotipy_error)
        return None
    logger.debug('Getting show info...')
    _show = _spotipy.show(pod_id)
    logger.debug('Getting DB filters')
    filters_db = await db_helper.get_output(
        template_info=envs.rss_db_filter_schema,
        select=('allow_or_deny', 'filter'),
        where=[('uuid', uuid)]
    )
    logger.debug('Getting DB log')
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
        'pod_uuid': uuid,
        'title': '',
        'description': '',
        'link': '',
        'hash': '',
        'img': '',
        'id': '',
        'duration': '',
        'type': 'spotify',
    }
    logger.debug('Processing episodes')
    try:
        for ep in episodes:
            if ep is None:
                continue
            temp_info = items_info.copy()
            temp_info['title'] = ep['name']
            temp_info['description'] = ep['description']
            temp_info['link'] = ep['external_urls']['spotify']
            temp_info['hash'] = await get_page_hash(temp_info['link'])
            temp_info['img'] = ep['images'][0]['url']
            temp_info['id'] = ep['id']
            temp_info['duration'] = ep['duration_ms'] * 1000
            logger.debug(f'Populated `temp_info`:\n{pformat(temp_info)}')
            items_out['items'].append(temp_info)
        items_out = filter_links(items_out)
        return items_out
    except TypeError as e:
        _msg = 'Error processing episodes from {}: {}'.format(
            items_info['pod_name'], e
        )
        logger.error(_msg)
        await discord_commands.log_to_bot_channel(_msg)


async def get_other_podcast_links(
    req, url, uuid, num_items=None
):
    '''
    Returns a dict with filters_db, log_db and items.
    Items is a list of dicts with the following keys:
    pod_name, pod_description, pod_img, title, description, link, img, id,
    duration, type
    '''
    try:
        soup = BeautifulSoup(req, features='lxml')
        rss_status = False
        if soup.find('feed') or soup.find('rss') or\
                soup.find('link', attrs={'type': 'application/rss+xml'}):
            rss_status = True
        if rss_status is False:
            logger.error(f'No rss feed found in {url}')
            return None
        else:
            logger.debug(f'Found rss feed in {url}')
    except Exception as e:
        logger.error(f'Error when reading `soup` from {url}: {e}')
        return None
    logger.debug('Getting DB filters')
    filters_db = await db_helper.get_output(
        template_info=envs.rss_db_filter_schema,
        select=('allow_or_deny', 'filter'),
        where=[('uuid', uuid)]
    )
    logger.debug('Getting DB log')
    log_db = await db_helper.get_output(
        template_info=envs.rss_db_log_schema,
        select=('url', 'hash'),
        where=[('uuid', uuid)]
    )
    items_out = {
        'filters': filters_db,
        'items': [],
        'log': log_db
    }
    pod_name = soup.find('channel').find('title').text
    pod_description = soup.find('channel').find('description').text
    pod_img = soup.find('channel').find('itunes:image')['href']
    items_info = {
        'pod_name': pod_name,
        'pod_description': pod_description,
        'pod_img': pod_img,
        'pod_uuid': uuid,
        'title': '',
        'description': '',
        'link': '',
        'hash': '',
        'img': '',
        'duration': '',
        'type': 'podcast',
    }
    logger.debug('Processing episodes')
    # Gets podcast feed
    if soup.find('enclosure') and 'audio' in soup.find('enclosure')['type']:
        logger.debug('Found podcast feed')
        if isinstance(num_items, int) and num_items > 0:
            all_items = soup.find_all('item')[0:num_items]
        else:
            all_items = soup.find_all('item')
        try:
            for item in all_items:
                temp_info = items_info.copy()
                temp_info['title'] = item.find('title').text if\
                    hasattr(item.find('title'), 'text') else\
                    item.find('title')
                desc_in = str(item.find('description').text) if\
                    hasattr(item.find('description'), 'text') else\
                    str(item.find('description'))
                temp_info['description'] = clean_pod_description(desc_in)
                itunes_link = item.find('media:player')
                normal_link = item.find('link')
                logger.info('normal_link is {} ({}) ({})'.format(
                    normal_link, type(normal_link), len(normal_link)
                ))
                if itunes_link:
                    temp_info['link'] = itunes_link['url']
                if len(normal_link) == 0 and isinstance(
                    normal_link, bs4_element.Tag
                ):
                    for line in str(item).split('\n'):
                        if '<link/>' in line:
                            temp_info['link'] = line.replace('<link/>', '')
                            continue
                elif len(normal_link) > 0:
                    temp_info['link'] = normal_link.text if\
                        hasattr(normal_link, 'text')\
                        else normal_link
                if temp_info['link'] is None or\
                        temp_info['link'] == '':
                    _msg = 'No link found for item: {}'.format(
                        temp_info['title']
                    )
                    logger.error(_msg)
                    await discord_commands.log_to_bot_channel(_msg)
                    continue
                if temp_info['link'] is not None or\
                        temp_info['link'] != '':
                    temp_info['hash'] = await get_page_hash(temp_info['link'])
                temp_info['img'] = item.find('itunes:image')['href']
                items_out['items'].append(temp_info)
            items_out = filter_links(items_out)
            return items_out
        except TypeError as e:
            _msg = 'Error processing episodes from {}: {}'.format(
                items_info['pod_name'], e
            )
            logger.error(_msg)
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
            logger.debug(f'Using filter: {filter_out}')
            try:
                if item['title'] is not None:
                    logger.debug(
                        'Checking filter against title `{}`'.format(
                            item['title'].lower()
                        )
                    )
                    if filter_out.lower() in str(item['title']).lower():
                        logger.debug(
                            f'Found filter `{filter_out}` in '
                            'title ({}) - not posting!'.format(item['title'])
                        )
                        return False
            except TypeError:
                logger.error(
                    'Title is not correct type: {} ({})'.format(
                        item['title'], type(item['title'])
                    )
                )
            try:
                if item['description']:
                    logger.debug(
                        'Checking filter against description`{}`'.format(
                            item['description'].lower()
                        )
                    )
                    if filter_out.lower() in str(item['description']).lower():
                        logger.debug(
                            f'Found filter `{filter_out}` in '
                            'description ({}) - not posting!'.format(
                                item['description']
                            )
                        )
                        return False
            except TypeError:
                logger.error(
                    'Description is not correct type: {} ({})'.format(
                        item['description'], type(item['description'])
                    )
                )
            logger.debug(
                'Fant ikke noe filter i tittel eller beskrivelse'
            )
            return True

    logger.debug(
        'Got {} `items` (sample): {}'.format(
            len(items['items']),
            items['items'][0]['title']
        )
    )
    links_out = []
    for item in items['items']:
        logger.debug('Checking item: {}'.format(
            item['title']
        ))
        if item['type'] == 'youtube':
            logger.debug('Checking Youtube item')
            if not config.env('YT_INCLUDE_SHORTS', default='true'):
                shorts_keywords = ['#shorts', '(shorts)']
                if any(kw in str(item['title']).lower()
                        for kw in shorts_keywords) or\
                        any(kw in str(item['description']).lower()
                            for kw in shorts_keywords):
                    logger.debug(
                        'Skipped {} because of `#Shorts` '
                        'or `(shorts)`'.format(
                            item['title']
                        )
                    )
                    continue
        logger.debug('Filters: {}'.format(items['filters']))
        if items['filters'] is not None and len(items['filters']) > 0:
            logger.debug('Found active filters, checking...')
            link_filter = post_based_on_filter(item, items['filters'])
            if link_filter:
                links_out.append(item)
        else:
            links_out.append(item)
    return links_out


async def make_event_start_stop(date, time=None):
    '''
    Make datetime objects for the event based on the start date and time.
    The event will start 30 minutes prior to the match, and it will end 2
    hours and 30 minutes after

    `date`: The match date or a datetime-object
    `time`: The match start time (optional)
    '''
    logger.debug(f'Got `date`: {date}')
    try:
        # Make the original startdate an object
        if time is None:
            start_dt = await datetime_handling.make_dt(date)
        else:
            start_dt = await datetime_handling.make_dt(f'{date} {time}')
        logger.debug(f'`start_dt` is {start_dt}')
    except Exception as e:
        logger.error(f'Got an error: {e}')
        return None
    try:
        start_date = await datetime_handling.get_dt('date', dt=start_dt)
        logger.debug(f'Making `start_date` {start_date}')
        start_time = await datetime_handling.get_dt(
            'time', sep=':', dt=start_dt
        )
        logger.debug(f'Making `start_time` {start_time}')
        # Make a startdate for the event that starts 30 minutes before
        # the match
        start_event = datetime_handling.change_dt(
            start_dt, 'remove', 30, 'minutes'
        )
        logger.debug(f'`start_event` is {start_event}')
        # Make an enddate for the event that should stop approximately
        # 30 minutes after the match is over
        end_dt = datetime_handling.change_dt(
            start_dt, 'add', 2.5, 'hours'
        )
        logger.debug(f'`end_dt` is {end_dt}')
        # Make the epochs that the event will use
        event_start_epoch = await datetime_handling.get_dt(dt=start_event)
        event_end_epoch = await datetime_handling.get_dt(dt=end_dt)
        # Make a relative start object for the game
        start_epoch = await datetime_handling.get_dt(dt=start_dt)
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
        logger.error('Error: {}'.format(e))
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
        logger.error('Got None as url')
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
    logger.debug(f'Got parser `{PARSER}`')
    if PARSER == 'nifs':
        if 'matchId=' not in url:
            # todo var msg
            logger.error('The NIFS url is not from a match page')
            return None
        try:
            parse = await parse_nifs(url)
            return parse
        except Exception as e:
            error_msg = f'Could not parse {url} - '\
                f'got the following error:\n{e}'
            logger.error(error_msg)
            return None
    elif PARSER == 'vglive':
        if '/kamp/' not in url:
            logger.error('The vglive url is not from a match page')
            return None
        try:
            parse = await parse_vglive(url)
            if parse is None:
                return None
            else:
                return parse
        except Exception as e:
            error_msg = f'Could not parse {url} - '\
                f'got the following error:\n{e}'
            logger.error(error_msg)
            return None
    elif PARSER == 'tv2livesport':
        if '/kamper/' not in url:
            # todo var msg
            logger.error('The tv2 url is not from a match page')
            return None
        parse = await parse_tv2livesport(url)
        return parse
    else:
        logger.error('Linken er ikke kjent')
        return None


async def parse_nifs(url_in=None, mock_in=None):
    '''
    Parse match ID from matchpage from nifs.no, then use that in an
    api call
    '''
    base_url = 'https://api.nifs.no/matches/{}'
    # Get info relevant for the event
    if url_in:
        _id = re.match(r'.*matchId=(\d+)\b', url_in).group(1)
        match_json = await get_link(
            url_in=base_url.format(_id)
        )
        match_json = json.loads(match_json)
    elif mock_in:
        match_json = await get_link(
            mock_file=mock_in
        )
    date_in = match_json['timestamp']
    _date_obj = await datetime_handling.make_dt(date_in)
    dt_in = await make_event_start_stop(_date_obj)
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


async def parse_vglive(url_in=None, mock_in=None, mock_in_tv=None):
    '''
    Parse match ID from matchpage from vglive.no, then use that in an
    api call
    '''
    base_url = 'https://vglive.vg.no/bff/vg/events/{}'
    tv_url = 'https://vglive.vg.no/bff/vg/events/tv-channels?eventIds={}'

    # Get info relevant for the event
    if url_in:
        _id = re.match(r'.*/kamp/.*/(\d+)/.*', url_in).group(1)
        _match_info = await get_link(base_url.format(_id))
        match_json = json.loads(_match_info)
    elif mock_in:
        match_json = await get_link(
            mock_file=mock_in
        )
        _id = match_json['event']['id']
    if isinstance(match_json, int):
        # TODO i18n
        error_msg = 'Link received HTTP status code {}'.format(match_json)
        logger.error(error_msg)
        await discord_commands.log_to_bot_channel(error_msg)
        return None
    logger.debug(f'Got `match_json`:\n{pformat(match_json)}')
    if mock_in and mock_in_tv:
        tv_json = await get_link(
            mock_file=mock_in_tv
        )
    else:
        _tv_info = await get_link(tv_url.format(_id))
        tv_json = json.loads(_tv_info)
    logger.debug(f'Got `tv_json`:\n{pformat(tv_json)}')
    teams = match_json['event']['participantIds']
    if 'venue' in match_json['event']['details']:
        stadium = match_json['event']['details']['venue']['name']
    else:
        stadium = None
    logger.debug(f'Got `stadium`: {stadium}')
    logger.debug('Channels ({}): {}'.format(
        len(tv_json['tvChannels']),
        tv_json['tvChannels']
    ))
    if len(tv_json['tvChannels']) > 0:
        tv = tv_json['tvChannels'][_id][0]['name']
    else:
        tv = None
    logger.debug(f'Got `tv`: {tv}')
    date_in = match_json['event']['startDate']
    _date_obj = await datetime_handling.make_dt(date_in)
    logger.debug(f'`_date_obj` is {_date_obj}')
    dt_in = await make_event_start_stop(_date_obj)
    if dt_in is None:
        logger.error('`dt_in` is None')
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


async def parse_tv2livesport(url_in=None, mock_in=None):
    '''
    Parse match ID from matchpage from tv2.no/livesport, then use that
    in an API call
    '''
    base_url = 'https://livesport-api.alpha.tv2.no/v3/football/'\
        'matches/{}/result'
    # Get info relevant for the event
    if url_in:
        _id = re.match(
            r'.*tv2.no/livesport/.*/kamper/.*/([a-f0-9\-]+)', url_in
        ).group(1)
        match_info = await get_link(base_url.format(_id))
        match_json = json.loads(match_info)
    elif mock_in:
        match_json = await get_link(
            mock_file=mock_in
        )
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
    _date_obj = await datetime_handling.make_dt(date_in)
    dt_in = await make_event_start_stop(_date_obj)
    if dt_in is None:
        logger.error('Error with `dt_in`')
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


async def extract_color_from_image_url(image_url):
    async with httpx.AsyncClient() as client:
        response = await client.get(image_url)
    image = Image.open(BytesIO(response.content)).convert('RGB')
    image = image.resize((50, 50))  # Nedskalere for raskere prosessering

    pixels = np_array(image).reshape(-1, 3)
    avg_color = pixels.mean(axis=0).astype(int)

    return '{:02X}{:02X}{:02X}'.format(*avg_color)


def clean_pod_description(desc_in):
    if '.]]>' in desc_in:
        desc_in = desc_in.split('.]]>')[0]
    desc_in = desc_in.replace('<p>', '\n')
    desc_in = re.sub(r'<(p|br)>', '\n', desc_in)
    desc_in = re.sub(r'<\/?\w+>|<\w+\s+.*?>', '', desc_in)
    if 'hosted on acast. see' in desc_in.lower():
        desc_in = desc_in.split(
            'Hosted on Acast'
        )[0]
    desc_in = desc_in.split('See omnystudio.com/listener for')[0]
    return desc_in


async def get_page_hash(url, debug=False):
    'Get hash of page at `url`'
    req = await get_link(url)
    if req is None:
        logger.error('Could not get link')
        return None
    desc = None
    soup = BeautifulSoup(req, features='html.parser')
    if desc is None and 'youtube.com' in url:
        logger.debug('Trying yt check')
        ydl_opts = {
            'simulate': True,
            'download': False,
            'ignoreerrors': True,
            'quiet': True
        }
        with YoutubeDL(ydl_opts) as ydl:
            yt_info = ydl.extract_info(url)
        desc = yt_info['fulltitle']
    if desc is None and 'open.spotify.com' in url:
        logger.debug('Trying spotify check')
        try:
            check_if_spotify = soup.find('meta', attrs={'content': 'Spotify'})
            if check_if_spotify is not None:
                desc = soup.find(
                    'meta', attrs={'name': 'description'}
                )['content']
                desc = re.search(
                    r'.*Listen to this episode from .* on Spotify. (.*)', desc
                ).group(1)
                desc = re.sub(r'\b\.\b', '\n', desc)
        except TypeError:
            pass
    dt = await datetime_handling.get_dt(
        format="revdatetimefull", sep="-"
    )
    if desc is None:
        logger.debug('Trying podcast check')
        if soup.find('enclosure'):
            desc = soup.find('description').text
    if desc is None:
        script_json = soup.find('script', attrs={'type': 'application/json'})
        if script_json:
            info_json = json.loads(script_json.text)
            try:
                desc = info_json['props']['pageProps']['clip']['Description']
            except KeyError:
                desc = info_json['props']['pageProps']['episode']['summary']
    if desc is None:
        logger.debug('Trying common html')
        try:
            desc = soup.find('meta', attrs={'name': 'description'})
            if desc is not None:
                desc = desc['content']
            if desc is None:
                logger.info(
                    f'Error when trying to hash description in {url},'
                    'trying to find an article tag instead'
                )
                desc = soup.find('article').text
            if debug:
                file_io.write_file(
                    envs.LOG_DIR / 'HTTP_files' / f'{dt}.html', soup
                )
                return
            logger.debug(f'Got this description: {desc[0:200]}')
        except Exception as e:
            logger.error(f'Error when trying to hash RSS-desc {url}: {e}')
    if debug:
        file_io.write_file(
            envs.LOG_DIR / 'HTTP_files' / f'{dt}.html', soup
        )
    if desc is None:
        hash = desc
        logger.debug(f'Using desc: {desc[0:200]}')
    elif desc is not None:
        hash = md5(str(desc).encode('utf-8')).hexdigest()
    logger.debug(f'Got `hash`: {hash}')
    return hash


if __name__ == "__main__":
    pass
