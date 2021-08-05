#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import json
from lxml import etree
from discord_rss import file_io, _vars, datetime_funcs

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
    feed_in = etree.fromstring(req.content)
    return feed_in


def check_feed(url):
    req = requests.get(url)
    try:
        feed_in = etree.fromstring(req.content)
        return True
    except(etree.XMLSyntaxError):
        return False


def add_feed(name, feed_link, channel, user_add):
    '''
    Add a new feed to the feed-json
    '''
    date_now = datetime_funcs.get_dt(format='datetimefull')
    feed_file = file_io.read_json(_vars.feed_file)
    feed_file[name] = {'url': feed_link,
                       'channel': channel,
                       'added': date_now,
                       'added by': user_add}
    file_io.write_json(_vars.feed_file, feed_file)


def remove_feed(name):
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
    for item in feed_in.xpath('/rss/channel/item')[0:3]:
        links.append(item.xpath("./link/text()")[0].strip())
    return links


#def get_feed_list():
#    def get_feed_item_lengths(feed_file):
#        feed_len = 0
#        url_len = 0
#        channel_len = 0
#        added_len = 0
#        added_by_len = 0
#        for feed in feed_file:
#            if len(feed) > feed_len:
#                feed_len = len(feed)
#            if len(url) > url_len:
#                url_len = len(url)
#            if len(channel) > channel_len:
#                channel_len = len(channel)
#            if len(added) > added_len:
#                added_len = len(added)
#            if len(added_by) > added_by_len:
#                added_by_len = len(added_by)
#        return {'feed_len': feed_len, 'url_len': url_len,
#                'channel_len': channel_len, 'added_len': added_len,
#                'added_by_len': added_by_len}
#
#    text_out = ''
#    feed_file = file_io.read_json(_vars.feed_file)
#    lengths = get_feed_item_lengths(feed_file)
#    text_out += '' 


if __name__ == "__main__":
    test_urls = ['https://wordpress.blaugrana.no/feed',
                 'http://lovdata.no/feed?data=newArticles&type=RSS']
    #add_feed('test', 'asdads', '123123')
    #del_feed('Lovdata')
    #get_feed_links(test_urls[0])
