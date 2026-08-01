#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration test for the per-guild gating check that all 5 shared
background posting loops (rss feeds/podcasts, youtube, stats,
barca_news, quotes autopost) now do on every tick: each loop is one
shared, always-running `discord.ext.tasks.Loop` object that iterates
every *approved* guild and, per guild, reads that guild's own
`envs.tasks_db_schema` row to decide whether to actually process it.

This exercises `cogs/youtube.py`'s `task_post_videos` as a
representative of the pattern (all 5 loops duplicate the same
query/if-skip shape - see the code review findings about that
duplication). It calls the loop's underlying coroutine directly
(`Loop.coro`, the plain async function `@tasks.loop` wraps) rather than
`.start()`ing the real scheduled loop, and spies on
`db_helper.guild_locale_context` (only ever entered *after* a guild
passes the gate) to observe which guilds were actually processed -
without needing a live Discord gateway connection or any network I/O
(a guild with no youtube-feeds table yet safely no-ops after the gate,
see `db_helper.get_output`'s `OperationalError` handling).
"""
from types import SimpleNamespace

from sausage_bot.util import envs, db_helper, config
from sausage_bot.cogs import youtube

GUILD_STARTED = 111111111111111111
GUILD_STOPPED = 222222222222222222
GUILD_MISSING_ROW = 333333333333333333


async def _seed_approved_guild(guild_id, name):
    await db_helper.insert_many_all(
        envs.guilds_db_schema,
        [(str(guild_id), name, "approved", "2026-01-01", None, None)],
    )


async def test_loop_processes_started_guild_and_skips_stopped_and_missing(
    guild_db_root, monkeypatch
):
    await db_helper.prep_table(envs.guilds_db_schema)
    await _seed_approved_guild(GUILD_STARTED, "Started Guild")
    await _seed_approved_guild(GUILD_STOPPED, "Stopped Guild")
    await _seed_approved_guild(GUILD_MISSING_ROW, "No Tasks Row Guild")

    await db_helper.ensure_guild_tasks_rows(GUILD_STARTED)
    await db_helper.update_fields(
        template_info=envs.tasks_db_schema,
        where=[("cog", "youtube"), ("task", "post_videos")],
        updates=("status", "started"),
        guild_id=GUILD_STARTED,
    )
    await db_helper.ensure_guild_tasks_rows(GUILD_STOPPED)
    # GUILD_MISSING_ROW: deliberately never seeded - simulates a guild
    # whose tasks row hasn't been created yet (must default to "stopped").

    fake_guilds = {
        GUILD_STARTED: SimpleNamespace(id=GUILD_STARTED, name="Started Guild"),
        GUILD_STOPPED: SimpleNamespace(id=GUILD_STOPPED, name="Stopped Guild"),
        GUILD_MISSING_ROW: SimpleNamespace(
            id=GUILD_MISSING_ROW, name="No Tasks Row Guild"
        ),
    }
    monkeypatch.setattr(config.bot, "get_guild", lambda gid: fake_guilds.get(gid))

    processed_guild_ids = []
    real_guild_locale_context = db_helper.guild_locale_context

    def _spy_guild_locale_context(guild_id):
        processed_guild_ids.append(guild_id)
        return real_guild_locale_context(guild_id)

    monkeypatch.setattr(db_helper, "guild_locale_context", _spy_guild_locale_context)

    await youtube.Youtube.task_post_videos.coro()

    assert processed_guild_ids == [GUILD_STARTED]


async def test_loop_skips_a_guild_not_in_bots_cache(guild_db_root, monkeypatch):
    """
    `config.bot.get_guild()` returning `None` (guild not in the
    gateway cache, e.g. bot briefly offline there) must be skipped
    before even reaching the tasks-row check, not raise.
    """
    await db_helper.prep_table(envs.guilds_db_schema)
    await _seed_approved_guild(GUILD_STARTED, "Uncached Guild")
    await db_helper.ensure_guild_tasks_rows(GUILD_STARTED)
    await db_helper.update_fields(
        template_info=envs.tasks_db_schema,
        where=[("cog", "youtube"), ("task", "post_videos")],
        updates=("status", "started"),
        guild_id=GUILD_STARTED,
    )
    monkeypatch.setattr(config.bot, "get_guild", lambda gid: None)

    # Must not raise
    await youtube.Youtube.task_post_videos.coro()
