#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'Get env values and initiate the Discord bot object'

import discord
from discord.ext import commands
import sys
import os
from . import _vars, file_io
from ..log import log


# Create necessary files before starting
if not os.path.exists(_vars.env_file):
    file_io.write_json(_vars.env_file, file_template=_vars.env_template)
    print(
        f'Created {_vars.env_file} file. Enter information for the bot. '
        'Check the README.md for more info.'
    )
    sys.exit()


def add_cog_envs_to_env_file(cog_name, cog_envs):
    # Check env values for cog envs and add if necessary
    cogs_status = file_io.read_json(_vars.env_file)
    log.log_more(f'Got `cogs_status`: {cogs_status}')
    if cog_name not in cogs_status:
        log.log_more(f'Adding `{cog_name}` with `{cog_envs}` to `cogs_status`')
        cogs_status[cog_name] = cog_envs
    file_io.write_json(_vars.env_file, cogs_status)


def config():
    return file_io.read_json(_vars.env_file)


# Check all basic env values
try:
    TOKEN = config()['basic']['discord_token']
    if TOKEN == '':
        log.log(_vars.BOT_NOT_SET_UP)
    GUILD = config()['basic']['discord_guild']
    PREFIX = config()['basic']['bot_prefix']
    LOCALE = config()['basic']['locale']
    BOT_CHANNEL = config()['basic']['bot_dump_channel']
    BOT_ID = config()['basic']['bot_id']
    BOT_WATCHING = config()['basic']['watching']
    intents = discord.Intents.all()
    bot = commands.Bot(command_prefix=PREFIX, intents=intents)
except KeyError as e:
    log.log(f'Couldn\'t load basic env: {e}')
    sys.exit()
