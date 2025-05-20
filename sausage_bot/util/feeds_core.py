#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'feeds_core: Core functions for RSS and Youtube feeds'
from bs4 import BeautifulSoup
from lxml import etree
from tabulate import tabulate
from uuid import uuid4
import discord
import re
import json
from hashlib import md5
from pprint import pformat

from sausage_bot.util import config, envs, datetime_handling, file_io
from sausage_bot.util import discord_commands, net_io, db_helper, file_io
from sausage_bot.util.args import args
from sausage_bot.util.i18n import I18N

logger = config.logger

async def check_if_feed_name_exist(feed_name):
    feeds = await db_helper.get_output(
        template_info=envs.rss_db_schema,
        select='feed_name'
    )
    feeds = [feed['feed_name'] for feed in feeds]
    logger.debug(f'`feeds`: {feeds}')
    return feed_name not in feeds


async def check_feed_validity(url_in, mock_file=None):
    'Make sure that `url_in` is a valid link with feed items'
    if args.rss_skip_url_validation:
        logger.debug('Skipping url validation')
        return True
    sample_item = None
    logger.debug(f'Checking `url_in`: {url_in}')
    req = await net_io.get_link(url_in, mock_file=mock_file)
    logger.debug(f'req is ({type(req)})')
    if req is None:
        logger.debug('Returned None')
        return None
    elif isinstance(req, int):
        return req
    if 'open.spotify.com/show/' in url_in:
        logger.debug('Discovered Spotify branded link')
        sample_item = await net_io.check_spotify_podcast(
            url=url_in, mock_file=mock_file
        )
    else:
        logger.debug('Discovered normal link')
        _items = await get_items_from_rss(
            req=req,
            url=url_in,
            num_items=1
        )
        if isinstance(_items, list):
            sample_item = _items[0]
    logger.debug(f'Got `sample_item`: {sample_item}')
    if sample_item is None:
        return False
    try:
        logger.debug(f'`req` is a {type(req)}')
        BeautifulSoup(req, features='xml')
        return True
    except (etree.XMLSyntaxError) as e:
        logger.error('Error: {}'.format(e))
        return False


async def get_page_hash(url):
    'Get hash of page at `url`'
    req = await net_io.get_link(url)
    if req is None:
        logger.error('Could not get link')
        return None
    desc = None
    try:
        soup = BeautifulSoup(req, features='xml')
        desc = soup.find('meta', attrs={'name': 'description'})
    except Exception as e:
        logger.error(f'Error when trying to hash RSS-desc {url}: {e}')
    try:
        soup = BeautifulSoup(req, features='html.parser')
        _scripts = soup.find_all('script')
        for _script in _scripts:
            if 'var ytInitialData =' in _script.text:
                _script = re.match(r'^var ytInitialData = (.*);$', _script.text).group(1)
                _script = json.loads(_script)
                desc = _script['contents']['twoColumnWatchNextResults']['results']['results']['contents'][1]['videoSecondaryInfoRenderer']['attributedDescription']['content']
    except Exception as e:
        logger.error(f'Error when trying to hash YT-desc {url}: {e}')
        soup = BeautifulSoup(req, features='html.parser')
        _scripts = soup.find_all('script')
        for _script in _scripts:
            if 'var ytInitialData =' in _script.text:
                _script = re.match(r'^var ytInitialData = (.*);$', _script.text).group(1)
                _script = json.loads(_script)
                desc = _script['contents']['twoColumnWatchNextResults']['results']['results']['contents'][0]['videoPrimaryInfoRenderer']['title']['runs'][0]['text']
        _file_date = datetime_handling.get_dt(
            format='revdatetimefull', sep='_'
        )
        error_out = f'{url}: {e}\n\n'
        error_out += str(_scripts)
        file_io.write_file(
            envs.LOG_DIR / 'YT_ERRORS' / f'{_file_date}.html',
            error_out
        )
    if desc is not None:
        hash = md5(str(desc).encode('utf-8')).hexdigest()
    else:
        hash = desc
    logger.debug(f'Got `hash`: {hash}')
    return hash


