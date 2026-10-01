#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
`/quote post` answers through `interaction.followup`, which only exists
once the interaction has been responded to. With the `defer()` commented
out every post failed with `404 Unknown Webhook (error code: 10015)`.
"""
from unittest.mock import AsyncMock, MagicMock

from sausage_bot.cogs import quote
from sausage_bot.util.i18n import I18N


def _interaction(calls):
    interaction = MagicMock()
    interaction.response.defer = AsyncMock(
        side_effect=lambda **kwargs: calls.append(("defer", kwargs))
    )
    return interaction


async def test_post_defers_before_posting_a_random_quote(monkeypatch):
    calls = []
    monkeypatch.setattr(
        quote,
        "post_random_quote",
        AsyncMock(side_effect=lambda **kwargs: calls.append(("post", kwargs))),
    )

    await quote.Quotes.post.callback(MagicMock(), _interaction(calls))

    assert [name for name, _ in calls] == ["defer", "post"]
    assert calls[0][1] == {"ephemeral": True}


async def test_post_defers_publicly_before_posting_a_selected_quote(monkeypatch):
    calls = []
    monkeypatch.setattr(
        quote,
        "post_selected_quote",
        AsyncMock(side_effect=lambda *args: calls.append(("post", args))),
    )

    await quote.Quotes.post.callback(
        MagicMock(),
        _interaction(calls),
        quote_in="3",
        public=I18N.t("common.literal_yes_no.lit_yes"),
    )

    assert [name for name, _ in calls] == ["defer", "post"]
    assert calls[0][1] == {"ephemeral": False}


# What `db_helper.get_imgs_with_quote` returns: a *list* of quote dicts
QUOTE_ROWS = [
    {
        "rowid": 2,
        "uuid": "8ec9a0a4-dfa1-4829-b09f-660b2137b232",
        "channel_id": "",
        "channel_backup": "general",
        "datetime": "2026-09-30 20:01:39.706000+00:00",
        "comments": {
            1: {"author_backup": "anna", "content": "hei", "imgs": {}},
            2: {"author_backup": "bob", "content": "hallo", "imgs": {}},
        },
    }
]


def _patch_posting(monkeypatch):
    monkeypatch.setattr(
        quote.db_helper, "get_imgs_with_quote", AsyncMock(return_value=QUOTE_ROWS)
    )
    monkeypatch.setattr(quote.db_helper, "insert_many_all", AsyncMock())
    monkeypatch.setattr(quote, "get_dt", AsyncMock(return_value="30.09.2026"))
    interaction = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


async def test_post_random_quote_posts_from_the_list(monkeypatch):
    interaction = _patch_posting(monkeypatch)
    monkeypatch.setattr(
        quote,
        "get_random_quote",
        AsyncMock(return_value=[(2, QUOTE_ROWS[0]["uuid"], "2026-09-30")]),
    )

    await quote.post_random_quote(guild=MagicMock(), interaction=interaction)

    posted = interaction.followup.send.await_args.args[0]
    assert "anna: hei" in posted and "bob : hallo" in posted


async def test_post_selected_quote_posts_from_the_list(monkeypatch):
    interaction = _patch_posting(monkeypatch)

    await quote.post_selected_quote(interaction, True, "2")

    posted = interaction.followup.send.await_args.args[0]
    assert "anna: hei" in posted and "bob : hallo" in posted
