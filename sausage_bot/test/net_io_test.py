#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import pytest
import requests
import bs4
from ..util import net_io


def test_get_link():
    url_ok_full = 'https://www.digi.no'
    url_ok_short = 'www.vg.no'
    url_ok_shorter = 'vg.no'
    url_fail_scheme_error = 'htts://www.vg.no'
    url_fail_no_tld = 'www.vgno'
    link_not_string = 123

    get_link = net_io.get_link

    assert type(get_link(url_ok_full)) is requests.models.Response
    assert type(get_link(url_ok_short)) == requests.models.Response
    assert type(get_link(url_ok_shorter)) == requests.models.Response
    assert get_link(url_fail_scheme_error) == None
    assert get_link(url_fail_no_tld) == None
    assert net_io.get_link(link_not_string) is None


def test_scrape_page():
    url_ok1 = 'www.digi.no'
    url_ok2 = 'www.vg.no'
    url_ok3 = 'vg.no'
    url_fail1 = 'htts://www.vg.no'
    url_fail2 = 'www.vgno'
    url_fail3 = 123

    scrape_page = net_io.scrape_page

    assert type(scrape_page(url_ok1)) == bs4.BeautifulSoup
    assert type(scrape_page(url_ok2)) == bs4.BeautifulSoup
    assert type(scrape_page(url_ok3)) == bs4.BeautifulSoup
    assert scrape_page(url_fail1) == None
    assert scrape_page(url_fail2) == None
    assert scrape_page(url_fail3) == None


def test_make_event_start_stop():
    date_yes, time_yes = ('17.05.2022', '21:00')
    date_yes, time_no = ('17.05.2022', '671:00')

    assert type(net_io.make_event_start_stop(date_yes, time_yes)) is dict
    assert net_io.make_event_start_stop(date_yes, time_no) is None
