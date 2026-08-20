#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for `load_admin_guild_from_db()` in __main__.py.

sausage_bot/__main__.py calls config.bot.run(...) at module level (no
`if __name__ == "__main__":` guard), so a plain import would try to
connect to Discord. config.bot.run is patched to a no-op for the
duration of the import below to avoid that.

What these guard: the `admin_guild` table is the source of truth for
which guild/channel the bot administers, with ADMIN_GUILD_ID and
ADMIN_CHANNEL_ID from the env file as fallback. A row that names a
guild the bot has left, or a channel that has since been deleted, must
not be applied - every admin notification would go to a channel that
cannot receive it, and `_in_admin_guild()` would lock the owner out of
the owner-only guild commands.
"""

from types import SimpleNamespace
from unittest import mock

from sausage_bot.util import config

with mock.patch.object(config.bot, "run", lambda *args, **kwargs: None):
    from sausage_bot import __main__ as main_module

ENV_GUILD_ID = "111"
ENV_CHANNEL_ID = "222"
DB_GUILD_ID = "868902121834176513"
DB_GUILD_NAME = "Gutteklubben Ugrei"
DB_CHANNEL_ID = "333444555666777888"
DB_CHANNEL_NAME = "bot-log"


def _make_bot(guild_id=None, channel_id=None):
    """
    A bot that is a member of exactly one guild with exactly one channel.
    Passing None for either leaves that lookup returning None, which is
    how a stale db row presents itself at startup.
    """
    channel = SimpleNamespace(id=int(channel_id), name=DB_CHANNEL_NAME)
    guild = SimpleNamespace(
        id=int(guild_id) if guild_id else None,
        name=DB_GUILD_NAME,
        get_channel=lambda wanted: channel if str(wanted) == str(channel_id) else None,
    )
    return SimpleNamespace(
        get_guild=lambda wanted: guild if str(wanted) == str(guild_id) else None
    )


async def _run(row, bot, env_guild=ENV_GUILD_ID, env_channel=ENV_CHANNEL_ID):
    db = main_module.db_helper
    with (
        mock.patch.object(db, "prep_table", mock.AsyncMock()),
        mock.patch.object(db, "get_output", mock.AsyncMock(return_value=row)),
        mock.patch.object(config, "bot", bot),
        mock.patch.object(config, "ENV_ADMIN_GUILD_ID", env_guild),
        mock.patch.object(config, "ENV_ADMIN_CHANNEL_ID", env_channel),
        mock.patch.object(config, "ADMIN_GUILD_ID", "stale"),
        mock.patch.object(config, "ADMIN_CHANNEL_ID", "stale"),
    ):
        await main_module.load_admin_guild_from_db()
        return SimpleNamespace(
            guild_id=config.ADMIN_GUILD_ID,
            channel_id=config.ADMIN_CHANNEL_ID,
        )


def _row(guild_id=DB_GUILD_ID, channel_id=DB_CHANNEL_ID):
    return {
        "guild_id": guild_id,
        "guild_name": DB_GUILD_NAME,
        "guild_channel": channel_id,
    }


async def test_empty_table_keeps_the_env_values():
    # First run on a fresh install - `register_guild()` seeds the row
    result = await _run(None, _make_bot(DB_GUILD_ID, DB_CHANNEL_ID))
    assert result.guild_id == ENV_GUILD_ID
    assert result.channel_id == ENV_CHANNEL_ID


async def test_a_valid_row_overrides_the_env_values():
    result = await _run(_row(), _make_bot(DB_GUILD_ID, DB_CHANNEL_ID))
    assert result.guild_id == DB_GUILD_ID
    assert result.channel_id == DB_CHANNEL_ID


async def test_a_guild_the_bot_has_left_falls_back_to_env():
    result = await _run(_row(), _make_bot("999999999999999999", DB_CHANNEL_ID))
    assert result.guild_id == ENV_GUILD_ID
    assert result.channel_id == ENV_CHANNEL_ID


async def test_a_deleted_channel_falls_back_to_env():
    result = await _run(_row(), _make_bot(DB_GUILD_ID, "999999999999999999"))
    assert result.guild_id == ENV_GUILD_ID
    assert result.channel_id == ENV_CHANNEL_ID


async def test_a_non_numeric_row_falls_back_to_env():
    result = await _run(
        _row(guild_id="not-an-id", channel_id="also-not"),
        _make_bot(DB_GUILD_ID, DB_CHANNEL_ID),
    )
    assert result.guild_id == ENV_GUILD_ID


async def test_running_twice_does_not_leave_a_stale_override():
    # The reset-to-env at the top is what makes this idempotent: without
    # it, a second call after a valid first one would keep the old values
    # as its "env fallback" instead of the real ones.
    bot = _make_bot(DB_GUILD_ID, DB_CHANNEL_ID)
    await _run(_row(), bot)
    result = await _run(None, bot)
    assert result.guild_id == ENV_GUILD_ID
    assert result.channel_id == ENV_CHANNEL_ID


async def test_missing_everywhere_is_reported_as_an_error():
    with mock.patch.object(main_module.logger, "error") as log_error:
        result = await _run(
            None,
            _make_bot(DB_GUILD_ID, DB_CHANNEL_ID),
            env_guild=None,
            env_channel=None,
        )
    assert result.guild_id is None
    log_error.assert_called_once()
    assert "set_admin_guild" in log_error.call_args.args[0]