async def get_items_from_rss(
    req, url, filters_in=None, log_in=None, num_items=None
) -> list:
    try:
        soup = BeautifulSoup(req, features='xml')
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
    items_out = {
        'filters': filters_in,
        'items': [],
        'log': log_in
    }
    items_info = {
        'type': '',
        'title': '',
        'description': '',
        'hash': '',
        'link': ''
    }
    # Gets podcast feed
    if soup.find('enclosure') and 'audio' in soup.find('enclosure')['type']:
        logger.debug('Found podcast feed')
        if isinstance(num_items, int) and num_items > 0:
            all_items = soup.find_all('item')[0:num_items]
        else:
            all_items = soup.find_all('item')
        for item in all_items:
            temp_info = items_info.copy()
            temp_info['type'] = 'podcast'
            temp_info['title'] = item.find('title').text if\
                hasattr(item.find('title'), 'text') else\
                item.find('title')
            temp_info['description'] = item.find('description').text if\
                hasattr(item.find('description'), 'text') else\
                item.find('description')
            temp_info['hash'] = md5(
                str(temp_info['description']).encode('utf-8')
            ).hexdigest()
            temp_info['link'] = item.find('link').text if\
                hasattr(item.find('link'), 'text') else\
                item.find('link')
            items_out['items'].append(temp_info)
    # Gets Youtube feed
    elif soup.find('yt:channelId'):
        logger.debug('Found Youtube feed')
        if isinstance(num_items, int) and num_items > 0:
            all_entries = soup.find_all('entry')[0:num_items]
        else:
            all_entries = soup.find_all('entry')
        for item in all_entries:
            temp_info = items_info.copy()
            temp_info['type'] = 'youtube'
            temp_info['title'] = item.find('title').text if\
                hasattr(item.find('title'), 'text') else\
                item.find('title')
            temp_info['description'] = item.find('media:description').text if\
                hasattr(item.find('media:description'), 'text') else\
                item.find('media:description')
            temp_info['hash'] = md5(
                str(temp_info['description']).encode('utf-8')
            ).hexdigest()
            temp_info['link'] = item.find('link')['href']
            items_out['items'].append(temp_info)
    # Gets plain articles
    else:
        logger.debug('Found normal RSS feed')
        article_method = False
        if len(soup.find_all('item')) > 0:
            article_method = 'item'
        elif len(soup.find_all('entry')) > 0:
            article_method = 'entry'
        else:
            logger.error('Could not find any articles')
            return None
        if isinstance(num_items, int) and num_items > 0:
            all_items = soup.find_all(article_method)[0:num_items]
        else:
            all_items = soup.find_all(article_method)
        for item in all_items:
            temp_info = items_info.copy()
            temp_info['type'] = 'rss'
            temp_info['title'] = item.find('title').text
            if item.find('description'):
                temp_info['description'] = item.find('description').text
            elif item.find('media:keywords'):
                temp_info['description'] = item.find('media:keywords')
            elif item.find('content'):
                temp_info['description'] = item.find('content').text
            else:
                temp_info['description'] = None
            if temp_info['description'] is not None:
                temp_info['hash'] = md5(
                    str(temp_info['description']).encode('utf-8')
                ).hexdigest()
            else:
                temp_info['hash'] = None
            if article_method == 'item':
                temp_info['link'] = item.find('link').text
            elif article_method == 'entry':
                temp_info['link'] = item.find('link')['href']
            logger.debug(f'Got `temp_info`: {temp_info}')
            items_out['items'].append(temp_info)
    links_out = net_io.filter_links(items_out)
    return links_out


async def add_to_feed_db(
    feed_type, name, feed_link=None, channel=None, user_add=None,
    yt_id=None, playlist_id=None
):
    '''
    Add a an item to the feeds table in db

    `feed_type`:
    `name`:         The identifiable name of the added feed
    `feed_link`:    The link for the feed
    `channel`:      The discord channel to post the feed to
    `user_add`:     The user who added the feed
    `yt_id`:        yt-id
    ``playlist_id`: id of playlist
    '''

    if feed_type not in ['rss', 'youtube', 'spotify']:
        logger.error('Function requires `feed_type`')
        return None
    # Test the link first
    test_link = await net_io.get_link(feed_link)
    if not args.rss_skip_url_validation:
        if test_link is None:
            logger.debug('`test_link` is None')
            return None
        elif isinstance(test_link, int):
            logger.debug(f'`test_link` returns code {test_link}')
            return test_link
    else:
        logger.debug('Skipping url validation')
    date_now = datetime_handling.get_dt(format='datetime')
    if feed_type in ['rss', 'spotify']:
        await db_helper.insert_many_some(
            envs.rss_db_schema,
            rows=(
                'uuid', 'feed_name', 'url', 'channel', 'added', 'added_by',
                'feed_type', 'status_url', 'status_url_counter',
                'status_channel', 'num_episodes'
            ),
            inserts=(
                (
                    str(uuid4()), name, feed_link, channel, date_now,
                    user_add, feed_type, envs.FEEDS_URL_SUCCESS, 0,
                    envs.CHANNEL_STATUS_SUCCESS, 0
                )
            )
        )
    elif feed_type == 'youtube':
        await db_helper.insert_many_some(
            envs.youtube_db_schema,
            rows=(
                'uuid', 'feed_name', 'url', 'channel', 'added', 'added_by',
                'status_url', 'status_url_counter', 'status_channel',
                'youtube_id', 'playlist_id'
            ),
            inserts=(
                (
                    str(uuid4()), name, feed_link, channel, date_now,
                    user_add, envs.FEEDS_URL_SUCCESS, 0,
                    envs.CHANNEL_STATUS_SUCCESS, yt_id, playlist_id
                )
            )
        )


