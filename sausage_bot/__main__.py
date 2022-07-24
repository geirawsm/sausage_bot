#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import discord
from discord.ext import commands
import os
from random import randrange
from sausage_bot.funcs import discord_commands
from sausage_bot.funcs._args import args
from sausage_bot.funcs import _config, _vars, file_io
from sausage_bot.log import log


# Create necessary folders before starting
check_and_create_folders = [_vars.LOG_DIR]
for folder in check_and_create_folders:
    try:
        os.makedirs(folder)
    except(FileExistsError):
        pass


# Create necessary files before starting
log.log_more('Creating necessary files')
check_and_create_files = [(_vars.feed_file, '{}'), _vars.feed_log_file]
for file in check_and_create_files:
    if isinstance(file, tuple):
        file_io.ensure_file(file[0], file_template=file[1])
    else:
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
    'Checks the bot\'s latency'
    await ctx.send(f'Pong! {round(_config.bot.latency * 1000)} ms')
    await ctx.message.add_reaction(emoji='✅')


@commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_messages=True)
    )
@_config.bot.command(aliases=['cls'])
async def delete(ctx, amount=0):
    'Delete x number of messages in the chat'
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
@commands.check_any(
        commands.is_owner(),
        commands.has_permissions(kick_members=True)
    )
async def kick(ctx, member: discord.Member, *, reason=None):
    'Kick a member from the server'
    try:
        await member.kick(reason=reason)
        await ctx.send(f'{member} has been kicked!')
        await ctx.message.add_reaction(emoji='✅')
    except Exception as failkick:
        await ctx.send("Failed to kick: " + str(failkick))
        await ctx.message.add_reaction(emoji='❌')


@_config.bot.command()
@commands.check_any(
        commands.is_owner(),
        commands.has_permissions(ban_members=True)
    )
async def ban(ctx, member: discord.Member, *, reason=None):
    'Ban a member from the server'
    try:
        await member.ban(reason=reason)
        await ctx.send(f'{member} has been banned!')
        await ctx.message.add_reaction(emoji='✅')
    except Exception as e:
        await ctx.send("Failed to ban: " + str(e))
        await ctx.message.add_reaction(emoji='❌')


@_config.bot.command()
@commands.check_any(
        commands.is_owner(),
        commands.has_permissions(ban_members=True)
    )
async def say(ctx, *, text):
    'Make the bot say something'
    if discord_commands.is_bot_owner(ctx) or discord_commands.is_admin(ctx):
        await ctx.message.delete()
        await ctx.send(f"{text}")


#@commands.has_permissions(manage_messages=True)
@_config.bot.command(name='checkmsg')
async def checkmsg(ctx):
    from difflib import SequenceMatcher
    async for msg in ctx.channel.history(limit=10):
        # wrong link:
        # https://stackoverflow.com/questions/22434218/delteing-user-mesasges-in-discord-py
        check_str = 'https://stackoverflow.com/questions/42182243/deleting-user-messages-in-discord-py'
        duplication_ratio = float(SequenceMatcher(a=check_str, b=msg.content).ratio())
        if duplication_ratio >= 0.9:
            await msg.edit(content=check_str)
    #async for message in _config.bot.logs_from(channel, limit=5):
    #    print(message.content)
    #    return
    #await ctx.channel.purge()


_config.bot.run(_config.TOKEN)
