#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exercises the multi-guild DB-routing layer added to `envs`/`db_helper`:
per-guild database file resolution, physical data isolation between two
guilds, the guild-approval gate used by bot-wide event handlers, and the
locale/timezone context manager that backs `I18N.t()`/`get_dt()`.

All tests use the `guild_db_root` fixture (see conftest.py), which points
`envs.DB_DIR` at a throwaway tmp_path directory - nothing here touches
real bot data.
"""
import pytest

from sausage_bot.util import envs, db_helper, guild_context

GUILD_A = 111111111111111111
GUILD_B = 222222222222222222


def test_resolve_db_file_global_scope_ignores_guild_id(guild_db_root):
    path = envs.resolve_db_file(envs.guilds_db_schema)
    assert path == envs.guilds_db_schema["db_file"]
    assert path == str(guild_db_root / "guilds.sqlite")


def test_resolve_db_file_guild_scope_requires_guild_id(guild_db_root):
    with pytest.raises(ValueError):
        envs.resolve_db_file(envs.dilemmas_db_schema)


def test_resolve_db_file_guild_scope_joins_guild_dir(guild_db_root):
    path = envs.resolve_db_file(envs.dilemmas_db_schema, guild_id=GUILD_A)
    assert path == str(guild_db_root / f"guild_{GUILD_A}" / "dilemmas.sqlite")


def test_guild_db_dir_is_unique_per_guild(guild_db_root):
    assert envs.guild_db_dir(GUILD_A) != envs.guild_db_dir(GUILD_B)
    assert str(GUILD_A) in str(envs.guild_db_dir(GUILD_A))


async def test_two_guilds_get_fully_isolated_databases(guild_db_root):
    await db_helper.prep_table(envs.dilemmas_db_schema, guild_id=GUILD_A)
    await db_helper.prep_table(envs.dilemmas_db_schema, guild_id=GUILD_B)
    await db_helper.insert_many_all(
        envs.dilemmas_db_schema, [("a-1", "Only in guild A")], guild_id=GUILD_A
    )
    await db_helper.insert_many_all(
        envs.dilemmas_db_schema,
        [("b-1", "In guild B"), ("b-2", "Also in guild B")],
        guild_id=GUILD_B,
    )

    rows_a = await db_helper.get_output(envs.dilemmas_db_schema, guild_id=GUILD_A)
    rows_b = await db_helper.get_output(envs.dilemmas_db_schema, guild_id=GUILD_B)

    assert len(rows_a) == 1
    assert len(rows_b) == 2
    assert all(row["dilemmas_text"] != "Only in guild A" for row in rows_b)

    file_a = envs.resolve_db_file(envs.dilemmas_db_schema, guild_id=GUILD_A)
    file_b = envs.resolve_db_file(envs.dilemmas_db_schema, guild_id=GUILD_B)
    assert file_a != file_b


async def test_is_guild_approved(guild_db_root):
    await db_helper.prep_table(envs.guilds_db_schema)
    await db_helper.insert_many_all(
        envs.guilds_db_schema,
        [
            (str(GUILD_A), "Guild A", "approved", "2026-01-01", "owner", "2026-01-01"),
            (str(GUILD_B), "Guild B", "pending", "2026-01-02", None, None),
        ],
    )

    assert await db_helper.is_guild_approved(GUILD_A) is True
    assert await db_helper.is_guild_approved(GUILD_B) is False
    assert await db_helper.is_guild_approved(999999999) is False


async def test_guild_locale_context_sets_and_resets_contextvars(guild_db_root):
    await db_helper.prep_table(
        envs.locale_db_schema,
        inserts=envs.locale_db_schema["inserts"],
        guild_id=GUILD_A,
    )
    await db_helper.update_fields(
        envs.locale_db_schema,
        where=("setting", "language"),
        updates=[("value", "nb")],
        guild_id=GUILD_A,
    )
    await db_helper.update_fields(
        envs.locale_db_schema,
        where=("setting", "timezone"),
        updates=[("value", "Europe/Oslo")],
        guild_id=GUILD_A,
    )

    assert guild_context.current_locale.get() == "en"

    async with db_helper.guild_locale_context(GUILD_A):
        assert guild_context.current_guild_id.get() == GUILD_A
        assert guild_context.current_locale.get() == "nb"
        assert guild_context.current_timezone.get() == "Europe/Oslo"

    # Context resets once the `async with` block exits
    assert guild_context.current_guild_id.get() is None
    assert guild_context.current_locale.get() == "en"
    assert guild_context.current_timezone.get() == "UTC"


async def test_guild_locale_context_falls_back_to_defaults_for_unknown_guild(
    guild_db_root,
):
    # No locale table has ever been prepped for this guild
    async with db_helper.guild_locale_context(987654321):
        assert guild_context.current_locale.get() == "en"
        assert guild_context.current_timezone.get() == "UTC"
