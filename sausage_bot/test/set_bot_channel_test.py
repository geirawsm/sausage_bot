#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the /bot_channel command in __main__.py and its helper
`_persist_bot_channel`.

Only the non-UI logic is exercised here: storing the setting, the
"channel already exists" fast path, and that the create/duplicate view is
offered when the channel is missing. The `DuplicateChannelModal` /
`CreateBotChannelView` button+modal flow talks to live Discord and must be
smoke-tested against a real server.

sausage_bot/__main__.py calls config.bot.run(...) at module level, so the
import below patches it to a no-op (same pattern as
main_profile_commands_test.py). Commands are invoked via their `.callback`
- the raw async function discord.py stores on the app_commands.Command.

Uses the `guild_db_root` fixture (conftest.py) so nothing touches real
bot data.
"""
from types import SimpleNamespace
from unittest import mock

from sausage_bot.util import config, envs, db_helper

with mock.patch.object(config.bot, "run", lambda *args, **kwargs: None):
    from sausage_bot.__main__ import (
        set_bot_channel,
        _persist_bot_channel,
        CreateBotChannelView,
    )

GUILD_ID = 444444444444444444


async def _prep_settings():
    await db_helper.prep_table(
        envs.settings_db_schema,
        inserts=envs.settings_db_schema["inserts"],
        guild_id=GUILD_ID,
    )


def _make_guild():
    return SimpleNamespace(id=GUILD_ID, name="Guild")


def _make_interaction(guild):
    return SimpleNamespace(
        guild=guild,
        response=SimpleNamespace(defer=mock.AsyncMock()),
        followup=SimpleNamespace(send=mock.AsyncMock()),
    )


async def _read_bot_channel():
    settings = await db_helper.get_output(
        envs.settings_db_schema, guild_id=GUILD_ID, as_settings_json=True
    )
    return settings["bot_channel"]


async def test_persist_bot_channel_stores_setting(guild_db_root):
    await _prep_settings()
    await _persist_bot_channel(_make_guild(), "my-log")
    assert await _read_bot_channel() == "my-log"


async def test_set_bot_channel_existing_channel_persists(
    guild_db_root, monkeypatch
):
    await _prep_settings()
    interaction = _make_interaction(_make_guild())
    monkeypatch.setattr(
        "sausage_bot.__main__.discord_commands.get_text_channel_list",
        lambda g: {"existing-log": "999"},
    )

    await set_bot_channel.callback(interaction, bot_channel="existing-log")

    assert await _read_bot_channel() == "existing-log"
    interaction.followup.send.assert_awaited()  # a confirmation was sent


async def test_set_bot_channel_missing_channel_offers_view(
    guild_db_root, monkeypatch
):
    await _prep_settings()
    interaction = _make_interaction(_make_guild())
    monkeypatch.setattr(
        "sausage_bot.__main__.discord_commands.get_text_channel_list",
        lambda g: {"other": "1"},
    )

    await set_bot_channel.callback(interaction, bot_channel="brand-new")

    # Nothing stored yet - the setting waits for the view's button flow.
    assert await _read_bot_channel() == ""
    # The user was offered the create/duplicate view.
    _, kwargs = interaction.followup.send.call_args
    assert isinstance(kwargs.get("view"), CreateBotChannelView)
