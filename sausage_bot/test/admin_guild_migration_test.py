#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
The `admin_guild` table gained a `guild_channel` column, but nothing
ever migrated the installations that already had the table.

`prep_table()` is a `CREATE TABLE IF NOT EXISTS`, so an existing
two-column table is left exactly as it was, and the three-value insert
in `_persist_admin_guild()` then dies with

    table admin_guild has 2 columns but 3 values were supplied

which leaves the bot with no stored admin guild at all. Every schema
that is prepped in a cog runs `add_missing_db_setup()` right after
`prep_table()` for exactly this reason; `admin_guild` is prepped in
__main__.py and never did.
"""

import sqlite3

from sausage_bot.util import envs, db_helper

GUILD_ID = "1000877858421477398"
GUILD_NAME = "sausage-bot"
CHANNEL_ID = "1531776650079899899"

OLD_TABLE = (
    "CREATE TABLE admin_guild ("
    "guild_id TEXT NOT NULL UNIQUE, guild_name TEXT, PRIMARY KEY(guild_id))"
)


def _make_old_table(guild_db_root, rows=()):
    "The table as it was before `guild_channel` was added to the schema"
    db_file = guild_db_root / "guilds.sqlite"
    con = sqlite3.connect(db_file)
    con.execute(OLD_TABLE)
    con.executemany("INSERT INTO admin_guild VALUES (?, ?)", rows)
    con.commit()
    con.close()
    return db_file


def _columns(db_file):
    con = sqlite3.connect(db_file)
    cols = [row[1] for row in con.execute("PRAGMA table_info(admin_guild)")]
    con.close()
    return cols


async def test_the_channel_column_is_added_to_an_old_table(guild_db_root):
    db_file = _make_old_table(guild_db_root)

    await db_helper.ensure_admin_guild_table()

    assert "guild_channel" in _columns(db_file)


async def test_a_three_value_insert_works_after_the_migration(guild_db_root):
    "The insert `_persist_admin_guild()` makes must go through"
    _make_old_table(guild_db_root)

    await db_helper.ensure_admin_guild_table()
    written = await db_helper.insert_many_all(
        envs.admin_guild_db_schema,
        inserts=[(GUILD_ID, GUILD_NAME, CHANNEL_ID)],
    )

    assert written is not False
    row = await db_helper.get_output(envs.admin_guild_db_schema, single=True)
    assert row["guild_id"] == GUILD_ID
    assert row["guild_channel"] == CHANNEL_ID


async def test_an_existing_row_survives_the_migration(guild_db_root):
    "Adding a column must not cost the guild that is already registered"
    db_file = _make_old_table(guild_db_root, rows=[(GUILD_ID, GUILD_NAME)])

    await db_helper.ensure_admin_guild_table()

    con = sqlite3.connect(db_file)
    rows = con.execute("SELECT guild_id, guild_name, guild_channel FROM admin_guild")
    assert list(rows) == [(GUILD_ID, GUILD_NAME, None)]
    con.close()


async def test_a_missing_table_is_created_whole(guild_db_root):
    await db_helper.ensure_admin_guild_table()

    assert _columns(guild_db_root / "guilds.sqlite") == [
        "guild_id",
        "guild_name",
        "guild_channel",
    ]


async def test_the_migration_is_idempotent(guild_db_root):
    db_file = _make_old_table(guild_db_root, rows=[(GUILD_ID, GUILD_NAME)])

    await db_helper.ensure_admin_guild_table()
    await db_helper.ensure_admin_guild_table()

    assert _columns(db_file) == ["guild_id", "guild_name", "guild_channel"]
