#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests the argument handling in the `/youtube list`, `/rss list` and
`/podcast list` commands.

Their `typing.Literal` choices are built from `I18N.t()` once, at import
time, and discord hands the picked *value* back untranslated - only the
name shown in the client is localized. Comparing that value against a
fresh `I18N.t()` call therefore matches nothing as soon as a guild runs
in another locale, which used to leave `Added`/`Filter` silently listing
the normal list. Each command is invoked via its `.callback` (see
main_profile_commands_test.py), with `feeds_core.get_feed_list` patched
out, to check what the cog passes on.
"""

from types import SimpleNamespace
from unittest import mock

import pytest

from sausage_bot.cogs import rss, youtube
from sausage_bot.util import feeds_core, guild_context

GUILD_ID = 555555555555555555


def _choice_values(command, parameter_name):
    "The values discord will hand back for `parameter_name`"
    for parameter in command.parameters:
        if parameter.name == parameter_name:
            return [choice.value for choice in parameter.choices]
    raise AssertionError(f"`{command.name}` has no `{parameter_name}` parameter")


def _make_interaction():
    return SimpleNamespace(
        response=SimpleNamespace(defer=mock.AsyncMock()),
        followup=SimpleNamespace(send=mock.AsyncMock()),
        guild=SimpleNamespace(id=GUILD_ID),
    )


@pytest.fixture
def feed_list_calls(monkeypatch):
    "Record what the cogs ask `get_feed_list` for, without touching a db"
    calls = []

    async def fake_get_feed_list(**kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr(feeds_core, "get_feed_list", fake_get_feed_list)
    return calls


@pytest.fixture
def norwegian_guild():
    "Run the command as a guild that isn't on the import-time locale"
    token = guild_context.current_locale.set("nb")
    yield
    guild_context.current_locale.reset(token)


@pytest.mark.parametrize(
    "command, parameter_name, constants",
    [
        (
            youtube.Youtube.youtube_list,
            "list_type",
            [
                youtube.LIST_TYPE_NORMAL,
                youtube.LIST_TYPE_ADDED,
                youtube.LIST_TYPE_FILTER,
            ],
        ),
        (
            youtube.Youtube.youtube_list,
            "link_type",
            [youtube.LINK_TYPE_CHANNEL, youtube.LINK_TYPE_PLAYLIST],
        ),
        (
            rss.RSSfeed.rss_list,
            "list_type",
            [rss.LIST_TYPE_NORMAL, rss.LIST_TYPE_ADDED, rss.LIST_TYPE_FILTER],
        ),
        (
            rss.RSSfeed.podcast_list,
            "list_type",
            [rss.LIST_TYPE_NORMAL, rss.LIST_TYPE_ADDED, rss.LIST_TYPE_FILTER],
        ),
    ],
)
def test_choices_are_the_constants_the_commands_compare_against(
    command, parameter_name, constants
):
    "Whatever locale the choices were built in, the comparisons must match"
    assert _choice_values(command, parameter_name) == constants


async def test_youtube_list_added_is_untranslated(feed_list_calls, norwegian_guild):
    await youtube.Youtube.youtube_list.callback(
        mock.Mock(), _make_interaction(), youtube.LIST_TYPE_ADDED
    )

    assert feed_list_calls[0]["list_type"] == "added"


async def test_youtube_list_filter_is_untranslated(feed_list_calls, norwegian_guild):
    await youtube.Youtube.youtube_list.callback(
        mock.Mock(), _make_interaction(), youtube.LIST_TYPE_FILTER
    )

    assert feed_list_calls[0]["list_type"] == "filter"


async def test_youtube_list_normal_has_no_list_type(feed_list_calls, norwegian_guild):
    await youtube.Youtube.youtube_list.callback(
        mock.Mock(), _make_interaction(), youtube.LIST_TYPE_NORMAL
    )

    assert "list_type" not in feed_list_calls[0]


@pytest.mark.parametrize(
    "link_type_literal, expected",
    [
        (youtube.LINK_TYPE_CHANNEL, "channel"),
        (youtube.LINK_TYPE_PLAYLIST, "playlist"),
        (None, None),
    ],
)
async def test_youtube_list_link_type_is_untranslated(
    feed_list_calls, norwegian_guild, link_type_literal, expected
):
    await youtube.Youtube.youtube_list.callback(
        mock.Mock(), _make_interaction(), youtube.LIST_TYPE_NORMAL, link_type_literal
    )

    assert feed_list_calls[0]["link_type"] == expected


@pytest.mark.parametrize(
    "command", [rss.RSSfeed.rss_list, rss.RSSfeed.podcast_list]
)
async def test_rss_list_added_is_untranslated(
    feed_list_calls, norwegian_guild, command
):
    await command.callback(mock.Mock(), _make_interaction(), rss.LIST_TYPE_ADDED)

    assert feed_list_calls[0]["list_type"] == "added"


@pytest.mark.parametrize(
    "command", [rss.RSSfeed.rss_list, rss.RSSfeed.podcast_list]
)
async def test_rss_list_filter_is_untranslated(
    feed_list_calls, norwegian_guild, command
):
    await command.callback(mock.Mock(), _make_interaction(), rss.LIST_TYPE_FILTER)

    assert feed_list_calls[0]["list_type"] == "filter"


@pytest.mark.parametrize(
    "command, feed_type",
    [(rss.RSSfeed.rss_list, "rss"), (rss.RSSfeed.podcast_list, "podcast")],
)
async def test_rss_list_normal_keeps_feed_type(
    feed_list_calls, norwegian_guild, command, feed_type
):
    await command.callback(mock.Mock(), _make_interaction(), rss.LIST_TYPE_NORMAL)

    assert "list_type" not in feed_list_calls[0]
    assert feed_list_calls[0]["feed_type"] == feed_type
