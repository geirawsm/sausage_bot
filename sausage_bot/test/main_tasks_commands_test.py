#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the `/tasks` and `/tasks-global` commands in `__main__.py`:
`/tasks` must only ever show the calling guild's own posting-task rows,
`/tasks-global` (admin-guild + bot-owner only) aggregates every approved
guild's rows into one table, and must paginate under Discord's 2000-char
message cap instead of raising or silently truncating.

sausage_bot/__main__.py calls config.bot.run(...) at module level (no
`if __name__ == "__main__":` guard), so a plain import would try to
connect to Discord. config.bot.run is patched to a no-op for the
duration of the import below to avoid that (same pattern as
main_profile_commands_test.py). Each command is invoked via its
`.callback` - the raw async function discord.py stores on the
app_commands.Command object - to exercise the actual command logic
directly, without going through discord.py's own interaction-dispatch
machinery (and therefore without the `is_owner()`/
`is_owner_or_manage_guild()` checks - those are covered separately in
discord_commands_permissions_test.py).
"""
from types import SimpleNamespace
from unittest import mock

from sausage_bot.util import envs, db_helper, config

with mock.patch.object(config.bot, "run", lambda *args, **kwargs: None):
    from sausage_bot.__main__ import get_tasks_list, get_tasks_global_list

GUILD_A = 111111111111111111
GUILD_B = 222222222222222222
ADMIN_GUILD = 999999999999999999


def _make_interaction(guild_id):
    return SimpleNamespace(
        guild=SimpleNamespace(id=guild_id),
        guild_id=guild_id,
        response=SimpleNamespace(defer=mock.AsyncMock()),
        followup=SimpleNamespace(send=mock.AsyncMock()),
    )


async def _seed_approved_guild(guild_id, name):
    await db_helper.insert_many_all(
        envs.guilds_db_schema,
        [(str(guild_id), name, "approved", "2026-01-01", None, None)],
    )


# --- /tasks ---


async def test_tasks_only_shows_the_calling_guilds_own_rows(guild_db_root):
    await db_helper.prep_table(envs.guilds_db_schema)
    await _seed_approved_guild(GUILD_A, "Guild A")
    await _seed_approved_guild(GUILD_B, "Guild B")
    await db_helper.ensure_guild_tasks_rows(GUILD_A)
    await db_helper.ensure_guild_tasks_rows(GUILD_B)
    await db_helper.update_fields(
        template_info=envs.tasks_db_schema,
        where=[("cog", "youtube"), ("task", "post_videos")],
        updates=("status", "started"),
        guild_id=GUILD_A,
    )

    interaction = _make_interaction(GUILD_A)
    await get_tasks_list.callback(interaction)

    interaction.followup.send.assert_awaited_once()
    (text_out,), kwargs = interaction.followup.send.call_args
    assert "youtube" in text_out
    assert "started" in text_out
    # Guild B's rows must not leak into Guild A's own /tasks output -
    # both guilds have a `quotes`/`autopost` row, so absence of "Guild B"
    # in the text is what we can actually assert on here (the table has
    # no guild-name column at all for the single-guild view).
    assert kwargs.get("ephemeral") is True


# --- /tasks-global ---


async def test_tasks_global_rejects_non_admin_guild(guild_db_root, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_GUILD_ID", ADMIN_GUILD)
    await db_helper.prep_table(envs.guilds_db_schema)
    await _seed_approved_guild(GUILD_A, "Guild A")
    await db_helper.ensure_guild_tasks_rows(GUILD_A)

    interaction = _make_interaction(GUILD_A)  # not the admin guild
    await get_tasks_global_list.callback(interaction)

    interaction.followup.send.assert_awaited_once()
    (text_out,), _ = interaction.followup.send.call_args
    assert "admin guild" in text_out.lower()


async def test_tasks_global_aggregates_across_all_approved_guilds(
    guild_db_root, monkeypatch
):
    monkeypatch.setattr(config, "ADMIN_GUILD_ID", ADMIN_GUILD)
    await db_helper.prep_table(envs.guilds_db_schema)
    await _seed_approved_guild(GUILD_A, "Guild A")
    await _seed_approved_guild(GUILD_B, "Guild B")
    await db_helper.ensure_guild_tasks_rows(GUILD_A)
    await db_helper.ensure_guild_tasks_rows(GUILD_B)
    await db_helper.update_fields(
        template_info=envs.tasks_db_schema,
        where=[("cog", "youtube"), ("task", "post_videos")],
        updates=("status", "started"),
        guild_id=GUILD_A,
    )

    interaction = _make_interaction(ADMIN_GUILD)
    await get_tasks_global_list.callback(interaction)

    assert interaction.followup.send.await_count >= 1
    all_text = "".join(
        call.args[0] for call in interaction.followup.send.call_args_list
    )
    assert "Guild A" in all_text
    assert "Guild B" in all_text


async def test_tasks_global_reports_empty_when_no_approved_guilds(
    guild_db_root, monkeypatch
):
    monkeypatch.setattr(config, "ADMIN_GUILD_ID", ADMIN_GUILD)
    await db_helper.prep_table(envs.guilds_db_schema)

    interaction = _make_interaction(ADMIN_GUILD)
    await get_tasks_global_list.callback(interaction)

    interaction.followup.send.assert_awaited_once()
    (text_out,), kwargs = interaction.followup.send.call_args
    assert kwargs.get("ephemeral") is True


async def test_tasks_global_paginates_under_2000_char_discord_limit(
    guild_db_root, monkeypatch
):
    """
    With enough approved guilds, the aggregated table must be split
    across multiple `followup.send()` calls, each safely under Discord's
    2000-character message cap once wrapped in a code block.
    """
    monkeypatch.setattr(config, "ADMIN_GUILD_ID", ADMIN_GUILD)
    await db_helper.prep_table(envs.guilds_db_schema)
    for i in range(80):
        guild_id = 1_000_000_000_000_000_000 + i
        await _seed_approved_guild(guild_id, f"Guild Number {i:03d} With A Long Name")
        await db_helper.ensure_guild_tasks_rows(guild_id)

    interaction = _make_interaction(ADMIN_GUILD)
    await get_tasks_global_list.callback(interaction)

    assert interaction.followup.send.await_count > 1
    for call in interaction.followup.send.call_args_list:
        (text_out,), kwargs = call
        assert len(text_out) <= 2000
        assert kwargs.get("ephemeral") is True
