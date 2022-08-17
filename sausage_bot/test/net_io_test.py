#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import pytest
import requests
import bs4
from ..funcs import net_io

def test_get_link():
    url_ok1 = 'https://www.nifs.no/kampfakta.php?kamp_id=2133607&land=20&t=45&u=690408&lag1=835&lag2=844'
    url_ok2 = 'www.vg.no'
    url_ok3 = 'vg.no'
    url_fail1 = 'htts://www.vg.no'
    url_fail2 = 'www.vgno'
    url_fail3 = 123

    get_link = net_io.get_link

    assert type(get_link(url_ok1)) == requests.models.Response
    assert type(get_link(url_ok2)) == requests.models.Response
    assert type(get_link(url_ok3)) == requests.models.Response
    assert get_link(url_fail1) == None
    assert get_link(url_fail2) == None
    assert get_link(url_fail3) == None


def test_scrape_page():
    url_ok1 = 'https://www.nifs.no/kampfakta.php?kamp_id=2133607&land=20&t=45&u=690408&lag1=835&lag2=844'
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