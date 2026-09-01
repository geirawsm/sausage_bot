#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Covers the allow/deny filters on `/youtube filter` and the filtering
`task_post_videos` does before it posts.

Two halves:

  * The commands - `add` and `remove` must write and delete a row keyed
    on the *feed's* uuid, and the autocomplete must be able to list what
    is in the table.
  * The loop - a filter belongs to one feed, so a deny on feed A must
    leave feed B alone, and the decision itself must come out of
    `net_io.FilterLinks.post_based_on_filter` (title + description,
    case-insensitive, `FEED_FILTER_PRIORITY`-aware).

The Youtube API is patched out at `YouTubeAPI`, so nothing here touches
the network, and `guild_db_root` (see conftest.py) keeps every write in
a throwaway directory.
"""

from types import SimpleNamespace
from unittest import mock

import pytest

from sausage_bot.cogs import youtube
from sausage_bot.util import envs, db_helper, discord_commands

GUILD_ID = 777777777777777777
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
    "status_channel",
    "playlist_id",
)


def _make_interaction():
    return SimpleNamespace(
        response=SimpleNamespace(defer=mock.AsyncMock()),
        followup=SimpleNamespace(send=mock.AsyncMock()),
        guild=SimpleNamespace(id=GUILD_ID),
    )


async def _prep_feeds():
    "Two working feeds, so a filter on one can be shown not to hit the other"
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
                "https://y.t/a",
                CHANNEL_A,
                "-",
                "someone",
                envs.FEEDS_URL_SUCCESS,
                envs.CHANNEL_STATUS_SUCCESS,
                "playlist-a",
            ),
            (
                UUID_B,
                "feed b",
                "https://y.t/b",
                CHANNEL_B,
                "-",
                "someone",
                envs.FEEDS_URL_SUCCESS,
                envs.CHANNEL_STATUS_SUCCESS,
                "playlist-b",
            ),
        ],
        guild_id=GUILD_ID,
    )


async def _add_filter(uuid, allow_or_deny, filter_in):
    await db_helper.insert_many_all(
        envs.youtube_db_filter_schema,
        inserts=[(uuid, allow_or_deny, filter_in)],
        guild_id=GUILD_ID,
    )


async def _filter_rows():
    return await db_helper.get_output(
        envs.youtube_db_filter_schema, guild_id=GUILD_ID
    )


# ---------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------


async def test_filter_add_stores_the_feeds_uuid(guild_db_root):
    await _prep_feeds()

    await youtube.Youtube.youtube_filter_add.callback(
        mock.Mock(), _make_interaction(), "feed a", "Deny", "omarchy"
    )

    assert await _filter_rows() == [
        {"uuid": UUID_A, "allow_or_deny": "Deny", "filter": "omarchy"}
    ]


async def test_filter_add_keeps_a_multi_word_filter_whole(guild_db_root):
    "One filter per command - a phrase must not be split into words"
    await _prep_feeds()

    await youtube.Youtube.youtube_filter_add.callback(
        mock.Mock(), _make_interaction(), "feed a", "Deny", "let's play"
    )

    assert [row["filter"] for row in await _filter_rows()] == ["let's play"]


async def test_filter_remove_deletes_the_row(guild_db_root):
    await _prep_feeds()
    await _add_filter(UUID_A, "Deny", "omarchy")

    await youtube.Youtube.youtube_filter_remove.callback(
        mock.Mock(), _make_interaction(), "feed a", "omarchy"
    )

    assert await _filter_rows() == []


async def test_filter_remove_leaves_the_other_feeds_filter(guild_db_root):
    "Same word filtered on both feeds - only the named feed's row goes"
    await _prep_feeds()
    await _add_filter(UUID_A, "Deny", "omarchy")
    await _add_filter(UUID_B, "Deny", "omarchy")

    await youtube.Youtube.youtube_filter_remove.callback(
        mock.Mock(), _make_interaction(), "feed a", "omarchy"
    )

    assert [row["uuid"] for row in await _filter_rows()] == [UUID_B]


async def test_filter_autocomplete_lists_the_filters(guild_db_root):
    await _prep_feeds()
    await _add_filter(UUID_A, "Deny", "omarchy")

    choices = await youtube.youtube_filter_autocomplete(_make_interaction(), "")

    assert [choice.value for choice in choices] == ["omarchy"]
    assert "feed a" in choices[0].name
    assert "Deny" in choices[0].name


async def test_filter_autocomplete_narrows_on_current(guild_db_root):
    await _prep_feeds()
    await _add_filter(UUID_A, "Deny", "omarchy")
    await _add_filter(UUID_B, "Allow", "hyprland")

    choices = await youtube.youtube_filter_autocomplete(_make_interaction(), "hypr")

    assert [choice.value for choice in choices] == ["hyprland"]


# ---------------------------------------------------------------------
# task_post_videos
# ---------------------------------------------------------------------


@pytest.fixture
def posted(monkeypatch):
    """
    Run `task_post_videos` for one started guild with the Youtube API
    faked out, and record what it tries to post. `videos` maps a
    playlist id to the video dicts `get_video_info` would return for it.
    """
    posts = []

    async def _fake_post_to_channel(channel_id, content_in=None, **kwargs):
        posts.append((channel_id, content_in))

    monkeypatch.setattr(discord_commands, "post_to_channel", _fake_post_to_channel)
    monkeypatch.setattr(
        youtube.config.bot,
        "get_guild",
        lambda gid: SimpleNamespace(id=GUILD_ID, name="Test Guild"),
    )

    async def _run(videos):
        by_id = {
            video["id"]: video for vids in videos.values() for video in vids
        }
        monkeypatch.setattr(
            youtube.YouTubeAPI,
            "get_latest_video_ids",
            lambda playlist_id, max_results=5: [
                video["id"] for video in videos.get(playlist_id, [])
            ],
        )
        monkeypatch.setattr(
            youtube.YouTubeAPI,
            "get_video_info",
            lambda video_ids: [by_id[video_id] for video_id in video_ids],
        )
        await youtube.Youtube.task_post_videos.coro()
        return [content for _channel, content in posts]

    return _run


def _video(video_id, title, description="", channel="Feed"):
    return {
        "channel": channel,
        "title": title,
        "description": description,
        "published": "2026-01-01T00:00:00Z",
        "id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }


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
    await _prep_feeds()


async def test_a_video_is_posted_when_no_filters_exist(guild_db_root, posted):
    await _start_the_loop()

    urls = await posted({"playlist-a": [_video("v1", "A new video")]})

    assert urls == ["https://www.youtube.com/watch?v=v1"]


async def test_a_deny_filter_in_the_title_blocks_the_video(guild_db_root, posted):
    await _start_the_loop()
    await _add_filter(UUID_A, "Deny", "omarchy")

    urls = await posted({"playlist-a": [_video("v1", "Omarchy is great")]})

    assert urls == []


async def test_a_deny_filter_in_the_description_blocks_the_video(
    guild_db_root, posted
):
    "post_based_on_filter looks at title *and* description"
    await _start_the_loop()
    await _add_filter(UUID_A, "Deny", "omarchy")

    urls = await posted(
        {"playlist-a": [_video("v1", "A new video", "all about omarchy")]}
    )

    assert urls == []


async def test_a_deny_filter_belongs_to_its_own_feed(guild_db_root, posted):
    "A deny on feed A must not silence feed B"
    await _start_the_loop()
    await _add_filter(UUID_A, "Deny", "omarchy")

    urls = await posted(
        {
            "playlist-a": [_video("v1", "Omarchy is great")],
            "playlist-b": [_video("v2", "Omarchy is still great")],
        }
    )

    assert urls == ["https://www.youtube.com/watch?v=v2"]


async def test_an_allow_filter_without_a_hit_blocks_the_video(guild_db_root, posted):
    await _start_the_loop()
    await _add_filter(UUID_A, "Allow", "hyprland")

    urls = await posted({"playlist-a": [_video("v1", "A new video")]})

    assert urls == []


async def test_an_allow_filter_with_a_hit_posts_the_video(guild_db_root, posted):
    await _start_the_loop()
    await _add_filter(UUID_A, "Allow", "hyprland")

    urls = await posted({"playlist-a": [_video("v1", "Hyprland tips")]})

    assert urls == ["https://www.youtube.com/watch?v=v1"]


async def test_an_allow_filter_on_one_feed_does_not_gate_the_other(
    guild_db_root, posted
):
    """
    An allow-filter only narrows the feed it was added to. Feed B has no
    filters at all, so everything on it still posts.
    """
    await _start_the_loop()
    await _add_filter(UUID_A, "Allow", "hyprland")

    urls = await posted(
        {
            "playlist-a": [_video("v1", "A new video")],
            "playlist-b": [_video("v2", "Another new video")],
        }
    )

    assert urls == ["https://www.youtube.com/watch?v=v2"]


async def test_a_posted_video_is_written_to_the_log(guild_db_root, posted):
    await _start_the_loop()

    await posted({"playlist-a": [_video("v1", "A new video")]})

    log = await db_helper.get_output(envs.youtube_db_log_schema, guild_id=GUILD_ID)
    assert [row["url"] for row in log] == ["https://www.youtube.com/watch?v=v1"]
    assert [row["uuid"] for row in log] == [UUID_A]


async def test_a_filtered_video_is_not_logged(guild_db_root, posted):
    "A denied video must stay unlogged, so it is reconsidered if the filter goes"
    await _start_the_loop()
    await _add_filter(UUID_A, "Deny", "omarchy")

    await posted({"playlist-a": [_video("v1", "Omarchy is great")]})

    log = await db_helper.get_output(envs.youtube_db_log_schema, guild_id=GUILD_ID)
    assert log == []
