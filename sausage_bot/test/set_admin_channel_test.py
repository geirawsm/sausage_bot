#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the /guild set_admin_channel command in __main__.py.

sausage_bot/__main__.py calls config.bot.run(...) at module level (no
`if __name__ == "__main__":` guard), so a plain import would try to
connect to Discord. config.bot.run is patched to a no-op for the
duration of the import below to avoid that.

What these guard: set_admin_channel moves the admin channel *within*
the guild that is already the admin guild. It shares the channel
resolution and create-with-confirmation flow with /guild
set_admin_guild via `resolve_admin_channel()`, but must not touch which
guild is the admin guild, and must not re-approve anything.
"""

import contextlib
import discord
from types import SimpleNamespace
from unittest import mock

from sausage_bot.util import config

with mock.patch.object(config.bot, "run", lambda *args, **kwargs: None):
    from sausage_bot import __main__ as main_module
    from sausage_bot.__main__ import Guild

ADMIN_GUILD_ID = "868902121834176513"
ADMIN_GUILD_NAME = "Gutteklubben Ugrei"
OTHER_GUILD_ID = "111"
EXISTING_CHANNEL_ID = "222333444555666777"
EXISTING_CHANNEL_NAME = "bot-log"


def _make_channel(channel_id, name):
    channel = mock.MagicMock(spec=discord.TextChannel)
    channel.id = int(channel_id)
    channel.name = name
    return channel


def _make_guild(guild_id, name, channels):
    guild = mock.MagicMock(spec=discord.Guild)
    guild.id = int(guild_id)
    guild.name = name
    guild.text_channels = channels
    guild.get_channel = lambda wanted: next(
        (channel for channel in channels if channel.id == wanted), None
    )
    return guild


def _make_bot(guilds):
    return SimpleNamespace(
        guilds=guilds,
        get_guild=lambda wanted: next(
            (guild for guild in guilds if guild.id == wanted), None
        ),
        user=SimpleNamespace(name="sausage-bot"),
    )


def _make_interaction(guild_id=ADMIN_GUILD_ID, user_id=42):
    message = mock.AsyncMock()
    return SimpleNamespace(
        guild_id=guild_id,
        user=SimpleNamespace(id=user_id),
        response=SimpleNamespace(defer=mock.AsyncMock()),
        followup=SimpleNamespace(send=mock.AsyncMock(return_value=message)),
        message=message,
    )


@contextlib.asynccontextmanager
async def _noop_locale_context(*args, **kwargs):
    yield


def _confirm_view(value):
    class _View:
        def __init__(self, user_id, timeout=60):
            self.user_id = user_id
            self.value = value

    async def _wait(self):
        return

    _View.wait = _wait
    return _View


async def _run(
    interaction,
    channel,
    confirm=True,
    created_channel=None,
    bot_in_admin_guild=True,
):
    admin_guild = _make_guild(
        ADMIN_GUILD_ID,
        ADMIN_GUILD_NAME,
        [_make_channel(EXISTING_CHANNEL_ID, EXISTING_CHANNEL_NAME)],
    )
    guilds = [admin_guild] if bot_in_admin_guild else []
    db = main_module.db_helper
    create_missing_channel = mock.AsyncMock(return_value=created_channel)
    with contextlib.ExitStack() as stack:
        for patch in (
            mock.patch.object(config, "bot", _make_bot(guilds)),
            mock.patch.object(db, "get_output", mock.AsyncMock(return_value=[])),
            mock.patch.object(db, "prep_table", mock.AsyncMock()),
            mock.patch.object(db, "empty_table", mock.AsyncMock()),
            mock.patch.object(db, "insert_many_all", mock.AsyncMock()),
            mock.patch.object(db, "update_fields", mock.AsyncMock()),
            mock.patch.object(db, "ensure_guild_tasks_rows", mock.AsyncMock()),
            mock.patch.object(db, "guild_locale_context", _noop_locale_context),
            mock.patch.object(
                main_module.discord_commands,
                "create_missing_channel",
                create_missing_channel,
            ),
            mock.patch.object(
                main_module, "CreateAdminChannelConfirm_view", _confirm_view(confirm)
            ),
            mock.patch.object(config, "ADMIN_GUILD_ID", ADMIN_GUILD_ID),
            mock.patch.object(config, "ADMIN_CHANNEL_ID", "000"),
        ):
            stack.enter_context(patch)
        await Guild.set_admin_channel.callback(None, interaction, channel)
        return SimpleNamespace(
            insert_many_all=db.insert_many_all,
            empty_table=db.empty_table,
            update_fields=db.update_fields,
            ensure_guild_tasks_rows=db.ensure_guild_tasks_rows,
            create_missing_channel=create_missing_channel,
            admin_guild_id=config.ADMIN_GUILD_ID,
            admin_channel_id=config.ADMIN_CHANNEL_ID,
        )


def _last_sent(interaction):
    return interaction.followup.send.await_args.args[0]


def _last_edited(interaction):
    return interaction.message.edit.await_args.kwargs["content"]


# --- picking an existing channel ---


async def test_existing_channel_is_stored_against_the_current_admin_guild():
    interaction = _make_interaction()
    db = await _run(interaction, EXISTING_CHANNEL_ID)
    db.create_missing_channel.assert_not_awaited()
    inserts = db.insert_many_all.await_args.kwargs["inserts"]
    assert inserts == [(ADMIN_GUILD_ID, ADMIN_GUILD_NAME, EXISTING_CHANNEL_ID)]
    assert EXISTING_CHANNEL_NAME in _last_sent(interaction)


async def test_existing_channel_by_name_resolves_to_that_channel():
    interaction = _make_interaction()
    db = await _run(interaction, EXISTING_CHANNEL_NAME)
    assert db.insert_many_all.await_args.kwargs["inserts"][0][2] == EXISTING_CHANNEL_ID


async def test_only_the_channel_moves_the_admin_guild_stays_put():
    interaction = _make_interaction()
    db = await _run(interaction, EXISTING_CHANNEL_ID)
    assert db.admin_guild_id == ADMIN_GUILD_ID
    assert db.admin_channel_id == EXISTING_CHANNEL_ID


async def test_nothing_is_re_approved():
    # The guild is already the admin guild - re-running the approval
    # would rewrite approved_by/approved_at for no reason
    interaction = _make_interaction()
    db = await _run(interaction, EXISTING_CHANNEL_ID)
    db.update_fields.assert_not_awaited()
    db.ensure_guild_tasks_rows.assert_not_awaited()


# --- creating a new channel ---


async def test_unknown_channel_name_is_created_after_confirmation():
    interaction = _make_interaction()
    new_channel = _make_channel("999888777666555444", "admin-log")
    db = await _run(
        interaction, "admin-log", confirm=True, created_channel=new_channel
    )
    assert db.create_missing_channel.await_args.kwargs["channel_name"] == "admin-log"
    assert db.insert_many_all.await_args.kwargs["inserts"][0][2] == str(new_channel.id)
    assert "admin-log" in _last_edited(interaction)


async def test_the_autocomplete_create_choice_is_unwrapped():
    interaction = _make_interaction()
    new_channel = _make_channel("999888777666555444", "admin-log")
    db = await _run(
        interaction,
        main_module.NEW_CHANNEL_PREFIX + "admin-log",
        created_channel=new_channel,
    )
    assert db.create_missing_channel.await_args.kwargs["channel_name"] == "admin-log"


async def test_cancelling_creates_nothing_and_changes_nothing():
    interaction = _make_interaction()
    db = await _run(interaction, "typo-channel", confirm=False)
    db.create_missing_channel.assert_not_awaited()
    db.insert_many_all.assert_not_awaited()
    assert db.admin_channel_id == "000"


# --- guard rails ---


async def test_rejects_use_outside_the_admin_guild():
    interaction = _make_interaction(guild_id=OTHER_GUILD_ID)
    db = await _run(interaction, EXISTING_CHANNEL_ID)
    assert "admin guild" in _last_sent(interaction)
    db.insert_many_all.assert_not_awaited()


async def test_reports_when_the_bot_is_no_longer_in_its_admin_guild():
    interaction = _make_interaction()
    db = await _run(interaction, EXISTING_CHANNEL_ID, bot_in_admin_guild=False)
    assert "no longer in its own admin guild" in _last_sent(interaction)
    db.insert_many_all.assert_not_awaited()


async def test_a_channel_id_that_no_longer_exists_writes_nothing():
    interaction = _make_interaction()
    db = await _run(interaction, "123456789012345678")
    assert "No channel with id" in _last_sent(interaction)
    db.insert_many_all.assert_not_awaited()


async def test_empty_channel_argument_writes_nothing():
    interaction = _make_interaction()
    db = await _run(interaction, "   ")
    assert "No channel given" in _last_sent(interaction)
    db.insert_many_all.assert_not_awaited()


# --- autocomplete ---


async def test_autocomplete_lists_the_current_admin_guilds_channels():
    admin_guild = _make_guild(
        ADMIN_GUILD_ID,
        ADMIN_GUILD_NAME,
        [_make_channel(EXISTING_CHANNEL_ID, EXISTING_CHANNEL_NAME)],
    )
    other_guild = _make_guild(OTHER_GUILD_ID, "somewhere else", [_make_channel("1", "general")])
    with (
        mock.patch.object(config, "bot", _make_bot([other_guild, admin_guild])),
        mock.patch.object(config, "ADMIN_GUILD_ID", ADMIN_GUILD_ID),
    ):
        choices = await main_module.admin_channel_only_autocomplete(None, "")
    assert [choice.value for choice in choices] == [EXISTING_CHANNEL_ID]


async def test_autocomplete_is_empty_without_a_reachable_admin_guild():
    with (
        mock.patch.object(config, "bot", _make_bot([])),
        mock.patch.object(config, "ADMIN_GUILD_ID", ADMIN_GUILD_ID),
    ):
        assert await main_module.admin_channel_only_autocomplete(None, "") == []
