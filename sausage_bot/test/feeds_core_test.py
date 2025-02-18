#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytest
from sausage_bot.util import file_io, feeds_core, envs
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
