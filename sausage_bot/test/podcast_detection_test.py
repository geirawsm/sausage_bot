#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for podcast feed detection.

The bug these guard against: a plain news feed carrying a single audio
enclosure used to be classified as a podcast, which made
`process_links_for_posting_or_editing` take the podcast branch and raise
`KeyError: 'feed_name'`, killing the whole `task_post_feeds` loop.
"""
from bs4 import BeautifulSoup

from sausage_bot.util import envs, feeds_core
from sausage_bot.util.net_io import (
    enclosure_is_media,
    get_channel_info,
    is_podcast_feed,
)


def soup_from(path):
    "#autodoc skip#"
    with open(path, "rb") as fd:
        return BeautifulSoup(fd.read(), features="xml")


def test_real_podcast_feed_is_detected():
    "A real podcast feed (Omny) is recognized as a podcast"
    podcast, ratio, signals = is_podcast_feed(soup_from(envs.test_xml_podcast))
    assert podcast is True
    assert ratio == 1.0
    assert "itunes-ns" in signals


def test_news_feed_with_single_audio_is_not_a_podcast():
    """
    A news feed where one article carries audio must stay an RSS feed.
    This is the regression that crashed `task_post_feeds`.
    """
    podcast, ratio, signals = is_podcast_feed(
        soup_from(envs.test_xml_news_single_audio)
    )
    assert podcast is False
    assert 0 < ratio < envs.PODCAST_RATIO_WITH_SIGNALS


def test_ordinary_news_feed_is_not_a_podcast():
    "A feed with no audio at all is never a podcast"
    podcast, ratio, _signals = is_podcast_feed(soup_from(envs.test_xml_good))
    assert podcast is False
    assert ratio == 0.0


def test_feed_without_items_is_not_a_podcast():
    "An empty feed must not divide by zero"
    soup = BeautifulSoup(
        '<?xml version="1.0"?><rss><channel><title>Tom</title></channel></rss>',
        features="xml",
    )
    assert is_podcast_feed(soup) == (False, 0.0, [])


def test_itunes_signals_cannot_promote_a_news_feed():
    """
    iTunes tags are supporting evidence only. Without episodes to back
    them up they must not turn a feed into a podcast.
    """
    soup = BeautifulSoup(
        '<?xml version="1.0"?>'
        '<rss xmlns:itunes="{}"><channel><title>Nyheter</title>'
        "<itunes:category/><itunes:author>Red</itunes:author>"
        "<item><title>Sak</title></item>"
        "<item><title>Sak 2</title></item>"
        "</channel></rss>".format(envs.ITUNES_NAMESPACE),
        features="xml",
    )
    podcast, ratio, signals = is_podcast_feed(soup)
    assert signals != []
    assert ratio == 0.0
    assert podcast is False


def test_generic_mime_type_falls_back_on_file_extension():
    "Aggregators serving octet-stream are still recognized by extension"
    soup = BeautifulSoup(
        '<enclosure url="https://ex.org/ep.mp3?auth=1" '
        'type="application/octet-stream"/>',
        features="xml",
    )
    assert enclosure_is_media(soup.find("enclosure")) is True


def test_non_media_enclosure_is_ignored():
    "Image enclosures, which news feeds use heavily, do not count"
    soup = BeautifulSoup(
        '<enclosure url="https://ex.org/bilde.jpg" type="image/jpeg"/>',
        features="xml",
    )
    assert enclosure_is_media(soup.find("enclosure")) is False


def test_get_channel_info_reads_podcast_channel():
    "Feed level name, description and image are picked up"
    feed_name, feed_description, feed_img = get_channel_info(
        soup_from(envs.test_xml_podcast)
    )
    assert feed_name
    assert feed_description
    assert feed_img and feed_img.startswith("http")


def test_get_channel_info_falls_back_to_plain_rss_image():
    "Feeds without `itunes:image` fall back on the plain RSS image"
    soup = BeautifulSoup(
        '<?xml version="1.0"?><rss><channel><title>Show</title>'
        "<description>Om</description>"
        "<image><url>https://ex.org/cover.png</url></image>"
        "</channel></rss>",
        features="xml",
    )
    assert get_channel_info(soup) == (
        "Show",
        "Om",
        "https://ex.org/cover.png",
    )


def test_get_channel_info_tolerates_missing_channel():
    "An html page must return empty values rather than raise"
    soup = BeautifulSoup("<html><body>ingen feed</body></html>", features="xml")
    assert get_channel_info(soup) == (None, None, None)


async def test_news_items_keep_rss_type():
    """
    End to end: the items produced from a news feed with one audio
    enclosure must be typed `rss`, not `podcast`.
    """
    with open(envs.test_xml_news_single_audio, "rb") as fd:
        req = fd.read()
    items = await feeds_core.get_items_from_rss(req=req, url="https://ex.org/feed")
    assert len(items) > 0
    assert all(item["type"] == "rss" for item in items)


async def test_podcast_items_get_feed_level_keys():
    """
    Items from a podcast feed carry the feed level keys the posting code
    reads, so the podcast branch can never raise `KeyError`.
    """
    with open(envs.test_xml_podcast, "rb") as fd:
        req = fd.read()
    items = await feeds_core.get_items_from_rss(req=req, url="https://ex.org/pod")
    assert len(items) > 0
    for item in items:
        assert item["type"] == "podcast"
        for key in ("feed_name", "feed_description", "feed_img", "feed_uuid"):
            assert key in item
