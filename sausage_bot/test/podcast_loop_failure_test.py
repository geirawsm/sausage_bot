#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regression test for 2026-10-23 20:46, when a Spotify connection reset made
`check_for_new_spotify_podcast_episodes` return `False`. `task_post_podcasts`
then did `len(False)`, raised `TypeError`, and discord.py stopped the loop
for good: no podcast was posted again until the bot was restarted.
"""
from types import SimpleNamespace

from sausage_bot.util import envs, db_helper, config, net_io
from sausage_bot.cogs import rss

GUILD_ID = 111111111111111111


async def _seed_started_guild():
    await db_helper.prep_table(envs.guilds_db_schema)
    await db_helper.insert_many_all(
        envs.guilds_db_schema,
        [(str(GUILD_ID), "Norsk Fotball", "approved", "2026-01-01", None, None)],
    )
    await db_helper.ensure_guild_tasks_rows(GUILD_ID)
    await db_helper.update_fields(
        template_info=envs.tasks_db_schema,
        where=[("cog", "rss"), ("task", "post_podcasts")],
        updates=("status", "started"),
        guild_id=GUILD_ID,
    )


async def test_a_failed_spotify_check_does_not_crash_the_loop(
    guild_db_root, monkeypatch
):
    await _seed_started_guild()
    guild = SimpleNamespace(id=GUILD_ID, name="Norsk Fotball")
    monkeypatch.setattr(config.bot, "get_guild", lambda gid: guild)

    async def _spotify_failed(guild_in):
        return False

    other_podcasts_checked = []

    async def _no_other_podcasts(guild_in):
        other_podcasts_checked.append(guild_in.id)
        return {}

    monkeypatch.setattr(
        net_io, "check_for_new_spotify_podcast_episodes", _spotify_failed
    )
    monkeypatch.setattr(net_io, "check_other_podcast_episodes", _no_other_podcasts)

    await rss.RSSfeed.task_post_podcasts.coro()

    # Non-Spotify podcasts must still be handled when Spotify is down
    assert other_podcasts_checked == [GUILD_ID]


async def test_the_loop_restarts_itself_after_an_unhandled_error(monkeypatch):
    restarted = []
    monkeypatch.setattr(
        rss.RSSfeed.task_post_podcasts, "restart", lambda: restarted.append(True)
    )

    await rss.RSSfeed.task_post_podcasts._error(RuntimeError("boom"))

    assert restarted == [True]
