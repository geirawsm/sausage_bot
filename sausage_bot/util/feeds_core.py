#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from lxml import etree
from tabulate import tabulate
from uuid import uuid4
import re

from sausage_bot.util import envs, datetime_handling, file_io, discord_commands
from sausage_bot.util import net_io, db_helper, config

from .log import log


async def check_if_feed_name_exist(feed_name):
    feeds = await db_helper.get_output(
        template_info=envs.rss_db_schema,
        select='feed_name'
    )
    feeds = [feed[0] for feed in feeds]
    log.debug(f'`feeds`: {feeds}')
    if feed_name not in feeds:
        return False
    else:
        return True


async def check_url_validity(url):
    'Make sure that `url` is a valid link'
    log.verbose(f'Checking `{url}`')
    req = await net_io.get_link(url)
    log.debug(f'req is ({type(req)})')
    if req is None:
        return False
    else:
        return True


async def check_feed_validity(url):
    'Make sure that `url` is a valid link'
    log.verbose(f'Checking `{url}`')
    req = await net_io.get_link(url)
    log.debug(f'req is ({type(req)})')
    if req is None:
        return None
    sample_item = await get_items_from_rss(
        req=req,
        url=url,
        test=True
    )
    log.debug(f'`sample_item`: {sample_item}')
    if req is None:
        log.verbose('Returned None')
        return False

    try:
        log.verbose(f'`req` is a {type(req)}')
        # etree.fromstring(req, parser=etree.XMLParser(encoding='utf-8'))
        BeautifulSoup(req, features='xml')
        return True
    except (etree.XMLSyntaxError) as e:
        log.error(envs.ERROR_WITH_ERROR_MSG.format(e))
        return False


async def get_items_from_rss(
    req, url, filters_in=None, log_in=None, test: bool = False
) -> list:
    try:
        soup = BeautifulSoup(req, features='xml')
    except Exception as e:
        log.error(envs.FEEDS_SOUP_ERROR.format(url, e))
        return None
    links_out = []
    # If used for testing feeds, only get one article
    if test:
        max_items = 1
    else:
        max_items = 3
    items_out = {
        'filters': filters_in,
        'items': [],
        'log': log_in
    }
    items_info = {
        'type': '',
        'title': '',
        'description': '',
        'link': ''
    }
    # Gets podcast feed
    if soup.find('enclosure') and 'audio' in soup.find('enclosure')['type']:
        log.debug('Found podcast feed')
        all_items = soup.find_all('item')
        for item in all_items[0:max_items]:
            temp_info = items_info.copy()
            temp_info['type'] = 'podcast'
            temp_info['title'] = item.find('title').text
            temp_info['description'] = item.find('description').text
            temp_info['link'] = item.find('link').text
            items_out['items'].append(temp_info)
    # Gets Youtube feed
    elif soup.find('yt:channelId'):
        log.debug('Found Youtube feed')
        all_entries = soup.find_all('entry')
        for item in all_entries[0:max_items]:
            temp_info = items_info.copy()
            temp_info['type'] = 'youtube'
            temp_info['title'] = item.find('title').text
            temp_info['description'] = item.find('media:description').text
            temp_info['link'] = item.find('link')['href']
            items_out['items'].append(temp_info)
    # Gets plain articles
    else:
        log.debug('Found normal RSS feed')
        article_method = False
        if len(soup.find_all('item')) > 0:
            article_method = 'item'
        elif len(soup.find_all('entry')) > 0:
            article_method = 'entry'
        else:
            log.error('Klarte ikke finne ut av feed?')
            return None
        all_items = soup.find_all(article_method)
        for item in all_items[0:max_items]:
            temp_info = items_info.copy()
            temp_info['type'] = 'rss'
            if article_method == 'item':
                temp_info['title'] = item.find('title').text
                temp_info['description'] = item.find('media:keywords')
                temp_info['link'] = item.find('link').text
            elif article_method == 'entry':
                temp_info['title'] = item.find('title').text
                temp_info['description'] = item.find('content').text
                temp_info['link'] = item.find('link')['href']
            log.debug(f'Got `temp_info`: {temp_info}')
            items_out['items'].append(temp_info)
    links_out = net_io.filter_links(items_out)
    links_out.reverse()
    return links_out


