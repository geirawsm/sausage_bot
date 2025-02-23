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
    good_url = 'https://www.metalsucks.net/category/shit-that-comes-out-today/feed/'
    good_mock = envs.test_xml_good
    bad_url = 'https://www.bbc.co.uk'
    bad_mock = envs.test_xml_bad2

    out_good = await feeds_core.check_feed_validity(
        good_url, mock_file=good_mock
    )
    out_bad = await feeds_core.check_feed_validity(
        bad_url, mock_file=bad_mock
    )

    assert out_good is True
    assert out_bad is False
