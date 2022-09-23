#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from lxml import etree
from sausage_bot.funcs import _vars, file_io, discord_commands
from sausage_bot.funcs import net_io

from . import file_io, _vars, datetimefuncs
from ..log import log


def check_feed_validity(url):
    'Make sure that `url` is a valid link'
    log.log_more(f'Checking `{url}`')
    req = net_io.get_link(url)
    if req is None:
        log.log_more(f'Returned None')
        return False
    try:
        etree.fromstring(req.content, parser=etree.XMLParser(encoding='utf-8'))
        return True
    except(etree.XMLSyntaxError) as e:
        log.log_more(_vars.ERROR_WITH_ERROR_MSG.format(e))
        return False


def add_feed_to_file(name, feed_link, channel, user_add, feeds_filename):
    '''
    Add a new feed to the feed-json.

    `name`:         The identifiable name of the added feed
    `feed_link`:    The link for the feed
    `channel`       The discord channel to post the feed to
    `user_add`      The user who added the feed
    '''
    date_now = datetimefuncs.get_dt(format='datetime')
    feeds_file = file_io.read_json(feeds_filename)
    feeds_file[name] = {
        'url': feed_link,
        'channel': channel,
        'added': date_now,
        'added by': user_add,
        'status': {
             'url': 'added',
             'channel': 'ok'
        }
    }
    file_io.write_json(_vars.rss_feeds_file, feeds_file)


def remove_feed_from_file(name, feed_file):
    'Remove a new from `feed file` based on `name`'
    name = str(name)
    feeds_list = file_io.read_json(feed_file)
    try:
        feeds_list.pop(name)
        file_io.write_json(feed_file, feeds_list)
        return True
    except(KeyError):
        return False


def update_feed_status(
    feed_name, channel_in=None, url_status=None, channel_status=None
    ):
    '''
    Update the fields for a feed in `_vars.rss_feeds_file`
    
    `feed_name`:        Idenetifiable name for the feed
    `channel_in`:       The channel to receive feed updates
    `url_status`:       The status of the url
    `channel_status`:   The status of the channel
    '''
    feed_name = str(feed_name)
    feeds_file = file_io.read_json(_vars.rss_feeds_file)
    if url_status:
        feeds_file[feed_name]['status']['url'] = str(url_status).lower()
    if channel_status:
        feeds_file[feed_name]['status']['channel'] = str(channel_status).lower()
    if channel_in:
        feeds_file[feed_name]['channel'] = str(channel_in).lower()
    file_io.write_json(_vars.rss_feeds_file, feeds_file)
    return True
    

def get_feed_links(url):
    'Get the links from a feeds `url`'
    # Get the url and make it parseable
    req = net_io.get_link(url)
    if req is None:
        return None
    try:
        soup = BeautifulSoup(req.content, features='xml')
    except Error as e:
        log.log(RSSCORE_SOUP_ERROR.format(url, e))
        return None
    links = []
    # Try normal RSS
    if '<rss version="' in str(soup).lower():
        try:
            feed_in = etree.fromstring(req.content, parser=etree.XMLParser(encoding='utf-8'))
        except(etree.XMLSyntaxError):
            return None
        for item in feed_in.xpath('/rss/channel/item')[0:2]:
            try:
                link = item.xpath("./link/text()")[0].strip()
            except(IndexError):
                log.log(RSSCORE_LINK_INDEX_ERROR.format(item, url))
            # TODO Is this still necessary?
            if 'wp.blgr.app' in link:
                link = link.replace('wp.blgr.app', 'www.blaugrana.no')
            links.append(link)
    elif '<feed xml' in str(soup):
        for entry in soup.findAll('entry')[0:2]:
            links.append(entry.find('link')['href'])
    return links


def get_feed_list(feeds_file, long=False):
    '''
    Get a prettified list of feeds from `feeds_file`.
    
    Get some extra field if `long` is given.
    '''
    def get_feed_item_lengths(feeds_file):
        'Get max lengths of items in `feeds_file`'
        feed_len = 0
        url_len = 0
        channel_len = 0
        added_len = 0
        added_by_len = 0
        for feed in feeds_file:
            _feed = feeds_file[feed]
            if len(feed) > feed_len:
                feed_len = len(feed)
            if len(_feed['url']) > url_len:
                url_len = len(_feed['url'])
            if len(_feed['channel']) > channel_len:
                channel_len = len(_feed['channel'])
            if len(_feed['added']) > added_len:
                added_len = len(_feed['added'])
            if len(_feed['added by']) > added_by_len:
                added_by_len = len(_feed['added by'])
        return {'feed_len': feed_len, 'url_len': url_len,
                'channel_len': channel_len, 'added_len': added_len,
                'added_by_len': added_by_len}

    feeds_file = file_io.read_json(feeds_file)
    text_out = ''
    lengths = get_feed_item_lengths(feeds_file)
    if long:
        template_line = '{:{feed_len}} | {:{url_len}} | {:{channel_len}} | {:{added_len}} | {:{added_by_len}}'
        # Add headers first
        text_out += template_line.format('Name', 'Feed', 'Channel', 'Added',
            'Added by', feed_len=lengths['feed_len'], url_len=lengths['url_len'],
            channel_len=lengths['channel_len'], added_len=lengths['added_len'],
            added_by_len=lengths['added_by_len'])
        text_out += '\n'
        for feed in feeds_file:
            _feed = feeds_file[feed]
            text_out += template_line.format(feed, _feed['url'], _feed['channel'],
                _feed['added'], _feed['added by'], feed_len=lengths['feed_len'],
                url_len=lengths['url_len'], channel_len=lengths['channel_len'],
                added_len=lengths['added_len'], added_by_len=lengths['added_by_len'])
            if feed != list(feeds_file)[-1]:
                text_out += '\n'
    else:
        template_line = '{:{feed_len}} | {:{url_len}} | {:{channel_len}}'
        # Add headers first
        text_out += template_line.format('Name', 'Feed', 'Channel',
            feed_len=lengths['feed_len'], url_len=lengths['url_len'],
            channel_len=lengths['channel_len'])
        text_out += '\n'
        for feed in feeds_file:
            _feed = feeds_file[feed]
            text_out += template_line.format(feed, _feed['url'], _feed['channel'],
                feed_len=lengths['feed_len'], url_len=lengths['url_len'],
                channel_len=lengths['channel_len'])
            if feed != list(feeds_file)[-1]:
                text_out += '\n'
    text_out = '```{}```'.format(text_out)
    return text_out


