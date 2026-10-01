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


def test_trunc_shortens_strings_in_nested_values():
    long_text = "✅✅ Local commands synced with global commands"
    quote_in = {
        "rowid": 2,
        "uuid": "8ec9a0a4-dfa1-4829-b09f-660b2137b232",
        "comments": {
            1554946394320539750: {
                "author_id": 1000831048483094638,
                "content": long_text,
                "imgs": {1: "QUJD" * 100},
            }
        },
        "tags": ["kort", long_text],
        "pair": ("kort", long_text),
        "missing": None,
    }

    out = quote.trunc(quote_in)

    comment = out["comments"][1554946394320539750]
    assert out["uuid"] == quote_in["uuid"][:29] + "…"
    assert comment["content"] == "✅✅ Local commands synced with…"
    assert len(comment["imgs"][1]) == 30
    assert comment["author_id"] == 1000831048483094638
    assert out["tags"] == ["kort", "✅✅ Local commands synced with…"]
    assert isinstance(out["pair"], tuple) and out["pair"][0] == "kort"
    assert out["missing"] is None
    # Logging a shortened copy must not touch the quote that gets posted
    assert quote_in["comments"][1554946394320539750]["content"] == long_text


def test_trunc_respects_n():
    assert quote.trunc("abcdef", n=4) == "abc…"
    assert quote.trunc("abcd", n=4) == "abcd"
