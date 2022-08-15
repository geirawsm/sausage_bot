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
check_and_create_files = [
    (_vars.cogs_status_file, '{}')
]
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
# Add cogs that are not present in the `cogs_status` file
cogs_status = file_io.read_json(_vars.cogs_status_file)
for filename in os.listdir(_vars.COGS_DIR):
    if filename.endswith('.py'):
        cog_name = filename[:-3]
        if cog_name not in cogs_status:
            # Added as disable
            log.log('Added cog {} to cogs_status file'.format(cog_name))
            cogs_status[cog_name] = 'disable'
file_io.write_json(_vars.cogs_status_file, cogs_status)
print(cogs_status)
# Start cogs based on status
log.log('Checking `cogs_status` file for enabled cogs')
for cog_name in cogs_status:
    if cogs_status[cog_name] == 'enable':
        log.log('Loading cog: {}'.format(cog_name))
        _config.bot.load_extension(
            '{}.{}'.format(
                _vars.COGS_REL_DIR, cog_name
            )
        )


# Commands
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
    elif amount <= 0:  # lower than 0
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
    await ctx.message.delete()
    await ctx.send(f"{text}")


@_config.bot.command()
@commands.check_any(
    commands.is_owner(),
    commands.has_permissions(administrator=True)
)
async def cog(ctx, cmd_in=None, cog_name=None):
    def change_status(cog_name, status):
        cogs_status = file_io.read_json(_vars.cogs_status_file)
        try:
            # Change status
            cogs_status[cog_name] = status
            # Write changes
            file_io.write_json(_vars.cogs_status_file, cogs_status)
            return True
        except Exception as e:
            log.log(_vars.COGS_CHANGE_STATUS_FAIL.format(e))
            return False

    def get_cogs_list(cogs_file):
        def get_cog_item_lengths(cogs_file):
            cog_len = 0
            status_len = 0
            for cog in cogs_file:
                if len(cog) > cog_len:
                    cog_len = len(cog)
                if len(cogs_file[cog]) > status_len:
                    status_len = len(cogs_file[cog])
            return {'cog_len': cog_len, 'status_len': status_len}

        text_out = ''
        lengths = get_cog_item_lengths(cogs_file)
        template_line = '{:{cog_len}} | {:{status_len}}'
        # Add headers first
        text_out += template_line.format('Cog', 'Status',
            cog_len = lengths['cog_len'],
            status_len = lengths['status_len']
        )
        text_out += '\n'
        for cog in cogs_file:
            text_out += template_line.format(cog, cogs_file[cog],
            cog_len = lengths['cog_len'],
            status_len = lengths['status_len'])
            if cog != list(cogs_file)[-1]:
                text_out += '\n'
        text_out = '```{}```'.format(text_out)
        return text_out

    if cmd_in == 'enable':
        # Start Cog
        _config.bot.load_extension(
            '{}.{}'.format(
                _vars.COGS_REL_DIR, f'{cog_name}'
            )
        )
        change_status(cog_name, 'enable')
        await ctx.send(
            _vars.COGS_ENABLED.format(cog_name)
        )
        return True
    elif cmd_in == 'disable':
        # Stop cog
        _config.bot.unload_extension(
            '{}.{}'.format(
                _vars.COGS_REL_DIR, f'{cog_name}'
            )
        )
        change_status(cog_name, 'disable')
        await ctx.send(
            _vars.COGS_DISABLED.format(cog_name)
        )
        return True
    elif cmd_in == 'list':
        cogs_status = file_io.read_json(_vars.cogs_status_file)
        await ctx.send(
            get_cogs_list(cogs_status)
        )
    elif cmd_in is None and cog_name is None:
        await ctx.send(
            COGS_TOO_FEW_ARGUMENTS
        )
    else:
        log.log('Something else happened?')
        return False


_config.bot.run(_config.TOKEN)
