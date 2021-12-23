#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import discord
from discord.ext import commands
import re
import os
from random import randrange
from discord_rss import rss_core, _vars, file_io, log, _config, discord_commands
from discord_rss._args import args
import sys


# Create necessary folders before starting
check_and_create_folders = [_vars.LOG_DIR]
for folder in check_and_create_folders:
    try:
        os.makedirs(folder)
    except(FileExistsError):
        pass


# Create necessary files before starting
check_and_create_files = [_vars.feed_file, _vars.feed_log_file]
for file in check_and_create_files:
    file_io.ensure_file(file)


@_config.bot.event
async def on_ready():
    for guild in _config.bot.guilds:
        if guild.name == _config.GUILD:
            break
    log.log('{} has connected to `{}`'.format(_config.bot.user, guild.name))
    if args.maintenance:
        await _config.bot.change_presence(
            status=discord.Status.dnd)
    else:
        season = randrange(1, 6)
        await _config.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name='Tangerudbakken s0{}'.format(season)
            )
        )

# Load cogs
for filename in os.listdir(_vars.COGS_DIR):
    if filename.endswith('.py'):
        _config.bot.load_extension('{}.{}'.format(
            _vars.COGS_REL_DIR, filename[:-3]
        ))


# Commands
@_config.bot.command(name='pølse')
async def polse(ctx):
    'Poster det famøse "Pølse-gate"-klippet fra Tangerudbakken'
    await ctx.send('https://www.youtube.com/watch?v=geJZ3kJUqoY')

_config.bot.run(_config.TOKEN)
