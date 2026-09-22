#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Covers the guild language/timezone context for slash commands.

Background tasks wrap themselves in `db_helper.guild_locale_context()`,
but interactions had no such wrapper - every slash command ran on the
`guild_context` defaults (`en`/`UTC`), so scraped match times in
`/autoevent add` and event lists in `/autoevent list` were rendered in
UTC no matter what the guild had set.

`config.GuildContextTree.interaction_check()` now loads the guild's
settings before discord.py invokes the command, in the same asyncio Task,
so the contextvars stay set for the whole invocation.

Uses the `guild_db_root` fixture (see conftest.py) - nothing here touches
real bot data.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from sausage_bot.util import config, db_helper, discord_commands, envs
from sausage_bot.util import guild_context

GUILD_ID = 333333333333333333


async def _guild_with_settings(language="nb", tz="Europe/Oslo"):
    "Prep a settings table for GUILD_ID with `language` and `tz` set."
    await db_helper.prep_table(
        envs.settings_db_schema,
        inserts=envs.settings_db_schema["inserts"],
        guild_id=GUILD_ID,
    )
    for setting, value in (("language", language), ("timezone", tz)):
        await db_helper.update_fields(
            envs.settings_db_schema,
            where=("setting", setting),
            updates=[("value", value)],
            guild_id=GUILD_ID,
        )


def _tree():
    "A GuildContextTree on a stand-in client, no Discord connection needed."
    client = SimpleNamespace(
        http=None, _connection=SimpleNamespace(_command_tree=None)
    )
    return config.GuildContextTree(client)


@pytest.fixture
def fake_interaction():
    return SimpleNamespace(guild_id=GUILD_ID)


async def test_check_sets_guild_context(guild_db_root, fake_interaction):
    await _guild_with_settings()

    assert await _tree().interaction_check(fake_interaction) is True

    # Still set after the check returns: discord.py invokes the command
    # in this same Task, so the command callback sees the guild's values
    assert guild_context.current_guild_id.get() == GUILD_ID
    assert guild_context.current_locale.get() == "nb"
    assert guild_context.current_timezone.get() == "Europe/Oslo"


async def test_check_without_guild_keeps_defaults(guild_db_root):
    dm_interaction = SimpleNamespace(guild_id=None)

    assert await _tree().interaction_check(dm_interaction) is True

    assert guild_context.current_guild_id.get() is None
    assert guild_context.current_timezone.get() == "UTC"


async def test_check_never_blocks_command_on_db_error(
    guild_db_root, fake_interaction, monkeypatch
):
    async def _boom(*args, **kwargs):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(db_helper, "set_guild_context", _boom)

    assert await _tree().interaction_check(fake_interaction) is True


async def test_event_list_uses_guild_timezone(guild_db_root, fake_interaction):
    """
    `/autoevent list` renders event start times through `get_dt()`, which
    reads the guild context - 20:00 UTC is 22.00 in Europe/Oslo.
    """
    await _guild_with_settings()
    start = datetime(2026, 9, 22, 20, 0, tzinfo=timezone.utc)
    event = SimpleNamespace(
        id=1, name="Home - Away", start_time=start, user_count=3
    )
    guild = SimpleNamespace(
        scheduled_events=[event], get_scheduled_event=lambda _id: event
    )

    await _tree().interaction_check(fake_interaction)
    events = await discord_commands.get_scheduled_events(guild)

    start_text = list(events.values())[0]["start"]
    assert "22.00" in start_text
    assert "20.00" not in start_text
