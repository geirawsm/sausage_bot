#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"Set's up the bot, have a few generic commands and controls cogs"
import discord
from discord.ext import commands
import os

from sausage_bot.util.args import args
from sausage_bot.util import config, envs, file_io, cogs, db_helper
from sausage_bot.util.log import log


# Create necessary folders before starting
check_and_create_folders = [
    envs.DB_DIR
]
for folder in check_and_create_folders:
    try:
        os.makedirs(folder)
    except (FileExistsError):
        pass

# Create necessary files before starting
log.verbose('Creating necessary files')
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
            log.log('{} has connected to `{}`'.format(
                config.bot.user, guild.name))
            break
    # Create necessary databases before starting `cog`
    cog_name = 'cogs'
    log.verbose('Checking db')
    # Convert json to sqlite db-files if exists
    cogs_prep_is_ok = False
    cogs_file_inserts = None
    if not file_io.file_size(envs.cogs_db_schema['db_file']):
        if file_io.file_size(envs.cogs_status_file):
            log.verbose('Found old json file')
            cogs_file_inserts = db_helper.json_to_db_inserts(cog_name)
        cogs_prep_is_ok = await db_helper.prep_table(
            envs.cogs_db_schema, cogs_file_inserts
        )
    # Delete old json files if they exist
    if cogs_prep_is_ok:
        file_io.remove_file(envs.cogs_status_file)
    await cogs.Loading.load_and_clean_cogs()
    if args.maintenance:
        log.log('Maintenance mode activated', color='RED')
        await config.bot.change_presence(
            status=discord.Status.dnd
        )
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
async def kick(ctx, member: discord.Member = None, *, reason: str = None):
    '''
    Kick a member from the server

    Parameters
    ------------
    member: discord.Member
        Name of Discord user you want to kick (default: None)
    reason: str
        Reason for kicking user (defautl: None)
    '''
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
async def ban(ctx, member: discord.Member = None, *, reason: str = None):
    '''
    Ban a member from the server

    Parameters
    ------------
    member: discord.Member
        Name of Discord user you want to ban (default: None)
    reason: str
        Reason for banning user (default: None)
    '''
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


async def setup(bot):
    @bot.event
    async def on_command_error(ctx, exception):
        # if the exception is of any of selected classes redirect to discord
        if isinstance(exception, commands.InvalidEndOfQuotedStringError):
            await ctx.message.reply('Sjekk bruken av anførselstegn')
