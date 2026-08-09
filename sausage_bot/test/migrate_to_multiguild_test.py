#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exercises the standalone migration tool
(`sausage_bot.testing.migrate_to_multiguild`) that moves an existing
single-guild `data/db/*.sqlite` layout into the per-guild
`data/db/guild_<id>/*.sqlite` layout.

Run as a real subprocess (`python -m sausage_bot.testing....`), the same
way it's actually used. This is deliberate: the script repoints
module-level globals in `envs` (DB_DIR, GUILDS_DB_FILE, schema db_files)
that must never leak into another test in this suite - running it
out-of-process is the simplest way to guarantee that.

`sausage_bot/testing/` is gitignored (it holds ad-hoc, non-bot-process
tooling - see CLAUDE.md), so this test skips itself if the script isn't
present on disk rather than failing a fresh checkout.
"""
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_SCRIPT = REPO_ROOT / "sausage_bot" / "testing" / "migrate_to_multiguild.py"

GUILD_ID = "444444444444444444"
GUILD_NAME = "Migration Test Guild"

pytestmark = pytest.mark.skipif(
    not MIGRATION_SCRIPT.exists(),
    reason="sausage_bot/testing/ is gitignored and not present in this checkout",
)


def _make_old_flat_dir(tmp_path):
    "A synthetic pre-migration single-guild db dir with two guild-scoped files"
    source = tmp_path / "old_flat"
    source.mkdir()
    with sqlite3.connect(source / "dilemmas.sqlite") as db:
        db.execute("CREATE TABLE dilemmas (id TEXT, dilemmas_text TEXT)")
        db.execute(
            "INSERT INTO dilemmas VALUES (?, ?)", ("old-uuid", "A legacy dilemma")
        )
    with sqlite3.connect(source / "tasks.sqlite") as db:
        db.execute("CREATE TABLE tasks (cog TEXT, task TEXT, status TEXT)")
        db.execute(
            "INSERT INTO tasks VALUES (?, ?, ?)",
            ("barca_news", "post_news", "stopped"),
        )
    return source


def _run_migration(source_dir, extra_args=()):
    cmd = [
        sys.executable,
        "-m",
        "sausage_bot.testing.migrate_to_multiguild",
        "--source-dir",
        str(source_dir),
        "--guild-id",
        GUILD_ID,
        "--guild-name",
        GUILD_NAME,
        *extra_args,
    ]
    return subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=60
    )


def test_dry_run_makes_no_changes(tmp_path):
    source = _make_old_flat_dir(tmp_path)
    result = _run_migration(source, extra_args=["--dry-run"])

    assert result.returncode == 0, result.stderr
    assert not (source / f"guild_{GUILD_ID}").exists()
    assert not (source / "guilds.sqlite").exists()


def test_copy_mode_migrates_guild_scoped_files_and_registers_guild(tmp_path):
    source = _make_old_flat_dir(tmp_path)
    result = _run_migration(source)
    assert result.returncode == 0, result.stderr

    dest_dilemmas = source / f"guild_{GUILD_ID}" / "dilemmas.sqlite"
    assert dest_dilemmas.exists()
    with sqlite3.connect(dest_dilemmas) as db:
        rows = db.execute("SELECT id, dilemmas_text FROM dilemmas").fetchall()
    assert rows == [("old-uuid", "A legacy dilemma")]

    # Copy mode (the default): original guild-scoped file is left in place
    assert (source / "dilemmas.sqlite").exists()

    # tasks.sqlite is now guild-scoped (posting tasks are per-guild), so it
    # is migrated into the guild folder. In copy mode the original stays put.
    dest_tasks = source / f"guild_{GUILD_ID}" / "tasks.sqlite"
    assert dest_tasks.exists()
    with sqlite3.connect(dest_tasks) as db:
        task_rows = db.execute("SELECT cog, task, status FROM tasks").fetchall()
    assert task_rows == [("barca_news", "post_news", "stopped")]
    assert (source / "tasks.sqlite").exists()

    # The guild registry itself is the only global file - it stays at the
    # db root and is never pulled into the guild folder.
    assert not (source / f"guild_{GUILD_ID}" / "guilds.sqlite").exists()

    with sqlite3.connect(source / "guilds.sqlite") as db:
        row = db.execute(
            "SELECT guild_id, guild_name, status FROM guilds WHERE guild_id = ?",
            (GUILD_ID,),
        ).fetchone()
    assert row == (GUILD_ID, GUILD_NAME, "approved")


def test_move_mode_removes_source_file(tmp_path):
    source = _make_old_flat_dir(tmp_path)
    result = _run_migration(source, extra_args=["--move"])
    assert result.returncode == 0, result.stderr

    assert (source / f"guild_{GUILD_ID}" / "dilemmas.sqlite").exists()
    assert not (source / "dilemmas.sqlite").exists()


def test_rerun_updates_existing_guild_instead_of_duplicating(tmp_path):
    source = _make_old_flat_dir(tmp_path)
    first = _run_migration(source)
    assert first.returncode == 0, first.stderr
    second = _run_migration(source)
    assert second.returncode == 0, second.stderr

    with sqlite3.connect(source / "guilds.sqlite") as db:
        rows = db.execute(
            "SELECT status FROM guilds WHERE guild_id = ?", (GUILD_ID,)
        ).fetchall()
    # A second run must update the existing row, not insert a duplicate
    assert rows == [("approved",)]
