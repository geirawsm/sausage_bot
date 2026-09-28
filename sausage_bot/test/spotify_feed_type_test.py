#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spotify show links only work as podcasts.

`/rss add` used to accept them, which stored the feed as `rss`. The RSS
loop then fetched the open.spotify.com html page, found no feed in it
and counted an error on every tick until the feed was given up:

    /rss add <spotify link> -> feed_type "rss" -> None x3 -> Failed

`/rss add` now points to `/podcast add` instead, and the startup
migration moves rows that already got in over to `podcast`.
"""

import sqlite3
from types import SimpleNamespace
from unittest import mock

from sausage_bot.cogs import rss
from sausage_bot.util import db_helper, envs, feeds_core
from sausage_bot.util.i18n import I18N

GUILD_ID = 777777777777777777
SPOTIFY_URL = "https://open.spotify.com/show/71beMOqrla4FWGy88WNoGb?si=04d20fa655854aa4"


def _make_interaction():
    return SimpleNamespace(
        response=SimpleNamespace(defer=mock.AsyncMock()),
        followup=SimpleNamespace(send=mock.AsyncMock()),
        guild=SimpleNamespace(id=GUILD_ID),
        user=SimpleNamespace(name="someone"),
    )


async def test_rss_add_refuses_spotify_link(monkeypatch):
    add_to_db = mock.AsyncMock()
    monkeypatch.setattr(feeds_core, "add_to_feed_db", add_to_db)
    monkeypatch.setattr(
        feeds_core, "check_feed_validity", mock.AsyncMock(return_value=True)
    )
    monkeypatch.setattr(
        rss.discord_commands, "log_to_bot_channel", mock.AsyncMock()
    )
    interaction = _make_interaction()

    await rss.RSSfeed.rss_add.callback(
        mock.Mock(), interaction, "Alt om OBOSligaen", SPOTIFY_URL,
        SimpleNamespace(id=1, name="podcast"),
    )

    add_to_db.assert_not_called()
    sent = interaction.followup.send.call_args
    assert sent.args[0] == I18N.t("rss.commands.add.msg_use_podcast_add")


async def test_rss_add_still_accepts_normal_feed(monkeypatch):
    add_to_db = mock.AsyncMock()
    monkeypatch.setattr(feeds_core, "add_to_feed_db", add_to_db)
    monkeypatch.setattr(
        feeds_core, "check_feed_validity", mock.AsyncMock(return_value=True)
    )
    monkeypatch.setattr(
        rss.discord_commands, "log_to_bot_channel", mock.AsyncMock()
    )

    await rss.RSSfeed.rss_add.callback(
        mock.Mock(), _make_interaction(), "news", "https://example.com/rss",
        SimpleNamespace(id=1, name="news"),
    )

    add_to_db.assert_called_once()


def _row(uuid, url, feed_type, status):
    return (
        uuid, uuid, url, "1111", "-", "someone", feed_type, status, 3,
        envs.CHANNEL_STATUS_SUCCESS, 0,
    )


async def test_migration_moves_spotify_rows_to_podcast(guild_db_root):
    await db_helper.prep_table(envs.rss_db_schema, guild_id=GUILD_ID)
    db_file = envs.resolve_db_file(envs.rss_db_schema, GUILD_ID)
    con = sqlite3.connect(db_file)
    con.executemany(
        "INSERT INTO rss_feeds VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            # Added with `/rss add`, then given up by the RSS loop
            _row("as-rss", SPOTIFY_URL, "rss", envs.FEEDS_URL_STALE),
            # Legacy feed type
            _row("as-spotify", SPOTIFY_URL, "spotify", envs.FEEDS_URL_SUCCESS),
            # Real podcast failures are not ours to reset
            _row("as-podcast", SPOTIFY_URL, "podcast", envs.FEEDS_URL_ERROR),
            _row("normal", "https://example.com/rss", "rss", envs.FEEDS_URL_ERROR),
        ],
    )
    con.commit()
    con.close()

    await db_helper.db_update_to_correct_feed_types(
        template_info=envs.rss_db_schema, guild_id=GUILD_ID
    )

    con = sqlite3.connect(db_file)
    rows = {
        row[0]: row[1:]
        for row in con.execute(
            "SELECT uuid, feed_type, status_url, status_url_counter FROM rss_feeds"
        )
    }
    con.close()
    assert rows["as-rss"] == ("podcast", envs.FEEDS_URL_SUCCESS, 0)
    assert rows["as-spotify"][0] == "podcast"
    assert rows["as-podcast"] == ("podcast", envs.FEEDS_URL_ERROR, 3)
    assert rows["normal"] == ("rss", envs.FEEDS_URL_ERROR, 3)
