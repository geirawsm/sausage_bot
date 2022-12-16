#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytest
import requests
from ..util import feeds_core, file_io


def test_check_similarity_return_number_or_none():
    link1 = 'https://www.kode24.no/artikkel/ny-utviklingsavdeling-skal-reovlusjonere-mattilsynet-vi-ma-torre-a-vaere-mer-risikovillige/7619499'
    link2 = 'https://www.kode24.no/artikkel/ny-utviklingsavdeling-skal-revolusjonere-mattilsynet-vi-ma-torre-a-vaere-mer-risikovillige/76194994'
    link3 = False
    assert file_io.check_similarity(link1, link2) is True
    assert file_io.check_similarity(link1, link3) is None


def test_process_feeds_correct():
    '''
    `test_urls` should consist of several rss feeds that are set up
    differently to really test the function `get_feed_links`
    '''
    test_urls = [
        'https://rss.kode24.no/',
        'http://lovdata.no/feed?data=newArticles&type=RSS',
        'https://wp.blgr.app/feed',
        'https://www.vif-fotball.no/rss-nyheter'
    ]
    for url in test_urls:
        test_feed = feeds_core.get_feed_links(url)
        assert type(test_feed) is list
