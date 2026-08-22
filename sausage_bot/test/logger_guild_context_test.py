#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
Tests for `GuildContextFilter` in util/logger.py - the filter that stamps
log records with the guild the current asyncio Task is handling.

What these guard:

- `LOG_FORMAT` contains `%(guild)s`, so any record reaching a handler
  without a `guild` attribute raises on format instead of being logged.
  The filter therefore has to run for *every* record the handler sees,
  including ones that propagated up from a child logger (discord.py,
  aiosqlite) and so never passed the root logger's own filters. Attaching
  the filter to the logger rather than the handler would compile and pass
  a naive test, then drop discord.py's logging in production.
- Lines with no guild in scope must look exactly like they did before the
  guild column existed.
"""

import io
import logging

from sausage_bot.util import guild_context
from sausage_bot.util.logger import (
    LOG_FORMAT,
    GuildContextFilter,
    configure_logging,
)

GUILD_ID = "868902121834176513"


def _record(name="sausage_bot", **extra):
    "A bare record, as logging would hand one to a handler"
    record = logging.LogRecord(
        name=name,
        level=logging.INFO,
        pathname="roles.py",
        lineno=2254,
        msg="Checking added reaction role",
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def _in_guild_context(guild_id):
    "Set the contextvar and hand back the token to reset it with"
    return guild_context.current_guild_id.set(guild_id)


# --- what the filter puts on the record ---


def test_no_guild_in_scope_leaves_the_column_empty():
    record = _record()
    GuildContextFilter().filter(record)
    assert record.guild == ""


def test_the_guild_in_scope_is_stamped_on_the_record():
    token = _in_guild_context(GUILD_ID)
    try:
        record = _record()
        GuildContextFilter().filter(record)
        assert record.guild == GUILD_ID
    finally:
        guild_context.current_guild_id.reset(token)


def test_an_explicit_guild_id_overrides_the_context():
    # For the code paths that know their guild but never enter
    # guild_locale_context() - logger.debug(msg, extra={"guild_id": ...})
    token = _in_guild_context(GUILD_ID)
    try:
        record = _record(guild_id="111")
        GuildContextFilter().filter(record)
        assert record.guild == "111"
    finally:
        guild_context.current_guild_id.reset(token)


def test_an_int_guild_id_is_rendered_as_a_string():
    # payload.guild_id and guild.id are ints, not strings
    record = _record(guild_id=int(GUILD_ID))
    GuildContextFilter().filter(record)
    assert record.guild == GUILD_ID


def test_the_filter_never_drops_a_record():
    assert GuildContextFilter().filter(_record()) is True


# --- the format string the filter feeds ---


def _handler_output(logger_name, guild_id=None):
    """
    Run a record through a real handler configured the way
    `configure_logging()` configures them, and return the formatted line.
    """
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, "%Y-%m-%d %H:%M:%S"))
    handler.addFilter(GuildContextFilter())

    root = logging.getLogger()
    old_handlers, old_level = root.handlers[:], root.level
    root.handlers = [handler]
    root.setLevel(logging.DEBUG)
    token = None if guild_id is None else _in_guild_context(guild_id)
    try:
        logging.getLogger(logger_name).info("hello")
        return stream.getvalue()
    finally:
        if token is not None:
            guild_context.current_guild_id.reset(token)
        root.handlers, root.level = old_handlers, old_level


def test_the_guild_column_sits_between_the_level_and_the_module():
    assert "%(levelname)-5.5s | [ %(guild)-19s ] | [ %(module)s" in LOG_FORMAT


def _guild_field(line):
    "The `[ ... ]` field between the level and the module field"
    return line.split(" | ")[2]


def test_a_record_with_a_guild_is_formatted_in_brackets():
    field = _guild_field(_handler_output("sausage_bot", GUILD_ID))
    assert field.startswith("[ ") and field.endswith(" ]")
    assert field.strip("[] ") == GUILD_ID


def test_a_record_without_a_guild_still_gets_the_brackets():
    field = _guild_field(_handler_output("sausage_bot"))
    assert field.startswith("[ ") and field.endswith(" ]")
    assert field.strip("[] ") == ""


def test_the_module_field_starts_in_the_same_column_either_way():
    # The point of padding the column: with and without a guild, the
    # module/function/line field has to line up
    with_guild = _handler_output("sausage_bot", GUILD_ID)
    without_guild = _handler_output("sausage_bot")
    assert with_guild.index("] | [") == without_guild.index("] | [")


def test_a_longer_guild_id_than_the_column_is_never_truncated():
    # Snowflakes grow a digit over time - widening one line beats
    # silently cutting the id
    long_id = "9" * 25
    field = _guild_field(_handler_output("sausage_bot", long_id))
    assert field.strip("[] ") == long_id


def test_a_child_loggers_record_is_stamped_too():
    # discord.py and aiosqlite log on their own loggers; those records
    # propagate straight to the root handler without passing the root
    # logger's filters. Without the filter on the *handler* this raises.
    field = _guild_field(_handler_output("discord.gateway", GUILD_ID))
    assert field.strip("[] ") == GUILD_ID


def test_a_child_loggers_record_without_a_guild_does_not_raise():
    line = _handler_output("discord.gateway")
    assert "hello" in line


# --- how configure_logging() wires it up ---


def test_configure_logging_puts_the_filter_on_its_handler():
    # The placement that matters: on the handler, not on the logger
    root = logging.getLogger()
    old_handlers, old_level = root.handlers[:], root.level
    root.handlers = []
    try:
        configure_logging()
        assert root.handlers
        for handler in root.handlers:
            assert any(
                isinstance(log_filter, GuildContextFilter)
                for log_filter in handler.filters
            )
    finally:
        root.handlers, root.level = old_handlers, old_level
