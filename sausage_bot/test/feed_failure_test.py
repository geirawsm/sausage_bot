#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the two-phase failure count that keeps a feed alive through a
bad patch at the source.

What these guard: a single non-200 reply used to set `status_url` to
`Failed` on the spot, and the posting query only ever selects `OK`, so
the feed was gone for good. Youtube answers 404 and 500 while it
throttles, and on 2026-08-22 that took out all 38 feeds in one guild
inside an hour - 26 of them on a 404.

    OK --3 errors--> Failed --3 errors--> Stale
    every 10 min     every 6 h           left alone
"""

from types import SimpleNamespace

import pytest

from sausage_bot.util import envs, config, db_helper, feeds_core

GUILD_ID = 444444444444444444
UUID = "11111111-2222-3333-4444-555555555555"
FEED_NAME = "FearlessRecords"
CHANNEL = "1022791150047858728"


@pytest.fixture
def guild(guild_db_root, monkeypatch):
    """A guild whose bot-channel messages are collected instead of sent."""
    posted = []

    async def _collect(guild_in, content):
        posted.append(content)

    monkeypatch.setattr(feeds_core.discord_commands, "log_to_bot_channel", _collect)
    return SimpleNamespace(id=GUILD_ID, name="Dissonance", posted=posted)


async def _seed_feed(status=envs.FEEDS_URL_SUCCESS, counter=0):
    await db_helper.prep_table(envs.youtube_db_schema, guild_id=GUILD_ID)
    await db_helper.insert_many_some(
        envs.youtube_db_schema,
        rows=(
            "uuid",
            "feed_name",
            "url",
            "channel",
            "status_url",
            "status_url_counter",
            "status_channel",
            "youtube_id",
        ),
        inserts=[
            (
                UUID,
                FEED_NAME,
                "https://www.youtube.com/@FearlessRecords",
                CHANNEL,
                status,
                counter,
                envs.CHANNEL_STATUS_SUCCESS,
                "UCST_KTjlK574mzXHDan7-_Q",
            )
        ],
        guild_id=GUILD_ID,
    )


async def _read_feed():
    return await db_helper.get_output(
        template_info=envs.youtube_db_schema,
        where=("uuid", UUID),
        single=True,
        guild_id=GUILD_ID,
    )


async def _fail(guild, times=1, status=500):
    for _ in range(times):
        feed = await _read_feed()
        await feeds_core.reg_feed_error(envs.youtube_db_schema, feed, guild, status)


async def test_one_error_only_counts(guild):
    # Regression: this used to disable the feed outright.
    await _seed_feed()
    await _fail(guild)
    feed = await _read_feed()
    assert feed["status_url"] == envs.FEEDS_URL_SUCCESS
    assert feed["status_url_counter"] == 1
    assert guild.posted == []


async def test_a_404_counts_like_any_other_error(guild):
    # Youtube served 404 for 26 live channels while throttling, so a 404
    # is no proof the channel is gone.
    await _seed_feed()
    await _fail(guild, times=2, status=404)
    feed = await _read_feed()
    assert feed["status_url"] == envs.FEEDS_URL_SUCCESS
    assert feed["status_url_counter"] == 2


async def test_the_third_error_deactivates_the_feed(guild):
    await _seed_feed()
    await _fail(guild, times=envs.FEEDS_URL_ERROR_LIMIT)
    feed = await _read_feed()
    assert feed["status_url"] == envs.FEEDS_URL_ERROR
    # Reset, so the retry phase gets a full count of its own
    assert feed["status_url_counter"] == 0
    assert len(guild.posted) == 1
    assert FEED_NAME in guild.posted[0]


async def test_a_success_clears_the_count(guild):
    await _seed_feed()
    await _fail(guild, times=2)
    feed = await _read_feed()
    await feeds_core.reg_feed_ok(envs.youtube_db_schema, feed, guild)
    feed = await _read_feed()
    assert feed["status_url"] == envs.FEEDS_URL_SUCCESS
    assert feed["status_url_counter"] == 0
    # Nothing was ever wrong from the guild's point of view
    assert guild.posted == []


async def test_a_null_counter_counts_as_zero(guild):
    # Rows migrated from the old json files never got the column filled.
    await _seed_feed(counter=None)
    await _fail(guild)
    feed = await _read_feed()
    assert feed["status_url_counter"] == 1


async def test_a_deactivated_feed_leaves_the_posting_query(guild):
    await _seed_feed(status=envs.FEEDS_URL_ERROR)
    posting = await db_helper.get_output(
        template_info=envs.youtube_db_schema,
        where=[
            ("status_url", envs.FEEDS_URL_SUCCESS),
            ("status_channel", envs.CHANNEL_STATUS_SUCCESS),
        ],
        guild_id=GUILD_ID,
    )
    assert posting == []


async def test_three_failed_retries_give_up(guild, monkeypatch):
    await _seed_feed(status=envs.FEEDS_URL_ERROR)

    async def _always_500(feed_type, feed_info, guild_id):
        return 500

    monkeypatch.setattr(feeds_core, "get_feed_links", _always_500)

    for _ in range(envs.FEEDS_URL_ERROR_LIMIT):
        await feeds_core.retry_failed("youtube", envs.youtube_db_schema, guild)

    feed = await _read_feed()
    assert feed["status_url"] == envs.FEEDS_URL_STALE
    assert feed["status_url_counter"] == 0
    assert len(guild.posted) == 1
    assert FEED_NAME in guild.posted[0]


async def test_a_stale_feed_is_left_alone(guild, monkeypatch):
    await _seed_feed(status=envs.FEEDS_URL_STALE)

    checked = []

    async def _spy(feed_type, feed_info, guild_id):
        checked.append(feed_info["feed_name"])
        return 500

    monkeypatch.setattr(feeds_core, "get_feed_links", _spy)
    await feeds_core.retry_failed("youtube", envs.youtube_db_schema, guild)

    assert checked == []
    assert guild.posted == []


async def test_a_successful_retry_revives_the_feed(guild, monkeypatch):
    await _seed_feed(status=envs.FEEDS_URL_ERROR, counter=2)

    async def _works(feed_type, feed_info, guild_id):
        return [{"title": "Some video", "link": "https://youtu.be/abc"}]

    monkeypatch.setattr(feeds_core, "get_feed_links", _works)
    await feeds_core.retry_failed("youtube", envs.youtube_db_schema, guild)

    feed = await _read_feed()
    assert feed["status_url"] == envs.FEEDS_URL_SUCCESS
    assert feed["status_url_counter"] == 0
    assert len(guild.posted) == 1
    assert FEED_NAME in guild.posted[0]


async def test_reset_url_errors_puts_feeds_back(guild):
    await _seed_feed(status=envs.FEEDS_URL_STALE, counter=2)
    reset = await feeds_core.reset_url_errors(envs.youtube_db_schema, guild)
    assert reset == [FEED_NAME]
    feed = await _read_feed()
    assert feed["status_url"] == envs.FEEDS_URL_SUCCESS
    assert feed["status_url_counter"] == 0


async def test_reset_url_errors_skips_healthy_feeds(guild):
    await _seed_feed()
    assert await feeds_core.reset_url_errors(envs.youtube_db_schema, guild) == []


async def _seed_approved_guild(task_status):
    await db_helper.prep_table(envs.guilds_db_schema)
    await db_helper.insert_many_all(
        envs.guilds_db_schema,
        [(str(GUILD_ID), "Dissonance", "approved", "2026-01-01", None, None)],
    )
    await db_helper.ensure_guild_tasks_rows(GUILD_ID)
    await db_helper.update_fields(
        template_info=envs.tasks_db_schema,
        where=[("cog", "youtube"), ("task", "post_videos")],
        updates=("status", task_status),
        guild_id=GUILD_ID,
    )


@pytest.mark.parametrize(
    "task_status, expect_retried",
    [("started", True), ("stopped", False)],
)
async def test_the_retry_loop_follows_the_posting_gate(
    guild, monkeypatch, task_status, expect_retried
):
    """
    The retry loop reads the `post_videos` row rather than one of its
    own - retrying feeds nobody is posting would only be bot channel
    noise.
    """
    from sausage_bot.cogs import youtube

    await _seed_approved_guild(task_status)
    await _seed_feed(status=envs.FEEDS_URL_ERROR)
    monkeypatch.setattr(config.bot, "get_guild", lambda gid: guild)

    retried = []

    async def _spy(feed_type, feed_db, guild_in, not_like=()):
        retried.append(guild_in.id)

    monkeypatch.setattr(youtube.feeds_core, "retry_failed", _spy)
    await youtube.Youtube.task_retry_failed.coro()

    assert bool(retried) is expect_retried