async def remove_feed_from_db(feed_type, feed_name):
    'Remove a feed from `feed file` based on `feed_name`'
    removal_ok = True
    if feed_type in ['rss', 'spotify']:
        feed_db = envs.rss_db_schema
        feed_db_filter = envs.rss_db_filter_schema
    elif feed_type == 'youtube':
        feed_db = envs.youtube_db_schema
        feed_db_filter = envs.youtube_db_filter_schema
    uuid_from_db = await db_helper.get_output(
        template_info=feed_db,
        select=('uuid'),
        where=[('feed_name', feed_name)],
        single=True
    )
    uuid_from_db = uuid_from_db['uuid']
    logger.debug(f'`uuid_from_db` is {uuid_from_db}')
    removal = await db_helper.del_row_by_AND_filter(
        feed_db,
        where=('uuid', uuid_from_db)
    )
    logger.debug(f'`removal` is {removal}')
    if not removal:
        removal_ok = False
    removal_filters = await db_helper.del_row_by_AND_filter(
        feed_db_filter,
        where=('uuid', uuid_from_db)
    )
    logger.debug(f'`removal_filters` is {removal_filters}')
    if not removal_filters:
        removal_ok = False
    return removal_ok


async def get_feed_links(feed_type, feed_info):
    'Get the links from a feed'
    UUID = feed_info['uuid']
    if feed_type == 'rss':
        URL = feed_info['url']
        feed_db_filter = envs.rss_db_filter_schema
        feed_db_log = envs.rss_db_log_schema
    elif feed_type == 'youtube':
        if feed_info['playlist_id'] is not None:
            URL = envs.YOUTUBE_PLAYLIST_RSS_LINK.format(
                feed_info['playlist_id']
            )
        else:
            URL = envs.YOUTUBE_RSS_LINK.format(feed_info['youtube_id'])
        feed_db_filter = envs.youtube_db_filter_schema
        feed_db_log = envs.youtube_db_log_schema
    else:
        URL = feed_info['url']
    # Get the url and make it parseable
    if feed_type in ['rss', 'youtube']:
        req = await net_io.get_link(URL)
        if isinstance(req, int):
            return req
        if req is not None or not isinstance(req, int):
            filters_db = await db_helper.get_output(
                template_info=feed_db_filter,
                select=('allow_or_deny', 'filter'),
                where=[('uuid', UUID)]
            )
            log_db = await db_helper.get_output(
                template_info=feed_db_log,
                where=[('uuid', UUID)]
            )
            links_out = await get_items_from_rss(
                req=req, url=URL, filters_in=filters_db,
                log_in=log_db, num_items=5
            )
            logger.debug('Got {} items from `get_items_from_rss`'.format(
                len(links_out) if links_out is not None else 0
            ))
            return links_out
        else:
            return


