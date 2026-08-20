#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the /set_profile and /reset_profile commands in __main__.py,
and the shared _has_manage_bot_profile_permission() gate they both use.

Supersedes main_botprofile_permission_test.py (delete that file) - the
command was renamed from /botprofile to /set_profile, and /reset_profile
was added alongside it.

sausage_bot/__main__.py calls config.bot.run(...) at module level (no
`if __name__ == "__main__":` guard), so a plain import would try to
connect to Discord. config.bot.run is patched to a no-op for the
duration of the import below to avoid that - the patch only needs to be
active while the module is first imported (and cached in sys.modules).

Each command is invoked via its `.callback` - the raw async function
discord.py stores on the app_commands.Command object once `@tree.command`
wraps it - to exercise the actual command logic directly, without going
through discord.py's own interaction-dispatch machinery.
"""

from types import SimpleNamespace
from unittest import mock

import discord

from sausage_bot.util import config

with mock.patch.object(config.bot, "run", lambda *args, **kwargs: None):
    from sausage_bot.__main__ import (
        _has_manage_bot_profile_permission,
        Profile,
    )


def _make_interaction(**perms):
    "Minimal mock interaction carrying the guild permissions given in `perms`"
    permissions = discord.Permissions(**perms)
    return SimpleNamespace(
        user=SimpleNamespace(guild_permissions=permissions),
        response=SimpleNamespace(send_message=mock.AsyncMock(), defer=mock.AsyncMock()),
        followup=SimpleNamespace(send=mock.AsyncMock()),
        guild=SimpleNamespace(me=SimpleNamespace(edit=mock.AsyncMock())),
    )


def _make_attachment(content: bytes):
    "Duck-typed stand-in for discord.Attachment - only .read() is used"
    return SimpleNamespace(read=mock.AsyncMock(return_value=content))


def _http_exception():
    return discord.HTTPException(mock.Mock(status=400, reason="Bad Request"), "nope")


# --- _has_manage_bot_profile_permission (shared gate) ---


def test_administrator_has_permission():
    interaction = _make_interaction(administrator=True)
    assert _has_manage_bot_profile_permission(interaction) is True


def test_manage_nicknames_has_permission():
    interaction = _make_interaction(manage_nicknames=True)
    assert _has_manage_bot_profile_permission(interaction) is True


def test_unrelated_permission_alone_is_not_enough():
    # manage_guild is a plausible "close but wrong" permission to confuse
    # with manage_nicknames - make sure it's specifically rejected
    interaction = _make_interaction(manage_guild=True)
    assert _has_manage_bot_profile_permission(interaction) is False


def test_no_permissions_is_denied():
    interaction = _make_interaction()
    assert _has_manage_bot_profile_permission(interaction) is False


# --- /set_profile ---


async def test_set_profile_denies_without_permission():
    interaction = _make_interaction()
    await Profile.set_profile.callback(None, interaction, nickname="New name")
    interaction.response.send_message.assert_awaited_once()
    interaction.guild.me.edit.assert_not_awaited()


async def test_set_profile_requires_at_least_one_field():
    interaction = _make_interaction(administrator=True)
    await Profile.set_profile.callback(None, interaction)
    interaction.response.send_message.assert_awaited_once()
    interaction.response.defer.assert_not_awaited()
    interaction.guild.me.edit.assert_not_awaited()


async def test_set_profile_only_sends_the_provided_field():
    interaction = _make_interaction(administrator=True)
    await Profile.set_profile.callback(None, interaction, nickname="New name")
    interaction.guild.me.edit.assert_awaited_once_with(nick="New name")


async def test_set_profile_reads_attachments_into_bytes():
    interaction = _make_interaction(administrator=True)
    avatar = _make_attachment(b"avatar-bytes")
    banner = _make_attachment(b"banner-bytes")
    await Profile.set_profile.callback(None, interaction, avatar=avatar, banner=banner)
    interaction.guild.me.edit.assert_awaited_once_with(
        avatar=b"avatar-bytes", banner=b"banner-bytes"
    )


async def test_set_profile_combines_all_four_fields():
    interaction = _make_interaction(manage_nicknames=True)
    avatar = _make_attachment(b"avatar-bytes")
    banner = _make_attachment(b"banner-bytes")
    await Profile.set_profile.callback(
        None,
        interaction,
        nickname="New name",
        avatar=avatar,
        banner=banner,
        bio="New bio",
    )
    interaction.guild.me.edit.assert_awaited_once_with(
        nick="New name",
        avatar=b"avatar-bytes",
        banner=b"banner-bytes",
        bio="New bio",
    )


async def test_set_profile_reports_discord_error():
    interaction = _make_interaction(administrator=True)
    interaction.guild.me.edit.side_effect = _http_exception()
    await Profile.set_profile.callback(None, interaction, nickname="New name")
    interaction.followup.send.assert_awaited_once()


# --- /reset_profile ---


async def test_reset_profile_denies_without_permission():
    interaction = _make_interaction()
    await Profile.reset_profile.callback(None, interaction)
    interaction.response.send_message.assert_awaited_once()
    interaction.guild.me.edit.assert_not_awaited()


async def test_reset_profile_clears_all_four_fields():
    interaction = _make_interaction(manage_nicknames=True)
    await Profile.reset_profile.callback(None, interaction)
    interaction.guild.me.edit.assert_awaited_once_with(
        nick=None, avatar=None, banner=None, bio=None
    )


async def test_reset_profile_reports_discord_error():
    interaction = _make_interaction(administrator=True)
    interaction.guild.me.edit.side_effect = _http_exception()
    await Profile.reset_profile.callback(None, interaction)
    interaction.followup.send.assert_awaited_once()
