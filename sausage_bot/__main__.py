#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"Set's up the bot, have a few generic commands and controls cogs"
import discord
from discord.ext import commands
import os
import locale
from sausage_bot.util.args import args
from sausage_bot.util import config, envs, file_io
from sausage_bot.util.log import log


# Set locale
locale.setlocale(locale.LC_ALL, config.LOCALE)

# Create necessary folders before starting
check_and_create_folders = [
    envs.LOG_DIR, envs.JSON_DIR, envs.COGS_DIR, envs.STATIC_DIR
]
for folder in check_and_create_folders:
    try:
        os.makedirs(folder)
    except (FileExistsError):
        pass

# Create necessary files before starting
log.log_more('Creating necessary files')
check_and_create_files = [
    (envs.cogs_status_file, '{}'),
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
        if guild.name == config.GUILD:
            break
    log.log('{} has connected to `{}`'.format(config.bot.user, guild.name))
    await Cog.load_and_clean_cogs()
    if args.maintenance:
        log.log('Maintenance mode activated', color='RED')
        await config.bot.change_presence(
            status=discord.Status.dnd)
    else:
        if not config.BOT_WATCHING:
            presence_name = 'some random youtube video'
        if config.BOT_WATCHING:
            presence_name = config.BOT_WATCHING
        await config.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=config.BOT_WATCHING
            )
        )

