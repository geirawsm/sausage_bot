#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"bot_i18n: Internationalization functions"

from . import envs, file_io, config, guild_context
from discord import app_commands
import discord
import i18n
import os
import re

logger = config.logger

i18n.load_path.append(envs.LOCALE_DIR)
i18n.set("fallback", "en")
# Static default locale, used only when no guild context is active (e.g.
# during startup logging, before any guild's settings have been loaded).
# Per-guild locale is resolved via `guild_context.current_locale`, set by
# `db_helper.guild_locale_context()` - see that function's docstring.
i18n.set("locale", "en")


class i18nProxy:
    """
    Thin wrapper around the `i18n` package that makes `.t()` guild-aware
    without requiring every call site in the codebase to pass a `locale`
    kwarg explicitly. Everything except `.t()` is delegated straight
    through to the underlying library.
    """

    def t(self, *args, **kwargs):
        kwargs.setdefault("locale", guild_context.current_locale.get())
        return i18n.t(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(i18n, name)


_t = i18nProxy().t

# Clean l10n log file before starting
_logfilename = envs.LOG_DIR / "l10n.log"
file_io.ensure_file(str(_logfilename))
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
        return _t(str(string))


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


i18n.set("on_missing_placeholder", handler_placeholder)
i18n.set("on_missing_plural", handler_plural)


def reloadi18n():
    i18nProxy.reload_everything()


def available_languages():
    locale_files = os.listdir(envs.LOCALE_DIR)
    locale_yml_check = list(
        filter(lambda files: re.search(r".*\.(.*)\.yml$", files), locale_files)
    )
    return locale_yml_check
