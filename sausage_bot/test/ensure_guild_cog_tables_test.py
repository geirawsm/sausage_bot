#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for `util/cogs.py`'s `ensure_guild_tables_for_loaded_cogs()`.

Every cog preps its own per-guild tables in its `setup()`, which only
runs when the cog is loaded at startup. A guild approved while the bot
was already running therefore got its `settings` and `tasks` rows from
`/guild approve` and nothing else - every cog sat there silently
inactive until someone restarted the bot. The helper walks the loaded
extensions and calls the idempotent `ensure_guild_tables(guild)` that
each cog with per-guild tables now exposes.
"""
from types import SimpleNamespace

from sausage_bot.util import cogs, config

GUILD = SimpleNamespace(id=111111111111111111, name="Guild A")


def _fake_cog(calls, name, raises=False):
    "A stand-in cog module exposing the uniform ensure_guild_tables()"

    async def ensure_guild_tables(guild):
        calls.append((name, guild.id))
        if raises:
            raise RuntimeError("table prep blew up")

    return SimpleNamespace(ensure_guild_tables=ensure_guild_tables)


def _load(monkeypatch, extensions):
    monkeypatch.setattr(config, "bot", SimpleNamespace(extensions=extensions))


async def test_every_loaded_cog_with_tables_is_prepped(monkeypatch):
    calls = []
    _load(
        monkeypatch,
        {
            "cogs.quote": _fake_cog(calls, "quote"),
            "cogs.youtube": _fake_cog(calls, "youtube"),
        },
    )

    await cogs.ensure_guild_tables_for_loaded_cogs(GUILD)

    assert calls == [("quote", GUILD.id), ("youtube", GUILD.id)]


async def test_cogs_without_per_guild_tables_are_skipped(monkeypatch):
    "autoevent has no per-guild tables and exposes no ensure function"
    calls = []
    _load(
        monkeypatch,
        {
            "cogs.autoevent": SimpleNamespace(),
            "cogs.quote": _fake_cog(calls, "quote"),
        },
    )

    await cogs.ensure_guild_tables_for_loaded_cogs(GUILD)

    assert calls == [("quote", GUILD.id)]


async def test_one_failing_cog_does_not_stop_the_rest(monkeypatch):
    """
    A guild set up except for one cog is a lot better than a guild half
    set up, so a cog that blows up is logged and stepped over.
    """
    calls = []
    _load(
        monkeypatch,
        {
            "cogs.rss": _fake_cog(calls, "rss", raises=True),
            "cogs.quote": _fake_cog(calls, "quote"),
        },
    )

    await cogs.ensure_guild_tables_for_loaded_cogs(GUILD)

    assert calls == [("rss", GUILD.id), ("quote", GUILD.id)]


async def test_a_guild_the_bot_is_no_longer_in_is_a_no_op(monkeypatch):
    "Callers resolve the guild from a registry row, which can come back None"
    calls = []
    _load(monkeypatch, {"cogs.quote": _fake_cog(calls, "quote")})

    await cogs.ensure_guild_tables_for_loaded_cogs(None)

    assert calls == []
