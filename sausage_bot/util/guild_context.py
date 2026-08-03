#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
guild_context: async-safe tracking of which guild the current command or
background-task iteration is handling.

Uses `contextvars` rather than a plain global so that concurrently running
asyncio tasks (e.g. two guilds' background loops, or two interactions
handled at the same time) never see each other's guild. Each asyncio Task
gets its own copy of these vars.

Read from here directly in synchronous code (`i18n.py`, `datetime_handling.py`).
Set via `db_helper.guild_locale_context()`, which does the async DB lookup
needed to populate these values for a given guild.

#autodoc skip#
"""

import contextvars

current_guild_id: contextvars.ContextVar = contextvars.ContextVar(
    "current_guild_id", default=None
)
current_locale: contextvars.ContextVar = contextvars.ContextVar(
    "current_locale", default="en"
)
current_timezone: contextvars.ContextVar = contextvars.ContextVar(
    "current_timezone", default="UTC"
)
