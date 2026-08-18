#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the /guild set_admin_guild command in __main__.py and the two
autocompletes it uses.

sausage_bot/__main__.py calls config.bot.run(...) at module level (no
`if __name__ == "__main__":` guard), so a plain import would try to
connect to Discord. config.bot.run is patched to a no-op for the
duration of the import below to avoid that.

The command is invoked via its `.callback` - the raw async function
discord.py stores on the app_commands.Command object once the group's
`.command()` decorator wraps it.

What these guard: the `channel` parameter is autocompleted but not
restricted, so its value can be a channel id picked from the list, the
name of an existing channel, or the name of one that doesn't exist yet.
Only the last of those may create anything, and only after the owner
confirms - a typo submits exactly like a deliberate new name.
"""

import contextlib
import discord
from types import SimpleNamespace
from unittest import mock

from sausage_bot.util import config

with mock.patch.object(config.bot, "run", lambda *args, **kwargs: None):
    from sausage_bot import __main__ as main_module
    from sausage_bot.__main__ import Guild

ADMIN_GUILD_ID = "111"
TARGET_GUILD_ID = "868902121834176513"
TARGET_GUILD_NAME = "Gutteklubben Ugrei"
EXISTING_CHANNEL_ID = "222333444555666777"
EXISTING_CHANNEL_NAME = "bot-log"

REGISTRY = [
    {
        "guild_id": TARGET_GUILD_ID,
        "guild_name": TARGET_GUILD_NAME,
        "status": "pending",
    },
    {
        "guild_id": ADMIN_GUILD_ID,
        "guild_name": "sausage-bot",
        "status": "approved",
    },
]


def _make_channel(channel_id, name):
    """
    A text channel stand-in. `spec=discord.TextChannel` matters: the
    command rejects anything that isn't a text channel via isinstance.
    """
    channel = mock.MagicMock(spec=discord.TextChannel)
    channel.id = int(channel_id)
    channel.name = name
    return channel


def _make_guild(guild_id, name, channels):
    guild = mock.MagicMock(spec=discord.Guild)
    guild.id = int(guild_id)
    guild.name = name
    guild.text_channels = channels
    guild.get_channel = lambda wanted: next(
        (channel for channel in channels if channel.id == wanted), None
    )
    return guild


def _make_bot(guilds):
    return SimpleNamespace(
        guilds=guilds,
        get_guild=lambda wanted: next(
            (guild for guild in guilds if guild.id == wanted), None
        ),
        user=SimpleNamespace(name="sausage-bot"),
    )


def _make_interaction(user_id=42):
    """
    Minimal mock interaction. `followup.send(wait=True)` has to hand back
    something with an `edit`, since the create flow edits its own
    confirmation prompt rather than sending a second message.
    """
    message = mock.AsyncMock()
    return SimpleNamespace(
        guild_id=ADMIN_GUILD_ID,
        user=SimpleNamespace(id=user_id),
        response=SimpleNamespace(defer=mock.AsyncMock()),
        followup=SimpleNamespace(send=mock.AsyncMock(return_value=message)),
        message=message,
    )


@contextlib.asynccontextmanager
async def _noop_locale_context(*args, **kwargs):
    yield


def _confirm_view(value):
    "Stand-in for CreateAdminChannelConfirm_view with a preset answer"

    class _View:
        def __init__(self, user_id, timeout=60):
            self.user_id = user_id
            self.value = value

        async def wait(self):
            return

    return _View


async def _run(interaction, guild, channel, confirm=True, created_channel=None):
    """
    Run the command with every outward-facing call patched, and hand back
    the mocks the assertions care about.
    """
    target_guild = _make_guild(
        TARGET_GUILD_ID,
        TARGET_GUILD_NAME,
        [_make_channel(EXISTING_CHANNEL_ID, EXISTING_CHANNEL_NAME)],
    )
    db = main_module.db_helper
    create_missing_channel = mock.AsyncMock(return_value=created_channel)
    with contextlib.ExitStack() as stack:
        for patch in (
            mock.patch.object(config, "bot", _make_bot([target_guild])),
            mock.patch.object(db, "get_output", mock.AsyncMock(return_value=REGISTRY)),
            mock.patch.object(db, "prep_table", mock.AsyncMock()),
            mock.patch.object(db, "empty_table", mock.AsyncMock()),
            mock.patch.object(db, "insert_many_all", mock.AsyncMock()),
            mock.patch.object(db, "update_fields", mock.AsyncMock()),
            mock.patch.object(db, "ensure_guild_tasks_rows", mock.AsyncMock()),
            mock.patch.object(db, "guild_locale_context", _noop_locale_context),
            mock.patch.object(
                main_module.discord_commands,
                "create_missing_channel",
                create_missing_channel,
            ),
            mock.patch.object(
                main_module,
                "CreateAdminChannelConfirm_view",
                _confirm_view(confirm),
            ),
            mock.patch.object(config, "ADMIN_GUILD_ID", ADMIN_GUILD_ID),
            mock.patch.object(config, "ADMIN_CHANNEL_ID", "000"),
        ):
            stack.enter_context(patch)
        await Guild.set_admin_guild.callback(None, interaction, guild, channel)
        return SimpleNamespace(
            insert_many_all=db.insert_many_all,
            empty_table=db.empty_table,
            update_fields=db.update_fields,
            ensure_guild_tasks_rows=db.ensure_guild_tasks_rows,
            create_missing_channel=create_missing_channel,
            target_guild=target_guild,
            # Read while the patches are still in place - mock.patch
            # restores the originals on the way out of the ExitStack
            admin_guild_id=config.ADMIN_GUILD_ID,
            admin_channel_id=config.ADMIN_CHANNEL_ID,
        )


def _last_sent(interaction):
    return interaction.followup.send.await_args.args[0]


def _last_edited(interaction):
    return interaction.message.edit.await_args.kwargs["content"]


# --- picking an existing channel ---


async def test_existing_channel_by_id_is_stored_without_creating_anything():
    interaction = _make_interaction()
    db = await _run(interaction, TARGET_GUILD_ID, EXISTING_CHANNEL_ID)
    db.create_missing_channel.assert_not_awaited()
    inserts = db.insert_many_all.await_args.kwargs["inserts"]
    assert inserts == [(TARGET_GUILD_ID, TARGET_GUILD_NAME, EXISTING_CHANNEL_ID)]
    # Single-row table: the old admin guild has to go before the new one
    db.empty_table.assert_awaited_once()
    assert EXISTING_CHANNEL_NAME in _last_sent(interaction)


async def test_existing_channel_by_name_resolves_to_that_channel():
    # Typing an existing channel name instead of picking the choice
    interaction = _make_interaction()
    db = await _run(interaction, TARGET_GUILD_ID, EXISTING_CHANNEL_NAME)
    db.create_missing_channel.assert_not_awaited()
    inserts = db.insert_many_all.await_args.kwargs["inserts"]
    assert inserts[0][2] == EXISTING_CHANNEL_ID


async def test_leading_hash_on_a_channel_name_is_ignored():
    interaction = _make_interaction()
    db = await _run(interaction, TARGET_GUILD_ID, "#" + EXISTING_CHANNEL_NAME)
    db.create_missing_channel.assert_not_awaited()
    assert db.insert_many_all.await_args.kwargs["inserts"][0][2] == EXISTING_CHANNEL_ID


async def test_guild_can_be_given_by_name():
    interaction = _make_interaction()
    db = await _run(interaction, TARGET_GUILD_NAME, EXISTING_CHANNEL_ID)
    assert db.insert_many_all.await_args.kwargs["inserts"][0][0] == TARGET_GUILD_ID


async def test_config_is_updated_in_memory_so_no_restart_is_needed():
    interaction = _make_interaction()
    db = await _run(interaction, TARGET_GUILD_ID, EXISTING_CHANNEL_ID)
    assert db.admin_guild_id == TARGET_GUILD_ID
    assert db.admin_channel_id == EXISTING_CHANNEL_ID


async def test_the_new_admin_guild_is_approved_in_the_registry():
    interaction = _make_interaction()
    db = await _run(interaction, TARGET_GUILD_ID, EXISTING_CHANNEL_ID)
    updates = dict(db.update_fields.await_args.kwargs["updates"])
    assert updates["status"] == "approved"
    assert db.update_fields.await_args.kwargs["where"] == ("guild_id", TARGET_GUILD_ID)
    db.ensure_guild_tasks_rows.assert_awaited_once_with(int(TARGET_GUILD_ID))


# --- creating a new channel ---


async def test_unknown_channel_name_is_created_after_confirmation():
    interaction = _make_interaction()
    new_channel = _make_channel("999888777666555444", "admin-log")
    db = await _run(
        interaction,
        TARGET_GUILD_ID,
        "admin-log",
        confirm=True,
        created_channel=new_channel,
    )
    db.create_missing_channel.assert_awaited_once()
    assert db.create_missing_channel.await_args.kwargs["channel_name"] == "admin-log"
    inserts = db.insert_many_all.await_args.kwargs["inserts"]
    assert inserts[0][2] == str(new_channel.id)
    assert "admin-log" in _last_edited(interaction)


async def test_the_autocomplete_create_choice_is_unwrapped():
    interaction = _make_interaction()
    new_channel = _make_channel("999888777666555444", "admin-log")
    db = await _run(
        interaction,
        TARGET_GUILD_ID,
        main_module.NEW_CHANNEL_PREFIX + "admin-log",
        created_channel=new_channel,
    )
    assert db.create_missing_channel.await_args.kwargs["channel_name"] == "admin-log"


async def test_cancelling_creates_nothing_and_leaves_the_admin_guild_alone():
    interaction = _make_interaction()
    db = await _run(interaction, TARGET_GUILD_ID, "typo-channel", confirm=False)
    db.create_missing_channel.assert_not_awaited()
    db.insert_many_all.assert_not_awaited()
    db.empty_table.assert_not_awaited()
    assert "typo-channel" in _last_edited(interaction)


async def test_timing_out_creates_nothing():
    interaction = _make_interaction()
    db = await _run(interaction, TARGET_GUILD_ID, "typo-channel", confirm=None)
    db.create_missing_channel.assert_not_awaited()
    db.insert_many_all.assert_not_awaited()


# --- guard rails ---


async def test_guild_the_bot_is_not_in_is_reported_and_writes_nothing():
    interaction = _make_interaction()
    db = await _run(interaction, "999999999999999999", EXISTING_CHANNEL_ID)
    assert "not a member" in _last_sent(interaction)
    db.insert_many_all.assert_not_awaited()
    db.empty_table.assert_not_awaited()


async def test_a_channel_id_that_no_longer_exists_is_not_treated_as_a_name():
    # An id can only come from the autocomplete, so a miss means the
    # channel was deleted - creating `#123456789` instead would be worse
    interaction = _make_interaction()
    db = await _run(interaction, TARGET_GUILD_ID, "123456789012345678")
    assert "No channel with id" in _last_sent(interaction)
    db.create_missing_channel.assert_not_awaited()
    db.insert_many_all.assert_not_awaited()


async def test_empty_channel_argument_writes_nothing():
    interaction = _make_interaction()
    db = await _run(interaction, TARGET_GUILD_ID, "   ")
    assert "No channel given" in _last_sent(interaction)
    db.insert_many_all.assert_not_awaited()


async def test_failing_to_create_the_channel_leaves_the_admin_guild_alone():
    interaction = _make_interaction()
    db = await _run(
        interaction, TARGET_GUILD_ID, "admin-log", created_channel=None
    )
    db.insert_many_all.assert_not_awaited()
    db.empty_table.assert_not_awaited()


# --- autocompletes ---


async def test_guild_autocomplete_offers_guilds_the_bot_is_in():
    guild = _make_guild(TARGET_GUILD_ID, TARGET_GUILD_NAME, [])
    with mock.patch.object(config, "bot", _make_bot([guild])):
        choices = await main_module.admin_guild_autocomplete(None, "gutte")
    assert [choice.value for choice in choices] == [TARGET_GUILD_ID]
    assert TARGET_GUILD_ID in choices[0].name


async def test_channel_autocomplete_is_empty_until_a_guild_is_picked():
    guild = _make_guild(TARGET_GUILD_ID, TARGET_GUILD_NAME, [])
    interaction = SimpleNamespace(namespace=SimpleNamespace(guild=None))
    with mock.patch.object(config, "bot", _make_bot([guild])):
        assert await main_module.admin_channel_autocomplete(interaction, "") == []


async def test_channel_autocomplete_lists_the_target_guilds_channels():
    channel = _make_channel(EXISTING_CHANNEL_ID, EXISTING_CHANNEL_NAME)
    guild = _make_guild(TARGET_GUILD_ID, TARGET_GUILD_NAME, [channel])
    interaction = SimpleNamespace(namespace=SimpleNamespace(guild=TARGET_GUILD_ID))
    with mock.patch.object(config, "bot", _make_bot([guild])):
        choices = await main_module.admin_channel_autocomplete(
            interaction, EXISTING_CHANNEL_NAME
        )
    # Exact match, so no "create this" choice on top
    assert [choice.value for choice in choices] == [EXISTING_CHANNEL_ID]
    assert choices[0].name == "#" + EXISTING_CHANNEL_NAME


async def test_channel_autocomplete_reads_the_target_guild_not_the_invoking_one():
    # The whole point of going through `interaction.namespace`: the
    # command runs in the admin guild but has to list channels in the
    # guild being promoted. A ChannelSelect or a TextChannel parameter
    # would have returned #general here.
    invoking_channel = _make_channel("1", "general")
    invoking_guild = _make_guild(ADMIN_GUILD_ID, "sausage-bot", [invoking_channel])
    target_channel = _make_channel(EXISTING_CHANNEL_ID, EXISTING_CHANNEL_NAME)
    target_guild = _make_guild(TARGET_GUILD_ID, TARGET_GUILD_NAME, [target_channel])
    interaction = SimpleNamespace(
        guild=invoking_guild,
        guild_id=ADMIN_GUILD_ID,
        namespace=SimpleNamespace(guild=TARGET_GUILD_ID),
    )
    with mock.patch.object(config, "bot", _make_bot([invoking_guild, target_guild])):
        choices = await main_module.admin_channel_autocomplete(interaction, "")
    assert [choice.value for choice in choices] == [EXISTING_CHANNEL_ID]
    assert "#general" not in [choice.name for choice in choices]


async def test_channel_autocomplete_works_with_a_real_discord_namespace():
    # Guards the discord.py contract the above relies on: every option
    # the user has already filled in is exposed on `interaction.namespace`
    # under its parameter name, while `channel` is still being typed.
    target_channel = _make_channel(EXISTING_CHANNEL_ID, EXISTING_CHANNEL_NAME)
    target_guild = _make_guild(TARGET_GUILD_ID, TARGET_GUILD_NAME, [target_channel])
    namespace = discord.app_commands.Namespace(
        mock.MagicMock(spec=discord.Interaction),
        {},
        [
            {"name": "guild", "type": 3, "value": TARGET_GUILD_ID},
            {"name": "channel", "type": 3, "value": "bot", "focused": True},
        ],
    )
    with mock.patch.object(config, "bot", _make_bot([target_guild])):
        choices = await main_module.admin_channel_autocomplete(
            SimpleNamespace(namespace=namespace), "bot"
        )
    assert EXISTING_CHANNEL_ID in [choice.value for choice in choices]


async def test_channel_autocomplete_offers_to_create_an_unknown_name():
    channel = _make_channel(EXISTING_CHANNEL_ID, EXISTING_CHANNEL_NAME)
    guild = _make_guild(TARGET_GUILD_ID, TARGET_GUILD_NAME, [channel])
    interaction = SimpleNamespace(namespace=SimpleNamespace(guild=TARGET_GUILD_ID))
    with mock.patch.object(config, "bot", _make_bot([guild])):
        choices = await main_module.admin_channel_autocomplete(interaction, "bot-l")
    assert choices[0].value == main_module.NEW_CHANNEL_PREFIX + "bot-l"
    assert choices[1].value == EXISTING_CHANNEL_ID
