#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for suggesting quotes (issue #66).

Members without "Manage Server" can suggest a quote through the
"Suggest quote" context menu. The suggestion is stored as `pending` in the
`suggest` table with a JSON snapshot of its rows, posted in the suggest
channel with approve/deny buttons, and only copied into `quote`,
`quote_content` and `quote_img` once a moderator approves it.

All tests use the `guild_db_root` fixture (see conftest.py), so nothing
here touches real bot data.
"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from sausage_bot.util import envs, db_helper, discord_commands
from sausage_bot.cogs import quote

GUILD = 666666666666666666
SOURCE_CHANNEL = 777777777777777777
SUGGEST_CHANNEL = 888888888888888888
# The button's custom_id must match `DynamicSuggestButton`'s template
POST_UUID = "0f0e5c2a-1b2c-4d3e-8f90-123456789abc"


async def _prep_quote_tables():
    for schema in (
        envs.quote_db_schema,
        envs.quote_content_db_schema,
        envs.quote_img_db_schema,
        envs.quote_db_log_schema,
        envs.quote_suggest_db_schema,
    ):
        await db_helper.prep_table(schema, guild_id=GUILD)
    await db_helper.prep_table(
        envs.quote_db_settings_schema,
        inserts=envs.quote_db_settings_schema["inserts"],
        guild_id=GUILD,
    )


def _msg(msg_id, author_id, author_name, content):
    return SimpleNamespace(
        id=msg_id,
        author=SimpleNamespace(id=author_id, name=author_name),
        content=content,
        attachments=[],
    )


async def _insert_pending(suggest_uuid, content_rows, img_rows=[]):
    await db_helper.insert_many_all(
        envs.quote_suggest_db_schema,
        [
            (
                suggest_uuid,
                SOURCE_CHANNEL,
                "general",
                "2026-01-01 10:00:00+00:00",
                42,
                "pending",
                None,
                json.dumps({"content": content_rows, "imgs": img_rows}),
            )
        ],
        guild_id=GUILD,
    )


async def _suggestion(suggest_uuid):
    rows = await db_helper.get_output(
        envs.quote_suggest_db_schema, where=[("uuid", suggest_uuid)], guild_id=GUILD
    )
    return rows[0] if rows else None


async def _count(schema):
    return len(await db_helper.get_output(schema, guild_id=GUILD))


def test_build_quote_rows_keeps_selection_order():
    msgs = [_msg(1, 10, "anna", "first"), _msg(2, 20, "bob", "second")]
    content_rows, img_rows = quote.build_quote_rows("u-1", msgs)
    assert content_rows == [
        ("u-1", 1, 10, "anna", "first", 0),
        ("u-1", 2, 20, "bob", "second", 1),
    ]
    assert img_rows == []


def test_is_suggest_enabled():
    assert quote.is_suggest_enabled({"suggest_enabled": "True"})
    assert quote.is_suggest_enabled({"suggest_enabled": "true"})
    assert not quote.is_suggest_enabled({"suggest_enabled": "False"})
    assert not quote.is_suggest_enabled({"suggest_enabled": ""})
    assert not quote.is_suggest_enabled({})


async def test_new_settings_are_added_to_an_existing_settings_table(guild_db_root):
    # A guild created before this feature has the old settings rows only
    old_schema = dict(envs.quote_db_settings_schema)
    old_schema["inserts"] = [
        row
        for row in envs.quote_db_settings_schema["inserts"]
        if not row[0].startswith("suggest_")
    ]
    await db_helper.prep_table(
        old_schema, inserts=old_schema["inserts"], guild_id=GUILD
    )
    await _prep_quote_tables()
    settings = await quote.get_quote_settings(GUILD)
    assert settings["suggest_enabled"] == "False"
    assert settings["suggest_channel"] == ""


async def test_approve_saves_the_quote_and_marks_it_approved(guild_db_root):
    await _prep_quote_tables()
    await _insert_pending(
        "u-approve",
        [["u-approve", 1, 10, "anna", "first", 0], ["u-approve", 2, 20, "bob", "b", 1]],
        img_rows=[["1", 1, "QUJD"]],
    )

    status, quote_number = await quote.handle_suggestion(GUILD, "u-approve", "approve")

    assert status == "approved"
    assert quote_number == 1
    assert (await _suggestion("u-approve"))["status"] == "approved"
    assert await _count(envs.quote_db_schema) == 1
    assert await _count(envs.quote_content_db_schema) == 2
    assert await _count(envs.quote_img_db_schema) == 1
    saved = await db_helper.get_output(envs.quote_db_schema, guild_id=GUILD)
    assert saved[0]["uuid"] == "u-approve"
    assert saved[0]["channel_backup"] == "general"


async def test_a_handled_suggestion_is_not_handled_twice(guild_db_root):
    await _prep_quote_tables()
    await _insert_pending("u-twice", [["u-twice", 1, 10, "anna", "first", 0]])

    await quote.handle_suggestion(GUILD, "u-twice", "approve")
    status, quote_number = await quote.handle_suggestion(GUILD, "u-twice", "approve")

    assert status == "already_handled"
    assert quote_number is None
    assert await _count(envs.quote_db_schema) == 1
    status, _ = await quote.handle_suggestion(GUILD, "u-twice", "deny")
    assert status == "already_handled"
    assert (await _suggestion("u-twice"))["status"] == "approved"


