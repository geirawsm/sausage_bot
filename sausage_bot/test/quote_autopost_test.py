#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for quote autoposting.

Two halves:

1. The 5-minute window-match arithmetic that `cogs/quote.py`'s
   `autopost_for_guild()` uses to decide whether *this* tick is the one
   where a given guild's configured `autopost_time` should fire. The
   formula still lives inline (in a function that also touches
   Discord/DB), so it is mirrored here rather than imported - see the
   block computing `now_minutes`/`target_minutes` around the
   `(now_minutes - target_minutes) % (24 * 60) >= 5` check. Caveat:
   because it is duplicated rather than imported, this does not catch a
   regression if someone edits the inline formula without updating this
   mirror.

2. The multi-guild routing of `Quotes.task_autopost` itself: every guild
   that has autopost enabled must get its own post, in its own channel,
   and one guild failing must not stop the others. `task_autopost` is a
   shared `@tasks.loop` - as in `task_loop_gating_test.py`, the tests
   call its underlying coroutine (`Loop.coro`) directly rather than
   `.start()`ing the real scheduled loop, so no gateway connection or
   network I/O is needed.
"""
from datetime import datetime, time
from types import SimpleNamespace
import uuid as uuid_module

import pytest

from sausage_bot.util import config, db_helper, envs
from sausage_bot.cogs import quote

GUILD_A = 111111111111111111
GUILD_B = 222222222222222222

CHANNEL_A = 444444444444444444
CHANNEL_B = 555555555555555555
NEW_CHANNEL = 666666666666666666
DEAD_CHANNEL = 777777777777777777


def is_within_autopost_window(now_hour, now_minute, target_hour, target_minute):
    "Mirrors the (now_minutes - target_minutes) % (24 * 60) >= 5 check in quote.py"
    now_minutes = now_hour * 60 + now_minute
    target_minutes = target_hour * 60 + target_minute
    return (now_minutes - target_minutes) % (24 * 60) < 5


def test_exact_target_time_matches():
    assert is_within_autopost_window(9, 0, 9, 0) is True


def test_four_minutes_after_target_matches():
    assert is_within_autopost_window(9, 4, 9, 0) is True


def test_five_minutes_after_target_does_not_match():
    # 5 minutes is the loop's own polling interval - the *next* tick
    # should have caught this, not this one
    assert is_within_autopost_window(9, 5, 9, 0) is False


def test_one_minute_before_target_does_not_match():
    assert is_within_autopost_window(8, 59, 9, 0) is False


def test_window_wraps_correctly_around_midnight():
    assert is_within_autopost_window(0, 2, 23, 59) is True
    assert is_within_autopost_window(23, 58, 23, 59) is False


def test_default_autopost_time_of_noon_matches_at_noon():
    # cogs/quote.py falls back to "12:00:00" when a guild has no
    # `autopost_time` set yet
    default_target = time.fromisoformat("12:00:00")
    assert (
        is_within_autopost_window(12, 3, default_target.hour, default_target.minute)
        is True
    )


# --- multi-guild routing ------------------------------------------------


class FakeChannel:
    def __init__(self, channel_id, name):
        self.id = channel_id
        self.name = name


class FakeGuild:
    def __init__(self, guild_id, name, text_channels):
        self.id = guild_id
        self.name = name
        self.text_channels = text_channels

    def get_role(self, role_id):
        return None


async def _seed_guild(guild_id, name, channel_value, with_quote=True):
    "Register `guild_id` as approved, with quote autopost turned on"
    await db_helper.insert_many_all(
        envs.guilds_db_schema,
        [(str(guild_id), name, "approved", "2026-01-01", None, None)],
    )
    await db_helper.prep_table(
        envs.settings_db_schema,
        inserts=envs.settings_db_schema["inserts"],
        guild_id=guild_id,
    )
    await quote.ensure_guild_quote_tables(SimpleNamespace(id=guild_id))
    await db_helper.ensure_guild_tasks_rows(guild_id)
    await db_helper.update_fields(
        template_info=envs.tasks_db_schema,
        where=[("cog", "quotes"), ("task", "autopost")],
        updates=("status", "started"),
        guild_id=guild_id,
    )
    await db_helper.update_fields(
        template_info=envs.quote_db_settings_schema,
        where=[("setting", "channel")],
        updates=[("value", channel_value)],
        guild_id=guild_id,
    )
    await db_helper.update_fields(
        template_info=envs.quote_db_settings_schema,
        where=[("setting", "autopost_time")],
        updates=[("value", "12:00:00")],
        guild_id=guild_id,
    )
    if with_quote:
        await db_helper.insert_many_all(
            envs.quote_db_schema,
            [(str(uuid_module.uuid4()), CHANNEL_A, "general", "2026-01-01 10:00:00")],
            guild_id=guild_id,
        )


async def _stored_channel(guild_id):
    "Read back the `channel` setting for `guild_id`"
    row = await db_helper.get_output(
        template_info=envs.quote_db_settings_schema,
        select=("value"),
        where=[("setting", "channel")],
        single=True,
        guild_id=guild_id,
    )
    return row.get("value")


@pytest.fixture
def autopost_env(guild_db_root, monkeypatch):
    """
    Freeze the clock inside the autopost window, and swap out everything
    that would talk to Discord. Returns the recorders the tests assert on.
    """

    async def _fake_get_dt(*args, **kwargs):
        return datetime(2026, 1, 1, 12, 0, 0)

    monkeypatch.setattr(quote, "get_dt", _fake_get_dt)

    posted = []
    created = []
    logged = []

    async def _fake_post_random_quote(guild, autopost=None, channel=None, **kwargs):
        posted.append((guild.id, channel))

    async def _fake_create_missing_channel(guild, channel_name=None, **kwargs):
        created.append((guild.id, channel_name))
        channel = FakeChannel(NEW_CHANNEL, channel_name)
        guild.text_channels.append(channel)
        return channel

    async def _fake_log_to_bot_channel(guild, content_in=None):
        logged.append((guild.id, content_in))

    monkeypatch.setattr(quote, "post_random_quote", _fake_post_random_quote)
    monkeypatch.setattr(
        quote.discord_commands, "create_missing_channel", _fake_create_missing_channel
    )
    monkeypatch.setattr(
        quote.discord_commands, "log_to_bot_channel", _fake_log_to_bot_channel
    )
    return SimpleNamespace(posted=posted, created=created, logged=logged)


def _register_guilds(monkeypatch, *guilds):
    by_id = {guild.id: guild for guild in guilds}
    monkeypatch.setattr(config.bot, "get_guild", lambda gid: by_id.get(gid))


async def test_every_enabled_guild_gets_its_own_post(autopost_env, monkeypatch):
    """
    The whole point of the shared loop: two guilds with autopost enabled
    both get a quote, each in its own channel.
    """
    await db_helper.prep_table(envs.guilds_db_schema)
    await _seed_guild(GUILD_A, "Guild A", CHANNEL_A)
    await _seed_guild(GUILD_B, "Guild B", CHANNEL_B)
    _register_guilds(
        monkeypatch,
        FakeGuild(GUILD_A, "Guild A", [FakeChannel(CHANNEL_A, "quotes")]),
        FakeGuild(GUILD_B, "Guild B", [FakeChannel(CHANNEL_B, "sitater")]),
    )

    await quote.Quotes.task_autopost.coro()

    assert autopost_env.posted == [(GUILD_A, CHANNEL_A), (GUILD_B, CHANNEL_B)]
    # Both channels already existed, so nothing was created
    assert autopost_env.created == []


async def test_legacy_channel_name_is_resolved_and_persisted_as_an_id(
    autopost_env, monkeypatch
):
    """
    `quote_db_settings_schema` used to seed `channel` with the channel
    *name* "quotes", which every reader then fed to `int()` - the
    ValueError ended the loop for every guild. The name must now resolve
    to a real channel, and the id must be written back.
    """
    await db_helper.prep_table(envs.guilds_db_schema)
    await _seed_guild(GUILD_A, "Guild A", "quotes")
    _register_guilds(monkeypatch, FakeGuild(GUILD_A, "Guild A", []))

    await quote.Quotes.task_autopost.coro()

    assert autopost_env.created == [(GUILD_A, "quotes")]
    assert autopost_env.posted == [(GUILD_A, NEW_CHANNEL)]
    assert await _stored_channel(GUILD_A) == str(NEW_CHANNEL)


async def test_channel_id_pointing_at_a_deleted_channel_is_replaced(
    autopost_env, monkeypatch
):
    "A stored id whose channel is gone falls back to the `quotes` channel"
    await db_helper.prep_table(envs.guilds_db_schema)
    await _seed_guild(GUILD_A, "Guild A", DEAD_CHANNEL)
    _register_guilds(
        monkeypatch,
        FakeGuild(GUILD_A, "Guild A", [FakeChannel(CHANNEL_A, "quotes")]),
    )

    await quote.Quotes.task_autopost.coro()

    # The `quotes` channel is already there, so it is reused, not recreated
    assert autopost_env.created == []
    assert autopost_env.posted == [(GUILD_A, CHANNEL_A)]
    assert await _stored_channel(GUILD_A) == str(CHANNEL_A)


async def test_one_failing_guild_does_not_stop_the_others(autopost_env, monkeypatch):
    """
    An unhandled error used to end `task_autopost` for every guild until
    someone restarted the bot. It must now be reported to that guild's
    own bot channel and the loop must carry on.
    """
    await db_helper.prep_table(envs.guilds_db_schema)
    await _seed_guild(GUILD_A, "Guild A", CHANNEL_A)
    await _seed_guild(GUILD_B, "Guild B", CHANNEL_B)
    _register_guilds(
        monkeypatch,
        FakeGuild(GUILD_A, "Guild A", [FakeChannel(CHANNEL_A, "quotes")]),
        FakeGuild(GUILD_B, "Guild B", [FakeChannel(CHANNEL_B, "sitater")]),
    )

    async def _boom_for_guild_a(guild, autopost=None, channel=None, **kwargs):
        if guild.id == GUILD_A:
            raise RuntimeError("Missing Permissions")
        autopost_env.posted.append((guild.id, channel))

    monkeypatch.setattr(quote, "post_random_quote", _boom_for_guild_a)

    await quote.Quotes.task_autopost.coro()

    assert autopost_env.posted == [(GUILD_B, CHANNEL_B)]
    assert [guild_id for guild_id, _ in autopost_env.logged] == [GUILD_A]
    assert "Missing Permissions" in autopost_env.logged[0][1]


async def test_guild_without_quotes_is_stopped_and_gets_no_channel(
    autopost_env, monkeypatch
):
    """
    An empty quote db disables that guild's own task - and must not
    leave a freshly created `quotes` channel behind on the way out.
    """
    await db_helper.prep_table(envs.guilds_db_schema)
    await _seed_guild(GUILD_A, "Guild A", "quotes", with_quote=False)
    _register_guilds(monkeypatch, FakeGuild(GUILD_A, "Guild A", []))

    await quote.Quotes.task_autopost.coro()

    assert autopost_env.posted == []
    assert autopost_env.created == []
    task_status = await db_helper.get_output(
        template_info=envs.tasks_db_schema,
        where=[("cog", "quotes"), ("task", "autopost")],
        select=("status"),
        single=True,
        guild_id=GUILD_A,
    )
    assert task_status.get("status") == "stopped"
