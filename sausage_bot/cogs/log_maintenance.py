#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import os
import discord
from discord.ext import commands, tasks
from discord.app_commands import locale_str
from tabulate import tabulate

from sausage_bot.util import envs, file_io
from sausage_bot.util import discord_commands, db_helper
from sausage_bot.util.i18n import I18N
from sausage_bot.util.log import log


async def name_of_settings_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    db_settings = await db_helper.get_output(
        template_info=envs.log_db_schema,
        select=('setting', 'value_help'),
    )
    settings = []
    for setting in db_settings:
        settings.append((setting[0], setting[1]))
    log.debug(f'settings: {settings}')
    return [
        discord.app_commands.Choice(
            name=f'{setting[0]} ({setting[1]})', value=str(setting[0])
        )
        for setting in settings if current.lower() in setting[0].lower()
    ]


class LogMaintenance(commands.Cog):
    '''
    Start or stop the log maintenance
    '''

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    log_group = discord.app_commands.Group(
        name="log",
        description=locale_str(I18N.t('log_maintenance.commands.log.cmd'))
    )
    log_maintenance_group = discord.app_commands.Group(
        name="maintenance", description=locale_str(
            I18N.t('log_maintenance.commands.maintenance.cmd')
        ), parent=log_group
    )
    log_settings_group = discord.app_commands.Group(
        name="settings", description=locale_str(
            I18N.t('log_maintenance.commands.settings.cmd')
        ), parent=log_group
    )

    @log_maintenance_group.command(
        name='start', description=locale_str(
            I18N.t('log_maintenance.commands.start.cmd')
        )
    )
    async def log_maintenance_start(
        self, interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)
        log.log('Task started')
        LogMaintenance.log_maintenance.start()
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[
                ('cog', 'log'),
                ('task', 'log_maintenance')
            ],
            updates=('status', 'started')
        )
        await interaction.followup.send(
            I18N.t('log_maintenance.commands.start.msg_confirm')
        )

    @log_maintenance_group.command(
        name='stop', description=locale_str(
            I18N.t('log_maintenance.commands.stop.cmd')
        )
    )
    async def rss_posting_stop(
        self, interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)
        log.log('Task stopped')
        LogMaintenance.log_maintenance.cancel()
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[
                ('task', 'log_maintenance'),
                ('cog', 'log'),
            ],
            updates=('status', 'stopped')
        )
        await interaction.followup.send(
            I18N.t('log_maintenance.commands.stop.msg_confirm')
        )

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @log_settings_group.command(
        name='list', description='List the available settings for this cog'
    )
    async def list_settings(
        self, interaction: discord.Interaction
    ):
        '''
        List the available settings for this cog
        '''
        await interaction.response.defer(ephemeral=True)
        settings_in_db = await db_helper.get_output(
            template_info=envs.log_db_schema,
            select=('setting', 'value', 'value_help')
        )
        headers = [
            I18N.t('log_maintenance.commands.list.headers.setting'),
            I18N.t('log_maintenance.commands.list.headers.value'),
            I18N.t('log_maintenance.commands.list.headers.value_type')
        ]
        await interaction.followup.send(
            content='```{}```'.format(
                tabulate(settings_in_db, headers=headers)
            ), ephemeral=True
        )

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @discord.app_commands.autocomplete(
        name_of_setting=name_of_settings_autocomplete
    )
    @log_settings_group.command(
        name='change', description='Change a setting for this cog'
    )
    async def log_setting(
        self, interaction: discord.Interaction, name_of_setting: str,
        value_in: str
    ):
        '''
        Change a setting for this cog

        Parameters
        ------------
        name_of_setting: str
            The names of the role to add (default: None)
        value_in: str
            The value of the settings (default: None)
        '''
        await interaction.response.defer(ephemeral=True)
        settings_in_db = await db_helper.get_output(
            template_info=envs.log_db_schema,
            select=('setting', 'value', 'value_check')
        )
        for setting in settings_in_db:
            if setting[0] == name_of_setting:
                if setting[2] == 'bool':
                    try:
                        value_in = eval(str(value_in).capitalize())
                    except NameError as _error:
                        log.error(f'Invalid input for `value_in`: {_error}')
                        # TODO var msg
                        await interaction.followup.send(
                            I18N.t(
                                'log_maintenance.commands.setting.'
                                'value_in_input_invalid',
                                error=_error
                            )
                        )
                        return
                log.debug(f'`value_in` is {value_in} ({type(value_in)})')
                log.debug(f'`setting[2]` is {setting[2]} ({type(setting[2])})')
                if type(value_in) is eval(setting[2]):
                    await db_helper.update_fields(
                        template_info=envs.log_db_schema,
                        where=[('setting', name_of_setting)],
                        updates=[('value', value_in)]
                    )
                await interaction.followup.send(
                    I18N.t('log_maintenance.commands.setting.msg_confirm'),
                    ephemeral=True
                )
                LogMaintenance.log_maintenance.restart()
                break
        return

    # Tasks
    @tasks.loop(hours=4)
    async def log_maintenance():
        log_files = os.listdir(envs.LOG_DIR)
        settings_type = await db_helper.get_output(
            template_info=envs.log_db_schema,
            select=('value'),
            where=('setting', 'type')
        )
        log.debug(f'Got `settings_type`: {settings_type}')
        settings_limit = await db_helper.get_output(
            template_info=envs.log_db_schema,
            select=('value'),
            where=('setting', 'limit')
        )
        settings_limit = int(settings_limit)
        log.debug(f'Got `settings_limit`: {settings_limit}')
        log.debug(
            f'Log limit is {settings_limit} in {settings_type}'
        )
        if settings_limit == 0:
            log.verbose(
                f'`settings_type` is {settings_limit} {type(settings_limit)}'
            )
            log.log('I\'m not deleting logs, but have notified the bot '
                    'channel about the situation')
            if settings_type == 'size':
                folder_size = file_io.folder_size(
                    str(envs.LOG_DIR), human=True
                )
                discord_msg = I18N.t(
                    'log_maintenance.tasks.log_maintenance.msg.size_and_none',
                    folder_size=folder_size
                )
                discord_msg += '\n'
                discord_msg += I18N.t(
                    'log_maintenance.tasks.log_maintenance.msg.disable_posting'
                )
            elif settings_type in ['day', 'days']:
                num_log_files = len(os.listdir(str(envs.LOG_DIR)))
                discord_msg = I18N.t(
                    'log_maintenance.tasks.log_maintenance.msg.days_and_none',
                    num_files=num_log_files
                )
                discord_msg += I18N.t(
                    'log_maintenance.tasks.log_maintenance.msg.disable_posting'
                )
            else:
                log_msg = 'Wrong input in `settings_type`: '\
                    f'{settings_type}'
                discord_msg = log_msg
            log.verbose(log_msg)
            await discord_commands.log_to_bot_channel(discord_msg)
        elif settings_limit > 0:
            deleted_files = []
            discord_msg_out = ''
            log_msg_out = ''
            folder_size = file_io.folder_size(str(envs.LOG_DIR))
            log.debug(f'`folder_size` is {folder_size}')
            if folder_size < settings_limit:
                log.verbose(
                    '`folder_size` is below threshold in `settings_type`'
                )
                return
            if settings_type == 'size':
                # Check total size and get diff from wanted limit
                size_diff = folder_size - settings_limit
                log.debug(f'`size_diff` is {size_diff}')
                log.debug(f'Checking these files: {log_files}')
                for _file in log_files:
                    print(f'Checking file {_file}')
                    size_diff -= file_io.file_size(envs.LOG_DIR / _file)
                    deleted_files.append(_file)
                    print(f'`size_diff` reduced to {size_diff}')
                    if size_diff <= 0:
                        break
                log.debug(f'Got enough files to delete: {deleted_files}')
                for _file in deleted_files:
                    os.remove(envs.LOG_DIR / _file)
                new_folder_size = file_io.folder_size(str(envs.LOG_DIR))
                log.debug(f'Folder went from {folder_size} to {new_folder_size}')
            elif settings_type in ['day', 'days']:
                if len(log_files) > 10:
                    for _file in log_files[0:-10]:
                        os.remove(envs.LOG_DIR / _file)
                        deleted_files.append(_file)
            else:
                log.error(
                    '`settings_type` empty or not parseable: '
                    f'`{settings_type}`'
                )
                return
            if len(deleted_files) > 0:
                status_msg = 'Log maintenance done. Deleted the following files:'
                discord_msg_out += I18N.t(
                    'log_maintenance.tasks.'
                    'log_maintenance.msg.maintenance_done')
                for _file in deleted_files:
                    discord_msg_out += f'\n- {_file}'
                await discord_commands.log_to_bot_channel(discord_msg_out)
                log_msg_out += status_msg
                log_msg_out += ' '
                log_msg_out += ', '.join(deleted_files)
                log.log(log_msg_out)
        else:
            _error_msg = '`settings_type` is less than 0'
            log.error(_error_msg)
            await discord_commands.log_to_bot_channel(_error_msg)


