#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the cog loading helpers in util/cogs.py.

`on_ready` runs again on every gateway reconnect/RESUME, but extensions
loaded by an earlier run stay loaded. Calling load_extension on one of
those raises ExtensionAlreadyLoaded, which used to propagate out of
`load_and_clean_cogs_internal()` and abort the rest of `on_ready` -
including the per-guild bot channel check that runs after it.

`config.bot.load_extension` is patched throughout, so no cog is ever
really imported and no Discord connection is needed.
"""

import os
from unittest import mock

from discord.ext import commands

from sausage_bot.util import config, envs
from sausage_bot.util.cogs import Cogs

COG_FILES = ["autoevent.py", "rss.py", "_ignored.py", "notes.txt"]


def _loaded_extension_names(load_extension_mock):
    "The extension names load_extension was actually called with"
    return [call.args[0] for call in load_extension_mock.await_args_list]


def _patch_cog_dir(cog_files=None):
    "Pretend COGS_DIR holds `cog_files`"
    if cog_files is None:
        cog_files = COG_FILES
    return mock.patch.object(os, "listdir", return_value=cog_files)


def _already_loaded(name):
    return commands.ExtensionAlreadyLoaded(name)


# --- load_cog_internal ---


async def test_loading_a_new_cog_reports_true():
    with mock.patch.object(config.bot, "load_extension", mock.AsyncMock()) as load:
        assert await Cogs.load_cog_internal("autoevent") is True
    assert _loaded_extension_names(load) == [
        "{}.autoevent".format(envs.COGS_REL_DIR)
    ]


async def test_loading_an_already_loaded_cog_reports_false_and_does_not_raise():
    # The reported bug: this used to raise ExtensionAlreadyLoaded
    with mock.patch.object(
        config.bot,
        "load_extension",
        mock.AsyncMock(side_effect=_already_loaded("sausage_bot.cogs.autoevent")),
    ):
        assert await Cogs.load_cog_internal("autoevent") is False


async def test_other_load_errors_still_propagate():
    # Only the already-loaded case is swallowed - a broken cog must not
    # be silently skipped
    with mock.patch.object(
        config.bot,
        "load_extension",
        mock.AsyncMock(side_effect=commands.ExtensionNotFound("nope")),
    ):
        try:
            await Cogs.load_cog_internal("nope")
        except commands.ExtensionNotFound:
            return
        raise AssertionError("ExtensionNotFound should propagate")


# --- load_and_clean_cogs_internal ---


async def test_a_second_on_ready_does_not_raise():
    # First run loads everything, second run finds it all loaded
    loaded = set()

    async def fake_load(name):
        if name in loaded:
            raise _already_loaded(name)
        loaded.add(name)

    with _patch_cog_dir(), mock.patch.object(
        config.bot, "load_extension", mock.AsyncMock(side_effect=fake_load)
    ):
        await Cogs.load_and_clean_cogs_internal()
        await Cogs.load_and_clean_cogs_internal()
    assert loaded == {
        "{}.autoevent".format(envs.COGS_REL_DIR),
        "{}.rss".format(envs.COGS_REL_DIR),
    }


async def test_only_public_python_files_are_loaded():
    with _patch_cog_dir(), mock.patch.object(
        config.bot, "load_extension", mock.AsyncMock()
    ) as load:
        await Cogs.load_and_clean_cogs_internal()
    assert _loaded_extension_names(load) == [
        "{}.autoevent".format(envs.COGS_REL_DIR),
        "{}.rss".format(envs.COGS_REL_DIR),
    ]
