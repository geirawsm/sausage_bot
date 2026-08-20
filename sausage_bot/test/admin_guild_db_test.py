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


async def _run(
    row, bot, env_guild=ENV_GUILD_ID, env_channel=ENV_CHANNEL_ID, persist=None
):
    # `_persist_admin_guild` is patched out by default: an empty table
    # makes `load_admin_guild_from_db()` try to seed the row, and an
    # unpatched seed would write to the real guilds db file.
    db = main_module.db_helper
    persist = persist if persist is not None else mock.AsyncMock(return_value=True)
    with (
        mock.patch.object(db, "prep_table", mock.AsyncMock()),
        mock.patch.object(db, "get_output", mock.AsyncMock(return_value=row)),
        mock.patch.object(main_module, "_persist_admin_guild", persist),
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
            persist=persist,
        )


def _row(guild_id=DB_GUILD_ID, channel_id=DB_CHANNEL_ID):
    return {
        "guild_id": guild_id,
        "guild_name": DB_GUILD_NAME,
        "guild_channel": channel_id,
    }


async def test_empty_table_keeps_the_env_values():
    # First run on a fresh install. The env guild is not one this bot is
    # in, so there is nothing to seed - the values still apply for the run.
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


async def test_reachable_env_values_are_seeded_into_an_empty_table():
    # The bootstrap path: env points at a guild/channel the bot can see
    # and the table is empty, so the row is written for the next start.
    result = await _run(
        None,
        _make_bot(DB_GUILD_ID, DB_CHANNEL_ID),
        env_guild=DB_GUILD_ID,
        env_channel=DB_CHANNEL_ID,
    )
    result.persist.assert_awaited_once()
    seeded_guild, seeded_channel = result.persist.await_args.args
    assert str(seeded_guild.id) == DB_GUILD_ID
    assert str(seeded_channel.id) == DB_CHANNEL_ID


async def test_seeding_is_skipped_when_the_env_guild_is_unreachable():
    result = await _run(
        None,
        _make_bot(DB_GUILD_ID, DB_CHANNEL_ID),
        env_guild="999999999999999999",
        env_channel=DB_CHANNEL_ID,
    )
    result.persist.assert_not_awaited()


async def test_seeding_is_skipped_when_the_env_channel_is_unreachable():
    result = await _run(
        None,
        _make_bot(DB_GUILD_ID, DB_CHANNEL_ID),
        env_guild=DB_GUILD_ID,
        env_channel="999999999999999999",
    )
    result.persist.assert_not_awaited()


async def test_a_dangling_row_is_not_overwritten_by_the_env_values():
    # The row names a guild the bot has left. It is deliberately kept so
    # the owner can see what it pointed at - seeding only fills an empty
    # table.
    result = await _run(
        _row(),
        _make_bot("999999999999999999", DB_CHANNEL_ID),
        env_guild="999999999999999999",
        env_channel=DB_CHANNEL_ID,
    )
    result.persist.assert_not_awaited()


async def test_persist_writes_a_value_for_every_column():
    # Regression: this used to insert (guild_id, guild_name) into a
    # three-column table, which SQLite rejects with "table admin_guild has
    # 3 columns but 2 values were supplied". The error was swallowed by
    # db_helper, so the row was silently never written.
    db = main_module.db_helper
    insert = mock.AsyncMock(return_value=True)
    guild = SimpleNamespace(id=int(DB_GUILD_ID), name=DB_GUILD_NAME)
    channel = SimpleNamespace(id=int(DB_CHANNEL_ID), name=DB_CHANNEL_NAME)
    with (
        mock.patch.object(db, "prep_table", mock.AsyncMock()),
        mock.patch.object(db, "empty_table", mock.AsyncMock()),
        mock.patch.object(db, "insert_many_all", insert),
        mock.patch.object(config, "ADMIN_GUILD_ID", None),
        mock.patch.object(config, "ADMIN_CHANNEL_ID", None),
    ):
        assert await main_module._persist_admin_guild(guild, channel) is True
        assert config.ADMIN_GUILD_ID == DB_GUILD_ID
        assert config.ADMIN_CHANNEL_ID == DB_CHANNEL_ID
    columns = main_module.envs.admin_guild_db_schema["items"]
    written = insert.await_args.kwargs["inserts"][0]
    assert len(written) == len(columns)
    assert written == (DB_GUILD_ID, DB_GUILD_NAME, DB_CHANNEL_ID)


async def test_persist_reports_a_failed_write_and_leaves_config_alone():
    db = main_module.db_helper
    guild = SimpleNamespace(id=int(DB_GUILD_ID), name=DB_GUILD_NAME)
    channel = SimpleNamespace(id=int(DB_CHANNEL_ID), name=DB_CHANNEL_NAME)
    with (
        mock.patch.object(db, "prep_table", mock.AsyncMock()),
        mock.patch.object(db, "empty_table", mock.AsyncMock()),
        mock.patch.object(db, "insert_many_all", mock.AsyncMock(return_value=False)),
        mock.patch.object(config, "ADMIN_GUILD_ID", "unchanged"),
        mock.patch.object(config, "ADMIN_CHANNEL_ID", "unchanged"),
    ):
        assert await main_module._persist_admin_guild(guild, channel) is False
        # A failed write must not leave the process claiming an admin
        # guild that is not stored anywhere.
        assert config.ADMIN_GUILD_ID == "unchanged"
        assert config.ADMIN_CHANNEL_ID == "unchanged"
