#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'Get env values and initiate the Discord bot object'

import discord
from discord.ext import commands
import json
import sys
import os
from . import mod_vars, file_io
from ..log import log


# Create necessary files before starting
if not os.path.exists(mod_vars.env_file):
    file_io.write_json(mod_vars.env_file, mod_vars.env_template)
    print(
        f'Created {mod_vars.env_file} file. Enter information for the bot. '
        'Check the README.md for more info.'
    )
    sys.exit()


def add_cog_envs_to_env_file(cog_name, cog_envs):
    # Check env values for cog envs and add if necessary
    cogs_status = file_io.read_json(mod_vars.env_file)
    log.debug(f'Got `cogs_status`: {cogs_status}')
    if cog_name not in cogs_status:
        log.log(f'Adding `{cog_name}` with `{cog_envs}` to `cogs_status`')
        cogs_status[cog_name] = cog_envs
    file_io.write_json(mod_vars.env_file, cogs_status)


def config():
    try:
        with open(mod_vars.env_file) as f:
            return dict(json.load(f))
    except json.JSONDecodeError as e:
        log.log(f"Error when reading json from {mod_vars.env_file}:\n{e}")
    except OSError as e:
        log.log(f"File can't be read {mod_vars.env_file}:\n{e}")
    return None


# Check all basic env values
try:
    TOKEN = config()['basic']['discord_token']
    if TOKEN == '':
        log.log(mod_vars.BOT_NOT_SET_UP)
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
