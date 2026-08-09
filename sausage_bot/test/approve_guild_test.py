#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the /guild approve command in __main__.py and the guild
lookup helpers it shares with the guild autocompletes.

sausage_bot/__main__.py calls config.bot.run(...) at module level (no
`if __name__ == "__main__":` guard), so a plain import would try to
connect to Discord. config.bot.run is patched to a no-op for the
duration of the import below to avoid that.

The command is invoked via its `.callback` - the raw async function
discord.py stores on the app_commands.Command object once the group's
`.command()` decorator wraps it - to exercise the command logic
directly.

The regression these guard: the autocomplete labels its choices with
the guild *name* but submits the guild *id* as the value. Submitting
the typed label instead of picking a choice sent a guild name into the
`guild_id` parameter, which used to UPDATE nothing, create a bogus
`db/guild_<name>/` directory and then raise IndexError on an empty
lookup result.
"""

from types import SimpleNamespace
from unittest import mock

from sausage_bot.util import config

with mock.patch.object(config.bot, "run", lambda *args, **kwargs: None):
    from sausage_bot import __main__ as main_module
    from sausage_bot.__main__ import Guild

ADMIN_GUILD_ID = "111"
TARGET_GUILD_ID = "868902121834176513"
TARGET_GUILD_NAME = "Gutteklubben Ugrei"

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


def _make_interaction(guild_id=ADMIN_GUILD_ID, user_id=42):
    "Minimal mock interaction - only defer/followup.send are used"
    return SimpleNamespace(
        guild_id=guild_id,
        user=SimpleNamespace(id=user_id),
        response=SimpleNamespace(defer=mock.AsyncMock()),
        followup=SimpleNamespace(send=mock.AsyncMock()),
    )


def _patch_env(registry=None):
    "Patch admin guild id and every db call /guild approve makes"
    if registry is None:
        registry = REGISTRY
    return (
        mock.patch.object(config, "ADMIN_GUILD_ID", ADMIN_GUILD_ID),
        mock.patch.object(
            main_module.db_helper, "get_output", mock.AsyncMock(return_value=registry)
        ),
        mock.patch.object(main_module.db_helper, "update_fields", mock.AsyncMock()),
        mock.patch.object(main_module.db_helper, "prep_table", mock.AsyncMock()),
        mock.patch.object(
            main_module.db_helper, "ensure_guild_tasks_rows", mock.AsyncMock()
        ),
    )


async def _run(interaction, guild_id, registry=None):
    "Run the command and hand back the patched db_helper mocks"
    patches = _patch_env(registry)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        await Guild.approve_guild.callback(None, interaction, guild_id)
        return SimpleNamespace(
            update_fields=main_module.db_helper.update_fields,
            prep_table=main_module.db_helper.prep_table,
            ensure_guild_tasks_rows=main_module.db_helper.ensure_guild_tasks_rows,
        )


# --- guard rails ---


async def test_rejects_use_outside_the_admin_guild():
    interaction = _make_interaction(guild_id="999")
    db = await _run(interaction, TARGET_GUILD_ID)
    assert "admin guild" in interaction.followup.send.await_args.args[0]
    db.update_fields.assert_not_awaited()


# --- resolving what the user submitted ---


async def test_approving_by_guild_id_updates_the_registry():
    interaction = _make_interaction()
    db = await _run(interaction, TARGET_GUILD_ID)
    where = db.update_fields.await_args.kwargs["where"]
    assert where == ("guild_id", TARGET_GUILD_ID)
    msg = interaction.followup.send.await_args.args[0]
    assert TARGET_GUILD_NAME in msg
    assert TARGET_GUILD_ID in msg


async def test_approving_by_guild_name_resolves_to_the_id():
    # Typing the autocomplete's label instead of picking the choice
    # submits the guild name - it must still hit the right row
    interaction = _make_interaction()
    db = await _run(interaction, TARGET_GUILD_NAME)
    assert db.update_fields.await_args.kwargs["where"] == ("guild_id", TARGET_GUILD_ID)
    db.prep_table.assert_awaited_once()
    assert db.prep_table.await_args.kwargs["guild_id"] == TARGET_GUILD_ID
    db.ensure_guild_tasks_rows.assert_awaited_once_with(TARGET_GUILD_ID)


async def test_guild_name_match_is_case_insensitive():
    interaction = _make_interaction()
    db = await _run(interaction, TARGET_GUILD_NAME.upper())
    assert db.update_fields.await_args.kwargs["where"] == ("guild_id", TARGET_GUILD_ID)


async def test_unknown_guild_is_reported_and_writes_nothing():
    # The bug: an unresolvable value used to update nothing, create a
    # `db/guild_<garbage>/` directory and then crash on IndexError
    interaction = _make_interaction()
    db = await _run(interaction, "no-such-guild")
    assert "No guild matching" in interaction.followup.send.await_args.args[0]
    db.update_fields.assert_not_awaited()
    db.prep_table.assert_not_awaited()
    db.ensure_guild_tasks_rows.assert_not_awaited()


async def test_empty_registry_is_reported_not_crashed():
    interaction = _make_interaction()
    db = await _run(interaction, TARGET_GUILD_ID, registry=[])
    assert "No guild matching" in interaction.followup.send.await_args.args[0]
    db.update_fields.assert_not_awaited()


# --- autocomplete labels ---


async def test_choice_label_shows_name_and_id():
    label = main_module.guild_choice_label(TARGET_GUILD_NAME, TARGET_GUILD_ID)
    assert label == "{} ({})".format(TARGET_GUILD_NAME, TARGET_GUILD_ID)


async def test_choice_label_stays_within_discords_100_char_limit():
    # Discord rejects the whole autocomplete response if a label is too
    # long, which would leave the user with no choices to pick at all
    label = main_module.guild_choice_label("a" * 200, TARGET_GUILD_ID)
    assert len(label) <= 100
    assert label.endswith("({})".format(TARGET_GUILD_ID))


async def test_pending_autocomplete_submits_the_guild_id_as_value():
    with mock.patch.object(
        main_module.db_helper, "get_output", mock.AsyncMock(return_value=[REGISTRY[0]])
    ):
        choices = await main_module.pending_guilds_autocomplete(
            _make_interaction(), TARGET_GUILD_NAME.lower()
        )
    assert [choice.value for choice in choices] == [TARGET_GUILD_ID]
    assert TARGET_GUILD_ID in choices[0].name
