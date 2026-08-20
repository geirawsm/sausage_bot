#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"i18n: Internationalization functions"

import os
import re
import discord
from discord import app_commands
import i18n as _i18n

from . import envs, file_io, config, guild_context

logger = config.logger

_i18n.load_path.append(envs.LOCALE_DIR)
_i18n.set("fallback", "en")
# Static default locale, used only when no guild context is active (e.g.
# during startup logging, before any guild's settings have been loaded).
# Per-guild locale is resolved via `guild_context.current_locale`, set by
# `db_helper.guild_locale_context()` - see that function's docstring.
_i18n.set("locale", "en")


class _I18NProxy:
    """
    Thin wrapper around the `i18n` package that makes `.t()` guild-aware
    without requiring every call site in the codebase to pass a `locale`
    kwarg explicitly. Everything except `.t()` is delegated straight
    through to the underlying library.
    """

    def t(self, *args, **kwargs):
        kwargs.setdefault("locale", guild_context.current_locale.get())
        return _i18n.t(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(_i18n, name)


I18N = _I18NProxy()

# Clean i18n log file before starting
_logfilename = envs.LOG_DIR / "i18n.log"
file_io.ensure_file(_logfilename)
with open(_logfilename, "w", encoding="utf-8") as write_log:
    write_log.write("")
    write_log.close()


class MyTranslator(app_commands.Translator):
    async def translate(
        self,
        string: app_commands.locale_str,
        locale: discord.Locale,
        context: app_commands.TranslationContext,
    ) -> str | None:
        return I18N.t(str(string))


def handler_placeholder(key, locale, text, name):
    _error = (
        f"Missing placeholder {name!r} while translating {key!r} to "
        f"{locale!r} (in {text!r})"
    )
    logger.error(_error)
    return "undefined"


def handler_translation(key, locale, **kwargs):
    _error = f"Missing translation for {key!r} in  {locale!r}"
    logger.error(_error)
    return "undefined"


def handler_plural(key, locale, **kwargs):
    _error = f"Missing plural for {key!r} in {locale!r}"
    logger.error(_error)
    return "undefined"


_i18n.set("on_missing_placeholder", handler_placeholder)
_i18n.set("on_missing_plural", handler_plural)


def reload_i18n():
    I18N.reload_everything()


def available_languages():
    lang_list = []
    for filename in os.listdir(envs.LOCALE_DIR):
        lang_check = re.search(r".*\.(.*)\.yml$", filename).group(1)
        if lang_check and lang_check not in lang_list:
            lang_list.append(lang_check)
    return lang_list
