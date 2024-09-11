#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytest
import pytest_asyncio
from sausage_bot.util import file_io


def test_check_similarity_return_number_or_none():
    link1 = 'https://www.kode24.no/artikkel/ny-utviklingsavdeling-skal-reo'\
        'vlusjonere-mattilsynet-vi-ma-torre-a-vaere-mer-risikovillige/7619499'
    link2 = 'https://www.kode24.no/artikkel/ny-utviklingsavdeling-skal-rev'\
        'olusjonere-mattilsynet-vi-ma-torre-a-vaere-mer-risikovillige/76194994'
    link3 = False
    assert file_io.check_similarity(link1, link2) is link2
    assert file_io.check_similarity(link1, link3) is None
