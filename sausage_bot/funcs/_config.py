#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from dotenv import dotenv_values
from discord.ext import commands
from . import _vars

config = dotenv_values(_vars.env_file)
TOKEN = config['discord_token']
GUILD = config['discord_guild']
PREFIX = config['bot_prefix']
BOT_CHANNEL = config['bot_dump_channel']
BOT_ID = config['bot_id']
BOT_WATCHING = config['watching']
RSS_SCRAPE_FCB_AGREEMENT_CHANNEL=config['rss_scrape_fcb_agreement_channel']

# envs for the `ps_sale` cog
#PLATPRICE_API_KEY = config['platprice_api']
#GAME_CHANNEL = config['game_channel']

bot = commands.Bot(command_prefix=PREFIX)
