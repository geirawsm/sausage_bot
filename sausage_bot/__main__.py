#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"Set's up the bot, have a few generic commands and controls cogs"
import discord
from discord.ext import commands
from discord.app_commands import locale_str
import os
import asyncio
from tabulate import tabulate

from sausage_bot.util.args import args
from sausage_bot.util import config, envs, file_io, cogs, db_helper
from sausage_bot.util import discord_commands
from sausage_bot.util.i18n import I18N, available_languages, set_language
from sausage_bot.util.i18n import MyTranslator
from sausage_bot.util.log import log


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
        self, title_in=None, channel=None, mention=None
    ):
        super().__init__(
            title=title_in, timeout=120
        )
        self.comment_out = None
        self.channel = channel
        self.mention = mention
        self.error_out = None

        # Create elements
        if self.mention:
            label_in = I18N.t(
                'main.commands.say.modal.reply', member=self.mention.name
            )
        else:
            label_in = I18N.t('main.commands.say.modal.comment')
        self.mention
        comment_text = SayTextInput(
            style_in=discord.TextStyle.paragraph,
            label_in=label_in,
            required_in=True,
            placeholder_in=I18N.t('main.commands.say.modal.comment')
        )

        self.add_item(comment_text)

    async def on_submit(self, interaction: discord.Interaction):
        self.comment_out = self.children[0].value
        await interaction.response.send_message(
            I18N.t(
                'main.commands.say.modal.confirm', channel=self.channel.name
            ),
            ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error):
        log.error(f'Error when editing message: {error}')
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
        log.verbose(f'self.comment_in is: {self.comment_in}')

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
        self.comment_out = self.children[0].value
        await interaction.response.send_message(
            I18N.t('main.context_menu.edit_msg.edit_confirm'),
            ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error):
        log.error(f'Error when editing message: {error}')
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
    log.debug(f'locales: {locales}')
    return [
        discord.app_commands.Choice(
            name=locale, value=locale
        )
        for locale in locales if current.lower() in locale.lower()
    ]


# Create necessary folders before starting
check_and_create_folders = [
    envs.DB_DIR,
    envs.LOG_DIR
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
    # Create locale db if not exists
    log.verbose('Checking locale db')
    await db_helper.prep_table(
        table_in=envs.locale_db_schema,
        old_inserts=['en']
    )
    locale_db = await db_helper.get_output(
        template_info=envs.locale_db_schema,
        single=True
    )
    log.debug(f'Setting locale to `{locale_db}`')
    I18N.set('locale', locale_db)
    await config.bot.tree.set_translator(MyTranslator())
    for guild in config.bot.guilds:
        if guild.name == config.env('DISCORD_GUILD'):
            log.log(
                I18N.t('main.msg.bot_connected',
                       bot=config.bot.user,
                       server=guild.name
                       )
            )
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
                    default=I18N.t('main.msg.bot_watching')
                )
            )
        )
    # Make sure that the BOT_CHANNEL is present
    if config.BOT_CHANNEL not in discord_commands.get_text_channel_list():
        bot_channel = config.BOT_CHANNEL
        log.debug(f'Bot channel `{bot_channel}` does not exist, creating...')
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


@commands.check_any(commands.is_owner())
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
    #log.debug('Clearing commands...')
    #config.bot.tree.clear_commands(guild=None)
    #config.bot.tree.clear_commands(guild=ctx.guild)
    await _reply.edit(
        content='✅💭 {}'.format(
            I18N.t('main.commands.synclocal.msg_cont_copy')
        )
    )
    log.debug('Copying global commands...')
    config.bot.tree.copy_global_to(guild=ctx.guild)
    for command in config.bot.tree.get_commands():
        log.debug(f'Checking {command.name}')
    log.debug('Syncing...')
    await config.bot.tree.sync(guild=ctx.guild)
    await _reply.edit(
        content='✅✅ {}'.format(
            I18N.t('main.commands.synclocal.msg_confirm')
        )
    )
    log.debug('Done')


@commands.is_owner()
@config.bot.command(name='syncglobal')
async def syncglobal(ctx):
    _reply = await ctx.reply(
        '💭💭 {}'.format(
            I18N.t('main.commands.syncglobal.msg_starting')
        )
    )
    log.debug('Clearing commands...')
    config.bot.tree.clear_commands(guild=None)
    for command in config.bot.tree.get_commands():
        log.debug(f'Checking {command.name}')
    log.debug('Syncing...')
    await config.bot.tree.sync(guild=None)
    await _reply.edit(
        content='✅✅ {}'.format(
            I18N.t('main.commands.syncglobal.msg_confirm')
        )
    )
    log.debug('Done')