async def get_items_from_spotify(
    url, filters_in=None, log_in=None, test: bool = False
) -> list:
    try:
        soup = BeautifulSoup(req, features='xml')
    except Exception as e:
        log.error(envs.FEEDS_SOUP_ERROR.format(url, e))
        return None
    links_out = []
    # If used for testing feeds, only get one article
    if test:
        max_items = 1
    else:
        max_items = 3
    items_out = {
        'filters': filters_in,
        'items': [],
        'log': log_in
    }
    items_info = {
        'type': '',
        'title': '',
        'description': '',
        'link': ''
    }
    # Gets podcast feed
    if soup.find('enclosure') and 'audio' in soup.find('enclosure')['type']:
        log.debug('Found podcast feed')
        all_items = soup.find_all('item')
        for item in all_items[0:max_items]:
            temp_info = items_info.copy()
            temp_info['type'] = 'podcast'
            temp_info['title'] = item.find('title').text
            temp_info['description'] = item.find('description').text
            temp_info['link'] = item.find('link').text
            items_out['items'].append(temp_info)
    # Gets Youtube feed
    elif soup.find('yt:channelId'):
        log.debug('Found Youtube feed')
        all_entries = soup.find_all('entry')
        for item in all_entries[0:max_items]:
            temp_info = items_info.copy()
            temp_info['type'] = 'youtube'
            temp_info['title'] = item.find('title').text
            temp_info['description'] = item.find('media:description').text
            temp_info['link'] = item.find('link')['href']
            items_out['items'].append(temp_info)
    # Gets plain articles
    else:
        log.debug('Found normal RSS feed')
        article_method = False
        if len(soup.find_all('item')) > 0:
            article_method = 'item'
        elif len(soup.find_all('entry')) > 0:
            article_method = 'entry'
        else:
            log.error('Klarte ikke finne ut av feed?')
            return None
        all_items = soup.find_all(article_method)
        for item in all_items[0:max_items]:
            temp_info = items_info.copy()
            temp_info['type'] = 'rss'
            if article_method == 'item':
                temp_info['title'] = item.find('title').text
                temp_info['description'] = item.find('media:keywords')
                temp_info['link'] = item.find('link').text
            elif article_method == 'entry':
                temp_info['title'] = item.find('title').text
                temp_info['description'] = item.find('content').text
                temp_info['link'] = item.find('link')['href']
            log.debug(f'Got `temp_info`: {temp_info}')
            items_out['items'].append(temp_info)
    links_out = net_io.filter_links(items_out)
    links_out.reverse()
    return links_out


async def add_to_feed_db(
    feed_type, name, feed_link=None, channel=None, user_add=None,
    yt_id=None
):
    '''
    Add a an item to the feeds table in db

    `feed_type`:
    `name`:         The identifiable name of the added feed
    `feed_link`:    The link for the feed
    `channel`:      The discord channel to post the feed to
    `user_add`:     The user who added the feed
    `yt_id`:        yt-id
    '''

    if feed_type not in ['rss', 'youtube']:
        log.error('Function requires `feed_type`')
        return None
    # Test the link first
    test_link = await net_io.get_link(feed_link)
    if test_link is None:
        return None
    date_now = datetime_handling.get_dt(format='datetime')
    if feed_type == 'rss':
        await db_helper.insert_many_some(
            envs.rss_db_schema,
            rows=(
                'uuid', 'feed_name', 'url', 'channel', 'added', 'added_by',
                'status_url', 'status_url_counter', 'status_channel'
            ),
            inserts=(
                (
                    str(uuid4()), name, feed_link, channel, date_now,
                    user_add, envs.FEEDS_URL_SUCCESS, 0,
                    envs.CHANNEL_STATUS_SUCCESS
                )
            )
        )
    elif feed_type == 'youtube':
        await db_helper.insert_many_some(
            envs.youtube_db_schema,
            rows=(
                'uuid', 'feed_name', 'url', 'channel', 'added', 'added_by',
                'status_url', 'status_url_counter', 'status_channel',
                'youtube_id'
            ),
            inserts=(
                (
                    str(uuid4()), name, feed_link, channel, date_now,
                    user_add, envs.FEEDS_URL_SUCCESS, 0,
                    envs.CHANNEL_STATUS_SUCCESS, yt_id
                )
            )
        )


