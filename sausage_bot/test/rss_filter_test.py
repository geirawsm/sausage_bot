#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
The `/rss filter` commands, and the repair of the rows the old ones left
behind.

`rss_filter_add` used to hand the whole `get_output(single=True)` row on
to the insert, so the `uuid` column got `{'uuid': '814adaed-...'}`
instead of the uuid. A row like that matches no feed, so the filter
never applies and `remove` cannot find it either.
`db_helper.db_fix_dict_uuid_in_filters` puts the uuid back on startup.

Unlike youtube, rss splits its filter input on `envs.input_split_regex`
- that stays, and is pinned here.
"""

from types import SimpleNamespace
from unittest import mock

from sausage_bot.cogs import rss
from sausage_bot.util import envs, db_helper

GUILD_ID = 888888888888888888
UUID_A = "uuid-feed-a"
UUID_B = "uuid-feed-b"

FEED_ROWS = ("uuid", "feed_name", "url", "channel", "added", "added_by", "feed_type")


def _make_interaction():
    return SimpleNamespace(
        response=SimpleNamespace(defer=mock.AsyncMock()),
        followup=SimpleNamespace(send=mock.AsyncMock()),
        guild=SimpleNamespace(id=GUILD_ID),
    )


async def _prep_feeds():
    await db_helper.prep_table(envs.rss_db_schema, guild_id=GUILD_ID)
    await db_helper.prep_table(envs.rss_db_filter_schema, guild_id=GUILD_ID)
    await db_helper.insert_many_some(
        envs.rss_db_schema,
        rows=FEED_ROWS,
        inserts=[
            (UUID_A, "feed a", "https://x.y/a", 1111, "-", "someone", "rss"),
            (UUID_B, "feed b", "https://x.y/b", 2222, "-", "someone", "rss"),
        ],
        guild_id=GUILD_ID,
    )


async def _filter_rows():
    return await db_helper.get_output(envs.rss_db_filter_schema, guild_id=GUILD_ID)


async def test_filter_add_stores_the_uuid_not_the_row(guild_db_root):
    await _prep_feeds()

    await rss.RSSfeed.rss_filter_add.callback(
        mock.Mock(), _make_interaction(), "feed a", "Deny", "omarchy"
    )

    assert [row["uuid"] for row in await _filter_rows()] == [UUID_A]


async def test_filter_add_splits_its_input(guild_db_root):
    "rss keeps splitting on `envs.input_split_regex` - one row per word"
    await _prep_feeds()

    await rss.RSSfeed.rss_filter_add.callback(
        mock.Mock(), _make_interaction(), "feed a", "Deny", "kaffe, te"
    )

    assert sorted(row["filter"] for row in await _filter_rows()) == ["kaffe", "te"]


async def test_filter_remove_deletes_the_row(guild_db_root):
    await _prep_feeds()
    await rss.RSSfeed.rss_filter_add.callback(
        mock.Mock(), _make_interaction(), "feed a", "Deny", "omarchy"
    )

    await rss.RSSfeed.rss_filter_remove.callback(
        mock.Mock(), _make_interaction(), "feed a", "omarchy"
    )

    assert await _filter_rows() == []


async def test_filter_autocomplete_lists_the_filters(guild_db_root):
    await _prep_feeds()
    await rss.RSSfeed.rss_filter_add.callback(
        mock.Mock(), _make_interaction(), "feed a", "Deny", "omarchy"
    )

    choices = await rss.rss_filter_autocomplete(_make_interaction(), "")

    assert [choice.value for choice in choices] == ["omarchy"]
    assert "feed a" in choices[0].name


# ---------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------


async def _insert_raw_filter(uuid_value):
    await db_helper.insert_many_all(
        envs.rss_db_filter_schema,
        inserts=[(uuid_value, "Deny", "omarchy")],
        guild_id=GUILD_ID,
    )


async def test_a_dict_shaped_uuid_is_repaired(guild_db_root):
    await _prep_feeds()
    await _insert_raw_filter(str({"uuid": UUID_A}))

    repaired = await db_helper.db_fix_dict_uuid_in_filters(
        envs.rss_db_filter_schema, guild_id=GUILD_ID
    )

    assert repaired == 1
    assert [row["uuid"] for row in await _filter_rows()] == [UUID_A]


async def test_a_plain_uuid_is_left_alone(guild_db_root):
    await _prep_feeds()
    await _insert_raw_filter(UUID_A)

    repaired = await db_helper.db_fix_dict_uuid_in_filters(
        envs.rss_db_filter_schema, guild_id=GUILD_ID
    )

    assert repaired == 0
    assert [row["uuid"] for row in await _filter_rows()] == [UUID_A]


async def test_the_repair_is_idempotent(guild_db_root):
    await _prep_feeds()
    await _insert_raw_filter(str({"uuid": UUID_A}))

    await db_helper.db_fix_dict_uuid_in_filters(
        envs.rss_db_filter_schema, guild_id=GUILD_ID
    )
    second_run = await db_helper.db_fix_dict_uuid_in_filters(
        envs.rss_db_filter_schema, guild_id=GUILD_ID
    )

    assert second_run == 0
    assert [row["uuid"] for row in await _filter_rows()] == [UUID_A]


async def test_a_repaired_filter_can_be_removed_again(guild_db_root):
    "The point of the repair: the row rejoins its feed and `remove` finds it"
    await _prep_feeds()
    await _insert_raw_filter(str({"uuid": UUID_A}))
    await db_helper.db_fix_dict_uuid_in_filters(
        envs.rss_db_filter_schema, guild_id=GUILD_ID
    )

    await rss.RSSfeed.rss_filter_remove.callback(
        mock.Mock(), _make_interaction(), "feed a", "omarchy"
    )

    assert await _filter_rows() == []


async def test_the_repair_handles_an_empty_table(guild_db_root):
    await _prep_feeds()

    assert (
        await db_helper.db_fix_dict_uuid_in_filters(
            envs.rss_db_filter_schema, guild_id=GUILD_ID
        )
        == 0
    )