@commands.is_owner()
@config.bot.command(name='clearglobals')
async def clear_globals(ctx):
    log.debug('Deleting global commands...')
    _reply = await ctx.reply(
        '💭 {}'.format(
            'Deleting global commands...'
            #I18N.t('main.commands.synclocal.msg_starting')
        )
    )
    config.bot.tree.clear_commands(guild=None)
    await config.bot.tree.sync(guild=None)
    log.debug('Commands deleted')
    await _reply.edit(
        content='✅ {}'.format(
            #I18N.t('main.commands.synclocal.msg_confirm')
            'Global commands deleted'
        )
    )


@commands.is_owner()
@config.bot.command(name='clearlocals')
async def clear_locals(ctx):
    log.debug('Deleting local commands...')
    _reply = await ctx.reply(
        '💭 {}'.format(
            'Deleting local commands...'
            #I18N.t('main.commands.synclocal.msg_starting')
        )
    )
    config.bot.tree.clear_commands(guild=ctx.guild)
    await config.bot.tree.sync(guild=ctx.guild)
    log.debug('Commands deleted')
    await _reply.edit(
        content='✅ {}'.format(
            #I18N.t('main.commands.synclocal.msg_confirm')
            'Local commands deleted'
        )
    )


@commands.is_owner()
@config.bot.tree.command(
    name='version', description=locale_str(I18N.t('main.owner_only'))
)
async def get_version(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    version_in = file_io.read_json(envs.version_file)
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


@commands.check_any(
    commands.is_owner(),
    commands.has_permissions(manage_messages=True)
)
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


@commands.check_any(
    commands.is_owner(),
    commands.has_permissions(kick_members=True)
)
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


@commands.check_any(
    commands.is_owner(),
    commands.has_permissions(ban_members=True)
)
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


@commands.check_any(commands.is_owner())
@config.bot.tree.command(
    name='say', description=locale_str(I18N.t('main.commands.say.command'))
)
async def say(
    interaction: discord.Interaction, channel: discord.TextChannel,
    message_id: str = None, mention: discord.Member = None
):
    reply_msg = None
    log.debug(f'`channel` is {channel} ({type(channel)})')
    if message_id and mention:
        log.error('Can\'t use `message_id` and `mention` at the same time')
        await interaction.response.send_message(
            I18N.t('main.commands.say.modal.error_both_args'),
            ephemeral=True
        )
        return
    if message_id:
        reply_msg = await discord_commands.get_message_obj(
            msg_id=message_id, channel_name_or_id=channel.name
        )
        log.debug(f'Got `reply_msg`: {reply_msg}')
    modal_in = SayModal(
        title_in=I18N.t('main.commands.say.modal.title'),
        channel=channel,
        mention=mention
    )
    await interaction.response.send_modal(modal_in)
    await modal_in.wait()
    if reply_msg:
        await reply_msg.reply(modal_in.comment_out)
    elif channel:
        msg_out = ''
        if mention:
            msg_out = mention.mention
        msg_out += modal_in.comment_out
        await channel.send(msg_out)
    return


@commands.check_any(
    commands.is_owner(),
    commands.has_permissions(administrator=True)
)
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
    log.debug(f'Got this from `tasks_in_db`: {tasks_in_db}')
    text_out = '```{}```'.format(
        tabulate(
            tasks_in_db, headers=['Cog', 'Task', 'Status']
        )
    )
    log.debug(f'Returning:\n{text_out}')
    await interaction.followup.send(text_out, ephemeral=True)
    return


@commands.check_any(commands.is_owner())
@config.bot.tree.command(
    name='language', description=locale_str(I18N.t('main.owner_only'))
)
@discord.app_commands.autocomplete(language=locales_autocomplete)
async def language(
    interaction: discord.Interaction, language: str
):
    await interaction.response.defer(ephemeral=True)
    log.verbose(f'Setting language to {language}')
    await set_language(language)
    log.verbose('Syncing commands')
    await config.bot.tree.sync()
    await interaction.followup.send(
        I18N.t(
            'main.commands.language.confirm_language_set',
            language=language
        ),
        ephemeral=True)
    return


@commands.check_any(
    commands.is_owner(),
    commands.has_permissions(administrator=True)
)
@config.bot.tree.context_menu(
    name=locale_str(I18N.t('main.context_menu.edit_msg.name'))
)
async def edit_bot_say_msg(
    interaction: discord.Interaction, message: discord.Message
):
    log.debug(
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
    if modal_in.comment_out is not None:
        await message.edit(content=modal_in.comment_out)
    return


try:
    config.bot.run(config.DISCORD_TOKEN)
except Exception as _error:
    log.error(f'Could not start bot: {_error}')
