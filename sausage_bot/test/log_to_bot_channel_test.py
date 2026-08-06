#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exercises the per-guild `bot_channel` resolution in
`discord_commands.log_to_bot_channel`: the target channel name is read
from the guild's own `settings` table, falling back to the bot-wide
default (`config.BOT_CHANNEL`) when the guild hasn't set one.

Uses the `guild_db_root` fixture (see conftest.py) so nothing touches
real bot data. Discord's `Guild`/channel objects are mocked - only the
channel-name resolution and the final `.send()` are under test.
"""
from unittest.mock import AsyncMock, MagicMock

from sausage_bot.util import envs, db_helper, discord_commands, config

GUILD_ID = 333333333333333333


async def _prep_settings(bot_channel_value=None):
    "Create the guild's settings table; optionally set its bot_channel."
    await db_helper.prep_table(
        envs.settings_db_schema,
        inserts=envs.settings_db_schema["inserts"],
        guild_id=GUILD_ID,
    )
    if bot_channel_value is not None:
        await db_helper.update_fields(
            envs.settings_db_schema,
            where=("setting", "bot_channel"),
            updates=[("value", bot_channel_value)],
            guild_id=GUILD_ID,
        )


def _make_guild():
    "A mock guild whose get_channel() returns a channel with async send()."
    channel = MagicMock()
    channel.send = AsyncMock(return_value="sent-msg")
    guild = MagicMock()
    guild.id = GUILD_ID
    guild.get_channel = MagicMock(return_value=channel)
    return guild, channel


async def test_log_to_bot_channel_uses_per_guild_setting(
    guild_db_root, monkeypatch
):
    await _prep_settings("guild-specific-log")
    guild, channel = _make_guild()
    monkeypatch.setattr(
        discord_commands,
        "get_text_channel_list",
        lambda g: {"guild-specific-log": "4242"},
    )

    result = await discord_commands.log_to_bot_channel(guild, "hello")

    guild.get_channel.assert_called_once_with(4242)
    channel.send.assert_awaited_once_with(content="hello")
    assert result == "sent-msg"


async def test_log_to_bot_channel_falls_back_to_config_default(
    guild_db_root, monkeypatch
):
    # bot_channel stays "" (its default insert) -> config.BOT_CHANNEL wins.
    await _prep_settings()
    guild, channel = _make_guild()
    monkeypatch.setattr(config, "BOT_CHANNEL", "default-log")
    monkeypatch.setattr(
        discord_commands,
        "get_text_channel_list",
        lambda g: {"default-log": "4242"},
    )

    await discord_commands.log_to_bot_channel(guild, "hi")

    guild.get_channel.assert_called_once_with(4242)
    channel.send.assert_awaited_once_with(content="hi")
