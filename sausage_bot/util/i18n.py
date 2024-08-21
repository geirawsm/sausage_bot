#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

# Using this:
# https://github.com/solaluset/i18nice
import os
import re
import discord
from discord import app_commands

from .log import log
from . import envs, db_helper

import i18n as _i18n
_i18n.load_path.append(envs.LOCALE_DIR)
I18N = _i18n
_i18n.set('fallback', 'en')


class MyTranslator(app_commands.Translator):
    async def translate(
        self,
        string: app_commands.locale_str,
        locale: discord.Locale,
        context: app_commands.TranslationContext,
    ) -> str | None:
        return I18N.t(str(string))


def handler_placeholder(key, locale, text, name):
    log.error(f"Missing placeholder {name!r} while translating {key!r} to {locale!r} (in {text!r})")
    return "undefined"


def handler_translation(key, locale, **kwargs):
    log.error(f"Missing translation for {key!r} in  {locale!r}")
    print(**kwargs)
    return "undefined"


def handler_plural(key, locale, **kwargs):
    log.error(f"Missing plural for {key!r} in {locale!r}")
    print(**kwargs)
    return "undefined"


_i18n.set("on_missing_placeholder", handler_placeholder)
_i18n.set('on_missing_translation', handler_translation)
_i18n.set('on_missing_plural', handler_plural)


def reload_i18n():
    I18N.reload_everything()


def available_languages():
    lang_list = []
    for filename in os.listdir(envs.LOCALE_DIR):
        file_check = re.search(r'.*\.(.*)\.yml$', filename).group(1)
        if file_check and file_check not in lang_list:
            lang_list.append(file_check)
    return lang_list


async def set_language(lang: str):
    if lang in available_languages():
        I18N.set('locale', lang)
        await db_helper.update_fields(
            template_info=envs.locale_db_schema,
            updates=[('locale', lang)]
        )
        I18N.reload_everything()
