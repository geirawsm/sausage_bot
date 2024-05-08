#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'Get env values and initiate the Discord bot object'

import discord
from discord.ext import commands
import json
import sys
from . import envs
from environs import Env, EnvError
from .log import log

env = Env()
env.read_env(path=envs.env_file)


def config():
    try:
        with open(envs.env_file) as f:
            return dict(json.load(f))
    except json.JSONDecodeError as e:
        log.error(f"Error when reading json from {envs.env_file}:\n{e}")
    except OSError as e:
        log.error(f"File can't be read {envs.env_file}:\n{e}")
    return None


# Set basic env values
PREFIX = env('PREFIX', default='!')
BOT_CHANNEL = env('BOT_DUMP_CHANNEL', default='bot-log')
TIMEZONE = env('TIMEZONE', default='Europe/Oslo')
LOCALE = env('LOCALE', default='nb_NO')
ROLE_CHANNEL = env('ROLE_CHANNEL', default='roles')

try:
    DISCORD_GUILD = env('DISCORD_GUILD')
    BOT_ID = env('BOT_ID')
    DISCORD_TOKEN = env('DISCORD_TOKEN')
except EnvError as e:
    print(f'Error: {e}')
    print('You need to set environment variables for the bot to work')

try:
    intents = discord.Intents.all()
    bot = commands.Bot(
        command_prefix=PREFIX,
        intents=intents
    )
except KeyError as e:
    log.error(f'Couldn\'t load basic env: {e}')
    sys.exit()
