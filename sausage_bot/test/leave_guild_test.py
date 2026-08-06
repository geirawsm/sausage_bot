#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the /leave_guild command in __main__.py and its
LeaveGuildConfirm_view.

sausage_bot/__main__.py calls config.bot.run(...) at module level (no
`if __name__ == "__main__":` guard), so a plain import would try to
connect to Discord. config.bot.run is patched to a no-op for the
duration of the import below to avoid that.

The command is invoked via its `.callback` - the raw async function
discord.py stores on the app_commands.Command object once
`@tree.command` wraps it - to exercise the command logic directly.

The confirmation view is replaced by a fake whose `value` is preset, so
the tests never have to wait on a real button press.
"""

from types import SimpleNamespace
from unittest import mock

import discord

from sausage_bot.util import config

with mock.patch.object(config.bot, "run", lambda *args, **kwargs: None):
    from sausage_bot import __main__ as main_module
    from sausage_bot.__main__ import LeaveGuildConfirm_view, leave_guild

ADMIN_GUILD_ID = "111"
TARGET_GUILD_ID = "222"


def _make_interaction(guild_id=ADMIN_GUILD_ID, user_id=42):
    "Minimal mock interaction - followup.send hands back an editable message"
    message = SimpleNamespace(edit=mock.AsyncMock())
    return SimpleNamespace(
        guild_id=guild_id,
        user=SimpleNamespace(id=user_id),
        response=SimpleNamespace(defer=mock.AsyncMock()),
        followup=SimpleNamespace(send=mock.AsyncMock(return_value=message)),
        _message=message,
    )


def _make_guild(leave_side_effect=None):
    "Duck-typed stand-in for discord.Guild - only .id/.name/.leave() are used"
    return SimpleNamespace(
        id=int(TARGET_GUILD_ID),
        name="Test Guild",
        leave=mock.AsyncMock(side_effect=leave_side_effect),
    )


def _fake_view_class(value):
    """
    Stand-in for LeaveGuildConfirm_view that resolves immediately with a
    preset `value`: True (confirmed), False (cancelled) or None (timeout)
    """

    class _FakeView:
        def __init__(self, user_id, timeout=60):
            self.user_id = user_id
            self.value = value

        async def wait(self):
            return None

    return _FakeView


def _http_exception():
    return discord.HTTPException(mock.Mock(status=400, reason="Bad Request"), "nope")


def _patch_env(guild, view_value=True, guilds_db=None):
    "Patch admin guild id, bot.get_guild, db lookup and the confirm view"
    if guilds_db is None:
        guilds_db = [{"guild_name": "Test Guild"}]
    return (
        mock.patch.object(config, "ADMIN_GUILD_ID", ADMIN_GUILD_ID),
        mock.patch.object(config.bot, "get_guild", return_value=guild),
        mock.patch.object(
            main_module.db_helper,
            "get_output",
            mock.AsyncMock(return_value=guilds_db),
        ),
        mock.patch.object(
            main_module, "LeaveGuildConfirm_view", _fake_view_class(view_value)
        ),
    )


async def _run(interaction, guild, view_value=True, guilds_db=None):
    patches = _patch_env(guild, view_value=view_value, guilds_db=guilds_db)
    with patches[0], patches[1], patches[2], patches[3]:
        await leave_guild.callback(interaction, TARGET_GUILD_ID)


# --- guard rails ---


async def test_rejects_use_outside_the_admin_guild():
    interaction = _make_interaction(guild_id="999")
    guild = _make_guild()
    await _run(interaction, guild)
    interaction.followup.send.assert_awaited_once()
    assert "admin guild" in interaction.followup.send.await_args.args[0]
    guild.leave.assert_not_awaited()


async def test_refuses_to_leave_the_admin_guild_itself():
    # Leaving the admin guild would lock the owner out of every
    # owner-only command, so it must be refused outright
    interaction = _make_interaction()
    guild = _make_guild()
    patches = _patch_env(guild)
    with patches[0], patches[1], patches[2], patches[3]:
        await leave_guild.callback(interaction, ADMIN_GUILD_ID)
    assert "Refusing" in interaction.followup.send.await_args.args[0]
    guild.leave.assert_not_awaited()


async def test_guild_the_bot_is_not_a_member_of_is_reported():
    # all_guilds_autocomplete also lists guilds with status `removed`
    interaction = _make_interaction()
    await _run(interaction, guild=None)
    assert "not a member" in interaction.followup.send.await_args.args[0]


async def test_non_numeric_guild_id_is_reported_not_crashed():
    interaction = _make_interaction()
    patches = _patch_env(_make_guild())
    with patches[0], patches[1], patches[2], patches[3]:
        await leave_guild.callback(interaction, "not-an-id")
    assert "not a member" in interaction.followup.send.await_args.args[0]


# --- confirmation outcomes ---


async def test_confirming_leaves_the_guild():
    interaction = _make_interaction()
    guild = _make_guild()
    await _run(interaction, guild, view_value=True)
    guild.leave.assert_awaited_once()
    assert "Left guild" in interaction._message.edit.await_args.kwargs["content"]


async def test_cancelling_does_not_leave_the_guild():
    interaction = _make_interaction()
    guild = _make_guild()
    await _run(interaction, guild, view_value=False)
    guild.leave.assert_not_awaited()
    assert "Cancelled" in interaction._message.edit.await_args.kwargs["content"]


async def test_timeout_does_not_leave_the_guild():
    interaction = _make_interaction()
    guild = _make_guild()
    await _run(interaction, guild, view_value=None)
    guild.leave.assert_not_awaited()
    assert "Timed out" in interaction._message.edit.await_args.kwargs["content"]


async def test_failing_leave_is_reported_to_the_user():
    interaction = _make_interaction()
    guild = _make_guild(leave_side_effect=_http_exception())
    await _run(interaction, guild, view_value=True)
    guild.leave.assert_awaited_once()
    assert "Could not leave" in interaction._message.edit.await_args.kwargs["content"]


async def test_guild_name_falls_back_to_discord_when_not_in_db():
    interaction = _make_interaction()
    guild = _make_guild()
    await _run(interaction, guild, view_value=True, guilds_db=[])
    assert "Test Guild" in interaction._message.edit.await_args.kwargs["content"]


# --- LeaveGuildConfirm_view ---


async def test_only_the_invoking_user_may_press_the_buttons():
    view = LeaveGuildConfirm_view(user_id=42)
    other = SimpleNamespace(
        user=SimpleNamespace(id=99),
        response=SimpleNamespace(send_message=mock.AsyncMock()),
    )
    assert await view.interaction_check(other) is False
    other.response.send_message.assert_awaited_once()


async def test_the_invoking_user_may_press_the_buttons():
    view = LeaveGuildConfirm_view(user_id=42)
    owner = SimpleNamespace(
        user=SimpleNamespace(id=42),
        response=SimpleNamespace(send_message=mock.AsyncMock()),
    )
    assert await view.interaction_check(owner) is True
    owner.response.send_message.assert_not_awaited()


async def test_timeout_disables_the_buttons():
    view = LeaveGuildConfirm_view(user_id=42)
    assert any(not btn.disabled for btn in view.children)
    await view.on_timeout()
    assert all(btn.disabled for btn in view.children)
