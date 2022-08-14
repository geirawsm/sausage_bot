#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from ctypes.wintypes import BOOL
import requests
from bs4 import BeautifulSoup
from lxml import etree
from difflib import SequenceMatcher
from sausage_bot.funcs import _vars, file_io, rss_core, discord_commands

from . import file_io, _vars, datetimefuncs
from ..log import log


def get_feed(url):
    if type(url) is not str:
        log.log(_vars.RSS_INVALID_URL)
        return None
    try:
        req = requests.get(url)
    except(requests.exceptions.InvalidSchema):
        log.log(_vars.RSS_INVALID_URL)
        return None
    except(requests.exceptions.MissingSchema):
        log.log(_vars.RSS_MISSING_SCHEME)
        req = get_feed(f'https://{url}')
    except(requests.exceptions.ConnectionError):
        log.log(_vars.RSS_CONNECTION_ERROR)
        return None
    if req is None:
        return None
    log.log_more('Got a {} when fetching {}'.format(req.status_code, url))
    if req.status_code != 200:
        return None
    else:
        return req


def check_feed_validity(url):
    req = get_feed(url)
    if req is None:
        return False
    try:
        etree.fromstring(req.content, parser=etree.XMLParser(encoding='utf-8'))
        return True
    except(etree.XMLSyntaxError):
        return False


def add_feed_to_file(name, feed_link, channel, user_add):
    '''Add a new feed to the feed-json'''
    date_now = datetimefuncs.get_dt(format='datetime')
    feeds_file = file_io.read_json(_vars.rss_feeds_file)
    feeds_file[name] = {'url': feed_link,
                       'channel': channel,
                       'added': date_now,
                       'added by': user_add,
                       'status': 'Added'}
    file_io.write_json(_vars.rss_feeds_file, feeds_file)


def remove_feed_from_file(name, feed_file):
    '''Remove a new feed from a feed file'''
    name = str(name)
    feeds_list = file_io.read_json(feed_file)
    try:
        feeds_list.pop(name)
        file_io.write_json(feed_file, feeds_list)
        return True
    except(KeyError):
        return False


def update_feed_status(name, status):
    '''Update a feed in the feed-json'''
    name = str(name)
    feeds_file = file_io.read_json(_vars.rss_feeds_file)
    try:
        feeds_file[name]['status'] = str(status)
        file_io.write_json(_vars.rss_feeds_file, feeds_file)
        return True
    except(KeyError):
        return False
    

def get_feed_links(url):
    'Get the links from a feed url'
    # Get the url and make it parseable
    req = get_feed(url)
    if req is None:
        return None
    try:
        soup = BeautifulSoup(req.content, features='xml')
    except(AttributeError):
        log.log('Error when reading soup from {}'.format(url))
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
                log.log('Error when getting link for item {} in {}'.format(item, url))
            if 'wp.blgr.app' in link:
                link = link.replace('wp.blgr.app', 'www.blaugrana.no')
            links.append(link)
    elif '<feed xml' in str(soup):
        for entry in soup.findAll('entry')[0:2]:
            links.append(entry.find('link')['href'])
    return links


def get_feed_list(feeds_file, long=False):
    def get_feed_item_lengths(feeds_file):
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


def check_similarity(text1: str, text2: str) -> BOOL:
    '''
    Check how similar `text1` and `text2` is. If it resembles eachother by
    between 95 % to 99.999999995 %, it is considered "similar" and will return
    True. Otherwise, return False.

    If neither `text1` nor `text2` is a string, it will return None.
    '''
    # Stop function if input is not str
    if type(text1) is not str or type(text2) is not str:
        return None
    ratio = float(SequenceMatcher(a=text1,b=text2).ratio())
    # Our "similarity" is defined by the following equation:
    if 0.95 <= ratio <= 0.99999999995:
        log.log(
            f'These texts seem similiar (ratio: {ratio}):\n'
            f'`{text1}`\n'
            'vs\n'
            f'`{text2}`'
        )
        return True
    else:
        log.log(
            f'Not similar, ratio too low or identical (ratio: {ratio}):\n'
            f'`{text1}`\n'
            'vs\n'
            f'`{text2}`'
        )
        return False


def review_feeds_status(feeds):
    for feed in feeds:
        log.log('{}: {}'.format(feed, feeds[feed]['status']))
        URL = feeds[feed]['url']
        URL_STATUS = feeds[feed]['status']
        if URL_STATUS == 'stale':
            log.log('Feed {} is stale, checking it...'.format(feed))
            if rss_core.get_feed_links(URL) is not None:
                log.log('Feed {} is ok, reactivating!'.format(feed))
                rss_core.update_feed_status(feed, 'ok')
            elif rss_core.get_feed_links(URL) is None:
                log.log('Feed {} is still stale, skipping'.format(feed))
                break


def link_is_in_log(link: str, feed_log: list) -> BOOL:
    # Checks if given link is in the log given
    if link in feed_log:
        return True
    else:
        return False


def link_similar_to_logged_post(link: str, feed_log: list):
    '''
    Checks if given link is similar to any logged link,
    then return the similar link from log.
    If no log-links are found to be similar, return None
    '''
    for log_item in feed_log:
        if check_similarity(log_item, link):
            return log_item


async def process_links_for_posting_or_editing(
    feed, FEED_POSTS, feed_log_file, CHANNEL
):
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
                await discord_commands.edit_post(
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
