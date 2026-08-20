#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exercises `cogs/quote.py`'s `delete_quote_with_content()`.

`/quote delete` used to remove the row in `quote` only, leaving the
quote's comments in `quote_content`, its (base64-encoded, by far the
largest rows in this database) images in `quote_img`, and its rows in the
posting log behind - the latter keeping a uuid that no longer exists
excluded from random picks for good.

All tests use the `guild_db_root` fixture (see conftest.py), so nothing
here touches real bot data.
"""
from sausage_bot.util import envs, db_helper
from sausage_bot.cogs.quote import delete_quote_with_content

GUILD = 444444444444444444


async def _prep_quote_tables():
    for schema in (
        envs.quote_db_schema,
        envs.quote_content_db_schema,
        envs.quote_img_db_schema,
        envs.quote_db_log_schema,
    ):
        await db_helper.prep_table(schema, guild_id=GUILD)


async def _insert_quote(uuid, comments, imgs=[]):
    await db_helper.insert_many_all(
        envs.quote_db_schema,
        [(uuid, 555, "quotes", "2026-01-01 10:00:00.000")],
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
    await db_helper.insert_many_all(
        envs.quote_db_log_schema,
        [(uuid, 555, "2026-01-02 10:00:00.000")],
        guild_id=GUILD,
    )


async def _rowid_of(uuid):
    rows = await db_helper.get_output(
        envs.quote_db_schema, select=("rowid", "uuid"), guild_id=GUILD
    )
    return next(row["rowid"] for row in rows if row["uuid"] == uuid)


async def _counts():
    return {
        "quote": len(await db_helper.get_output(envs.quote_db_schema, guild_id=GUILD)),
        "content": len(
            await db_helper.get_output(envs.quote_content_db_schema, guild_id=GUILD)
        ),
        "img": len(
            await db_helper.get_output(envs.quote_img_db_schema, guild_id=GUILD)
        ),
        "log": len(
            await db_helper.get_output(envs.quote_db_log_schema, guild_id=GUILD)
        ),
    }


async def test_delete_removes_comments_images_and_log_rows(guild_db_root):
    await _prep_quote_tables()
    await _insert_quote(
        "u-doomed",
        [(875423461655334924, "a"), (875423598968467467, "b")],
        imgs=[(875423461655334924, 1, "QUJD"), (875423461655334924, 2, "WFla")],
    )
    assert await _counts() == {"quote": 1, "content": 2, "img": 2, "log": 1}

    await delete_quote_with_content(
        guild_id=GUILD, uuid="u-doomed", rowid=await _rowid_of("u-doomed")
    )

    assert await _counts() == {"quote": 0, "content": 0, "img": 0, "log": 0}


async def test_delete_leaves_other_quotes_untouched(guild_db_root):
    await _prep_quote_tables()
    await _insert_quote(
        "u-doomed",
        [(875423461655334924, "delete me")],
        imgs=[(875423461655334924, 1, "QUJD")],
    )
    await _insert_quote(
        "u-keeper",
        [(875424818034532513, "keep me")],
        imgs=[(875424818034532513, 1, "WFla")],
    )

    await delete_quote_with_content(
        guild_id=GUILD, uuid="u-doomed", rowid=await _rowid_of("u-doomed")
    )

    assert await _counts() == {"quote": 1, "content": 1, "img": 1, "log": 1}
    remaining = await db_helper.get_output(envs.quote_db_schema, guild_id=GUILD)
    assert remaining[0]["uuid"] == "u-keeper"
    content = await db_helper.get_output(envs.quote_content_db_schema, guild_id=GUILD)
    assert content[0]["content_text"] == "keep me"


async def test_delete_of_imported_quote_without_message_ids(guild_db_root):
    # Imported comments have no message id, so there are no image rows to
    # look up - deleting must not choke on the empty id list
    await _prep_quote_tables()
    await _insert_quote("u-imported", [(None, "line one"), (None, "line two")])

    await delete_quote_with_content(
        guild_id=GUILD, uuid="u-imported", rowid=await _rowid_of("u-imported")
    )

    assert await _counts() == {"quote": 0, "content": 0, "img": 0, "log": 0}
