#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import sys
from lxml import etree
from discord_rss import file_io, _vars, datetime_funcs, log

'''
This script does the rss-job for the bot. All feeds are stored in
`json/feeds.json`, and all articles that has already been processed are
stored in `json/feed_logging.json`.

Things this script should be able to do:
- Parse a feed
- Add a feed
- Remove a feed
- List feeds
- Log feed items that has been fetched
'''


def get_feed(url):
    req = requests.get(url)
    req.encoding = req.apparent_encoding
    try:
        feed_in = etree.fromstring(req.content, parser=etree.XMLParser(encoding='utf-8'))
    except(etree.XMLSyntaxError):
        return None
    return feed_in


def check_feed_validity(url):
    req = requests.get(url)
    req.encoding = req.apparent_encoding
    try:
        feed_in = etree.fromstring(req.content, parser=etree.XMLParser(encoding='utf-8'))
        return True
    except(etree.XMLSyntaxError):
        return False


def add_feed_to_file(name, feed_link, channel, user_add):
    '''Add a new feed to the feed-json'''
    date_now = datetime_funcs.get_dt(format='datetimefull')
    feed_file = file_io.read_json(_vars.feed_file)
    feed_file[name] = {'url': feed_link,
                       'channel': channel,
                       'added': date_now,
                       'added by': user_add}
    file_io.write_json(_vars.feed_file, feed_file)


def remove_feed_from_file(name):
    '''
    Remove a new feed from the feed-json
    '''
    name = str(name)
    feed_file = file_io.read_json(_vars.feed_file)
    try:
        feed_file.pop(name)
        file_io.write_json(_vars.feed_file, feed_file)
        return True
    except(KeyError):
        return False
    

def get_feed_links(url):
    links = []
    feed_in = get_feed(str(url))
    if feed_in is None:
        return None
    for item in feed_in.xpath('/rss/channel/item')[0:2]:
        links.append(item.xpath("./link/text()")[0].strip())
    return links


def get_feed_list(long=False):
    def get_feed_item_lengths(feed_file):
        feed_len = 0
        url_len = 0
        channel_len = 0
        added_len = 0
        added_by_len = 0
        for feed in feed_file:
            _feed = feed_file[feed]
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

    text_out = ''
    feed_file = file_io.read_json(_vars.feed_file)
    lengths = get_feed_item_lengths(feed_file)
    if long:
        template_line = '{:{feed_len}} | {:{url_len}} | {:{channel_len}} | {:{added_len}} | {:{added_by_len}}'
        # Add headers first
        text_out += template_line.format('Name', 'Feed', 'Channel', 'Added',
            'Added by', feed_len=lengths['feed_len'], url_len=lengths['url_len'],
            channel_len=lengths['channel_len'], added_len=lengths['added_len'],
            added_by_len=lengths['added_by_len'])
        text_out += '\n'
        for feed in feed_file:
            _feed = feed_file[feed]
            text_out += template_line.format(feed, _feed['url'], _feed['channel'],
                _feed['added'], _feed['added by'], feed_len=lengths['feed_len'],
                url_len=lengths['url_len'], channel_len=lengths['channel_len'],
                added_len=lengths['added_len'], added_by_len=lengths['added_by_len'])
            if feed != list(feed_file)[-1]:
                text_out += '\n'
    else:
        template_line = '{:{feed_len}} | {:{url_len}} | {:{channel_len}}'
        # Add headers first
        text_out += template_line.format('Name', 'Feed', 'Channel',
            feed_len=lengths['feed_len'], url_len=lengths['url_len'],
            channel_len=lengths['channel_len'])
        text_out += '\n'
        for feed in feed_file:
            _feed = feed_file[feed]
            text_out += template_line.format(feed, _feed['url'], _feed['channel'],
                feed_len=lengths['feed_len'], url_len=lengths['url_len'],
                channel_len=lengths['channel_len'])
            if feed != list(feed_file)[-1]:
                text_out += '\n'
    text_out = '```{}```'.format(text_out)
    return text_out


if __name__ == "__main__":
    #test_urls = ['https://wordpress.blaugrana.no/feed',
    #             'http://lovdata.no/feed?data=newArticles&type=RSS']
    pass
