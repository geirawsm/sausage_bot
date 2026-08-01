#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for `discord_commands.is_owner()` / `is_owner_or_manage_guild()` -
the app_commands checks that replaced the non-functional
`@commands.is_owner()` on every slash command/context menu in this
codebase (`discord.ext.commands.is_owner()` only registers on
`__commands_checks__`, which `discord.app_commands.Command` never reads,
so it silently never ran - see the docstrings on the two functions under
test).

`discord.app_commands.check(predicate)` (what both functions return)
stores the raw `predicate` coroutine on the decorated function as
`__discord_app_commands_checks__` rather than invoking it - so the tests
below apply the decorator to a throwaway dummy function and pull the
predicate back out to call directly with a mock `discord.Interaction`.
This exercises the exact same coroutine discord.py would call during a
real interaction, without needing a live gateway connection.
"""
from types import SimpleNamespace
from unittest import mock

import discord
import pytest

from sausage_bot.util import discord_commands


def _extract_predicate(check_decorator):
    "Apply a `discord.app_commands.check(...)`-based decorator, return its predicate"

    async def dummy(interaction):
        pass

    decorated = check_decorator(dummy)
    return decorated.__discord_app_commands_checks__[0]


def _make_interaction(is_owner: bool, **guild_perms):
    permissions = discord.Permissions(**guild_perms)
    return SimpleNamespace(
        command=SimpleNamespace(name="some_command"),
        client=SimpleNamespace(is_owner=mock.AsyncMock(return_value=is_owner)),
        user=SimpleNamespace(guild_permissions=permissions),
    )


# --- is_owner() ---


async def test_is_owner_allows_the_bot_owner():
    predicate = _extract_predicate(discord_commands.is_owner())
    interaction = _make_interaction(is_owner=True)
    assert await predicate(interaction) is True


async def test_is_owner_rejects_non_owner_even_with_manage_guild():
    # Manage Server must NOT be enough for an owner-only command - that
    # would defeat the point of having two separate checks.
    predicate = _extract_predicate(discord_commands.is_owner())
    interaction = _make_interaction(is_owner=False, manage_guild=True)
    with pytest.raises(discord_commands.OwnerOnlyCheckFailure):
        await predicate(interaction)


async def test_is_owner_rejects_plain_member():
    predicate = _extract_predicate(discord_commands.is_owner())
    interaction = _make_interaction(is_owner=False)
    with pytest.raises(discord_commands.OwnerOnlyCheckFailure):
        await predicate(interaction)


async def test_owner_only_check_failure_is_a_check_failure():
    # The tree-level error handler in __main__.py branches on
    # `isinstance(error, discord_commands.OwnerOnlyCheckFailure)` *before*
    # the generic `discord.app_commands.CheckFailure` branch - this only
    # works if it's a subclass.
    assert issubclass(
        discord_commands.OwnerOnlyCheckFailure, discord.app_commands.CheckFailure
    )


# --- is_owner_or_manage_guild() ---


async def test_is_owner_or_manage_guild_allows_the_bot_owner():
    predicate = _extract_predicate(discord_commands.is_owner_or_manage_guild())
    interaction = _make_interaction(is_owner=True)
    assert await predicate(interaction) is True


async def test_is_owner_or_manage_guild_allows_manage_guild_permission():
    predicate = _extract_predicate(discord_commands.is_owner_or_manage_guild())
    interaction = _make_interaction(is_owner=False, manage_guild=True)
    assert await predicate(interaction) is True


async def test_is_owner_or_manage_guild_rejects_plain_member():
    predicate = _extract_predicate(discord_commands.is_owner_or_manage_guild())
    interaction = _make_interaction(is_owner=False)
    assert await predicate(interaction) is False


async def test_is_owner_or_manage_guild_rejects_unrelated_permission():
    # A plausible "close but wrong" permission to confuse with manage_guild
    predicate = _extract_predicate(discord_commands.is_owner_or_manage_guild())
    interaction = _make_interaction(is_owner=False, manage_nicknames=True)
    assert await predicate(interaction) is False
