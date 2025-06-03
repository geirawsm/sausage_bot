#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'__main__: Set up the bot, have a few generic commands and controls cogs'
import discord
from discord.ext import commands, tasks
from discord.app_commands import locale_str
from tabulate import tabulate
from pendulum import timezones as p_timezones
import asyncio
import aiosqlite

from sausage_bot.util.args import args
from sausage_bot.util import config, envs, file_io, cogs, db_helper, net_io
from sausage_bot.util import discord_commands
from sausage_bot.util.i18n import I18N, available_languages, set_language
from sausage_bot.util.i18n import MyTranslator

logger = config.logger


@tasks.loop(
    hours=1
)
async def get_random_user_agent():
    await net_io.fetch_random_user_agent()


class SayTextInput(discord.ui.TextInput):
    def __init__(
            self, style_in, label_in, default_in=None, required_in=None,
            placeholder_in=None
    ):
        super().__init__(
            style=style_in,
            label=label_in,
            default=default_in,
            required=required_in,
            placeholder=placeholder_in
        )


class SayModal(discord.ui.Modal):
    def __init__(
        self, title_in=None, channel=None
    ):
        super().__init__(
            title=title_in, timeout=120
        )
        self.comment_out = None
        self.channel = channel
        self.error_out = None

        # Create elements
        label_in = I18N.t('main.commands.say.modal.comment')
        comment_text = SayTextInput(
            style_in=discord.TextStyle.paragraph,
            label_in=label_in,
            required_in=True,
            placeholder_in=I18N.t('main.commands.say.modal.comment')
        )

        self.add_item(comment_text)

    async def on_submit(self, interaction: discord.Interaction):
        comment_out = discord_commands.check_user_channel_role(
            self.children[0].value
        )
        logger.debug(f'Got `comment_out`: {comment_out}')
        msg_out = I18N.t('main.context_menu.edit_msg.edit_confirm')
        if len(comment_out['username_errors']) > 0:
            msg_out += I18N.t(
                'main.context_menu.edit_msg.edit_confirm_with_errors',
                errors=', '.join(comment_out['username_errors'])
            )
        if len(comment_out['channel_errors']) > 0:
            if len(msg_out) == 0:
                msg_out += I18N.t(
                    'main.context_menu.edit_msg.edit_confirm_with_errors',
                    errors=', '.join(comment_out['channel_errors'])
                )
            else:
                # TODO i18n
                msg_out += '\nChannels: {}'.format(
                    ', '.join(comment_out['channel_errors'])
                )
        await interaction.response.send_message(
            I18N.t(
                'main.commands.say.modal.confirm', channel=self.channel.name
            ),
            ephemeral=True
        )
        self.comment_out = comment_out['text']
        return

    async def on_error(self, interaction: discord.Interaction, error):
        logger.error(f'Error when editing message: {error}')
        await interaction.response.send_message(
            I18N.t(
                'main.commands.say.modal.error_sending',
                channel=self.channel.name,
                error=error
            ),
            ephemeral=True
        )


class EditModal(discord.ui.Modal):
    def __init__(
        self, title_in=None, comment_in=None
    ):
        super().__init__(
            title=title_in, timeout=60
        )
        self.comment_in = comment_in
        self.comment_out = None
        self.error_out = None
        logger.debug(f'self.comment_in is: {self.comment_in}')

        # Create elements
        comment_text = SayTextInput(
            style_in=discord.TextStyle.paragraph,
            label_in=I18N.t('quote.modals.quote_text'),
            default_in=self.comment_in,
            required_in=True,
            placeholder_in='Text'
        )

        self.add_item(comment_text)

    async def on_submit(self, interaction: discord.Interaction):
        comment_out = discord_commands.check_user_channel_role(
            self.children[0].value
        )
        logger.debug(f'Got `comment_out`: {comment_out}')
        msg_out = I18N.t('main.context_menu.edit_msg.edit_confirm')
        if len(comment_out['username_errors']) > 0:
            msg_out += I18N.t(
                'main.context_menu.edit_msg.edit_confirm_with_errors',
                errors=', '.join(comment_out['username_errors'])
            )
        if len(comment_out['channel_errors']) > 0:
            if len(msg_out) == 0:
                msg_out += I18N.t(
                    'main.context_menu.edit_msg.edit_confirm_with_errors',
                    errors=', '.join(comment_out['channel_errors'])
                )
            else:
                # TODO i18n
                msg_out += '\nChannels: {}'.format(
                    ', '.join(comment_out['channel_errors'])
                )

        self.comment_out = comment_out['text']

        await interaction.response.send_message(
            msg_out, ephemeral=True
        )
        return

    async def on_error(self, interaction: discord.Interaction, error):
        logger.error(f'Error when editing message: {error}')
        self.error_out = error
        await interaction.response.send_message(
            I18N.t(
                'main.context_menu.edit_msg.edit_error',
                error=error
            ),
            ephemeral=True
        )


