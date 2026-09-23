#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exercises `roles.convert_roles_db_to_uuid()`: the conversion of a roles
database that is still keyed on `msg_id` over to `uuid`.

Every test builds an old-layout database by hand in the `guild_db_root`
tmp_path, so nothing here touches real bot data.
"""
import sqlite3
from types import SimpleNamespace

from sausage_bot.util import envs, db_helper
from sausage_bot.cogs import roles

GUILD_ID = 333333333333333333


def _guild():
    return SimpleNamespace(id=GUILD_ID, name="testguild")


def _old_db(guild_db_root):
    """Build a roles.sqlite in the layout the bot used before uuid."""
    db_dir = envs.guild_db_dir(GUILD_ID)
    db_dir.mkdir(parents=True, exist_ok=True)
    db_file = db_dir / "roles.sqlite"
    con = sqlite3.connect(db_file)
    con.execute(
        "CREATE TABLE messages (msg_id TEXT, channel TEXT, name TEXT,"
        " header TEXT, content TEXT, description TEXT, msg_order INTEGER,"
        " PRIMARY KEY(msg_id))"
    )
    con.execute(
        "CREATE TABLE roles (msg_id TEXT NOT NULL, role TEXT, emoji TEXT)"
    )
    con.execute("CREATE TABLE settings (setting TEXT NOT NULL, value TEXT)")
    con.executemany(
        "INSERT INTO messages VALUES (?,?,?,?,?,?,?)",
        [
            ("111", "999", "farger", "Farger", "Velg farge", "d1", 1),
            ("222", "999", "lag", None, "Velg lag", "d2", 2),
        ],
    )
    con.executemany(
        "INSERT INTO roles VALUES (?,?,?)",
        [
            ("111", "1001", "\U0001F534"),
            ("111", "1002", "1234567890"),
            ("222", "2001", "⚽"),
            ("333", "3001", "\U0001F47B"),  # orphan - no such message
        ],
    )
    con.execute("INSERT INTO settings VALUES ('unique', '4001')")
    con.commit()
    con.close()
    return db_file


async def test_conversion_moves_both_tables_to_uuid(guild_db_root):
    _old_db(guild_db_root)

    assert await roles.convert_roles_db_to_uuid(_guild()) is True

    msgs_cols = await db_helper.list_cols(envs.roles_db_msgs_schema, GUILD_ID)
    roles_cols = await db_helper.list_cols(envs.roles_db_roles_schema, GUILD_ID)
    assert msgs_cols == [item[0] for item in envs.roles_db_msgs_schema["items"]]
    assert roles_cols == [item[0] for item in envs.roles_db_roles_schema["items"]]
    assert "msg_id" not in roles_cols


async def test_every_message_gets_a_uuid_written_to_the_db(guild_db_root):
    _old_db(guild_db_root)
    await roles.convert_roles_db_to_uuid(_guild())

    db_msgs = await db_helper.get_output(
        envs.roles_db_msgs_schema, select=("uuid", "msg_id", "name"),
        guild_id=GUILD_ID,
    )
    assert len(db_msgs) == 2
    uuids = [msg["uuid"] for msg in db_msgs]
    assert all(uuid and len(uuid) == 36 for uuid in uuids)
    assert len(set(uuids)) == 2, "each message must get its own uuid"


async def test_reaction_roles_follow_their_message(guild_db_root):
    _old_db(guild_db_root)
    await roles.convert_roles_db_to_uuid(_guild())

    joined = await db_helper.get_combined_output(
        envs.roles_db_msgs_schema,
        envs.roles_db_roles_schema,
        key="uuid",
        select=["name", "A.msg_id", "role", "emoji"],
        guild_id=GUILD_ID,
    )
    by_name = {}
    for row in joined:
        by_name.setdefault(row["name"], []).append(row["role"])
    assert sorted(by_name["farger"]) == ["1001", "1002"]
    assert by_name["lag"] == ["2001"]


async def test_orphaned_reaction_roles_are_dropped(guild_db_root):
    _old_db(guild_db_root)
    await roles.convert_roles_db_to_uuid(_guild())

    db_roles = await db_helper.get_output(
        envs.roles_db_roles_schema, guild_id=GUILD_ID
    )
    assert len(db_roles) == 3
    assert all(role["uuid"] for role in db_roles)
    assert "3001" not in [role["role"] for role in db_roles]


async def test_primary_key_moves_to_uuid(guild_db_root):
    db_file = _old_db(guild_db_root)
    await roles.convert_roles_db_to_uuid(_guild())

    con = sqlite3.connect(db_file)
    schema = con.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'messages'"
    ).fetchone()[0]
    con.close()
    assert "PRIMARY KEY(uuid)" in schema


async def test_settings_table_is_left_alone(guild_db_root):
    _old_db(guild_db_root)
    await roles.convert_roles_db_to_uuid(_guild())

    settings = await db_helper.get_output(
        envs.roles_db_settings_schema, guild_id=GUILD_ID
    )
    assert settings == [{"setting": "unique", "value": "4001"}]


async def test_conversion_is_idempotent(guild_db_root):
    _old_db(guild_db_root)
    assert await roles.convert_roles_db_to_uuid(_guild()) is True
    before = await db_helper.get_output(
        envs.roles_db_msgs_schema, select=("uuid", "msg_id"), guild_id=GUILD_ID
    )
    # A second pass must find nothing to do and must not re-roll the uuids
    assert await roles.convert_roles_db_to_uuid(_guild()) is False
    after = await db_helper.get_output(
        envs.roles_db_msgs_schema, select=("uuid", "msg_id"), guild_id=GUILD_ID
    )
    assert before == after


async def test_fresh_tables_need_no_conversion(guild_db_root):
    await db_helper.prep_table(envs.roles_db_msgs_schema, guild_id=GUILD_ID)
    await db_helper.prep_table(envs.roles_db_roles_schema, guild_id=GUILD_ID)

    assert await roles.convert_roles_db_to_uuid(_guild()) is False


async def test_missing_database_is_not_converted(guild_db_root):
    assert await roles.convert_roles_db_to_uuid(_guild()) is False


async def test_inserts_land_in_the_right_columns_after_conversion(guild_db_root):
    """
    `insert_many_all` inserts by position, so a converted table must hold
    its columns in the order the schema in `envs` states.
    """
    _old_db(guild_db_root)
    await roles.convert_roles_db_to_uuid(_guild())

    await db_helper.insert_many_all(
        envs.roles_db_msgs_schema,
        inserts=[("new-uuid", "444", "999", "nytt", "H", "Tekst", "desc", 3)],
        guild_id=GUILD_ID,
    )
    await db_helper.insert_many_all(
        envs.roles_db_roles_schema,
        inserts=[("new-uuid", "4001", "\U0001F600")],
        guild_id=GUILD_ID,
    )
    msg = await db_helper.get_output(
        envs.roles_db_msgs_schema,
        where=[("uuid", "new-uuid")],
        single=True,
        guild_id=GUILD_ID,
    )
    assert msg["msg_id"] == "444"
    assert msg["name"] == "nytt"
    assert msg["msg_order"] == 3
    role = await db_helper.get_output(
        envs.roles_db_roles_schema,
        where=[("uuid", "new-uuid")],
        single=True,
        guild_id=GUILD_ID,
    )
    assert role["role"] == "4001"
