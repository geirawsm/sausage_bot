#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import discord
from discord.ext import commands
import os
import locale
from sausage_bot.funcs._args import args
from sausage_bot.funcs import _config, _vars, discord_commands, file_io
from sausage_bot.log import log


# Set locale
locale.setlocale(locale.LC_ALL, _config.LOCALE)

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
    await Cog.load_and_clean_cogs()
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

# Cogs
class Cog:
    'Control the cogs for the bot'
    def change_cog_status(cog_name, status):
        '''
        Change a cog status in the status file

        `cog_name` should be name of cog

        `status` should be `enable` or `disable`
        '''
        accepted_status = ['enable', 'disable']
        if not any(status == ok_status for ok_status in accepted_status):
            log.log('This command only accept `enable` or `disable`')
            return False
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

    async def load_cog(cog_name):
        'Load a specific cog by `cog_name`'
        await _config.bot.load_extension(
            '{}.{}'.format(
                _vars.COGS_REL_DIR, f'{cog_name}'
            )
        )
        return

    async def unload_cog(cog_name):
        'Unload a specific cog by `cog_name`'
        await _config.bot.unload_extension(
            '{}.{}'.format(
                _vars.COGS_REL_DIR, f'{cog_name}'
            )
        )
        return

    async def reload_cog(cog_name):
        'Reload a specific cog by `cog_name`'
        await _config.bot.reload_extension(
            '{}.{}'.format(
                _vars.COGS_REL_DIR, f'{cog_name}'
            )
        )
        return

    async def load_and_clean_cogs():
        '''
        This does three things:
        1. Adds cogs from files that are not already present in the
            `cogs_status` file
        2. Removes cogs from the `cogs_status` file if a file doesn't exist
        3. Start cogs based on status in `cogs_status` file
        '''
        cog_files = []
        # Add cogs that are not present in the `cogs_status` file
        cogs_status = file_io.read_json(_vars.cogs_status_file)
        for filename in os.listdir(_vars.COGS_DIR):
            if filename.endswith('.py'):
                cog_name = filename[:-3]
                # Add all cog names to `cog_files` for easier cleaning
                cog_files.append(cog_name)
                if cog_name not in cogs_status:
                    # Added as disable
                    log.log('Added cog {} to cogs_status file'.format(cog_name))
                    cogs_status[cog_name] = 'disable'
        # Clean out cogs that no longer has a file
        log.log('Checking `cogs_status` file for non-existing cogs')
        to_be_removed = []
        for cog_name in cogs_status:
            if cog_name not in cog_files:
                log.log(f'Removing `{cog_name}`')
                to_be_removed.append(cog_name)
        for removal in to_be_removed:
            cogs_status.pop(removal)
        # Start cogs based on status
        log.log('Checking `cogs_status` file for enabled cogs')
        for cog_name in cogs_status:
            if cogs_status[cog_name] == 'enable':
                log.log('Loading cog: {}'.format(cog_name))
                await Cog.load_cog(cog_name)
        file_io.write_json(_vars.cogs_status_file, cogs_status)

    async def reload_all_cogs():
        'Reload all cogs which is already enabled'
        cogs_status = file_io.read_json(_vars.cogs_status_file)
        for cog_name in cogs_status:
            if cogs_status[cog_name] == 'enable':
                log.log('Reloading cog: {}'.format(cog_name))
                await Cog.reload_cog(cog_name)


# Commands
@_config.bot.command(name='ping')
async def ping(ctx):
    'Checks the bot\'s latency'
    await ctx.send(f'Pong! {round(_config.bot.latency * 1000)} ms')
    await ctx.message.add_reaction('✅')


@commands.check_any(
    commands.is_owner(),
    commands.has_permissions(manage_messages=True)
)
@_config.bot.command(aliases=['cls'])
async def delete(ctx, amount=0):
    'Delete x number of messages in the chat'
    if amount == 0:
        await ctx.send('Please specify the number of messages you want to delete!')
        await ctx.message.add_reaction('❌')
    elif amount <= 0:  # lower than 0
        await ctx.send("The number must be bigger than 0!")
        await ctx.message.add_reaction('❌')
    else:
        await ctx.message.add_reaction('✅')
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
        await ctx.message.add_reaction('✅')
    except Exception as failkick:
        await ctx.send("Failed to kick: " + str(failkick))
        await ctx.message.add_reaction('❌')


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
        await ctx.message.add_reaction('✅')
    except Exception as e:
        await ctx.send("Failed to ban: " + str(e))
        await ctx.message.add_reaction('❌')


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
    '''
    Enable, disable or list cogs for this bot
    '''

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

        # Sort cogs first
        cogs_file = dict(sorted(cogs_file.items()))
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
        await Cog.load_cog(cog_name)
        Cog.change_cog_status(cog_name, 'enable')
        await ctx.send(
            _vars.COGS_ENABLED.format(cog_name)
        )
        return True
    elif cmd_in == 'disable':
        # Stop cog
        await Cog.unload_cog(cog_name)
        Cog.change_cog_status(cog_name, 'disable')
        await ctx.send(
            _vars.COGS_DISABLED.format(cog_name)
        )
        return True
    elif cmd_in == 'list':
        # List cogs and their status
        cogs_status = file_io.read_json(_vars.cogs_status_file)
        await ctx.send(
            get_cogs_list(cogs_status)
        )
        return
    elif cmd_in == 'reload':
        # Reload all cogs
        await reload_all_cogs()
        await ctx.send('Cogs reloaded')
    elif cmd_in is None and cog_name is None:
        await ctx.send(
            COGS_TOO_FEW_ARGUMENTS
        )
        return
    else:
        log.log('Something else happened?')
        return False


_config.bot.run(_config.TOKEN)