async def remove_feed_from_db(feed_type, feed_name):
    'Remove a feed from `feed file` based on `feed_name`'
    removal_ok = True
    if feed_type == 'rss':
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
    removal = await db_helper.del_row_by_AND_filter(
        feed_db,
        where=('uuid', uuid_from_db)
    )
    if not removal:
        removal_ok = False
    removal_filters = await db_helper.del_row_by_AND_filter(
        feed_db_filter,
        where=('uuid', uuid_from_db)
    )
    if not removal_filters:
        removal_ok = False
    return removal_ok


async def get_feed_links(feed_type, feed_info):
    'Get the links from a feed'
    UUID = feed_info[0]
    if feed_type == 'rss':
        URL = feed_info[2]
        feed_db_filter = envs.rss_db_filter_schema
        feed_db_log = envs.rss_db_log_schema
    elif feed_type == 'youtube':
        URL = envs.YOUTUBE_RSS_LINK.format(feed_info[9])
        feed_db_filter = envs.youtube_db_filter_schema
        feed_db_log = envs.youtube_db_log_schema
    else:
        URL = feed_info[2]
    # Get the url and make it parseable
    if feed_type in ['rss', 'youtube']:
        req = await net_io.get_link(URL)
        if req is not None:
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
                log_in=log_db
            )
            log.debug(f'Got this from `get_items_from_rss`: {links_out}')
            return links_out
        else:
            return None


