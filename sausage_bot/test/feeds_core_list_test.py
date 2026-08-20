#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exercises `feeds_core.get_feed_list`, the function behind `/youtube list`
and `/rss list`: a feed pointing at a deleted channel (or a member that
has left the guild) must not take the whole listing down, and the
`link_type` filter must actually filter.

Uses the `guild_db_root` fixture (see conftest.py) so nothing touches
real bot data. Discord's `Guild` object is mocked - only the name
resolution and the resulting table are under test.
"""
from unittest.mock import MagicMock

from sausage_bot.util import envs, db_helper, feeds_core
from sausage_bot.util.i18n import I18N

GUILD_ID = 444444444444444444
CHANNEL_OK = 4242
CHANNEL_GONE = 1337

YOUTUBE_ROWS = (
    "uuid",
    "feed_name",
    "url",
    "channel",
    "added",
    "added_by",
    "playlist_id",
)


def _make_guild():
    """
    A mock guild that only knows about `CHANNEL_OK` - every other
    channel or member id resolves to None, like discord.py does for
    deleted channels and members that have left.
    """
    channel = MagicMock()
    channel.name = "feed-channel"
    guild = MagicMock()
    guild.id = GUILD_ID
    guild.get_channel_or_thread = MagicMock(
        side_effect=lambda _id: channel if _id == CHANNEL_OK else None
    )
    guild.get_member = MagicMock(return_value=None)
    return guild


async def _prep_youtube_feeds(inserts):
    await db_helper.prep_table(envs.youtube_db_schema, guild_id=GUILD_ID)
    await db_helper.insert_many_some(
        envs.youtube_db_schema,
        rows=YOUTUBE_ROWS,
        inserts=inserts,
        guild_id=GUILD_ID,
    )


async def test_get_feed_list_survives_deleted_channel(guild_db_root):
    await _prep_youtube_feeds(
        [
            ("uuid-1", "good feed", "https://y.t/1", CHANNEL_OK, "-", "someone", None),
            (
                "uuid-2",
                "orphan feed",
                "https://y.t/2",
                CHANNEL_GONE,
                "-",
                "someone",
                None,
            ),
        ]
    )

    out = await feeds_core.get_feed_list(
        guild=_make_guild(), db_in=envs.youtube_db_schema
    )

    assert out is not None
    table = "\n".join(out)
    assert "good feed" in table
    # The feed with the deleted channel is still listed, with a
    # placeholder naming the id that needs fixing
    assert "orphan feed" in table
    assert str(CHANNEL_GONE) in table


async def test_get_feed_list_added_handles_missing_member(guild_db_root):
    await _prep_youtube_feeds(
        [
            (
                "uuid-1",
                "good feed",
                "https://y.t/1",
                CHANNEL_OK,
                "2026-08-20",
                "123456789012345678",
                None,
            ),
        ]
    )

    out = await feeds_core.get_feed_list(
        guild=_make_guild(), db_in=envs.youtube_db_schema, list_type="added"
    )

    assert out is not None
    assert "good feed" in "\n".join(out)


async def test_get_feed_list_filters_on_link_type(guild_db_root):
    await _prep_youtube_feeds(
        [
            ("uuid-1", "a channel", "https://y.t/1", CHANNEL_OK, "-", "someone", None),
            (
                "uuid-2",
                "a playlist",
                "https://y.t/2",
                CHANNEL_OK,
                "-",
                "someone",
                "PL123",
            ),
        ]
    )
    guild = _make_guild()

    channels_out = await feeds_core.get_feed_list(
        guild=guild,
        db_in=envs.youtube_db_schema,
        link_type=I18N.t("youtube.commands.list.literal_link_type.channel"),
    )
    playlists_out = await feeds_core.get_feed_list(
        guild=guild,
        db_in=envs.youtube_db_schema,
        link_type=I18N.t("youtube.commands.list.literal_link_type.playlist"),
    )

    assert "a channel" in "\n".join(channels_out)
    assert "a playlist" not in "\n".join(channels_out)
    assert "a playlist" in "\n".join(playlists_out)
    assert "a channel" not in "\n".join(playlists_out)


async def test_get_feed_list_returns_none_on_empty_db(guild_db_root):
    await db_helper.prep_table(envs.youtube_db_schema, guild_id=GUILD_ID)

    out = await feeds_core.get_feed_list(
        guild=_make_guild(), db_in=envs.youtube_db_schema
    )

    assert out is None


async def test_get_feed_list_rss_added_without_playlist_column(guild_db_root):
    "The rss db has no `playlist_id` column - listing it must still work"
    await db_helper.prep_table(envs.rss_db_schema, guild_id=GUILD_ID)
    await db_helper.insert_many_some(
        envs.rss_db_schema,
        rows=("uuid", "feed_name", "url", "channel", "added", "added_by", "feed_type"),
        inserts=[
            ("uuid-1", "a feed", "https://r.ss/1", CHANNEL_OK, "-", "someone", "rss"),
            (
                "uuid-2",
                "a podcast",
                "https://r.ss/2",
                CHANNEL_OK,
                "-",
                "someone",
                "podcast",
            ),
        ],
        guild_id=GUILD_ID,
    )

    out = await feeds_core.get_feed_list(
        guild=_make_guild(),
        db_in=envs.rss_db_schema,
        list_type="added",
        feed_type="rss",
    )

    assert out is not None
    table = "\n".join(out)
    assert "a feed" in table
    assert "a podcast" not in table