async def get_feed_list(
    db_in: str = None, db_filter_in: str = None, list_type: str = None,
    link_type: str = None
):
    '''
    Get a prettified list of feeds.

    Parameters
    ------------
    db_in: str
        Database to get feeds from (default: None)
    db_filter_in: str
        Database with the filters (default: None)
    list_type: str
        If specified, should show that specific list_type
    link_type: str
        If specified, should show that specific link_type
    '''

    async def split_lengthy_list(table_in):
        def split_list(lst, chunk_size):
            chunks = [[] for _ in range(
                (len(lst) + chunk_size - 1) // chunk_size
            )]
            for i, item in enumerate(lst):
                chunks[i // chunk_size].append(item)
            return chunks
        logger.debug(f'length of table_in: {len(table_in)}')
        max_post_limit = 1900
        paginated = []
        if len(table_in) >= max_post_limit:
            line_len = len(table_in.split('\n')[1])
            logger.debug(f'Each line is {line_len} chars long')
            post_limit = int(max_post_limit / line_len)
            logger.debug(f'Each post can therefore hold {post_limit} lines')
            splits = split_list(table_in.split('\n')[2:], post_limit - 2)
            header = table_in.split('\n')[0]
            header += '\n{}'.format(table_in.split('\n')[1])
            temp_page = ''
            for split in splits:
                temp_page = header
                for line in split:
                    temp_page += f'\n{line}'
                paginated.append(temp_page)
        else:
            paginated.append(table_in)
        return paginated

    _guild = discord_commands.get_guild()
    if link_type == I18N.t(
        'youtube.commands.list.literal_link_type.channel'
    ):
        wheres_in = [('playlist_id', 'IS', 'None')]
    elif link_type == I18N.t(
        'youtube.commands.list.literal_link_type.playlist'
    ):
        wheres_in = [('playlist_id', 'IS NOT', 'None')]
    else:
        wheres_in = None
    if list_type is None:
        feeds_out = await db_helper.get_output(
            template_info=db_in,
            select=(
                'feed_name', 'url', 'channel', 'playlist_id'
            ),
            where=wheres_in,
            order_by=[
                ('feed_name', 'ASC')
            ]
        )
        for feed in feeds_out:
            feed['channel'] = _guild.get_channel(
                int(feed['channel'])
            ).name
            if feed['playlist_id'] is None:
                feed['playlist_id'] = I18N.t(
                    'common.channel'
                )
            else:
                feed['playlist_id'] = I18N.t(
                    'common.playlist'
                )
        logger.debug(f'`feeds_out` is {feeds_out}')
        # Return None if empty db
        if feeds_out is None:
            logger.info('No feeds in database')
            return None
        headers = {
            'feed_name': I18N.t('feeds_core.list_headers.feed_name'),
            'url': I18N.t('feeds_core.list_headers.url'),
            'channel': I18N.t('feeds_core.list_headers.channel'),
            'playlist_id': I18N.t('feeds_core.list_headers.link_type')
        }
        maxcolwidths = [None, None, None, None]
    elif list_type == 'added':
        feeds_out = await db_helper.get_output(
            template_info=db_in,
            select=(
                'feed_name', 'url', 'channel', 'added', 'added_by', 'playlist_id'
            ),
            where=wheres_in,
            order_by=[
                ('feed_name', 'ASC')
            ]
        )
        for feed in feeds_out:
            feed['channel'] = _guild.get_channel(
                int(feed['channel'])
            ).name
            if re.match(r'(\d+)', feed['added_by']):
                feed['added_by'] = _guild.get_member(
                    int(feed['added_by'])
                ).name
            if feed['playlist_id'] is None:
                feed['playlist_id'] = I18N.t(
                    'common.channel'
                )
            else:
                feed['playlist_id'] = I18N.t(
                    'common.playlist'
                )
        # Return None if empty db
        if len(feeds_out) <= 0:
            logger.info('No feeds in database')
            return None
        headers = {
            'feed_name': I18N.t('feeds_core.list_headers.feed_name'),
            'url': I18N.t('feeds_core.list_headers.url'),
            'channel': I18N.t('feeds_core.list_headers.channel'),
            'added': I18N.t('feeds_core.list_headers.added'),
            'added_by': I18N.t('feeds_core.list_headers.added_by'),
            'playlist_id': I18N.t('feeds_core.list_headers.link_type')
        }
        maxcolwidths = [None, None, None, None, None, None]
    elif list_type == 'filter':
        if db_filter_in is None:
            logger.error('`db_filter_in` is not specified')
            return None
        feeds_db = await db_helper.get_output(
            template_info=db_in,
            select=(
                'uuid', 'feed_name', 'channel', 'playlist_id'
            ),
            where=wheres_in,
            order_by=[
                ('feed_name', 'ASC')
            ]
        )
        logger.debug(f'Got `feeds_db`:\n{pformat(feeds_db)}')
        feeds_filter = await db_helper.get_output(
            template_info=db_filter_in,
            order_by=[
                ('uuid', 'DESC'),
                ('filter', 'ASC')
            ]
        )
        logger.debug(f'Got `feeds_filter`:\n{pformat(feeds_filter)}')
        feeds_out = []
        for feed in feeds_db:
            filter_uuid = [
                filter_item for filter_item in feeds_filter
                if filter_item['uuid'] == feed['uuid']
            ]
            logger.debug(f'`filter_uuid` is {filter_uuid}')
            filter_allow = [
                filter_item['filter'] for filter_item in filter_uuid
                if filter_item['allow_or_deny'].lower() == 'allow'
            ]
            logger.debug(f'`filter_allow` is {filter_allow}')
            filter_deny = [
                filter_item['filter'] for filter_item in filter_uuid
                if filter_item['allow_or_deny'].lower() == 'deny'
            ]
            logger.debug(f'`filter_deny` is {filter_deny}')
            temp_list = []
            temp_list.append(feed['feed_name'])
            temp_list.append(
                _guild.get_channel(
                    int(feed['channel'])
                ).name
            )
            temp_list.append(
                ', '.join(item for item in filter_allow)
            )
            temp_list.append(
                ', '.join(item for item in filter_deny)
            )
            feeds_out.append(temp_list)
            logger.debug(f'`temp_list` is {temp_list}')
        headers = ('Feed', 'Channel', 'Allow', 'Deny')
        maxcolwidths = [None, None, 30, 30]
    if len(feeds_out) <= 0:
        return None
    table_out = tabulate(
        tabular_data=feeds_out,
        headers=headers,
        maxcolwidths=maxcolwidths
    )
    return await split_lengthy_list(table_out)


async def link_is_in_log(link, log_in, log_env, channel, uuid):
    '''
    Check if a link already is in the log. Replace and repost if it is
    similar to a logged link.
    '''
    async def replace_post(link, log_in, link_hash, channel, uuid):
        # Replace link on discord and add link to log
        list_of_old_links = []
        for item in log_in:
            if item['hash'] == link_hash:
                list_of_old_links.append(item['url'])
        logger.debug('Replacing link in discord message')
        await discord_commands.replace_post(
            list_of_old_links, link, channel
        )

    link_in_log = None
    hash_in_log = None
    link_hash = None
    if log_in is None:
        logger.debug('Log is empty')
        return False
    logger.debug(f'log_in is {log_in}')
    link_hash = await get_page_hash(link)
    logger.debug(f'Link hash is `{link_hash}`')
    if link in [log_url['url'] for log_url in log_in]:
        logger.debug('Link in log')
        link_in_log = True
    else:
        link_in_log = False
    if len(log_in) > 0:
        if 'hash' in log_in[0]:
            if link_hash in [log_url['hash'] for log_url in log_in]:
                logger.debug('Hash in log')
                hash_in_log = True
            else:
                hash_in_log = False
    else:
        hash_in_log = False
    if ((link_in_log and hash_in_log) or
            (link_in_log and hash_in_log is None)):
        logger.debug('Link is in log, returning True')
        return True
    if link_in_log and not hash_in_log:
        logger.debug('Link is in log, but hash has changed. Replacing...')
        await replace_post(link, log_in, link_hash, channel)
        logger.debug('Adding link to log')
        await log_link(
            log_env, uuid, link, link_hash
        )
        return True
    elif not link_in_log and hash_in_log:
        logger.debug(
            'Hash in log, but link is not. '
            'Adding to log and replacing post'
        )
        await replace_post(link, log_in, link_hash, channel, uuid)
        return True
    elif not link_in_log and hash_in_log is None:
        logger.debug('Link is not in log, logging it and returning False')
        await log_link(
            log_env, uuid, link, link_hash
        )
        return False


async def log_link(template_info, uuid, feed_link, page_hash):
    print(
        f'Got these vars: template_info: {template_info}, uuid: {uuid}, '
        f'feed_link: {feed_link}, page_hash: {page_hash}'
    )
    inserts = [
        uuid, feed_link, str(
            datetime_handling.get_dt(
                format='ISO8601'
            )
        )
    ]
    if page_hash is not None:
        inserts.append(page_hash)
    logger.debug(f'Adding this to log:\n{pformat(inserts)}')

    await db_helper.insert_many_all(
        template_info=template_info,
        inserts=[inserts]
    )


async def process_links_for_posting_or_editing(
    feed_type: str, uuid, FEED_POSTS, CHANNEL
):
    '''
    Compare links in `FEED_POSTS` items to posts belonging to `feed` to see
    if they already have been posted or not.
    - If not posted, post to `CHANNEL`
    - If posted, make a similarity check just to make sure we are not posting
    duplicate links because someone's aggregation systems can't handle
    editing urls with spelling mistakes. If it is similar, but not identical,
    replace the logged link and edit the previous post with the new link.

    `feed`:             Name of the feed to process
    `FEED_POSTS`:       The newly received feed posts
    `CHANNEL`:          Discord channel to post/edit
    '''
    logger.debug(
        'Starting `process_links_for_posting_or_editing`'
    )
    if feed_type not in ['rss', 'youtube', 'spotify']:
        logger.error('Function requires `feed_type`')
        return None
    if feed_type in ['rss', 'spotify']:
        feed_db_log = envs.rss_db_log_schema
        FEED_SETTINGS = await db_helper.get_output(
            template_info=envs.rss_db_settings_schema,
            select=('setting', 'value')
        )
    elif feed_type == 'youtube':
        feed_db_log = envs.youtube_db_log_schema
        FEED_SETTINGS = None
    if FEED_POSTS is None:
        logger.debug('`FEED_POSTS` is None')
        return None
    logger.debug(f'Got {len(FEED_POSTS)} items in `FEED_POSTS`')
    if feed_type == 'rss':
        FEED_LOG = await db_helper.get_output(
            template_info=feed_db_log,
            select=('url', 'hash'),
            where=[('uuid', uuid)]
        )
    else:
        FEED_LOG = await db_helper.get_output(
            template_info=feed_db_log,
            select=('url'),
            where=[('uuid', uuid)]
        )
    FEED_SETTINGS = dict(FEED_SETTINGS) if FEED_SETTINGS is not None\
        else FEED_SETTINGS
    for item in FEED_POSTS[0:3].reverse():
        logger.debug(f'Got this item:\n{item}')
        if isinstance(item, str):
            feed_link = item
        elif isinstance(item, dict):
            feed_link = item['link']
        # Check if the link is in the log
        logger.debug(f'Checking if link `{feed_link}` is in log')
        link_in_log = await link_is_in_log(
            feed_link, FEED_LOG, feed_db_log, CHANNEL, uuid
        )
        if link_in_log:
            logger.debug(f'Link `{feed_link}` already logged. Skipping.')
            continue
        elif not link_in_log:
            # Add link to log
            _page_hash = await get_page_hash(feed_link)
            logger.debug(
                f'Link {feed_link} got hash {_page_hash}'
            )
            await log_link(
                template_info=feed_db_log, uuid=uuid,
                feed_link=feed_link, page_hash=_page_hash
            )
            # Consider this a whole new post and post link to channel
            logger.debug(f'Posting link `{feed_link}`')
            if isinstance(item, dict) and item['type'] == 'spotify':
                logger.debug(
                    'Found a podcast that should '
                    f'be embedded:\n{pformat(item)}',
                )
                embed_color = await net_io.\
                    extract_color_from_image_url(
                        item['img']
                    )
                embed = discord.Embed(
                    title=item['title'],
                    url=item['link'],
                    description='{}\n\n{}'.format(
                        item['description'],
                        '[🎧 HØR PÅ SPOTIFY 🎧]({})'.format(
                            item['link']
                        )
                    ),
                    colour=discord.Color.from_str(f'#{embed_color}')
                )
                embed.set_author(name=item['pod_name'])
                embed.set_image(url=item['img'])
                desc_setting = 'show_pod_description_in_embed'
                if desc_setting in FEED_SETTINGS\
                        and FEED_SETTINGS[desc_setting].lower()\
                        == 'true':
                    embed.set_footer(text=item['pod_description'])
                logger.debug(
                    f'Sending this embed to channel:\n{pformat(embed)}'
                )
                if args.testmode:
                    logger.debug(embed, color='yellow')
                else:
                    await discord_commands.post_to_channel(
                        CHANNEL, embed_in=embed
                    )
            else:
                logger.debug('Found a regular post')
                if args.testmode:
                    logger.debug(
                        f'TESTMODE: Would post this link: {feed_link}',
                        color='yellow'
                    )
                else:
                    await discord_commands.post_to_channel(
                        CHANNEL, feed_link
                    )


if __name__ == "__main__":
    pass