async def get_feed_list(
        db_in: str = None, db_filter_in: str = None, list_type: str = None
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
    '''
    def split_lengthy_list(table_in):
        def split_list(lst, chunk_size):
            chunks = [[] for _ in range(
                (len(lst) + chunk_size - 1) // chunk_size
            )]
            for i, item in enumerate(lst):
                chunks[i // chunk_size].append(item)
            return chunks

        log.debug(f'length of table_in: {len(table_in)}')
        max_post_limit = 1900
        paginated = []
        if len(table_in) >= max_post_limit:
            line_len = len(table_in.split('\n')[1])
            log.debug(f'Each line is {line_len} chars long')
            post_limit = int(max_post_limit / line_len)
            log.debug(f'Each post can therefore hold {post_limit} lines')
            splits = split_list(table_in.split('\n')[2:], post_limit-2)
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

    if list_type is None:
        feeds_out = await db_helper.get_output(
            template_info=db_in,
            select=(
                'feed_name', 'url', 'channel'
            ),
            order_by=[
                ('feed_name', 'DESC')
            ]
        )
        # Return None if empty db
        if feeds_out is None:
            log.log('No feeds in database')
            return None
        headers = ('Feed', 'URL', 'Channel')
        maxcolwidths = [None, None, None]
    elif list_type == 'added':
        feeds_out = await db_helper.get_output(
            template_info=db_in,
            select=(
                'feed_name', 'url', 'channel', 'added', 'added_by'
            ),
            order_by=[
                ('feed_name', 'DESC')
            ]
        )
        # Return None if empty db
        if len(feeds_out) <= 0:
            log.log('No feeds in database')
            return None
        headers = ('Feed', 'URL', 'Channel', 'Added', 'Added by')
        maxcolwidths = [None, None, None, None, None]
    elif list_type == 'filter':
        if db_filter_in is None:
            log.error('`db_filter_in` is not specified')
            return None
        feeds_db = await db_helper.get_output(
            template_info=db_in,
            select=(
                'uuid', 'feed_name', 'channel'
            ),
            order_by=[
                ('feed_name', 'DESC')
            ]
        )
        feeds_filter = await db_helper.get_output(
            template_info=db_filter_in,
            order_by=[
                ('uuid', 'DESC'),
                ('filter', 'ASC')
            ]
        )
        feeds_out = []
        for feed in feeds_db:
            filter_uuid = [filter_item for filter_item in feeds_filter
                           if filter_item[0] == feed[0]]
            log.debug(f'`filter_uuid` is {filter_uuid}')
            filter_allow = [filter_item[2] for filter_item in filter_uuid
                            if filter_item[1].lower() == 'allow']
            log.debug(f'`filter_allow` is {filter_allow}')
            filter_deny = [filter_item[2] for filter_item in filter_uuid
                           if filter_item[1].lower() == 'deny']
            log.debug(f'`filter_deny` is {filter_deny}')
            temp_list = []
            for item in feed[1:]:
                temp_list.append(item)
            temp_list.append(
                ', '.join(item for item in filter_allow)
            )
            temp_list.append(
                ', '.join(item for item in filter_deny)
            )
            feeds_out.append(temp_list)
            log.debug(f'`temp_list` is {temp_list}')
        headers = ('Feed', 'Channel', 'Allow', 'Deny')
        maxcolwidths = [None, None, 30, 30]
    table_out = tabulate(
        tabular_data=feeds_out,
        headers=headers,
        maxcolwidths=maxcolwidths
    )
    return split_lengthy_list(table_out)


async def review_feeds_status(feed_type: str = None):
    '''
    Get a status for a feed that is `feed_type` and update it in database.
    Checks both url and channel availability

    Parameters
    ------------
    feed_type: str
        Can be `rss` or `youtube` (default: None)
    '''
    if feed_type not in ['rss', 'youtube']:
        log.error('`feed_type` must be `rss` or `youtube`')
        return False
    if feed_type == 'rss':
        feed_db = envs.rss_db_schema
    elif feed_type == 'youtube':
        feed_db = envs.youtube_db_schema
    feeds_status_db_in = await db_helper.get_output(
        template_info=feed_db,
        order_by=[('feed_name', 'DESC')]
    )
    if feeds_status_db_in is None:
        log.log('No feeds to review')
        return None
    db_updates = {}
    for feed in feeds_status_db_in:
        log.debug('Got this feed: ', pretty=feed)
        UUID = feed[0]
        FEED_NAME = feed[1]
        if feed_type == 'rss':
            URL = feed[2]
        elif feed_type == 'youtube':
            URL = envs.YOUTUBE_RSS_LINK.format(feed[9])
        URL_STATUS = feed[3]
        URL_STATUS_COUNTER = feed[4]
        if not isinstance(URL_STATUS_COUNTER, int):
            URL_STATUS_COUNTER = 0
        is_valid_feed = await check_feed_validity(URL)
        if is_valid_feed:
            log.log('Feed url for {} is ok!'.format(FEED_NAME))
            if URL_STATUS != envs.FEEDS_URL_SUCCESS:
                log.verbose('status_url is not OK, fixing...')
                if 'status_url' not in db_updates:
                    db_updates['status_url'] = []
                db_updates['status_url'].append(
                    ('uuid', UUID, envs.FEEDS_URL_SUCCESS)
                )
            if URL_STATUS_COUNTER != 0:
                log.verbose('status_url_counter is not 0, fixing...')
                if 'status_url_counter' not in db_updates:
                    db_updates['status_url_counter'] = []
                db_updates['status_url_counter'].append(
                    ('uuid', UUID, 0)
                )
        elif not is_valid_feed:
            if URL_STATUS_COUNTER >= envs.FEEDS_URL_ERROR_LIMIT:
                _url_e_msg = f'Error when getting feed for {FEED_NAME}'\
                    f' (strike {envs.FEEDS_URL_ERROR_LIMIT})'
                log.error(_url_e_msg)
                log.log_to_bot_channel(_url_e_msg)
                if URL_STATUS != envs.FEEDS_URL_ERROR:
                    if 'status_url' not in db_updates:
                        db_updates['status_url'] = []
                    db_updates['status_url'].append(
                        ('uuid', UUID, envs.FEEDS_URL_ERROR)
                    )
            elif URL_STATUS_COUNTER < envs.FEEDS_URL_ERROR_LIMIT:
                log.log(
                    f'Problems with url for {feed}, marking it as `Stale` and'
                    'starting counting'
                )
                if URL_STATUS != envs.FEEDS_URL_STALE:
                    if 'status_url' not in db_updates:
                        db_updates['status_url'] = []
                    db_updates['status_url'].append(
                        ('uuid', UUID, envs.FEEDS_URL_STALE)
                    )
                if 'status_url_counter' not in db_updates:
                    db_updates['status_url_counter'] = []
                db_updates['status_url_counter'].append(
                    ('uuid', UUID, (URL_STATUS_COUNTER + 1))
                )
        CHANNEL = feed[3]
        CHANNEL_STATUS = feed[8]
        if CHANNEL in discord_commands.get_text_channel_list():
            log.log(
                'Feed channel {} for {} is ok'.format(
                    CHANNEL, FEED_NAME
                )
            )
            if CHANNEL_STATUS == envs.CHANNEL_STATUS_ERROR:
                if 'status_channel' not in db_updates:
                    db_updates['status_channel'] = []
                db_updates['status_channel'].append(
                    ('uuid', UUID, envs.CHANNEL_STATUS_SUCCESS)
                )
        elif CHANNEL not in discord_commands.get_text_channel_list():
            if 'status_channel' not in db_updates:
                db_updates['status_channel'] = []
            db_updates['status_channel'].append(
                ('uuid', UUID, envs.CHANNEL_STATUS_ERROR)
            )
            await log.log_to_bot_channel(
                f'{FEED_NAME} skal poste i #{CHANNEL} men den finnes ikke'
            )
    if len(db_updates) == 0:
        log.verbose('All feeds are OK, nothing to update')
        return True
    else:
        log.verbose(f'Updating db with `db_updates`: {db_updates}')
        await db_helper.update_fields(
            template_info=feed_db,
            updates=db_updates
        )
        return True


def link_similar_to_logged_post(link: str, feed_log: list):
    '''
    Checks if `link` is similar to any other logged link in `feed_log`.
    If similiar, return the similar link from log.
    If no links are found to be similar, return None.
    '''
    if feed_log is None:
        return False
    for log_item in feed_log:
        if file_io.check_similarity(log_item[0], link):
            return True
    return False


def link_is_in_log(link, log_in):
    if log_in is None:
        log.verbose('Log is empty')
        return False
    try:
        if link not in [log_url[0] for log_url in log_in]:
            log.verbose('Link not in log')
            return False
        else:
            log.verbose(f'Found link logs ({link})')
            return True
    except Exception as e:
        log.error(
            f'Error: {e}:', pretty=log_in)
        return None


async def process_links_for_posting_or_editing(
    feed_type: str, uuid, FEED_POSTS, CHANNEL
):
    '''
    Compare links in `FEED_POSTS` items  to posts belonging to `feed` to see
    if they already have been posted or not.
    - If not posted, post to `CHANNEL`
    - If posted, make a similarity check just to make sure we are not posting
    duplicate links because someone's aggregation systems can't handle
    editing urls with spelling mistakes. If it is simliar, but not identical,
    replace the logged link and edit the previous post with the new link.

    `feed`:             Name of the feed to process
    `FEED_POSTS`:       The newly received feed posts
    `CHANNEL`:          Discord channel to post/edit
    '''
    log.verbose(
        'Starting `process_links_for_posting_or_editing`',
        sameline=True
    )
    if feed_type not in ['rss', 'youtube']:
        log.error('Function requires `feed_type`')
        return None
    if feed_type in ['rss', 'spotify']:
        feed_db_log = envs.rss_db_log_schema
    elif feed_type == 'youtube':
        feed_db_log = envs.youtube_db_log_schema
    log.debug(f'Here\'s the `FEED_POSTS`: {FEED_POSTS}')
    FEED_LOG = await db_helper.get_output(
        template_info=feed_db_log,
        select='url',
        where=[('uuid', uuid)]
    )
    for item in FEED_POSTS:
        feed_link = item['link']
        log.debug(f'Got feed_link `{feed_link}`')
        # Check if the link is in the log
        link_in_log = link_is_in_log(feed_link, FEED_LOG)
        if not link_in_log:
            log.debug('Checking if link is similar to log')
            feed_link_similar = link_similar_to_logged_post(
                feed_link, FEED_LOG)
            if not feed_link_similar:
                # Consider this a whole new post and post link to channel
                log.verbose(f'Posting link `{feed_link}`')
                if 'img' in item:
                    log.debug('Found a post that should be embedded')

                    await discord_commands.post_to_channel(
                        CHANNEL, content_embed_in=''
                    )
                else:
                    log.debug('Found a regular text post')
                    await discord_commands.post_to_channel(CHANNEL, feed_link)
                # Add link to log
                await db_helper.insert_many_all(
                    template_info=feed_db_log,
                    inserts=[
                        (uuid, feed_link, str(
                            datetime_handling.get_dt(
                                format='ISO8601'
                            )
                        ))
                    ]
                )
            elif feed_link_similar:
                # Consider this a similar post that needs to
                # be edited in the channel
                await discord_commands.replace_post(
                    feed_link_similar, feed_link, CHANNEL
                )
                # Replace original link with new
                await db_helper.update_fields(
                    template_info=feed_db_log,
                    where=[
                        ('url', feed_link_similar)
                    ],
                    updates=[
                        ('url', feed_link)
                    ]
                )
        elif link_in_log:
            log.verbose(f'Link `{feed_link}` already logged. Skipping.')
    log.verbose('Stopping `process_links_for_posting_or_editing`')


if __name__ == "__main__":
    pass
