#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared pytest fixtures for the multi-guild test suite.
"""
import pytest

from sausage_bot.util import envs


@pytest.fixture
def guild_db_root(tmp_path, monkeypatch):
    """
    Point every DB helper at a throwaway `tmp_path` directory for the
    duration of a test, mirroring what a running bot does via
    `--db-dir` (see `envs.DB_DIR`) - so multi-guild DB tests never touch
    real bot data. The guild registry is the only globally-scoped schema
    (it resolves its `db_file` once at import time), so it needs
    patching separately from `envs.DB_DIR`. `tasks_db_schema` is
    guild-scoped like everything else and rebases automatically once
    `envs.DB_DIR` is patched.
    """
    monkeypatch.setattr(envs, "DB_DIR", tmp_path)
    monkeypatch.setitem(envs.guilds_db_schema, "db_file", str(tmp_path / "guilds.sqlite"))
    return tmp_path
