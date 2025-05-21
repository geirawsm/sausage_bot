#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'config: Get env values and initiate the Discord bot object'
import discord
from discord.ext import commands
from sys import exit
from environs import Env, EnvError
from contextlib import suppress
import os
from pathlib import Path
import pendulum
import aiosqlite
import asyncio

from . import envs
from . import logger

logger.configure_logging(to_file=True)
logger = logger.logging


async def db_get_output():
    # Get timezone and locale from db
    try:
        async with aiosqlite.connect(envs.locale_db_schema['db_file']) as db:
            db.row_factory = aiosqlite.Row
            out = await db.execute(
                'SELECT * FROM {};'.format(
                    envs.locale_db_schema['name']
                )
            )
            out = [dict(row) for row in await out.fetchall()]
            return out
    except aiosqlite.OperationalError as e:
        print(f'Error: {e}')
        return None


# Create necessary folders before starting
check_and_create_folders = [
    envs.DB_DIR,
    envs.LOG_DIR,
    envs.DATA_DIR
]
for folder in check_and_create_folders:
    with suppress(FileExistsError):
        os.makedirs(folder)


def ensure_file(file_path_in: str, file_template=False):
    def ensure_folder(folder_path: str):
        '''
        Create folders in `folder_path` if it doesn't exist
        '''
        folder_path = str(folder_path)
        # Make the folders if necessary
        if not os.path.exists(folder_path):
            _dirs = str(folder_path).split(os.sep)
            _path = ''
            for _dir in _dirs:
                _path += '{}/'.format(_dir)
            Path(_path).mkdir(parents=True, exist_ok=True)

    full_file_path = str(file_path_in).split(os.sep)
    folder_path = '/'.join(full_file_path[0:-1])
    folder_path += '/'
    # Make the folders if necessary
    ensure_folder(folder_path)
    try:
        os.stat(str(file_path_in), follow_symlinks=True)
        file_exist = True
    except FileNotFoundError:
        file_exist = False
    if not file_exist:
        with open(file_path_in, 'w+') as fout:
            if file_template:
                fout.write(file_template)
            else:
                fout.write('')


# Create necessary files before starting
logger.debug('Ensuring env file')
ensure_file(envs.env_file, envs.env_template)

try:
    env = Env()
    env.read_env(path=envs.env_file)
    # Set basic env values
    DISCORD_TOKEN = env('DISCORD_TOKEN', default=None)
    DISCORD_GUILD = env('DISCORD_GUILD', default=None)
    BOT_ID = env('BOT_ID', default=None)
    PREFIX = env('PREFIX', default='!')
    BOT_CHANNEL = env('BOT_DUMP_CHANNEL', default='bot-log')
    TIMEZONE = env('TIMEZONE', default='UTC')
    LANGUAGE = env('LANGUAGE', default='en')
    ROLE_CHANNEL = env('ROLE_CHANNEL', default='roles')
    SPOTIFY_ID = env('SPOTIFY_ID', default=None)
    SPOTIFY_SECRET = env('SPOTIFY_SECRET', default=None)
    SCRAPEOPS_API_KEY = env('SCRAPEOPS_API_KEY', default=None)
    if any(envvar is None for envvar in [
        DISCORD_TOKEN, DISCORD_GUILD, BOT_ID
    ]):
        print('Something is wrong with the env file.')
        exit()
except EnvError as e:
    logger.error(f'You need to set environment variables for the bot to work: {e}')
    exit()

# If empty in db, get from env or env default
locale_db = asyncio.run(db_get_output())
logger.debug(f'locale_db: {locale_db}')
if len(locale_db) > 0:
    if 'setting' in locale_db[0] and 'value' in locale_db[0]:
        locale_from_db = {}
        for setting in locale_db:
            locale_from_db[setting['setting']] = setting['value']
        _TZ = locale_from_db['timezone']
        _LANG = locale_from_db['language']
    else:
        _TZ = TIMEZONE
        _LANG = LANGUAGE
else:
    _TZ = TIMEZONE
    _LANG = LANGUAGE

timezone = pendulum.timezone(_TZ)
locale = pendulum.set_locale(_LANG)
pendulum.week_starts_at(pendulum.MONDAY)
pendulum.week_ends_at(pendulum.SUNDAY)

try:
    intents = discord.Intents.all()
    bot = commands.Bot(
        command_prefix=PREFIX,
        intents=intents
    )
except KeyError as e:
    logger.error(f'Couldn\'t load basic env: {e}')
    exit()
