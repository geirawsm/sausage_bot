#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Covers what happens to `task_post_videos` when a feed has no usable
`playlist_id`, and the startup backfill that gives it one.

A feed added before the `playlist_id` column existed has a NULL there.
`playlistItems` answers `400 No filter selected` on an empty
`playlistId`, and `tasks.loop` only retries the network errors in its
own `_valid_exception` - so that `HttpError` used to end the task for
every guild until the bot was restarted.

Two halves:

  * The loop - a feed with no `playlist_id`, or one the api refuses, is
    counted as a feed error and skipped, and the other feeds in the same
    round still post.
  * `backfill_missing_playlist_ids` - looks the id up from the feed's
    own url, writes it back, and leaves the feeds it already has alone.

The Youtube API is patched out at `YouTubeAPI`, so nothing here touches
the network, and `guild_db_root` (see conftest.py) keeps every write in
a throwaway directory.
"""

from types import SimpleNamespace
from unittest import mock

import httplib2
import pytest
from googleapiclient.errors import HttpError

from sausage_bot.cogs import youtube
from sausage_bot.util import envs, db_helper, discord_commands

GUILD_ID = 888888888888888888
UUID_A = "uuid-feed-a"
UUID_B = "uuid-feed-b"
CHANNEL_A = 1111
CHANNEL_B = 2222

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


def _guild():
    return SimpleNamespace(id=GUILD_ID, name="Test Guild")


def _http_error(status=400, message="No filter selected"):
    "The error the Youtube api hands back for an empty `playlistId`"
    return HttpError(
        httplib2.Response({"status": status, "reason": "Bad Request"}),
        ('{"error": {"message": "%s"}}' % message).encode("utf-8"),
        uri="https://youtube.googleapis.com/youtube/v3/playlistItems",
    )


def _feed_row(uuid, feed_name, channel, playlist_id, url="https://y.t/a"):
    return (
        uuid,
        feed_name,
        url,
        channel,
        "-",
        "someone",
        envs.FEEDS_URL_SUCCESS,
        0,
        envs.CHANNEL_STATUS_SUCCESS,
        "channel-id",
        playlist_id,
    )


async def _prep_feeds(rows):
    await db_helper.prep_table(envs.youtube_db_schema, guild_id=GUILD_ID)
    await db_helper.prep_table(envs.youtube_db_filter_schema, guild_id=GUILD_ID)
    await db_helper.prep_table(envs.youtube_db_log_schema, guild_id=GUILD_ID)
    await db_helper.insert_many_some(
        envs.youtube_db_schema,
        rows=FEED_ROWS,
        inserts=rows,
        guild_id=GUILD_ID,
    )


async def _start_the_loop(rows):
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
    await _prep_feeds(rows)


async def _feeds_by_name():
    feeds = await db_helper.get_output(envs.youtube_db_schema, guild_id=GUILD_ID)
    return {feed["feed_name"]: feed for feed in feeds}


def _video(video_id, title, channel="Feed"):
    return {
        "channel": channel,
        "title": title,
        "description": "",
        "published": "2026-01-01T00:00:00Z",
        "id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }


@pytest.fixture
def no_bot_channel(monkeypatch):
    "`reg_feed_error` and the backfill both report to the bot channel"
    logged = []

    async def _fake_log_to_bot_channel(guild, content_in=None, **kwargs):
        logged.append(content_in)

    monkeypatch.setattr(
        discord_commands, "log_to_bot_channel", _fake_log_to_bot_channel
    )
    return logged


@pytest.fixture
def posted(monkeypatch, no_bot_channel):
    """
    Run `task_post_videos` for one started guild with the Youtube API
    faked out, and record what it tries to post. `videos` maps a
    playlist id to the video dicts `get_video_info` would return for it
    - or to an exception, which `get_latest_video_ids` then raises for
    that playlist.
    """
    posts = []

    async def _fake_post_to_channel(channel_id, content_in=None, **kwargs):
        posts.append((channel_id, content_in))

    monkeypatch.setattr(discord_commands, "post_to_channel", _fake_post_to_channel)
    monkeypatch.setattr(youtube.config.bot, "get_guild", lambda gid: _guild())
    monkeypatch.setattr(youtube.config, "YOUTUBE_API_KEY", "test-key")

    async def _run(videos):
        by_id = {
            video["id"]: video
            for vids in videos.values()
            if not isinstance(vids, Exception)
            for video in vids
        }

        def _latest(playlist_id, max_results=5):
            found = videos.get(playlist_id, [])
            if isinstance(found, Exception):
                raise found
            return [video["id"] for video in found]

        monkeypatch.setattr(youtube.YouTubeAPI, "get_latest_video_ids", _latest)
        monkeypatch.setattr(
            youtube.YouTubeAPI,
            "get_video_info",
            lambda video_ids: [by_id[video_id] for video_id in video_ids],
        )
        await youtube.Youtube.task_post_videos.coro()
        return [content for _channel, content in posts]

    return _run


# ---------------------------------------------------------------------
# task_post_videos
# ---------------------------------------------------------------------


async def test_a_feed_without_playlist_id_does_not_stop_the_round(
    guild_db_root, posted
):
    "The feed is skipped - the other one in the same round still posts"
    await _start_the_loop(
        [
            _feed_row(UUID_A, "feed a", CHANNEL_A, "playlist-a"),
            _feed_row(UUID_B, "feed b", CHANNEL_B, None),
        ]
    )

    urls = await posted({"playlist-a": [_video("v1", "A new video")]})

    assert urls == ["https://www.youtube.com/watch?v=v1"]


async def test_a_feed_without_playlist_id_is_counted_as_a_feed_error(
    guild_db_root, posted
):
    "Not silent: the feed counts down to `Failed` like any other broken one"
    await _start_the_loop([_feed_row(UUID_B, "feed b", CHANNEL_B, "")])

    await posted({})

    assert (await _feeds_by_name())["feed b"]["status_url_counter"] == 1


async def test_an_api_error_on_one_feed_does_not_stop_the_round(
    guild_db_root, posted
):
    "The `HttpError` that used to end the whole task"
    await _start_the_loop(
        [
            _feed_row(UUID_A, "feed a", CHANNEL_A, "playlist-a"),
            _feed_row(UUID_B, "feed b", CHANNEL_B, "playlist-b"),
        ]
    )

    urls = await posted(
        {
            "playlist-a": [_video("v1", "A new video")],
            "playlist-b": _http_error(),
        }
    )

    assert urls == ["https://www.youtube.com/watch?v=v1"]
    assert (await _feeds_by_name())["feed b"]["status_url_counter"] == 1


async def test_a_feed_that_works_again_has_its_error_count_cleared(
    guild_db_root, posted
):
    await _start_the_loop([_feed_row(UUID_A, "feed a", CHANNEL_A, "playlist-a")])
    await db_helper.update_fields(
        template_info=envs.youtube_db_schema,
        where=("uuid", UUID_A),
        updates=("status_url_counter", 2),
        guild_id=GUILD_ID,
    )

    await posted({"playlist-a": [_video("v1", "A new video")]})

    assert (await _feeds_by_name())["feed a"]["status_url_counter"] == 0


# ---------------------------------------------------------------------
# backfill_missing_playlist_ids
# ---------------------------------------------------------------------


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setattr(youtube.config, "YOUTUBE_API_KEY", "test-key")


async def test_backfill_looks_up_a_channel_feed(
    guild_db_root, monkeypatch, api_key, no_bot_channel
):
    await _prep_feeds(
        [
            _feed_row(
                UUID_A,
                "feed a",
                CHANNEL_A,
                None,
                url="https://www.youtube.com/@somechannel",
            )
        ]
    )
    monkeypatch.setattr(
        youtube.YouTubeAPI,
        "extract_yt_channel_info",
        lambda url: {"channel_id": "UC123", "playlist_id": "UU123"},
    )

    await youtube.backfill_missing_playlist_ids(_guild())

    assert (await _feeds_by_name())["feed a"]["playlist_id"] == "UU123"


async def test_backfill_looks_up_a_playlist_feed(
    guild_db_root, monkeypatch, api_key, no_bot_channel
):
    "A link with a `list=` in it is a playlist, and gets the playlist lookup"
    await _prep_feeds(
        [
            _feed_row(
                UUID_A,
                "feed a",
                CHANNEL_A,
                None,
                url="https://www.youtube.com/playlist?list=PL123",
            )
        ]
    )
    monkeypatch.setattr(
        youtube.YouTubeAPI,
        "extract_yt_channel_info",
        mock.Mock(side_effect=AssertionError("should not look up a channel")),
    )
    monkeypatch.setattr(
        youtube.YouTubeAPI,
        "get_playlist_info",
        lambda url: {"channel_id": "UC123", "playlist_id": "PL123"},
    )

    await youtube.backfill_missing_playlist_ids(_guild())

    assert (await _feeds_by_name())["feed a"]["playlist_id"] == "PL123"


async def test_backfill_leaves_feeds_that_have_an_id_alone(
    guild_db_root, monkeypatch, api_key, no_bot_channel
):
    "Idempotent, and no api call - a full db costs nothing to re-check"
    await _prep_feeds([_feed_row(UUID_A, "feed a", CHANNEL_A, "playlist-a")])
    monkeypatch.setattr(
        youtube.YouTubeAPI,
        "extract_yt_channel_info",
        mock.Mock(side_effect=AssertionError("should not call the api")),
    )

    await youtube.backfill_missing_playlist_ids(_guild())

    assert (await _feeds_by_name())["feed a"]["playlist_id"] == "playlist-a"


async def test_backfill_reports_the_feeds_it_could_not_look_up(
    guild_db_root, monkeypatch, api_key, no_bot_channel
):
    "A dead link leaves the feed as it was, and the guild is told about it"
    await _prep_feeds([_feed_row(UUID_A, "feed a", CHANNEL_A, None)])
    monkeypatch.setattr(
        youtube.YouTubeAPI,
        "extract_yt_channel_info",
        mock.Mock(side_effect=_http_error(404, "Not found")),
    )

    await youtube.backfill_missing_playlist_ids(_guild())

    assert (await _feeds_by_name())["feed a"]["playlist_id"] is None
    assert any("feed a" in str(msg) for msg in no_bot_channel)
