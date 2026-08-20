#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exercises `db_helper.get_imgs_with_quote()`, which assembles a quote and
its comments/images for every quote-posting path in `cogs/quote.py`.

Two regressions are covered:

* Comments were keyed on `quote_content.comment_id`, which is NULL for
  imported quotes (265 of 507 comment rows in the bot's own main guild),
  so every comment of such a quote collapsed into one entry and only the
  first line was ever posted.
* The image column was selected as `quote_img.base64` but read as
  `img_base64`, so any quote with an attachment raised
  `KeyError: 'img_base64'`.

All tests use the `guild_db_root` fixture (see conftest.py), so nothing
here touches real bot data.
"""
from sausage_bot.util import envs, db_helper

GUILD = 333333333333333333


async def _prep_quote_tables():
    for schema in (
        envs.quote_db_schema,
        envs.quote_content_db_schema,
        envs.quote_img_db_schema,
    ):
        await db_helper.prep_table(schema, guild_id=GUILD)


async def _insert_quote(uuid, channel_id, channel_backup, comments, imgs=[]):
    await db_helper.insert_many_all(
        envs.quote_db_schema,
        [(uuid, channel_id, channel_backup, "2026-01-01 10:00:00.000")],
        guild_id=GUILD,
    )
    await db_helper.insert_many_all(
        envs.quote_content_db_schema,
        [
            (uuid, comment_id, 9, "someone", text, order)
            for order, (comment_id, text) in enumerate(comments)
        ],
        guild_id=GUILD,
    )
    if imgs:
        await db_helper.insert_many_all(
            envs.quote_img_db_schema, imgs, guild_id=GUILD
        )


async def test_imported_quote_keeps_every_comment(guild_db_root):
    # An imported quote: no channel id, and no message id per comment
    await _prep_quote_tables()
    await _insert_quote(
        "u-imported",
        None,
        "Telegram-chatten",
        [(None, "line one"), (None, "line two"), (None, "line three")],
    )

    quote = (await db_helper.get_imgs_with_quote(envs.quote_db_schema, guild_id=GUILD))[
        0
    ]

    assert len(quote["comments"]) == 3
    assert [c["content"] for c in quote["comments"].values()] == [
        "line one",
        "line two",
        "line three",
    ]
    # Keyed by content_order, so nothing mistakes these for message ids
    assert all(isinstance(key, str) for key in quote["comments"])


async def test_discord_quote_is_still_keyed_by_message_id(guild_db_root):
    await _prep_quote_tables()
    await _insert_quote(
        "u-discord", 555, "quotes", [(875423461655334924, "a"), (875423598968467467, "b")]
    )

    quote = (await db_helper.get_imgs_with_quote(envs.quote_db_schema, guild_id=GUILD))[
        0
    ]

    assert list(quote["comments"]) == [875423461655334924, 875423598968467467]


async def test_quote_with_images_returns_them_per_comment(guild_db_root):
    await _prep_quote_tables()
    await _insert_quote(
        "u-imgs",
        555,
        "quotes",
        [(875423461655334924, "look at this"), (875423598968467467, "no image here")],
        imgs=[(875423461655334924, 1, "QUJD"), (875423461655334924, 2, "WFla")],
    )

    quote = (await db_helper.get_imgs_with_quote(envs.quote_db_schema, guild_id=GUILD))[
        0
    ]

    assert quote["comments"][875423461655334924]["imgs"] == {1: "QUJD", 2: "WFla"}
    assert quote["comments"][875423598968467467]["imgs"] == {}


async def test_comment_level_columns_do_not_leak_into_the_quote(guild_db_root):
    await _prep_quote_tables()
    await _insert_quote(
        "u-leak",
        555,
        "quotes",
        [(875423461655334924, "a")],
        imgs=[(875423461655334924, 1, "QUJD")],
    )

    quote = (await db_helper.get_imgs_with_quote(envs.quote_db_schema, guild_id=GUILD))[
        0
    ]

    assert set(quote) == {
        "rowid",
        "uuid",
        "channel_id",
        "channel_backup",
        "datetime",
        "comments",
    }
