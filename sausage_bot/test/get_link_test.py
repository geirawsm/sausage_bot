#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for `net_io.get_link()`'s handling of a missing user-agent file
and of failures that never reached the server.

What these guard: `SCRAPEOPS_API_KEY` is optional, so the scraped
`headers.json` is regularly missing. `file_io.read_json()` creates it as
an empty `{}`, which used to make the user-agent lookup raise
`KeyError: 'result'`. The broad `except` in `get_link()` then reported
it as `Error when getting url:(0) 'result'` - a url error for what was
really a missing local file - and returned `url_status`, still 0, which
callers read as a real HTTP status code.
"""

from unittest import mock

import pytest

from sausage_bot.util import net_io

URL = "https://www.youtube.com/@example"


class _FakeResponse:
    def __init__(self, status=200, text="<html>ok</html>"):
        self.status = status
        self._text = text

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


class _FakeSession:
    """Records the headers it was called with, then returns a 200."""

    def __init__(self, response=None):
        self.headers_seen = []
        self._response = response or _FakeResponse()

    def get(self, url, headers=None):
        self.headers_seen.append(headers)
        return self._response

    async def close(self):
        return None


def _no_user_agents():
    # What read_json() returns for a missing/empty headers file
    return mock.patch.object(net_io.file_io, "read_json", return_value={})


def _some_user_agents():
    return mock.patch.object(
        net_io.file_io,
        "read_json",
        return_value={"result": [{"user-agent": "test-agent/1.0"}]},
    )


async def test_missing_headers_file_does_not_break_the_request():
    # Regression: this raised KeyError: 'result' before ever connecting.
    session = _FakeSession()
    with (
        _no_user_agents(),
        mock.patch.object(net_io.aiohttp, "ClientSession", lambda: session),
    ):
        result = await net_io.get_link(URL)
    assert result == "<html>ok</html>"
    # No user-agent to send, so aiohttp's own default is used
    assert session.headers_seen == [None]


async def test_a_scraped_user_agent_is_used_when_available():
    session = _FakeSession()
    with (
        _some_user_agents(),
        mock.patch.object(net_io.aiohttp, "ClientSession", lambda: session),
    ):
        await net_io.get_link(URL)
    assert session.headers_seen == [{"user-agent": "test-agent/1.0"}]


async def test_a_failed_request_returns_none_rather_than_a_fake_status():
    # `url_status` is still 0 when the request never happened. Returning
    # it made callers report "HTTP status 0" and slip past `is None`
    # checks - `get_page_hash()` then handed the 0 to BeautifulSoup.
    def _explode():
        raise OSError("no route to host")

    with (
        _no_user_agents(),
        mock.patch.object(net_io.aiohttp, "ClientSession", _explode),
    ):
        result = await net_io.get_link(URL)
    assert result is None


async def test_a_failed_request_keeps_the_dict_shape_for_status_out():
    # `feeds_core`/`rss` index req["status"] with no guard, so the
    # failure path has to stay subscriptable.
    def _explode():
        raise OSError("no route to host")

    with (
        _no_user_agents(),
        mock.patch.object(net_io.aiohttp, "ClientSession", _explode),
    ):
        result = await net_io.get_link(URL, status_out=True)
    assert result["status"] != 200
    assert result["content"] is None


@pytest.mark.parametrize("bad_url", [None, "", 42])
async def test_an_unusable_url_still_returns_none(bad_url):
    assert await net_io.get_link(bad_url) is None
