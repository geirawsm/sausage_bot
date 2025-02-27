#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'Get env values and initiate the Discord bot object'

import discord
from discord.ext import commands
from sys import exit
from environs import Env, EnvError
from contextlib import suppress
import os
from pathlib import Path

from . import envs


# Create necessary folders before starting
check_and_create_folders = [
    envs.DB_DIR,
    envs.LOG_DIR
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
    TIMEZONE = env('TIMEZONE', default='Europe/Oslo')
    LOCALE = env('LOCALE', default='nb_NO')
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
    print(f'You need to set environment variables for the bot to work: {e}')
    exit()

try:
    intents = discord.Intents.all()
    bot = commands.Bot(
        command_prefix=PREFIX,
        intents=intents
    )
except KeyError as e:
    print(f'Couldn\'t load basic env: {e}')
    exit()
