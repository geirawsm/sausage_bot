#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exercises `roles.sync_reaction_message_from_settings()` and the backup
`roles.convert_roles_db_to_uuid()` takes before it drops reaction roles.

The discord message is a stand-in that records what `edit` got, so
nothing here talks to discord.
"""
import sqlite3
from types import SimpleNamespace

import pytest

from sausage_bot.util import envs, db_helper, discord_commands
from sausage_bot.cogs import roles

from sausage_bot.test.roles_uuid_conversion_test import _old_db

GUILD_ID = 333333333333333333
MSG_UUID = "0b7c7f4e-2f7a-4d3c-9d7e-3c1f0a6b2e11"


class FakeMsg:
    def __init__(self):
        self.edits = []

    async def clear_reactions(self):
        return

    async def add_reaction(self, emoji):
        return

    async def edit(self, **kwargs):
        self.edits.append(kwargs)


def _guild():
    return SimpleNamespace(id=GUILD_ID, name="testguild", roles=[], emojis=[])


async def _sync(monkeypatch, header, content):
    """Store one reaction message without reaction roles, then sync it."""
    await db_helper.prep_table(envs.roles_db_msgs_schema, guild_id=GUILD_ID)
    await db_helper.prep_table(envs.roles_db_roles_schema, guild_id=GUILD_ID)
    await db_helper.insert_many_all(
        envs.roles_db_msgs_schema,
        inserts=[(MSG_UUID, "111", "999", "lag", header, content, "", 1)],
        guild_id=GUILD_ID,
    )
    msg = FakeMsg()

    async def _get_msg(**kwargs):
        return msg

    monkeypatch.setattr(discord_commands, "get_message_obj", _get_msg)
    await roles.sync_reaction_message_from_settings(MSG_UUID, guild=_guild())
    return msg.edits[-1]


async def test_sync_without_reaction_roles_sends_no_embed(
    guild_db_root, monkeypatch
):
    # Discord refuses an embed with an empty description (400, 50035)
    edit = await _sync(monkeypatch, "Eliteserien", "Velg lag")
    assert edit["embed"] is None


async def test_sync_puts_header_above_content(guild_db_root, monkeypatch):
    edit = await _sync(monkeypatch, "Eliteserien", "Velg lag")
    assert edit["content"] == "## Eliteserien\nVelg lag"


@pytest.mark.parametrize(
    "content", ["## Eliteserien", "## Eliteserien\nVelg lag"]
)
async def test_sync_does_not_repeat_header_already_in_content(
    guild_db_root, monkeypatch, content
):
    edit = await _sync(monkeypatch, "Eliteserien", content)
    assert edit["content"] == content


async def test_conversion_backs_up_db_before_dropping_roles(guild_db_root):
    db_file = _old_db(guild_db_root)
    await roles.convert_roles_db_to_uuid(SimpleNamespace(id=GUILD_ID, name="g"))

    backup = db_file.with_name("roles.sqlite.pre-uuid.bak")
    assert backup.exists()
    con = sqlite3.connect(backup)
    orphan = con.execute("SELECT * FROM roles WHERE role = '3001'").fetchall()
    con.close()
    assert orphan == [("333", "3001", "\U0001F47B")]