def review_feeds_status(feeds):
    'Get a status for a feed from `feeds` and update it in source file'
    for feed in feeds:
        log.log('{}: {}'.format(feed, feeds[feed]['status']))
        URL = feeds[feed]['url']
        URL_STATUS = feeds[feed]['status']['url']
        if URL_STATUS == 'stale':
            log.log('Feed url for {} is stale, checking it...'.format(feed))
            if get_feed_links(URL) is not None:
                log.log('Feed url for {} is ok, reactivating!'.format(feed))
                update_feed_status(feed, url_status='ok')
                break
            elif get_feed_links(URL) is None:
                log.log('Feed url for {} is still stale, skipping'.format(feed))
                break
        CHANNEL = feeds[feed]['channel']
        CHANNEL_STATUS = feeds[feed]['status']['channel']
        if CHANNEL_STATUS == 'unlisted':
            log.log(
                'Feed channel {} for {} is unlisted, checking it...'.format(
                    CHANNEL, feed
                )
            )
            if CHANNEL in discord_commands.get_text_channel_list():
                log.log(
                    'Feed channel {} for {} is ok, reactivating!'.format(
                        CHANNEL, feed
                    )
                )
                update_feed_status(feed, channel_status='ok')


def link_is_in_log(link: str, feed_log: list) -> bool:
    'Checks if `link` is in the `feed_log`'
    if link in feed_log:
        return True
    else:
        return False


def link_similar_to_logged_post(link: str, feed_log: list):
    '''
    Checks if `link` is similar to any other logged link in `feed_log`.
    If simliar, return the similar link from log.
    If no links are found to be similar, return None.
    '''
    for log_item in feed_log:
        if file_io.check_similarity(log_item, link):
            return log_item


async def process_links_for_posting_or_editing(
    feed, FEED_POSTS, feed_log_file, CHANNEL
):
    '''
    Compare `FEED_POSTS` to posts belonging to `feed` in `feed_log_file`
    to see if they already have been posted or not.
    If not posted, post to `CHANNEL`
    If posted, make a similarity check just to make sure we are not posting
    duplicate links because someone's aggregation systems can't handle
    editing urls with spelling mistakes. If it is simliar, but not identical,
    replace the logged link and edit the previous post with the new link.

    `feed`:             Name of the feed to process
    `FEED_POSTS`:       The newly received feed posts
    `feed_log_file`:    File containing the logs of posts
    `CHANNEL`:          Discord channel to post/edit
    '''
    FEED_LOG = file_io.read_json(feed_log_file)
    try:
        FEED_LOG[feed]
    except(KeyError):
        FEED_LOG[feed] = []
    for feed_link in FEED_POSTS[0:2]:
        log.log_more(f'Got feed_link `{feed_link}`')
        # Check if the link is in the log
        if not link_is_in_log(feed_link, FEED_LOG[feed]):
            feed_link_similar = link_similar_to_logged_post(feed_link, FEED_LOG[feed])
            if not feed_link_similar:
                # Consider this a whole new post and post link to channel
                log.log_more(f'Posting link `{feed_link}`')
                await discord_commands.post_to_channel(feed_link, CHANNEL)
                # Add link to log
                FEED_LOG[feed].append(feed_link)
            elif feed_link_similar:
                # Consider this a similar post that needs to
                # be edited in the channel
                await discord_commands.replace_post(
                    feed_link_similar, feed_link, CHANNEL
                )
                FEED_LOG[feed].remove(feed_link_similar)
                FEED_LOG[feed].append(feed_link)
        elif link_is_in_log(feed_link, FEED_LOG[feed]):
            log.log_more(f'Link `{feed_link}` already logged. Skipping.')
        # Write to the logs-file at the end
        file_io.write_json(feed_log_file, FEED_LOG)


if __name__ == "__main__":
    pass
