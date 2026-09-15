#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Covers that the Youtube API is never called from the event loop.

`googleapiclient` is synchronous: an `execute()` awaited straight from a
coroutine holds the bot until the request comes back, about half a
second per feed. A guild with 38 feeds blocked the loop for long enough
that discord.py warned `Shard ID None heartbeat blocked for more than 10
seconds` - and a gateway that gets no heartbeat drops the connection.

Every call goes through `youtube.api_call`, which hands it to a thread,
so the tests here check the thread the API is called from rather than
any output of it.

`guild_db_root` (see conftest.py) keeps every write in a throwaway
directory.
"""

import threading
from types import SimpleNamespace
from unittest import mock

import pytest

from sausage_bot.cogs import youtube
from sausage_bot.util import envs, db_helper, discord_commands

GUILD_ID = 999999999999999999
UUID_A = "uuid-feed-a"
CHANNEL_A = 1111

FEED_ROWS = (
    "uuid",
    "feed_name",
    "url",
    "channel",
    "added",
    "added_by",
    "status_url",
    "status_url_counter",
    "status_channel",
    "youtube_id",
    "playlist_id",
)


@pytest.fixture
def api_threads(monkeypatch):
    """
    Patch the Youtube API out and record which thread each call is made
    from. `main` is the thread the event loop runs in.
    """
    threads = []

    def _record(name, result):
        def _call(*args, **kwargs):
            threads.append((name, threading.current_thread()))
            return result

        return _call

    monkeypatch.setattr(
        youtube.YouTubeAPI, "get_latest_video_ids", _record("latest", [])
    )
    monkeypatch.setattr(youtube.YouTubeAPI, "get_video_info", _record("info", []))
    monkeypatch.setattr(
        youtube.YouTubeAPI,
        "extract_yt_channel_info",
        _record("channel", {"channel_id": "UC123", "playlist_id": "UU123"}),
    )
    monkeypatch.setattr(youtube.config, "YOUTUBE_API_KEY", "test-key")
    return threads


async def _prep_feed(playlist_id="playlist-a"):
    await db_helper.prep_table(envs.youtube_db_schema, guild_id=GUILD_ID)
    await db_helper.prep_table(envs.youtube_db_filter_schema, guild_id=GUILD_ID)
    await db_helper.prep_table(envs.youtube_db_log_schema, guild_id=GUILD_ID)
    await db_helper.insert_many_some(
        envs.youtube_db_schema,
        rows=FEED_ROWS,
        inserts=[
            (
                UUID_A,
                "feed a",
                "https://www.youtube.com/@somechannel",
                CHANNEL_A,
                "-",
                "someone",
                envs.FEEDS_URL_SUCCESS,
                0,
                envs.CHANNEL_STATUS_SUCCESS,
                "channel-id",
                playlist_id,
            )
        ],
        guild_id=GUILD_ID,
    )


async def _start_the_loop():
    await db_helper.prep_table(envs.guilds_db_schema)
    await db_helper.insert_many_all(
        envs.guilds_db_schema,
        [(str(GUILD_ID), "Test Guild", "approved", "2026-01-01", None, None)],
    )
    await db_helper.ensure_guild_tasks_rows(GUILD_ID)
    await db_helper.update_fields(
        template_info=envs.tasks_db_schema,
        where=[("cog", "youtube"), ("task", "post_videos")],
        updates=("status", "started"),
        guild_id=GUILD_ID,
    )
    await _prep_feed()


async def test_the_posting_loop_calls_the_api_from_a_thread(
    guild_db_root, monkeypatch, api_threads
):
    monkeypatch.setattr(
        youtube.config.bot,
        "get_guild",
        lambda gid: SimpleNamespace(id=GUILD_ID, name="Test Guild"),
    )
    monkeypatch.setattr(discord_commands, "post_to_channel", mock.AsyncMock())
    await _start_the_loop()

    await youtube.Youtube.task_post_videos.coro()

    assert [name for name, _thread in api_threads] == ["latest", "info"]
    assert all(
        thread is not threading.current_thread() for _name, thread in api_threads
    )


async def test_the_backfill_calls_the_api_from_a_thread(
    guild_db_root, monkeypatch, api_threads
):
    monkeypatch.setattr(discord_commands, "log_to_bot_channel", mock.AsyncMock())
    await _prep_feed(playlist_id=None)

    await youtube.backfill_missing_playlist_ids(
        SimpleNamespace(id=GUILD_ID, name="Test Guild")
    )

    assert [name for name, _thread in api_threads] == ["channel"]
    assert api_threads[0][1] is not threading.current_thread()
