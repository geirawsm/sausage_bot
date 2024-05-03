#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"Set's up the bot, have a few generic commands and controls cogs"
import discord
from discord.ext import commands
import os
import asyncio
from tabulate import tabulate

from sausage_bot.util.args import args
from sausage_bot.util import config, envs, file_io, cogs, db_helper
from sausage_bot.util import discord_commands
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

    log.verbose('Checking cog tasks db')
    await db_helper.prep_table(
        envs.tasks_db_schema
    )
    log.verbose('Deleting old json files')
    if file_io.file_size(envs.cogs_status_file):
        log.verbose('Found old json file')
        file_io.remove_file(envs.cogs_status_file)
    await cogs.Cogs.load_and_clean_cogs_internal()
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


@commands.check_any(commands.is_owner())
@config.bot.tree.command(
    name='syncglobal', description='Owner only'
)
async def sync_global(interaction: discord.Interaction):
    await config.bot.tree.sync()
    _cmd = ''
    for command in config.bot.tree.get_commands():
        _cmd += (f"- {command.name} (Type: "
                 "{'Slash Command' if "
                 "isinstance(command, discord.app_commands.Command) "
                 "else 'Text Command'})"
                 )
        if _cmd != '':
            _cmd += '\n'
    await interaction.response.send_message(
        f'Commands synched!\n{_cmd}',
        ephemeral=True
    )
    return


