#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared pytest fixtures for the multi-guild test suite.
"""
from types import SimpleNamespace

import pytest

from sausage_bot.util import config, envs

BOT_USER_ID = 1234567890123456789


@pytest.fixture
def guild_db_root(tmp_path, monkeypatch):
    """
    Point every DB helper at a throwaway `tmp_path` directory for the
    duration of a test, mirroring what a running bot does via
    `--db-dir` (see `envs.DB_DIR`) - so multi-guild DB tests never touch
    real bot data. The guild registry and the admin guild are the
    globally-scoped schemas (they resolve their `db_file` once at import
    time), so they need patching separately from `envs.DB_DIR`.
    `tasks_db_schema` is guild-scoped like everything else and rebases
    automatically once `envs.DB_DIR` is patched.
    """
    monkeypatch.setattr(envs, "DB_DIR", tmp_path)
    monkeypatch.setitem(envs.guilds_db_schema, "db_file", str(tmp_path / "guilds.sqlite"))
    monkeypatch.setitem(
        envs.admin_guild_db_schema, "db_file", str(tmp_path / "guilds.sqlite")
    )
    return tmp_path


@pytest.fixture
def bot_user(monkeypatch):
    """
    Give the code a logged-in bot to read `config.bot.user.id` from.

    `bot.user` is None until discord.py has logged in, and it is a
    read-only property on the client, so the whole `config.bot` object is
    swapped for a stand-in that carries the id. The id is an `int`, just
    like the real `ClientUser.id`.
    """
    user = SimpleNamespace(id=BOT_USER_ID, name="sausage-bot")
    monkeypatch.setattr(config, "bot", SimpleNamespace(user=user))
    return user
