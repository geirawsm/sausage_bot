#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'Get env values and initiate the Discord bot object'

from dotenv import dotenv_values
import discord
from discord.ext import commands
import sys
import os
from . import _vars, file_io
from ..log import log

# Create necessary files before starting
if not os.path.exists(_vars.env_file):
    file_io.ensure_file(_vars.env_file, file_template=_vars.env_template)
    print(
        'Created .env file. Enter information for the bot. Check the README.md'
        ' for more info.'
    )
    sys.exit()

config = dotenv_values(_vars.env_file)
# Check all basic env values
try:
    TOKEN = config['discord_token']
    if TOKEN == '':
        log.log(_vars.BOT_NOT_SET_UP)
    GUILD = config['discord_guild']
    PREFIX = config['bot_prefix']
    LOCALE = config['locale']
    BOT_CHANNEL = config['bot_dump_channel']
    BOT_ID = config['bot_id']
    BOT_WATCHING = config['watching']
    intents = discord.Intents.all()
    bot = commands.Bot(command_prefix=PREFIX, intents=intents)
except KeyError as e:
    log.log(f'Couldn\'t load basic env: {e}')
    sys.exit()

# Check env values for cogs
try:
    PATREON_ROLE_ID = config['patreon_role_id']
    STATS_CHANNEL = config['stats_channel']
    YOUTUBE_API_KEY = config['youtube_api_key']
    # envs for `scrape_fcb_news`
    FIRSTTEAM = config['firstteam']
    FEMENI = config['femeni']
    ATLETIC = config['atletic']
    JUVENIL = config['juvenil']
    CLUB = config['club']
except KeyError as e:
    log.log(f'Couldn\'t load cog env: {e}')
    sys.exit()

# envs for the `ps_sale` cog
#PLATPRICE_API_KEY = config['platprice_api']
#GAME_CHANNEL = config['game_channel']