async def test_deny_does_not_save_the_quote(guild_db_root):
    await _prep_quote_tables()
    await _insert_pending("u-deny", [["u-deny", 1, 10, "anna", "first", 0]])

    status, quote_number = await quote.handle_suggestion(GUILD, "u-deny", "deny")

    assert status == "denied"
    assert quote_number is None
    assert (await _suggestion("u-deny"))["status"] == "denied"
    assert await _count(envs.quote_db_schema) == 0
    assert await _count(envs.quote_content_db_schema) == 0


async def test_unknown_suggestion_is_reported_missing(guild_db_root):
    await _prep_quote_tables()
    status, _ = await quote.handle_suggestion(GUILD, "u-nope", "approve")
    assert status == "missing"


async def test_suggest_is_refused_when_disabled(guild_db_root):
    await _prep_quote_tables()
    interaction = MagicMock()
    interaction.guild.id = GUILD
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()

    await quote.quote_suggest.callback(interaction, MagicMock())

    interaction.response.send_message.assert_awaited_once()
    interaction.response.send_modal.assert_not_awaited()
    assert await _count(envs.quote_suggest_db_schema) == 0


async def test_post_suggestion_stores_pending_and_posts_buttons(guild_db_root):
    await _prep_quote_tables()
    review_msg = SimpleNamespace(id=999)
    suggest_channel = MagicMock()
    suggest_channel.id = SUGGEST_CHANNEL
    suggest_channel.send = AsyncMock(return_value=review_msg)
    guild = MagicMock()
    guild.id = GUILD
    guild.text_channels = [suggest_channel]
    guild.get_channel.return_value = suggest_channel
    source_channel = SimpleNamespace(id=SOURCE_CHANNEL, name="general")
    suggested_by = SimpleNamespace(id=42, mention="<@42>")

    out = await quote.post_suggestion(
        guild=guild,
        suggest_uuid=POST_UUID,
        channel=source_channel,
        created_at="2026-01-01 10:00:00+00:00",
        suggested_by=suggested_by,
        content_rows=[(POST_UUID, 1, 10, "anna", "first", 0)],
        img_rows=[],
        suggest_channel_value=str(SUGGEST_CHANNEL),
    )

    assert out is review_msg
    suggestion = await _suggestion(POST_UUID)
    assert suggestion["status"] == "pending"
    assert suggestion["review_msg_id"] == 999
    assert suggestion["suggested_by"] == 42
    view = suggest_channel.send.await_args.kwargs["view"]
    custom_ids = sorted(item.custom_id for item in view.children)
    assert custom_ids == [
        f"quote.suggest:approve:{POST_UUID}",
        f"quote.suggest:deny:{POST_UUID}",
        f"quote.suggest:edit:{POST_UUID}",
    ]
    # Nothing is a real quote until it has been approved
    assert await _count(envs.quote_db_schema) == 0


async def test_only_owner_or_manage_guild_can_review():
    interaction = MagicMock()
    interaction.client.is_owner = AsyncMock(return_value=False)
    interaction.user.guild_permissions.manage_guild = False
    assert not await quote.can_review_suggestions(interaction)
    interaction.user.guild_permissions.manage_guild = True
    assert await quote.can_review_suggestions(interaction)


def _settings_interaction(text_channels=[]):
    interaction = MagicMock()
    interaction.guild.id = GUILD
    interaction.guild.name = "Guild"
    interaction.guild.text_channels = text_channels
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


async def test_change_suggest_channel_to_missing_name_offers_to_create(
    guild_db_root,
):
    await _prep_quote_tables()
    interaction = _settings_interaction()

    await quote.Quotes.change_setting.callback(
        MagicMock(), interaction, name_of_setting="suggest_channel", value_in="#forslag"
    )

    kwargs = interaction.followup.send.await_args.kwargs
    view = kwargs["view"]
    assert isinstance(view, discord_commands.CreateChannelView)
    assert view.channel_name == "forslag"
    # Nothing is stored until one of the view's buttons has made the channel
    assert (await quote.get_quote_settings(GUILD))["suggest_channel"] == ""


async def test_change_suggest_channel_to_existing_name_stores_its_id(guild_db_root):
    await _prep_quote_tables()
    existing = SimpleNamespace(id=SUGGEST_CHANNEL, name="forslag")
    interaction = _settings_interaction(text_channels=[existing])

    await quote.Quotes.change_setting.callback(
        MagicMock(), interaction, name_of_setting="suggest_channel", value_in="forslag"
    )

    assert "view" not in interaction.followup.send.await_args.kwargs
    settings = await quote.get_quote_settings(GUILD)
    assert settings["suggest_channel"] == str(SUGGEST_CHANNEL)


async def test_fresh_channel_from_view_is_stored_in_the_setting(guild_db_root):
    await _prep_quote_tables()
    new_channel = SimpleNamespace(id=SUGGEST_CHANNEL, mention="<#1>", name="forslag")
    interaction = MagicMock()
    interaction.guild.id = GUILD
    interaction.guild.create_text_channel = AsyncMock(return_value=new_channel)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    view = discord_commands.CreateChannelView(
        "forslag",
        on_created=quote.channel_setting_saver("suggest_channel"),
        modal_title="title",
        modal_name_label="label",
    )

    await view.fresh.callback(interaction)

    assert interaction.guild.create_text_channel.await_args.kwargs["name"] == "forslag"
    interaction.followup.send.assert_awaited_once()
    settings = await quote.get_quote_settings(GUILD)
    assert settings["suggest_channel"] == str(SUGGEST_CHANNEL)
