#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"Set's up the bot, have a few generic commands and controls cogs"
import discord
from discord.ext import commands
import os
#import locale

from sausage_bot.util.args import args
from sausage_bot.util import config, envs, file_io, cogs
from sausage_bot.util.log import log


# Set locale
#locale.setlocale(locale.LC_ALL, config.env('LOCALE', default='nb_NO.UTF-8'))

# Create necessary folders before starting
check_and_create_folders = [
    envs.LOG_DIR, envs.JSON_DIR
]
for folder in check_and_create_folders:
    try:
        os.makedirs(folder)
    except (FileExistsError):
        pass

# Create necessary files before starting
log.log_more('Creating necessary files')
check_and_create_files = [
    (envs.env_file, envs.env_template)
]
for file in check_and_create_files:
    if isinstance(file, tuple):
        file_io.ensure_file(file[0], file_template=file[1])
    else:
        file_io.ensure_file(file)


@config.bot.event
async def on_ready():
    '''
    When the bot is ready, it will notify in the log.
    #autodoc skip#
    '''
    for guild in config.bot.guilds:
        if guild.name == config.env('DISCORD_GUILD'):
            break
    log.log('{} has connected to `{}`'.format(config.bot.user, guild.name))
    await cogs.loading.load_and_clean_cogs()
    if args.maintenance:
        log.log('Maintenance mode activated', color='RED')
        await config.bot.change_presence(
            status=discord.Status.dnd)
    else:
        await config.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=config.env(
                    'BOT_WATCHING',
                    default='some random youtube video'
                )
            )
        )


# Commands
@config.bot.command(name='ping')
async def ping(ctx):
    'Checks the bot latency'
    await ctx.send(f'Pong! {round(config.bot.latency * 1000)} ms')
    await ctx.message.add_reaction('✅')


@commands.check_any(
    commands.is_owner(),
    commands.has_permissions(manage_messages=True)
)
@config.bot.command(aliases=['del', 'cls'])
async def delete(ctx, amount=0):
    'Delete `amount` number of messages in the chat'
    if amount == 0:
        await ctx.message.add_reaction('❌')
        await ctx.send(
            'Please specify the number of messages you want to delete!'
        )
    elif amount <= 0:  # lower than 0
        await ctx.message.add_reaction('❌')
        await ctx.send("The number must be bigger than 0!")
    else:
        await ctx.message.add_reaction('✅')
        await ctx.channel.purge(limit=amount + 1)


@config.bot.command()
@commands.check_any(
    commands.is_owner(),
    commands.has_permissions(kick_members=True)
)
async def kick(ctx, member: discord.Member = commands.param(
    default=None,
    description="Name of Discord user you want to kick"
), *, reason: str = commands.param(
    default=None,
    description="Reason for kicking user")
):
    'Kick a member from the server'
    try:
        await member.kick(reason=reason)
        await ctx.send(f'{member} has been kicked')
    except Exception as failkick:
        await ctx.send(f'Failed to kick: {failkick}', delete_after=5)


@config.bot.command()
@commands.check_any(
    commands.is_owner(),
    commands.has_permissions(ban_members=True)
)
async def ban(ctx, member: discord.Member = commands.param(
    default=None,
    description="Name of Discord user you want to ban"
), *, reason: str = commands.param(
    default=None,
    description="Reason for banning user")
):
    'Ban a member from the server'
    try:
        await member.ban(reason=reason)
        await ctx.send(f'{member} has been banned!')
    except Exception as e:
        await ctx.send(f'Failed to ban: {e}', delete_after=5)


@config.bot.command()
@commands.check_any(
    commands.is_owner(),
    commands.has_permissions(manage_messages=True)
)
async def say(ctx, *, text):
    'Make the bot say something'
    await ctx.message.delete()
    await ctx.send(f"{text}")
    return


@config.bot.command()
@commands.check_any(
    commands.is_owner(),
    commands.has_permissions(administrator=True)
)
async def edit(ctx, *, text):
    'Make the bot rephrase a previous message. Reply to it with `!edit [text]`'
    if ctx.message.reference is None:
        await ctx.message.reply(
            'You have to reply to a message: `!edit [text]`'
        )
        return
    elif ctx.message.reference.message_id:
        msgid = ctx.message.reference.message_id
        edit_msg = await ctx.fetch_message(msgid)
        await edit_msg.edit(content=text)
        await ctx.message.delete()
        return


try:
    config.bot.run(config.DISCORD_TOKEN)
except Exception as e:
    log.log(e)


def setup(bot):
    @bot.event
    async def on_command_error(ctx, exception):
        # if the exception is of any of selected classes redirect to discord
        if isinstance(exception, commands.InvalidEndOfQuotedStringError):
            await ctx.message.reply('Sjekk bruken av anførselstegn')
