#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for `cogs/quote.py`'s `get_quote_channel_name()`.

The quote table's `channel_id` is empty for quotes that were imported
rather than picked up from a Discord channel (the bot's own guild has 105
such rows out of 186), and it can also point at a channel that has since
been deleted. Every quote-posting path builds its `# <n> - #<channel>`
header from this, so an unguarded `int(channel_id)` raised
`TypeError: int() argument must be ... not 'NoneType'` on `/quote post`
whenever a random draw hit one of those rows.
"""
from types import SimpleNamespace

from sausage_bot.cogs.quote import get_quote_channel_name


def _guild(*channels):
    return SimpleNamespace(text_channels=list(channels))


def _channel(channel_id, name):
    return SimpleNamespace(id=channel_id, name=name)


def test_resolvable_channel_id_gives_the_live_channel_name():
    guild = _guild(_channel(555, "quotes"))
    quote = {"channel_id": 555, "channel_backup": "stale-name"}
    assert get_quote_channel_name(guild, quote) == "quotes"


def test_channel_id_as_string_still_resolves():
    # Rows written by older versions can hold the id as TEXT
    guild = _guild(_channel(555, "quotes"))
    quote = {"channel_id": "555", "channel_backup": "stale-name"}
    assert get_quote_channel_name(guild, quote) == "quotes"


def test_null_channel_id_falls_back_to_backup():
    # Imported quotes - this is the case that crashed `/quote post`
    guild = _guild(_channel(555, "quotes"))
    quote = {"channel_id": None, "channel_backup": "Telegram-chatten"}
    assert get_quote_channel_name(guild, quote) == "Telegram-chatten"


def test_empty_channel_id_falls_back_to_backup():
    guild = _guild(_channel(555, "quotes"))
    quote = {"channel_id": "", "channel_backup": "Telegram-chatten"}
    assert get_quote_channel_name(guild, quote) == "Telegram-chatten"


def test_deleted_channel_falls_back_to_backup():
    guild = _guild(_channel(555, "quotes"))
    quote = {"channel_id": 999, "channel_backup": "deleted-channel"}
    assert get_quote_channel_name(guild, quote) == "deleted-channel"


def test_channel_from_another_guild_is_not_used():
    # Guild-scoped lookup: only this guild's own channels may resolve, so
    # a channel id belonging to another guild must fall back to the backup
    other_guilds_channel = _channel(777, "other-guild-quotes")
    guild = _guild(_channel(555, "quotes"))
    quote = {"channel_id": other_guilds_channel.id, "channel_backup": "backup-name"}
    assert get_quote_channel_name(guild, quote) == "backup-name"
