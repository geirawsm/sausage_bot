#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
guild_context is the contextvars-based mechanism the whole multi-guild
architecture relies on: it lets synchronous code (I18N.t(), get_dt())
resolve "which guild's settings" without a guild_id being threaded
through every call site. These tests check the property that matters
most - that it never leaks between two guilds handled concurrently.
"""
import asyncio

from sausage_bot.util import guild_context


def test_defaults_are_locale_agnostic():
    assert guild_context.current_guild_id.get() is None
    assert guild_context.current_locale.get() == "en"
    assert guild_context.current_timezone.get() == "UTC"


async def test_set_is_visible_within_the_same_task_and_resets_after():
    token_id = guild_context.current_guild_id.set(123)
    token_locale = guild_context.current_locale.set("nb")
    token_tz = guild_context.current_timezone.set("Europe/Oslo")
    try:
        assert guild_context.current_guild_id.get() == 123
        assert guild_context.current_locale.get() == "nb"
        assert guild_context.current_timezone.get() == "Europe/Oslo"
    finally:
        guild_context.current_guild_id.reset(token_id)
        guild_context.current_locale.reset(token_locale)
        guild_context.current_timezone.reset(token_tz)

    assert guild_context.current_guild_id.get() is None
    assert guild_context.current_locale.get() == "en"
    assert guild_context.current_timezone.get() == "UTC"


async def test_concurrent_tasks_do_not_leak_guild_context():
    """
    This is the guarantee `db_helper.guild_locale_context()` depends on:
    two guilds' background-loop iterations (or two interactions) running
    as separate asyncio Tasks at the same time must never see each
    other's locale/timezone. A plain global would fail this test.
    """
    seen = {}

    async def run_as_guild(guild_id, locale, timezone, yield_first):
        token_id = guild_context.current_guild_id.set(guild_id)
        token_locale = guild_context.current_locale.set(locale)
        token_tz = guild_context.current_timezone.set(timezone)
        try:
            if yield_first:
                # Give the other task a chance to run first. If the
                # values below were plain globals, this task would now
                # observe the other guild's values instead of its own.
                await asyncio.sleep(0.01)
            seen[guild_id] = (
                guild_context.current_guild_id.get(),
                guild_context.current_locale.get(),
                guild_context.current_timezone.get(),
            )
        finally:
            guild_context.current_guild_id.reset(token_id)
            guild_context.current_locale.reset(token_locale)
            guild_context.current_timezone.reset(token_tz)

    await asyncio.gather(
        run_as_guild(111, "nb", "Europe/Oslo", yield_first=True),
        run_as_guild(222, "en", "UTC", yield_first=False),
    )

    assert seen[111] == (111, "nb", "Europe/Oslo")
    assert seen[222] == (222, "en", "UTC")

    # Isolation inside asyncio.gather() proves the propagation mechanism
    # works; this confirms the outer/parent context was never touched.
    assert guild_context.current_guild_id.get() is None
    assert guild_context.current_locale.get() == "en"
    assert guild_context.current_timezone.get() == "UTC"
