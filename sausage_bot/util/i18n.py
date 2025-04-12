#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'i18n: Internationalization functions'
import os
import re
import discord
from discord import app_commands
import aiosqlite

from . import envs, file_io, config

import i18n as _i18n
_i18n.load_path.append(envs.LOCALE_DIR)
_i18n.set('fallback', 'en')
I18N = _i18n

logger = config.logger

# Clean i18n log file before starting
_logfilename = envs.LOG_DIR / 'i18n.log'
file_io.ensure_file(_logfilename)
with open(_logfilename, 'w', encoding="utf-8") as write_log:
    write_log.write('')
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
    _error = f'Missing placeholder {name!r} while translating {key!r} to '\
        f'{locale!r} (in {text!r})'
    logger.error(_error)
    return 'undefined'


def handler_translation(key, locale, **kwargs):
    _error = f'Missing translation for {key!r} in  {locale!r}'
    logger.error(_error)
    return 'undefined'


def handler_plural(key, locale, **kwargs):
    _error = f'Missing plural for {key!r} in {locale!r}'
    logger.error(_error)
    return 'undefined'


_i18n.set('on_missing_placeholder', handler_placeholder)
#_i18n.set('on_missing_translation', handler_translation)
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
        db_info = envs.locale_db_schema
        table_name = db_info['name']
        _cmd = 'UPDATE {} SET {} = \'{}\';'.format(
            table_name, 'locale', lang
        )
        try:
            async with aiosqlite.connect(db_info['db_file']) as db:
                await db.execute(_cmd)
                await db.commit()
            logger.debug('Done and commited!')
        except aiosqlite.OperationalError as e:
            logger.error(f'Error: {e}')
            return None
        I18N.reload_everything()
