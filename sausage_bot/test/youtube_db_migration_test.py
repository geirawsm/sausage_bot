#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Covers the move of the Youtube data out of `youtube_feeds.sqlite` and
`youtube_log.sqlite` and into a single `youtube.sqlite`.

The point of the migration is that nothing is silently lost on upgrade:
feeds and filters have to survive the file/table rename, and the post
log especially - an empty log makes `task_post_videos` treat every video
it finds as unposted and repost the lot.

Legacy databases are written here with plain sqlite3, the way an older
version of the bot would have left them, and `guild_db_root` (see
conftest.py) keeps every file in a throwaway directory.
"""

import sqlite3
from types import SimpleNamespace
from unittest import mock

from sausage_bot.cogs import youtube
from sausage_bot.util import envs, db_helper

GUILD_ID = 888888888888888888
UUID_A = "uuid-feed-a"
UUID_B = "uuid-feed-b"


def _make_guild():
    return SimpleNamespace(id=GUILD_ID, name="a guild")


def _write_legacy_feeds_db(db_dir):
    """
    `youtube_feeds.sqlite` as it looked before: the feed table named
    after the file, and the filters alongside it.
    """
    db_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_dir / youtube.LEGACY_FEEDS_DB_FILE)
    con.execute(
        "CREATE TABLE youtube_feeds ("
        "uuid TEXT NOT NULL, feed_name TEXT, url TEXT, channel TEXT, "
        "added TEXT, added_by TEXT, status_url TEXT, status_url_counter "
        "INTEGER, status_channel TEXT, youtube_id TEXT, playlist_id TEXT)"
    )
    con.executemany(
        "INSERT INTO youtube_feeds VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                UUID_A, "feed a", "https://y.t/a", "1111", "-", "someone",
                envs.FEEDS_URL_SUCCESS, 0, envs.CHANNEL_STATUS_SUCCESS,
                "chan-a", "playlist-a",
            ),
            (
                UUID_B, "feed b", "https://y.t/b", "2222", "-", "someone",
                envs.FEEDS_URL_SUCCESS, 0, envs.CHANNEL_STATUS_SUCCESS,
                "chan-b", "playlist-b",
            ),
        ],
    )
    con.execute(
        "CREATE TABLE filter (uuid TEXT NOT NULL, allow_or_deny TEXT NOT "
        "NULL, filter TEXT NOT NULL)"
    )
    con.executemany(
        "INSERT INTO filter VALUES (?, ?, ?)",
        [(UUID_A, "Deny", "shorts"), (UUID_B, "Allow", "let's play")],
    )
    con.commit()
    con.close()


def _write_legacy_log_db(db_dir):
    """
    `youtube_log.sqlite` as it looked before, `hash` column and all -
    the column is gone from the schema now and must not block the copy.
    """
    db_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_dir / youtube.LEGACY_LOG_DB_FILE)
    con.execute("CREATE TABLE log (uuid TEXT NOT NULL, url TEXT, date TEXT, hash TEXT)")
    con.executemany(
        "INSERT INTO log VALUES (?, ?, ?, ?)",
        [
            (UUID_A, "https://www.youtube.com/watch?v=aaa", "2025-01-01", "hash-a"),
            (UUID_A, "https://www.youtube.com/watch?v=bbb", "2025-01-02", "hash-b"),
            (UUID_B, "https://www.youtube.com/watch?v=ccc", "2025-01-03", "hash-c"),
        ],
    )
    con.commit()
    con.close()


async def _migrate(guild_db_root):
    """
    Run the whole table prep the cog does on startup, which is what
    calls the migration.
    """
    with mock.patch.object(
        youtube.db_helper, "db_channel_names_to_ids", mock.AsyncMock()
    ), mock.patch.object(
        youtube.discord_commands, "log_to_bot_channel", mock.AsyncMock()
    ):
        await youtube.ensure_guild_youtube_tables(_make_guild())


# ---------------------------------------------------------------------
# The happy path
# ---------------------------------------------------------------------


async def test_feeds_are_moved_to_the_new_database(guild_db_root):
    _write_legacy_feeds_db(envs.guild_db_dir(GUILD_ID))

    await _migrate(guild_db_root)

    feeds = await db_helper.get_output(envs.youtube_db_schema, guild_id=GUILD_ID)
    assert len(feeds) == 2
    by_name = {feed["feed_name"]: feed for feed in feeds}
    assert by_name["feed a"]["uuid"] == UUID_A
    assert by_name["feed a"]["playlist_id"] == "playlist-a"
    assert by_name["feed b"]["channel"] == "2222"


async def test_filters_are_moved_to_the_new_database(guild_db_root):
    _write_legacy_feeds_db(envs.guild_db_dir(GUILD_ID))

    await _migrate(guild_db_root)

    filters = await db_helper.get_output(
        envs.youtube_db_filter_schema, guild_id=GUILD_ID
    )
    assert len(filters) == 2
    # `allow_or_deny` comes out canonical - the legacy rows hold the
    # literal as the client sent it, which `normalize_filter_allow_deny`
    # rewrites on the way in
    assert (UUID_A, "deny", "shorts") in [
        (row["uuid"], row["allow_or_deny"], row["filter"]) for row in filters
    ]


async def test_the_post_log_is_moved_so_nothing_gets_reposted(guild_db_root):
    _write_legacy_log_db(envs.guild_db_dir(GUILD_ID))

    await _migrate(guild_db_root)

    logged = await db_helper.get_output(
        envs.youtube_db_log_schema, guild_id=GUILD_ID, select=("url"),
        single_col_results=True,
    )
    assert len(logged) == 3
    assert "https://www.youtube.com/watch?v=aaa" in logged


async def test_the_dropped_hash_column_does_not_block_the_copy(guild_db_root):
    "The old log had a `hash` column that is not in the schema anymore"
    _write_legacy_log_db(envs.guild_db_dir(GUILD_ID))

    await _migrate(guild_db_root)

    rows = await db_helper.get_output(envs.youtube_db_log_schema, guild_id=GUILD_ID)
    assert len(rows) == 3
    assert "hash" not in rows[0].keys()


# ---------------------------------------------------------------------
# Not losing data on the way, and not doing it twice
# ---------------------------------------------------------------------


async def test_the_legacy_databases_are_left_alone(guild_db_root):
    db_dir = envs.guild_db_dir(GUILD_ID)
    _write_legacy_feeds_db(db_dir)
    _write_legacy_log_db(db_dir)

    await _migrate(guild_db_root)

    assert (db_dir / youtube.LEGACY_FEEDS_DB_FILE).is_file()
    con = sqlite3.connect(db_dir / youtube.LEGACY_FEEDS_DB_FILE)
    assert con.execute("SELECT count(*) FROM youtube_feeds").fetchone()[0] == 2
    con.close()


async def test_running_twice_does_not_duplicate_rows(guild_db_root):
    db_dir = envs.guild_db_dir(GUILD_ID)
    _write_legacy_feeds_db(db_dir)
    _write_legacy_log_db(db_dir)

    await _migrate(guild_db_root)
    await _migrate(guild_db_root)

    feeds = await db_helper.get_output(envs.youtube_db_schema, guild_id=GUILD_ID)
    logged = await db_helper.get_output(envs.youtube_db_log_schema, guild_id=GUILD_ID)
    assert len(feeds) == 2
    assert len(logged) == 3


async def test_a_populated_new_database_is_not_touched(guild_db_root):
    """
    A guild that already runs the new layout keeps what it has - the
    legacy file must not be copied in on top of it.
    """
    _write_legacy_feeds_db(envs.guild_db_dir(GUILD_ID))
    await db_helper.prep_table(envs.youtube_db_schema, guild_id=GUILD_ID)
    await db_helper.insert_many_some(
        envs.youtube_db_schema,
        rows=("uuid", "feed_name", "url", "channel"),
        inserts=[("uuid-new", "a newer feed", "https://y.t/new", "3333")],
        guild_id=GUILD_ID,
    )

    await _migrate(guild_db_root)

    feeds = await db_helper.get_output(envs.youtube_db_schema, guild_id=GUILD_ID)
    assert len(feeds) == 1
    assert feeds[0]["feed_name"] == "a newer feed"


async def test_a_fresh_install_has_nothing_to_migrate(guild_db_root):
    "No legacy files at all - the tables are just created empty"
    await _migrate(guild_db_root)

    feeds = await db_helper.get_output(envs.youtube_db_schema, guild_id=GUILD_ID)
    assert feeds == []
