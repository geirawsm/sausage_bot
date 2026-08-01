#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for `db_helper.ensure_guild_tasks_rows()` and the guild-scoped
`envs.tasks_db_schema` it seeds - the per-guild table that tracks
"started"/"stopped" for each background posting task (rss feeds/
podcasts, youtube, stats, barca_news, quotes autopost).

All tests use the `guild_db_root` fixture (see conftest.py), which points
`envs.DB_DIR` at a throwaway tmp_path directory - nothing here touches
real bot data.
"""
from sausage_bot.util import envs, db_helper

GUILD_A = 111111111111111111
GUILD_B = 222222222222222222

EXPECTED_DEFAULT_PAIRS = {
    ("rss", "post_feeds"),
    ("rss", "post_podcasts"),
    ("youtube", "post_videos"),
    ("stats", "post_stats"),
    ("barca_news", "post_news"),
    ("quotes", "autopost"),
}


async def test_ensure_guild_tasks_rows_seeds_six_stopped_default_rows(guild_db_root):
    await db_helper.ensure_guild_tasks_rows(GUILD_A)

    rows = await db_helper.get_output(envs.tasks_db_schema, guild_id=GUILD_A)

    assert len(rows) == 6
    assert {(row["cog"], row["task"]) for row in rows} == EXPECTED_DEFAULT_PAIRS
    assert all(row["status"] == "stopped" for row in rows)


async def test_ensure_guild_tasks_rows_is_idempotent(guild_db_root):
    await db_helper.ensure_guild_tasks_rows(GUILD_A)
    await db_helper.ensure_guild_tasks_rows(GUILD_A)
    await db_helper.ensure_guild_tasks_rows(GUILD_A)

    rows = await db_helper.get_output(envs.tasks_db_schema, guild_id=GUILD_A)

    assert len(rows) == 6


async def test_ensure_guild_tasks_rows_does_not_touch_flipped_status(guild_db_root):
    """
    Re-running `ensure_guild_tasks_rows()` (e.g. because the cog reloads,
    or a new guild is approved while this one is already known) must
    never reset a guild's own choice back to "stopped".
    """
    await db_helper.ensure_guild_tasks_rows(GUILD_A)
    await db_helper.update_fields(
        template_info=envs.tasks_db_schema,
        where=[("cog", "youtube"), ("task", "post_videos")],
        updates=("status", "started"),
        guild_id=GUILD_A,
    )

    await db_helper.ensure_guild_tasks_rows(GUILD_A)

    rows = await db_helper.get_output(
        template_info=envs.tasks_db_schema,
        where=[("cog", "youtube"), ("task", "post_videos")],
        guild_id=GUILD_A,
    )
    assert len(rows) == 1
    assert rows[0]["status"] == "started"


async def test_ensure_guild_tasks_rows_only_adds_missing_pairs(guild_db_root):
    """
    If a guild already has some (but not all) of the canonical rows -
    e.g. because it was seeded by an older codebase version with fewer
    tasks - a re-run should only backfill the missing ones, not touch
    what is already there.
    """
    await db_helper.prep_table(envs.tasks_db_schema, guild_id=GUILD_A)
    await db_helper.insert_many_all(
        template_info=envs.tasks_db_schema,
        inserts=[("rss", "post_feeds", "started")],
        guild_id=GUILD_A,
    )

    await db_helper.ensure_guild_tasks_rows(GUILD_A)

    rows = await db_helper.get_output(envs.tasks_db_schema, guild_id=GUILD_A)
    assert len(rows) == 6
    pairs_to_status = {(row["cog"], row["task"]): row["status"] for row in rows}
    assert pairs_to_status[("rss", "post_feeds")] == "started"
    assert pairs_to_status[("youtube", "post_videos")] == "stopped"


async def test_ensure_guild_tasks_rows_is_isolated_per_guild(guild_db_root):
    await db_helper.ensure_guild_tasks_rows(GUILD_A)
    await db_helper.update_fields(
        template_info=envs.tasks_db_schema,
        where=[("cog", "quotes"), ("task", "autopost")],
        updates=("status", "started"),
        guild_id=GUILD_A,
    )
    await db_helper.ensure_guild_tasks_rows(GUILD_B)

    rows_b = await db_helper.get_output(
        template_info=envs.tasks_db_schema,
        where=[("cog", "quotes"), ("task", "autopost")],
        guild_id=GUILD_B,
    )
    assert rows_b[0]["status"] == "stopped"


async def test_missing_task_row_reads_as_stopped_not_a_crash(guild_db_root):
    """
    Every loop's gating check does the same
    `get_output(..., single=True, guild_id=guild.id).get("status") !=
    "started"` query. A guild that has never had `ensure_guild_tasks_rows`
    run for it (its tasks table/row does not exist yet) must be treated
    as opted-out, not raise.
    """
    task_status = await db_helper.get_output(
        template_info=envs.tasks_db_schema,
        where=[("cog", "youtube"), ("task", "post_videos")],
        select=("status"),
        single=True,
        guild_id=GUILD_A,
    )
    assert task_status == {}
    assert task_status.get("status") != "started"

    # Table exists (guild is known) but this particular (cog, task) row
    # was never inserted (e.g. an older, shorter list of default tasks).
    await db_helper.prep_table(envs.tasks_db_schema, guild_id=GUILD_B)
    task_status = await db_helper.get_output(
        template_info=envs.tasks_db_schema,
        where=[("cog", "youtube"), ("task", "post_videos")],
        select=("status"),
        single=True,
        guild_id=GUILD_B,
    )
    assert task_status == {}
    assert task_status.get("status") != "started"