@commands.is_owner()
@config.bot.tree.command(
    name='syncdev', description='Owner only'
)
async def sync_dev(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    config.bot.tree.copy_global_to(
        guild=discord_commands.get_guild()
    )
    await config.bot.tree.sync(
        guild=discord_commands.get_guild()
    )
    _cmd = ''
    slash_cmds = []
    text_cmds = []
    for command in config.bot.tree.get_commands():
        log.debug(f'Checking {command.name}')
        if isinstance(command, discord.app_commands.Command):
            slash_cmds.append(command.name)
        else:
            text_cmds.append(command.name)
    if len(slash_cmds) > 0:
        _cmd += 'Slash-commands:'
        for cmd in slash_cmds:
            _cmd += f'\n- {cmd}'
    if len(text_cmds) > 0:
        if len(_cmd) > 0:
            _cmd += '\n'
        _cmd += 'Text-commands:'
        for cmd in text_cmds:
            _cmd += f'\n- {cmd}'

    await interaction.followup.send(
        f'Commands synched!\n{_cmd}',
        ephemeral=True
    )
    return


# This is for the example purposes only and should only be used for
# debugging
@config.bot.tree.command(
    name='synclocal'
)
async def synclocal(ctx):
    # sync to the guild where the command was used
    log.debug('Clearing commands...')
    config.bot.tree.clear_commands(guild=ctx.guild)
    log.debug('Copying global commands...')
    config.bot.tree.copy_global_to(guild=ctx.guild)
    for command in config.bot.tree.get_commands():
        log.debug(f'Checking {command.name}')
    log.debug('Syncing...')
    await config.bot.tree.sync(guild=ctx.guild)
    log.debug('Done')


# Commands
@config.bot.tree.command(
    name='ping', description='Sjekk latency'
)
async def ping(interaction: discord.Interaction):
    'Checks the bot latency'
    await interaction.response.send_message(
        f'Pong! {round(config.bot.latency * 1000)} ms',
        ephemeral=True
    )


@commands.check_any(
    commands.is_owner(),
    commands.has_permissions(manage_messages=True)
)
@config.bot.tree.command(
    name='delete',
    description='Delete `amount` number of messages in the chat'
)
async def delete(interaction: discord.Interaction, amount: int):
    'Delete `amount` number of messages in the chat'
    if amount <= 0:
        await interaction.response.send_message(
            'The number must be bigger than 0',
            ephemeral=True
        )
    else:
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.purge(
            limit=amount, reason='Massesletting via bot'
        )
        await interaction.followup.send(
            f'Deleted {amount} messages',
            ephemeral=True
        )
    return


@commands.check_any(
    commands.is_owner(),
    commands.has_permissions(kick_members=True)
)
@config.bot.tree.command(
    name='kick',
    description='Kick a user with reason'
)
async def kick(
    interaction: discord.Interaction, member: discord.Member = None,
    *, reason: str = None
):
    '''
    Kick a member from the server

    Parameters
    ------------
    member: discord.Member
        Name of Discord user you want to kick (default: None)
    reason: str
        Reason for kicking user (default: None)
    '''
    await interaction.response.defer(ephemeral=True)
    try:
        await member.kick(reason=reason)
        await interaction.followup.send(
            f'{member} has been kicked',
            ephemeral=True
        )
    except Exception as failkick:
        await interaction.followup.send(
            f'Failed to kick: {failkick}',
            ephemeral=True
        )


@commands.check_any(
    commands.is_owner(),
    commands.has_permissions(ban_members=True)
)
@config.bot.tree.command(
    name='ban',
    description='Ban a user with reason'
)
async def ban(
    interaction: discord.Interaction, member: discord.Member = None,
    *, reason: str = None
):
    '''
    Ban a member from the server

    Parameters
    ------------
    member: discord.Member
        Name of Discord user you want to ban (default: None)
    reason: str
        Reason for banning user (default: None)
    '''
    await interaction.response.defer(ephemeral=True)
    try:
        await member.ban(reason=reason)
        await interaction.followup.send(
            f'{member} has been banned',
            ephemeral=True
        )
    except Exception as failban:
        await interaction.followup.send(
            f'Failed to ban: {failban}',
            ephemeral=True
        )


@commands.check_any(commands.is_owner())
@config.bot.tree.command(
    name='say', description='Sender melding til en kanal. Fyll inn '
    '`message_id` hvis det skal svares på en melding'
)
async def say(
    interaction: discord.Interaction, channel: discord.TextChannel,
    message_id: str = None, *, message: str
):
    await interaction.response.defer(ephemeral=True)
    try:
        async with channel.typing():
            await asyncio.sleep(3)
        if message_id:
            reply_msg = await discord_commands.get_message_obj(
                msg_id=message_id, channel=channel
            )
            log.debug(f'Got `reply_msg`: {reply_msg}')
            await reply_msg.reply(message)
        else:
            await channel.send(message)
        await interaction.followup.send(
            f'Melding sent til `#{channel.name}`', ephemeral=True
        )
    except discord.Forbidden:
        await interaction.followup.send(
            'Jeg har ikke tilgang til å sende melding '
            f'i `#{channel.name}`.',
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f'An error occurred: {e}', ephemeral=True
        )


@commands.check_any(
    commands.is_owner(),
    commands.has_permissions(administrator=True)
)
@config.bot.tree.command(
    name='sayagain',
    description='Endre en tidligere melding sendt med /say'
)
async def say_again(
    interaction: discord.Interaction, msg_id: str, *, text: str
):
    'Make the bot rephrase a previous message'
    await interaction.response.defer(ephemeral=True)
    guild = discord_commands.get_guild()
    if guild is None:
        return None
    log.debug(f'`guild` is {guild}')
    for channel in guild.text_channels:
        async for message in channel.history(limit=25):
            if str(message.id) == str(msg_id):
                async with channel.typing():
                    await asyncio.sleep(3)
                old_text = message.content
                new_message = await message.edit(
                    content=text
                )
                new_text = new_message.content
                await interaction.followup.send(
                    f'Changed [message]({new_message.jump_url}) from:\n'
                    f'```{old_text}```\nto\n```{new_text}```',
                    ephemeral=True, suppress_embeds=True
                )


@commands.check_any(
    commands.is_owner(),
    commands.has_permissions(administrator=True)
)
@config.bot.tree.command(
    name="tasks", description="List tasks and their status"
)
async def get_tasks_list(interaction: discord.Interaction):
    '''
    Get a pretty list of all the tasks
    #autodoc skip#
    '''
    await interaction.response.defer()
    tasks_in_db = await db_helper.get_output(
        template_info=envs.tasks_db_schema,
        order_by=[
            ('cog', 'ASC'),
            ('task', 'ASC')
        ]
    )
    log.debug(f'Got this from `tasks_in_db`: {tasks_in_db}')
    text_out = '```{}```'.format(
        tabulate(
            tasks_in_db, headers=['Cog', 'Task', 'Status']
        )
    )
    log.debug(f'Returning:\n{text_out}')
    await interaction.followup.send(text_out, ephemeral=True)
    return


try:
    config.bot.run(config.DISCORD_TOKEN)
except Exception as e:
    log.error(f'Could not start bot: {e}')
