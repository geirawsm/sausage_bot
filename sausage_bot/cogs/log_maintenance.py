#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import os
from discord.ext import commands, tasks
import discord

from sausage_bot.util import envs, file_io, config
from sausage_bot.util import discord_commands, db_helper
from sausage_bot.util.log import log


class LogMaintenance(commands.Cog):
    '''
    Start or stop the log maintenance
    '''

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    log_group = discord.app_commands.Group(
        name="log_maintenance", description='Administer log task'
    )

    @log_group.command(
        name='start', description='Start log maintenance'
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
            'Log maintenance started'
        )

    @log_group.command(
        name='stop', description='Stop log maintenance'
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
            'Log maintenance stopped'
        )

    # Tasks
    @tasks.loop(hours=4)
    async def log_maintenance():
        # maintenance logs folder
        log_files = os.listdir(envs.LOG_DIR)
        log.debug(
            f'Log limit is {config.LOG_LIMIT} in {config.LOG_LIMIT_TYPE}'
        )
        if config.LOG_LIMIT == 0:
            log.verbose(
                f'`LOG_LIMIT` is {config.LOG_LIMIT} {type(config.LOG_LIMIT)}'
            )
            log_msg = 'I\'m not deleting logs, but have notified the bot '\
                'channel about the situation'
            if config.LOG_LIMIT_TYPE == 'size':
                folder_size = file_io.folder_size(
                    str(envs.LOG_DIR), human=True
                )
                discord_msg = '`LOG_LIMIT` is set to `0` in the .env file. '\
                    f'The log folder\'s size as of now is {folder_size}. To '\
                    'disable these messages, run `/log_clean stop`'
            elif config.LOG_LIMIT_TYPE in ['day', 'days']:
                num_log_files = len(os.listdir(str(envs.LOG_DIR)))
                discord_msg = '`LOG_LIMIT` is set to `0` in the .env file. '\
                    f'The log folder has logs from {num_log_files} days '\
                    'back. To disable these messages, run `/log_clean stop`'
            else:
                log_msg = 'Wrong input in LOG_LIMIT_TYPE: '\
                    f'{config.LOG_LIMIT_TYPE}'
                discord_msg = log_msg
            log.verbose(log_msg)
            await discord_commands.log_to_bot_channel(discord_msg)
        elif config.LOG_LIMIT > 0:
            deleted_files = []
            status_msg = 'Log maintenance done. Deleted the following files:'
            discord_msg_out = ''
            log_msg_out = ''
            folder_size = file_io.folder_size(str(envs.LOG_DIR))
            log.debug(f'`folder_size` is {folder_size}')
            if folder_size < config.LOG_LIMIT:
                log.verbose('`folder_size` is below threshold in `LOG_LIMIT`')
                return
            if config.LOG_LIMIT_TYPE == 'size':
                # Check total size and get diff from wanted limit
                size_diff = folder_size - config.LOG_LIMIT
                log.debug(f'`size_diff` is {size_diff}')
                log.debug(f'Checking these files: {log_files}')
                for _file in log_files:
                    print(f'Checking file {_file}')
                    size_diff -= file_io.file_size(envs.LOG_DIR / _file)
                    deleted_files.append(_file)
                    print(f'`size_diff` reduced to {size_diff}')
                    if size_diff <= 0:
                        break
                print(f'Got enough files to delete: {deleted_files}')
                for _file in deleted_files:
                    os.remove(envs.LOG_DIR / _file)
                new_folder_size = file_io.folder_size(str(envs.LOG_DIR))
                print(f'Folder went from {folder_size} to {new_folder_size}')
            elif config.LOG_LIMIT_TYPE in ['day', 'days']:
                if len(log_files) > 10:
                    for _file in log_files[0:-10]:
                        os.remove(envs.LOG_DIR / _file)
                        deleted_files.append(_file)
            else:
                log.error(
                    '`LOG_LIMIT_TYPE` empty or not parseable: '
                    f'`{config.LOG_LIMIT_TYPE}`'
                )
                return
            if len(deleted_files) > 0:
                discord_msg_out += status_msg
                for _file in deleted_files:
                    discord_msg_out += f'\n- {_file}'
                await discord_commands.log_to_bot_channel(discord_msg_out)
                log_msg_out += status_msg
                log_msg_out += ' '
                log_msg_out += ', '.join(deleted_files)
                log.log(log_msg_out)
        else:
            _error_msg = 'LOG_LIMIT is less than 0'
            log.error(_error_msg)
            await discord_commands.log_to_bot_channel(_error_msg)


async def setup(bot):
    # Create necessary databases before starting
    cog_name = 'log_maintenance'
    log.log(envs.COG_STARTING.format(cog_name))
    log.verbose('Checking db')

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
