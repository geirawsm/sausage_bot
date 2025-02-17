#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytest
from sausage_bot.util import file_io, feeds_core, envs, db_helper
from sausage_bot.util.net_io import get_link


def test_check_similarity_return_number_or_none():
    link1 = 'https://www.kode24.no/artikkel/ny-utviklingsavdeling-skal-reo'\
        'vlusjonere-mattilsynet-vi-ma-torre-a-vaere-mer-risikovillige/7619499'
    link2 = 'https://www.kode24.no/artikkel/ny-utviklingsavdeling-skal-rev'\
        'olusjonere-mattilsynet-vi-ma-torre-a-vaere-mer-risikovillige/76194994'
    link3 = False
    assert file_io.check_similarity(link1, link2) is link2
    assert file_io.check_similarity(link1, link3) is None


async def test_check_feed_validity_url():
    good_url1 = 'https://www.metalsucks.net/category/shit-that-comes-out-today/feed/'
    good_url2 = 'http://feeds.bbci.co.uk/news/rss.xml'
    bad_url1 = 'https://www.youtube.com'
    bad_url2 = ''

    out_good1 = await feeds_core.check_feed_validity(good_url1)
    out_good2 = await feeds_core.check_feed_validity(good_url2)
    out_bad1 = await feeds_core.check_feed_validity(bad_url1)
    out_bad2 = await feeds_core.check_feed_validity(bad_url2)

    assert out_good1 is True
    assert out_good2 is True
    assert out_bad1 is False
    assert out_bad2 is None


async def test_get_items_from_rss():
    good_url = 'https://www.angrymetalguy.com/category/reviews/feed/'
    bad_url = 'https://www.youtube.com'

    good_out = await feeds_core.get_items_from_rss(
        await get_link(good_url),
        good_url
    )
    bad_out = await feeds_core.get_items_from_rss(
        await get_link(bad_url),
        bad_url
    )

    assert type(good_out) is list
    assert bad_out is None


async def test_get_feed_links():
    feeds = [
        {
            'uuid': '388cfab2-a1b6-4738-aee0-5368fe97a2c6',
            'feed_name': 'good_feed',
            'url': 'https://www.angrymetalguy.com/category/reviews/feed/',
            'channel': '1000000000000000000',
            'added': '17.05.2022 12.00',
            'added_by': 'geirawsm',
            'status_url': 'OK',
            'status_url_counter': 0,
            'status_channel': 'OK',
            'feed_type': 'rss',
            'num_episodes': 0
        },
        {
            'uuid': 'asdasyd9asdasd-asdagrehwd-qwdqdqwqd',
            'feed_name': 'bad_feed',
            'url': 'https://www.youtube.com',
            'channel': '1000000000000000000',
            'added': '17.05.2022 12.00',
            'added_by': 'geirawsm',
            'status_url': 'OK',
            'status_url_counter': 0,
            'status_channel': 'OK',
            'feed_type': 'rss',
            'num_episodes': 0
        }
    ]

    for feed in feeds:
        if feed['feed_name'] == 'good_feed':
            good_out = await feeds_core.get_feed_links(
                'rss', feed
            )
            assert type(good_out) is list
            assert type(good_out[0]) is dict

        if feed['feed_name'] == 'bad_feed':
            bad_out = await feeds_core.get_feed_links(
                'rss', feed
            )
            assert bad_out is None
