#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytest
import requests
from ..funcs import rss_core


def test_get_feed():
    link_not_string = 1234
    link_correct = 'https://www.kode24.no/artikkel/ny-utviklingsavdeling-skal-revolusjonere-mattilsynet-vi-ma-torre-a-vaere-mer-risikovillige/76194994'
    link_error_https = 'httsp://gv.on'
    link_error_no_scheme_but_correct_address = 'vg.no'
    link_error_no_scheme_and_wrong_address = 'gv.on'
    assert rss_core.get_feed(link_not_string) is None
    assert type(
        rss_core.get_feed(link_correct)
    ) is requests.models.Response
    assert rss_core.get_feed(link_error_https) is None
    assert type(
        rss_core.get_feed(link_error_no_scheme_but_correct_address)
    ) is requests.models.Response
    assert rss_core.get_feed(link_error_no_scheme_and_wrong_address) is None



def test_check_link_duplication_return_number_or_none():
    link1 = 'https://www.kode24.no/artikkel/ny-utviklingsavdeling-skal-reovlusjonere-mattilsynet-vi-ma-torre-a-vaere-mer-risikovillige/7619499'
    link2 = 'https://www.kode24.no/artikkel/ny-utviklingsavdeling-skal-revolusjonere-mattilsynet-vi-ma-torre-a-vaere-mer-risikovillige/76194994'
    link3 = False
    assert type(rss_core.check_link_duplication(link1, link2)) is float
    assert rss_core.check_link_duplication(link1, link3) is None


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
        test_feed = rss_core.get_feed_links(url)
        assert type(test_feed) is list