async def setup(bot):
    # Create necessary databases before starting
    cog_name = 'log_maintenance'
    log.log(envs.COG_STARTING.format(cog_name))
    log.verbose('Checking db')

    # Prep of DBs should only be done if the db files does not exist
    if not file_io.file_exist(envs.log_db_schema['db_file']):
        log.verbose('Log db does not exist')
        log_settings_inserts = envs.log_db_schema['inserts']
        log_prep_is_ok = await db_helper.prep_table(
            table_in=envs.log_db_schema,
            old_inserts=log_settings_inserts
        )
        log.verbose(f'`log_prep_is_ok` is {log_prep_is_ok}')
    else:
        log.verbose('Log db exist!')

    log.verbose('Registering cog to bot')
    await bot.add_cog(LogMaintenance(bot))

    task_list = await db_helper.get_output(
        template_info=envs.tasks_db_schema,
        select=('task', 'status'),
        where=('cog', 'log')
    )
    if len(task_list) == 0:
        log.debug('Could not find `log_maintenance` as a task, adding...')
        await db_helper.insert_many_all(
            template_info=envs.tasks_db_schema,
            inserts=(
                ('log', 'log_maintenance', 'stopped')
            )
        )
    for task in task_list:
        if task[0] == 'log_maintenance':
            if task[1] == 'started':
                log.debug(f'`{task[0]}` is set as `{task[1]}`, starting...')
                LogMaintenance.log_maintenance.start()
            elif task[1] == 'stopped':
                log.debug(f'`{task[0]}` is set as `{task[1]}`')
                LogMaintenance.log_maintenance.cancel()