async def locales_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    locales = available_languages()
    logger.debug(f'locales: {locales}')
    return [
        discord.app_commands.Choice(
            name=locale, value=locale
        )
        for locale in locales if current.lower() in locale.lower()
    ][:25]


async def timezones_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    logger.debug(f'p_timezones(): {p_timezones()}')
    return [
        discord.app_commands.Choice(
            name=timezone, value=timezone
        )
        for timezone in p_timezones() if current.lower() in timezone.lower()
    ][:25]


@config.bot.event
async def on_ready():
    '''
    When the bot is ready, it will notify in the log.
    #autodoc skip#
    '''
    await config.bot.tree.set_translator(MyTranslator())
    for guild in config.bot.guilds:
        if guild.name == config.env('DISCORD_GUILD'):
            logger.info(
                I18N.t('main.msg.bot_connected',
                       bot=config.bot.user,
                       server=guild.name
                       )
            )
            break

    logger.debug('Checking cog tasks db')
    await db_helper.prep_table(
        envs.tasks_db_schema
    )
    logger.debug('Deleting old json files')
    if file_io.file_size(envs.cogs_status_file):
        logger.debug('Found old json file')
        file_io.remove_file(envs.cogs_status_file)
    await cogs.Cogs.load_and_clean_cogs_internal()
    if args.maintenance:
        logger.info('Maintenance mode activated', color='RED')
        await config.bot.change_presence(
            status=discord.Status.dnd
        )
    # Make sure that the BOT_CHANNEL is present
    bot_channel = config.BOT_CHANNEL
    if bot_channel not in discord_commands.get_text_channel_list():
        logger.debug(
            f'Bot channel `{bot_channel}` does not exist, creating...'
        )
        guild = discord_commands.get_guild()
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                read_messages=False
            ),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        channel_out = await guild.create_text_channel(
            name=str(bot_channel),
            topic=I18N.t(
                'main.msg.create_log_channel_logging',
                botname=config.bot.user.name
            ),
            overwrites=overwrites
        )
        channel_out.set_permissions()


sync_group = discord.app_commands.Group(
    name="sync", description=locale_str(
        I18N.t('stats.commands.groups.stats')
    )
)


@commands.is_owner()
@sync_group.command(
    name='global', description=locale_str(I18N.t('main.owner_only'))
)
async def sync_global(interaction: discord.Interaction):
    await config.bot.tree.sync()
    _cmd = ''
    for command in config.bot.tree.get_commands():
        slash_or_text = 'Slash Command' if isinstance(
            command, discord.app_commands.Command
        ) else 'Text Command'
        _cmd += (
            f'- {command.name} (Type: {slash_or_text})'
        )
        if _cmd != '':
            _cmd += '\n'
    await interaction.response.send_message(
        # TODO i18n
        f'Commands synched!\n{_cmd}',
        ephemeral=True
    )
    return


