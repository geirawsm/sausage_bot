#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the `synclocal`/`syncglobal` prefix commands in `__main__.py`.

What these guard: `tree.clear_commands()` only empties the tree in
memory, so clearing right before `tree.sync()` pushes an empty set to
Discord and *deletes* the commands instead of registering them.
`syncglobal` used to do exactly that, which made it a duplicate of
`clearglobals` - and because it emptied the global tree in memory, a
`synclocal` afterwards had nothing left to `copy_global_to()` and wiped
the guild commands too.

sausage_bot/__main__.py calls config.bot.run(...) at module level (no
`if __name__ == "__main__":` guard), so a plain import would try to
connect to Discord. config.bot.run is patched to a no-op for the
duration of the import below to avoid that (same pattern as
main_tasks_commands_test.py). The commands are invoked via `.callback`,
the raw async function discord.py stores on the Command object, which
also bypasses the `is_owner()` check.
"""

from types import SimpleNamespace
from unittest import mock

from sausage_bot.util import config

with mock.patch.object(config.bot, "run", lambda *args, **kwargs: None):
    from sausage_bot.__main__ import synclocal, syncglobal

GUILD_ID = 868902121834176513


def _make_ctx():
    reply = SimpleNamespace(edit=mock.AsyncMock())
    return SimpleNamespace(
        guild=SimpleNamespace(id=GUILD_ID),
        reply=mock.AsyncMock(return_value=reply),
    )


def _make_tree():
    return mock.MagicMock(
        clear_commands=mock.MagicMock(),
        copy_global_to=mock.MagicMock(),
        sync=mock.AsyncMock(return_value=[]),
        get_commands=mock.MagicMock(return_value=[]),
    )


def _patched_tree(tree):
    # `Bot.tree` is a read-only property, so it has to be patched on the
    # class rather than on the instance.
    return mock.patch.object(
        type(config.bot), "tree", new_callable=mock.PropertyMock, return_value=tree
    )


async def test_syncglobal_does_not_clear_the_tree_before_syncing():
    # Regression: `clear_commands(guild=None)` followed by `sync()` pushed
    # an empty command set, deleting every global command.
    tree = _make_tree()
    ctx = _make_ctx()
    with _patched_tree(tree):
        await syncglobal.callback(ctx)
    tree.clear_commands.assert_not_called()
    tree.sync.assert_awaited_once_with(guild=None)


async def test_synclocal_refills_the_guild_scope_it_clears():
    # `synclocal` may clear the guild scope, but only because
    # `copy_global_to()` fills it again before the sync. The global scope
    # must be left alone - that is what it copies *from*.
    tree = _make_tree()
    ctx = _make_ctx()
    with _patched_tree(tree):
        await synclocal.callback(ctx)
    for call in tree.clear_commands.call_args_list:
        assert call.kwargs.get("guild") is not None, (
            "synclocal must not clear the global scope - copy_global_to() "
            "reads from it"
        )
    tree.copy_global_to.assert_called_once_with(guild=ctx.guild)
    tree.sync.assert_awaited_once_with(guild=ctx.guild)
