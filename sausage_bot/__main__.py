#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import discord
from discord.ext import commands
import os
from random import randrange
from sausage_bot import _vars, file_io, log, _config, discord_commands
from sausage_bot._args import args


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
        log.log('Maintenance mode activated', color='RED')
        await _config.bot.change_presence(
            status=discord.Status.dnd)
    else:
        if not _config.BOT_WATCHING:
            presence_name = 'some random youtube video'
        if _config.BOT_WATCHING:
            presence_name = _config.BOT_WATCHING
        await _config.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=_config.BOT_WATCHING
            )
        )

# Load cogs
for filename in os.listdir(_vars.COGS_DIR):
    if filename.endswith('.py') and not filename.startswith('_'):
        log.log('Loading cog: {}'.format(filename))
        _config.bot.load_extension(
            '{}.{}'.format(
                _vars.COGS_REL_DIR, filename[:-3]
            )
        )


# Commands
@_config.bot.command(name='pølse')
async def polse(ctx):
    'Poster det famøse "Pølse-gate"-klippet fra Tangerudbakken'
    await ctx.send('https://www.youtube.com/watch?v=geJZ3kJUqoY')


@_config.bot.command(name='ping')
async def ping(ctx):
    await ctx.send(f'Pong! {round(_config.bot.latency * 1000)} ms')
    await ctx.message.add_reaction(emoji='✅')


@_config.bot.command(aliases=['purge', 'clear', 'cls'])
@commands.has_permissions(manage_messages=True)
async def prune(ctx, amount=0):
    if amount == 0:
        await ctx.send('Please specify the number of messages you want to delete!')
        await ctx.message.add_reaction(emoji='❌')
    elif amount <= 0:  # lower then 0
        await ctx.send("The number must be bigger than 0!")
        await ctx.message.add_reaction(emoji='❌')
    else:
        await ctx.message.add_reaction(emoji='✅')
        await ctx.channel.purge(limit=amount + 1)


@_config.bot.command()
@commands.has_permissions(kick_members=True)  # check user permission
async def kick(ctx, member: discord.Member, *, reason=None):
    try:
        await member.kick(reason=reason)
        await ctx.send(f'{member} has been kicked!')
        await ctx.message.add_reaction(emoji='✅')
    except Exception as failkick:
        await ctx.send("Failed to kick: " + str(failkick))
        await ctx.message.add_reaction(emoji='❌')


@_config.bot.command()
@commands.has_permissions(ban_members=True)  # check user permission
async def ban(ctx, member: discord.Member, *, reason=None):
    try:
        await member.ban(reason=reason)
        await ctx.send(f'{member} has been banned!')
        await ctx.message.add_reaction(emoji='✅')
    except Exception as e:
        await ctx.send("Failed to ban: " + str(e))
        await ctx.message.add_reaction(emoji='❌')


_config.bot.run(_config.TOKEN)