@commands.is_owner()
@config.bot.tree.command(
    name='syncdev', description=locale_str(I18N.t('main.owner_only')),
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
        logger.debug(f'Checking {command.name}')
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


# This needs to be used to init the first sync so
# `syncglobal` and `syncdev` will be visible
@commands.is_owner()
@config.bot.command(name='synclocal')
async def synclocal(ctx):
    # sync to the guild where the command was used
    _reply = await ctx.reply(
        '💭💭 {}'.format(
            I18N.t('main.commands.synclocal.msg_starting')
        )
    )
    # logger.debug('Clearing commands...')
    # config.bot.tree.clear_commands(guild=None)
    # config.bot.tree.clear_commands(guild=ctx.guild)
    await _reply.edit(
        content='✅💭 {}'.format(
            I18N.t('main.commands.synclocal.msg_cont_copy')
        )
    )
    logger.debug('Copying global commands...')
    config.bot.tree.copy_global_to(guild=ctx.guild)
    for command in config.bot.tree.get_commands():
        logger.debug(f'Checking {command.name}')
    logger.debug('Syncing...')
    await config.bot.tree.sync(guild=ctx.guild)
    await _reply.edit(
        content='✅✅ {}'.format(
            I18N.t('main.commands.synclocal.msg_confirm')
        )
    )
    logger.debug('Done')


@commands.is_owner()
@config.bot.command(name='syncglobal')
async def syncglobal(ctx):
    _reply = await ctx.reply(
        '💭💭 {}'.format(
            I18N.t('main.commands.syncglobal.msg_starting')
        )
    )
    logger.debug('Clearing commands...')
    config.bot.tree.clear_commands(guild=None)
    for command in config.bot.tree.get_commands():
        logger.debug(f'Checking {command.name}')
    logger.debug('Syncing...')
    await config.bot.tree.sync(guild=None)
    await _reply.edit(
        content='✅✅ {}'.format(
            I18N.t('main.commands.syncglobal.msg_confirm')
        )
    )
    logger.debug('Done')


@commands.is_owner()
@config.bot.command(name='clearglobals')
async def clear_globals(ctx):
    logger.debug('Deleting global commands...')
    _reply = await ctx.reply(
        '💭 {}'.format(
            I18N.t('main.commands.clearglobals.msg_starting')
        )
    )
    config.bot.tree.clear_commands(guild=None)
    await config.bot.tree.sync(guild=None)
    logger.debug('Commands deleted')
    await _reply.edit(
        content='✅ {}'.format(
            I18N.t('main.commands.clearglobals.msg_confirm')
        )
    )


@commands.is_owner()
@config.bot.command(name='clearlocals')
async def clear_locals(ctx):
    logger.debug('Deleting local commands...')
    _reply = await ctx.reply(
        '💭 {}'.format(
            I18N.t('main.commands.clearlocals.msg_starting')
        )
    )
    config.bot.tree.clear_commands(guild=ctx.guild)
    await config.bot.tree.sync(guild=ctx.guild)
    logger.debug('Commands deleted')
    await _reply.edit(
        content='✅ {}'.format(
            I18N.t('main.commands.clearlocals.msg_confirm')
        )
    )


@commands.is_owner()
@config.bot.tree.command(
    name='version', description=locale_str(I18N.t('main.owner_only'))
)
async def get_version(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    version_in = file_io.read_json(envs.version_file)
    logger.debug(f'Got `version_in`: {version_in}')
    await interaction.followup.send(
        'Branch: {}\n'
        'Last commit message: {}\n'
        'Last commit: {}\n'
        'Last run number: {}'.format(
            version_in['BRANCH'],
            version_in['LAST_COMMIT_MSG'],
            version_in['LAST_COMMIT'],
            version_in['LAST_RUN_NUMBER']
        ),
        ephemeral=True
    )
    return


# Commands
@commands.is_owner()
@config.bot.tree.command(
    name='ping', description=locale_str(I18N.t('main.commands.ping.command'))
)
async def ping(interaction: discord.Interaction):
    'Checks the bot latency'
    await interaction.response.send_message(
        f'Pong! {round(config.bot.latency * 1000)} ms',
        ephemeral=True
    )


@commands.is_owner()
@config.bot.tree.command(
    name='delete',
    description=locale_str(I18N.t('main.commands.delete.command'))
)
async def delete(interaction: discord.Interaction, amount: int):
    'Delete `amount` number of messages in the chat'
    if amount <= 0:
        await interaction.response.send_message(
            I18N.t('main.commands.delete.less_than_0'),
        )
    else:
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.purge(
            limit=amount, reason=I18N.t('main.commands.delete.log_confirm')
        )
        await interaction.followup.send(
            I18N.t('main.commands.delete.msg_confirm',
                   amount=amount),
            ephemeral=True
        )
    return


@commands.is_owner()
@config.bot.tree.command(
    name='kick',
    description=locale_str(I18N.t('main.commands.kick.command'))
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
            I18N.t(
                'main.commands.kick.msg_confirm',
                member=member
            ),
            ephemeral=True
        )
    except Exception as _error:
        await interaction.followup.send(
            I18N.t(
                'main.commands.kick.msg_failed',
                error=_error
            ),
            ephemeral=True
        )


@commands.is_owner()
@config.bot.tree.command(
    name='ban',
    description=locale_str(I18N.t('main.commands.ban.command'))
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
            I18N.t(
                'main.commands.ban.msg_confirm',
                member=member,
            ),
            ephemeral=True
        )
    except Exception as _error:
        await interaction.followup.send(
            I18N.t(
                'main.commands.ban.msg_failed',
                error=_error
            ),
            ephemeral=True
        )


@commands.is_owner()
@config.bot.tree.command(
    name='say', description=locale_str(I18N.t('main.commands.say.command'))
)
async def say(
    interaction: discord.Interaction, channel: discord.TextChannel,
    message_id: str = None
):
    reply_msg = None
    logger.debug(f'`channel` is {channel} ({type(channel)})')
    if message_id:
        reply_msg = await discord_commands.get_message_obj(
            msg_id=message_id, channel_name_or_id=channel.name
        )
        logger.debug(f'Got `reply_msg`: {reply_msg}')
    modal_in = SayModal(
        title_in=I18N.t('main.commands.say.modal.title'),
        channel=channel
    )
    await interaction.response.send_modal(modal_in)
    await modal_in.wait()
    if reply_msg:
        await reply_msg.reply(modal_in.comment_out)
    elif channel:
        await channel.send(modal_in.comment_out)
    return


@commands.is_owner()
@config.bot.tree.command(
    name="tasks", description=locale_str(I18N.t('main.commands.tasks.command'))
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
    logger.debug(f'Got this from `tasks_in_db`: {tasks_in_db}')
    text_out = '```{}```'.format(
        tabulate(
            tasks_in_db, headers={
                'cog': 'Cog', 'task': 'Task', 'status': 'Status'
            }
        )
    )
    logger.debug(f'Returning:\n{text_out}')
    await interaction.followup.send(text_out, ephemeral=True)
    return


@commands.is_owner()
@config.bot.tree.command(
    name='language', description=locale_str(I18N.t('main.owner_only'))
)
@discord.app_commands.autocomplete(language=locales_autocomplete)
async def language(
    interaction: discord.Interaction, language: str
):
    await interaction.response.defer(ephemeral=True)
    logger.debug(f'Setting language to {language}')
    await set_language(language)
    logger.debug('Syncing commands')
    await config.bot.tree.sync()
    await config.bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=config.env(
                'BOT_WATCHING',
                default=I18N.t('main.msg.bot_watching')
            )
        )
    )
    await interaction.followup.send(
        I18N.t(
            'main.commands.language.confirm_language_set',
            language=language
        ),
        ephemeral=True)
    return


@commands.is_owner()
@config.bot.tree.command(
    name='timezone', description=locale_str(I18N.t('main.owner_only'))
)
@discord.app_commands.autocomplete(timezone=timezones_autocomplete)
async def timezone(
    interaction: discord.Interaction, timezone: str
):
    async def set_timezone(timezone: str):
        db_info = envs.locale_db_schema
        table_name = db_info['name']
        _cmd = 'UPDATE {} SET {} = \'{}\' WHERE setting = '\
            '\'timezone\';'.format(
                table_name, 'value', timezone
            )
        try:
            async with aiosqlite.connect(db_info['db_file']) as db:
                await db.execute(_cmd)
                await db.commit()
            logger.debug('Done and commited!')
        except aiosqlite.OperationalError as e:
            logger.error(f'Error: {e}')
            return None

    await interaction.response.defer(ephemeral=True)
    logger.debug(f'Setting timezone to {timezone}')
    await set_timezone(timezone)
    await interaction.followup.send(
        # TODO i18n
        'Set timezone to `{}`'.format(timezone),
        ephemeral=True)
    return


@commands.is_owner()
@config.bot.tree.context_menu(
    name=locale_str(I18N.t('main.context_menu.edit_msg.name'))
)
async def edit_bot_say_msg(
    interaction: discord.Interaction, message: discord.Message
):
    logger.debug(
        f'`message.author.id` {message.author.id} '
        f'({type(message.author.id)})) vs `config.bot.user.id` '
        f'{config.bot.user.id} ({type(config.bot.user.id)}))'
    )
    if message.author.id != config.bot.user.id:
        await interaction.response.send_message(
            I18N.t('main.context_menu.edit_msg.not_bot'),
            ephemeral=True
        )
        return
    modal_in = EditModal(
        title_in=I18N.t('main.context_menu.edit_msg.name'),
        comment_in=message.content
    )
    await interaction.response.send_modal(modal_in)
    await modal_in.wait()
    await message.edit(content=modal_in.comment_out)
    return


# Create locale db if not exists
logger.debug('Checking locale db')
asyncio.run(
    db_helper.prep_table(
        table_in=envs.locale_db_schema,
        inserts=envs.locale_db_schema['inserts']
    )
)

try:
    config.bot.run(config.DISCORD_TOKEN)
except Exception as _error:
    logger.error(f'Could not start bot: {_error}')
