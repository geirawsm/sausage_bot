#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for `register_guild()` in __main__.py - the function `on_guild_join`
calls to put a guild into the guild registry.

sausage_bot/__main__.py calls config.bot.run(...) at module level (no
`if __name__ == "__main__":` guard), so a plain import would try to
connect to Discord. config.bot.run is patched to a no-op for the
duration of the import below to avoid that.

The regression these guard: the admin guild check only covered guilds
the registry had never seen. A guild the bot had been removed from was
reset to `pending` unconditionally, so removing the bot from the admin
guild and adding it back left the admin guild itself waiting for
approval - with no approved guild to run `/approve-guild` from, and no
task rows, its own posting cogs stayed inactive.
"""

from types import SimpleNamespace
from unittest import mock

from sausage_bot.util import config

with mock.patch.object(config.bot, "run", lambda *args, **kwargs: None):
    from sausage_bot import __main__ as main_module

ADMIN_GUILD_ID = "111"
ADMIN_GUILD_NAME = "sausage-bot"
OTHER_GUILD_ID = "868902121834176513"
OTHER_GUILD_NAME = "Gutteklubben Ugrei"


def _make_guild(guild_id, name):
    "A guild stand-in - register_guild only reads id and name"
    return SimpleNamespace(id=int(guild_id), name=name, member_count=3)


def _make_row(guild_id, guild_name, status):
    return {
        "guild_id": guild_id,
        "guild_name": guild_name,
        "status": status,
        "joined_at": "2020-01-01T00:00:00",
        "approved_by": None,
        "approved_at": None,
    }


async def _register(guild, row):
    """
    Run `register_guild()` against a registry holding a single `row`
    (None for a guild that has never been seen) and hand back the
    patched calls it made.

    `get_output` serves two callers with different shapes here:
    `register_guild()` asks for `single=True` and gets the row itself,
    `resolve_guild_row()` (via `_approve_admin_guild()`) asks for the
    whole table and gets a list.
    """
    rows = [] if row is None else [row]

    async def get_output(*args, **kwargs):
        return row if kwargs.get("single") else rows

    notify = mock.AsyncMock()
    with (
        mock.patch.object(config, "ADMIN_GUILD_ID", ADMIN_GUILD_ID),
        mock.patch.object(config, "BOT_ID", "botbotbot"),
        mock.patch.object(main_module.db_helper, "get_output", get_output),
        mock.patch.object(main_module.db_helper, "prep_table", mock.AsyncMock()),
        mock.patch.object(main_module.db_helper, "update_fields", mock.AsyncMock()),
        mock.patch.object(
            main_module.db_helper, "insert_many_some", mock.AsyncMock()
        ),
        mock.patch.object(
            main_module.db_helper, "ensure_guild_tasks_rows", mock.AsyncMock()
        ),
        mock.patch.object(
            main_module, "get_dt", mock.AsyncMock(return_value="2024-05-05T10:00:00")
        ),
        mock.patch.object(main_module, "notify_admin_of_new_guild", notify),
    ):
        await main_module.register_guild(guild)
        return SimpleNamespace(
            update_fields=main_module.db_helper.update_fields,
            insert_many_some=main_module.db_helper.insert_many_some,
            ensure_guild_tasks_rows=main_module.db_helper.ensure_guild_tasks_rows,
            notify=notify,
        )


def _status_written(update_fields):
    "Pull the status value out of whatever shape update_fields was given"
    updates = update_fields.await_args.kwargs["updates"]
    if isinstance(updates, tuple):
        updates = [updates]
    return dict(updates)["status"]


# --- the admin guild coming back ---


async def test_admin_guild_is_approved_again_when_the_bot_rejoins():
    guild = _make_guild(ADMIN_GUILD_ID, ADMIN_GUILD_NAME)
    row = _make_row(ADMIN_GUILD_ID, ADMIN_GUILD_NAME, "removed")
    db = await _register(guild, row)
    assert db.update_fields.await_args.kwargs["where"] == ("guild_id", ADMIN_GUILD_ID)
    assert _status_written(db.update_fields) == "approved"


async def test_rejoined_admin_guild_gets_its_task_rows_back():
    # Without these the admin guild's own posting cogs stay inactive
    guild = _make_guild(ADMIN_GUILD_ID, ADMIN_GUILD_NAME)
    row = _make_row(ADMIN_GUILD_ID, ADMIN_GUILD_NAME, "removed")
    db = await _register(guild, row)
    db.ensure_guild_tasks_rows.assert_awaited_once_with(guild.id)


async def test_rejoined_admin_guild_is_not_asked_to_approve_itself():
    guild = _make_guild(ADMIN_GUILD_ID, ADMIN_GUILD_NAME)
    row = _make_row(ADMIN_GUILD_ID, ADMIN_GUILD_NAME, "removed")
    db = await _register(guild, row)
    assert db.notify.await_args.kwargs["auto_approved"] is True
    assert db.notify.await_args.kwargs["rejoined"] is True


async def test_a_pending_admin_guild_is_promoted_to_approved():
    # A row left over from before this guild became the admin guild
    guild = _make_guild(ADMIN_GUILD_ID, ADMIN_GUILD_NAME)
    row = _make_row(ADMIN_GUILD_ID, ADMIN_GUILD_NAME, "pending")
    db = await _register(guild, row)
    assert _status_written(db.update_fields) == "approved"
    assert db.notify.await_args.kwargs["rejoined"] is False


async def test_an_already_approved_admin_guild_is_left_alone():
    guild = _make_guild(ADMIN_GUILD_ID, ADMIN_GUILD_NAME)
    row = _make_row(ADMIN_GUILD_ID, ADMIN_GUILD_NAME, "approved")
    db = await _register(guild, row)
    db.update_fields.assert_not_awaited()
    db.notify.assert_not_awaited()


async def test_a_brand_new_admin_guild_is_still_inserted_as_approved():
    guild = _make_guild(ADMIN_GUILD_ID, ADMIN_GUILD_NAME)
    db = await _register(guild, None)
    inserts = db.insert_many_some.await_args.kwargs["inserts"]
    assert inserts[0][2] == "approved"
    db.ensure_guild_tasks_rows.assert_awaited_once_with(guild.id)


# --- ordinary guilds are unaffected ---


async def test_an_ordinary_guild_rejoining_still_goes_back_to_pending():
    guild = _make_guild(OTHER_GUILD_ID, OTHER_GUILD_NAME)
    row = _make_row(OTHER_GUILD_ID, OTHER_GUILD_NAME, "removed")
    db = await _register(guild, row)
    assert _status_written(db.update_fields) == "pending"
    db.ensure_guild_tasks_rows.assert_not_awaited()
    assert db.notify.await_args.kwargs["rejoined"] is True
    assert "auto_approved" not in db.notify.await_args.kwargs


async def test_an_approved_ordinary_guild_keeps_its_approval():
    guild = _make_guild(OTHER_GUILD_ID, OTHER_GUILD_NAME)
    row = _make_row(OTHER_GUILD_ID, OTHER_GUILD_NAME, "approved")
    db = await _register(guild, row)
    db.update_fields.assert_not_awaited()
    db.notify.assert_not_awaited()


async def test_a_brand_new_ordinary_guild_is_inserted_as_pending():
    guild = _make_guild(OTHER_GUILD_ID, OTHER_GUILD_NAME)
    db = await _register(guild, None)
    inserts = db.insert_many_some.await_args.kwargs["inserts"]
    assert inserts[0][2] == "pending"
    db.ensure_guild_tasks_rows.assert_not_awaited()


# --- what the admin channel is told ---


async def test_the_auto_approved_notification_drops_the_approve_instruction():
    guild = SimpleNamespace(
        id=int(ADMIN_GUILD_ID),
        name=ADMIN_GUILD_NAME,
        member_count=3,
        description=None,
        vanity_url_code=None,
        text_channels=[],
        me=None,
    )
    post = mock.AsyncMock()
    with (
        mock.patch.object(config, "ADMIN_CHANNEL_ID", "999"),
        mock.patch.object(main_module.discord_commands, "post_to_channel", post),
    ):
        await main_module.notify_admin_of_new_guild(
            guild, rejoined=True, auto_approved=True
        )
    content = post.await_args.kwargs["content_in"]
    assert "/approve-guild" not in content
    assert ADMIN_GUILD_NAME in content