# Cogs
class Cog:
    '''
    Control the cogs for the bot
    #autodoc skip#
    '''
    def change_cog_status(cog_name, status):
        '''
        Change a cog status in the status file

        `cog_name` should be name of cog

        `status` should be `enable` or `disable`
        #autodoc skip#
        '''
        accepted_status = ['enable', 'e', 'disable', 'd']
        if not any(status == ok_status for ok_status in accepted_status):
            log.log('This command only accept `enable` or `disable`')
            return False
        cogs_status = file_io.read_json(envs.cogs_status_file)
        try:
            # Change status
            cogs_status[cog_name] = status
            # Write changes
            file_io.write_json(envs.cogs_status_file, cogs_status)
            return True
        except Exception as e:
            log.log(envs.COGS_CHANGE_STATUS_FAIL.format(e))
            return False

    async def load_cog(cog_name):
        '''
        Load a specific cog by `cog_name`
        #autodoc skip#
        '''
        await config.bot.load_extension(
            '{}.{}'.format(
                envs.COGS_REL_DIR, f'{cog_name}'
            )
        )
        return

    async def unload_cog(cog_name):
        '''
        Unload a specific cog by `cog_name`
        #autodoc skip#
        '''
        await config.bot.unload_extension(
            '{}.{}'.format(
                envs.COGS_REL_DIR, f'{cog_name}'
            )
        )
        return

    async def reload_cog(cog_name):
        '''
        Reload a specific cog by `cog_name`
        #autodoc skip#
        '''
        await config.bot.reload_extension(
            '{}.{}'.format(
                envs.COGS_REL_DIR, f'{cog_name}'
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
        #autodoc skip#
        '''
        cog_files = []
        # Add cogs that are not present in the `cogs_status` file
        cogs_status = file_io.read_json(envs.cogs_status_file)
        try:
            log.debug(
                f'These cogs are already registered: '
                f'{sorted(list(file_io.read_json(envs.cogs_status_file)))}'
            )
        except TypeError as e:
            log.debug(
                f'Error when reading json file.'
            )
        log.debug(f'Got these files in `COGS_DIR`: {os.listdir(envs.COGS_DIR)}')
        for filename in os.listdir(envs.COGS_DIR):
            if filename.endswith('.py') and not filename.startswith('_'):
                cog_name = filename[:-3]
                log.debug(f'Checking `{cog_name}`')
                # Add all cog names to `cog_files` for easier cleaning
                cog_files.append(cog_name)
                # Hvor er `cog_status` egentlig?
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
            if cogs_status[cog_name] in ['enable', 'e']:
                log.log('Loading cog: {}'.format(cog_name))
                await Cog.load_cog(cog_name)
        file_io.write_json(envs.cogs_status_file, cogs_status)

    async def reload_all_cogs():
        '''
        Reload all cogs which is already enabled
        #autodoc skip#
        '''
        cogs_status = file_io.read_json(envs.cogs_status_file)
        for cog_name in cogs_status:
            if cogs_status[cog_name] == 'enable':
                log.log('Reloading cog: {}'.format(cog_name))
                await Cog.reload_cog(cog_name)


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
        await ctx.send('Please specify the number of messages you want to delete!')
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
        await ctx.message.reply('You have to reply to a message: `!edit [text]`')
        return
    elif ctx.message.reference.message_id:
        msgid = ctx.message.reference.message_id
        edit_msg = await ctx.fetch_message(msgid)
        await edit_msg.edit(content=text)
        await ctx.message.delete()
        return


@ config.bot.command()
@ commands.check_any(
    commands.is_owner(),
    commands.has_permissions(administrator=True)
)
async def cog(ctx, cmd_in, *cog_names):
    '''
    Enable, disable, reload or list cogs for this bot

    cmd_in      "enable"/"e" or "disable"/"d"
    cog_names   Name(s) of wanted cog, or "all"
    '''

    async def action_on_cog(cog_name, cmd_in):
        '#autodoc skip#'
        if cmd_in in ['enable', 'e']:
            await Cog.load_cog(cog_name)
            Cog.change_cog_status(cog_name, 'enable')
        elif cmd_in in ['disable', 'd']:
            await Cog.unload_cog(cog_name)
            Cog.change_cog_status(cog_name, 'disable')

    async def action_on_cog(cog_name, cmd_in):
        '#autodoc skip#'
        if cmd_in in ['enable', 'e']:
            await Cog.load_cog(cog_name)
            Cog.change_cog_status(cog_name, 'enable')
        elif cmd_in in ['disable', 'd']:
            await Cog.unload_cog(cog_name)
            Cog.change_cog_status(cog_name, 'disable')

    def get_cogs_list(cogs_file):
        '''
        Get a pretty list of all the cogs
        #autodoc skip#
        '''
        def get_cog_item_lengths(cogs_file):
            '''
            Find max lengths for info fields about a cog
            #autodoc skip#
            '''
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
        log.debug(f'Got this from `cogs_file`: {cogs_file}')
        text_out = '```'
        lengths = get_cog_item_lengths(cogs_file)
        template_line = '{:{cog_len}} | {:{status_len}}'
        # Add headers first
        text_out += template_line.format(
            'Cog', 'Status', cog_len=lengths['cog_len'],
            status_len=lengths['status_len']
        )
        text_out += '\n'
        for cog in cogs_file:
            text_out += template_line.format(
                cog, cogs_file[cog], cog_len=lengths['cog_len'],
                status_len=lengths['status_len']
            )
            if cog != list(cogs_file)[-1]:
                text_out += '\n'
        text_out += '```'
        log.debug(f'Returning:\n{text_out}')
        return text_out

    if cmd_in in ['enable', 'e', 'disable', 'd']:
        if cmd_in == 'e':
            cmd_in = 'enable'
        if cmd_in == 'd':
            cmd_in = 'disable'
        cogs_file = file_io.read_json(envs.cogs_status_file)
        cogs_file = dict(sorted(cogs_file.items()))
        names_out = ''
        for cog_name in cog_names:
            if cog_name == 'all':
                for cog_name in cogs_file:
                    if cogs_file[cog_name] != cmd_in:
                        await action_on_cog(cog_name, cmd_in)
                        names_out += cog_name
                        if len(cog_names) > 1 and cog_name != cog_names[-1]:
                            names_out += ', '
            else:
                await action_on_cog(cog_name, cmd_in)
                names_out += cog_name
                if len(cog_names) > 1 and cog_name != cog_names[-1]:
                    names_out += ', '
        if cmd_in in ['enable', 'e']:
            if cog_names[0] == 'all':
                conf_msg = envs.ALL_COGS_ENABLED
            else:
                conf_msg = envs.COGS_ENABLED.format(names_out)
        elif cmd_in in ['disable', 'd']:
            if cog_names[0] == 'all':
                conf_msg = envs.ALL_COGS_DISABLED
            else:
                conf_msg = envs.COGS_DISABLED.format(names_out)
        await ctx.send(conf_msg)
        return True
    elif cmd_in == 'list':
        # List cogs and their status
        cogs_status = file_io.read_json(envs.cogs_status_file)
        await ctx.send(
            get_cogs_list(cogs_status)
        )
        return
    elif cmd_in == 'reload':
        # Reload all cogs
        await Cog.reload_all_cogs()
        await ctx.send('Cogs reloaded')
        return
    elif cmd_in is None and cog_name is None:
        await ctx.send(
            envs.COGS_TOO_FEW_ARGUMENTS
        )
        return
    else:
        log.log('Something else happened?')
        return False


config.bot.run(config.TOKEN)

def setup(bot):
    @bot.event
    async def on_command_error(ctx, exception):
        # if the exception is of any of selected classes redirect to discord
        if isinstance(exception, InvalidEndOfQuotedStringError):
            await ctx.message.reply('Sjekk bruken av anførselstegn')
