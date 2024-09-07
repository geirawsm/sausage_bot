#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import os
from discord.ext import commands, tasks
from discord.app_commands import locale_str
import discord
from discord.utils import get
from tabulate import tabulate
import typing

from sausage_bot.util import envs, datetime_handling, file_io, config
from sausage_bot.util import discord_commands, db_helper
from sausage_bot.util.i18n import I18N
from sausage_bot.util.log import log


async def name_of_settings_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    db_settings = await db_helper.get_output(
        template_info=envs.stats_db_settings_schema,
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


async def hidden_roles_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    hidden_roles_in_db = await db_helper.get_output(
        template_info=envs.stats_db_hide_roles_schema,
        get_row_ids=True
    )
    hidden_roles_in_list = []
    for role in hidden_roles_in_db:
        hidden_roles_in_list.append(
            (
                role[0], role[1], get(
                    discord_commands.get_guild().roles,
                    id=int(role[1])
                ).name
            )
        )
    log.debug(f'hidden_roles_in_list: {hidden_roles_in_list}')
    return [
        discord.app_commands.Choice(
            name=f'{hidden_role[2]} ({hidden_role[1]})',
            value=str(hidden_role[0])
        ) for hidden_role in hidden_roles_in_list if current
        in hidden_role[2]
    ]


def get_role_numbers(
    hide_bots: bool = None,
    hide_empties: bool = None,
    hide_roles: list = None
):
    'Get roles and number of members'
    roles_info = discord_commands.get_roles(
        hide_empties=hide_empties, filter_bots=hide_bots,
        hide_roles=hide_roles
    )
    num_members = discord_commands.get_guild().member_count
    return {
        'member_count': num_members,
        'roles': roles_info
    }


def get_stats_codebase():
    'Get statistics for the code base'
    total_lines = 0
    total_files = 0
    for root, dirs, files in os.walk(envs.ROOT_DIR):
        for filename in files:
            filename_without_extension, extension = os.path.splitext(filename)
            if extension == '.py':
                total_files += 1
                with open(os.path.join(root, filename), 'r') as _file:
                    for line in _file:
                        total_lines += 1
    return {
        'total_lines': total_lines,
        'total_files': total_files
    }


class Stats(commands.Cog):
    'Get interesting stats for the discord server'

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    stats_group = discord.app_commands.Group(
        name="stats",
        description=locale_str(I18N.t('stats.commands.groups.stats'))
    )
    stats_posting_group = discord.app_commands.Group(
        name="posting",
        description=locale_str(I18N.t('stats.commands.groups.posting')),
        parent=stats_group
    )

    @stats_posting_group.command(
        name='start',
        description=locale_str(I18N.t('stats.commands.start.command'))
    )
    async def stats_posting_start(
        self, interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)
        log.log(I18N.t('stats.commands.start.log_started'))
        Stats.update_stats.start()
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[
                ('cog', 'stats'),
                ('task', 'post_stats')
            ],
            updates=('status', 'started')
        )
        await interaction.followup.send(
            I18N.t('stats.commands.start.confirm_started')
        )

    @stats_posting_group.command(
        name='stop',
        description=locale_str(I18N.t('stats.commands.stop.command'))
    )
    async def stats_posting_stop(
        self, interaction: discord.Interaction,
        remove_post: typing.Literal['Yes', 'No']
    ):
        await interaction.response.defer(ephemeral=True)
        log.log(I18N.t('stats.commands.stop.log_stopped'))
        Stats.update_stats.cancel()
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[
                ('task', 'post_stats'),
                ('cog', 'stats'),
            ],
            updates=('status', 'stopped')
        )
        if remove_post.lower() == 'yes':
            stats_settings = dict(
                await db_helper.get_output(
                    template_info=envs.stats_db_settings_schema,
                    select=('setting', 'value')
                )
            )
            if len(stats_settings['channel']) > 0:
                stats_channel = stats_settings['channel']
            else:
                stats_channel = 'stats'
            await discord_commands.remove_stats_post(stats_channel)
        await interaction.followup.send(
            I18N.t('commands.stop.confirm_stopped')
        )

    @stats_posting_group.command(
        name='restart',
        description=locale_str(I18N.t('stats.commands.restart.command'))
    )
    async def stats_posting_restart(
        self, interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)
        log.log('Stats posting restarted')
        Stats.update_stats.restart()
        await interaction.followup.send(
            I18N.t('commands.restart.log_restarted')
        )

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @stats_group.command(
        name='list',
        description=locale_str(I18N.t('stats.commands.list.command'))
    )
    async def list_settings(
        self, interaction: discord.Interaction
    ):
        '''
        List the available settings for this cog
        '''
        await interaction.response.defer(ephemeral=True)
        settings_in_db = await db_helper.get_output(
            template_info=envs.stats_db_settings_schema,
            select=('setting', 'value', 'value_help')
        )
        headers_settings = [
            I18N.t('stats.commands.list.headers.settings.setting'),
            I18N.t('stats.commands.list.headers.settings.value'),
            I18N.t('stats.commands.list.headers.settings.value_type')
        ]
        out = '## {}\n```{}```'.format(
            I18N.t('stats.commands.list.stats_msg_out.sub_settings'),
            tabulate(settings_in_db, headers=headers_settings)
        )
        hidden_roles_in_db = await db_helper.get_output(
            template_info=envs.stats_db_hide_roles_schema
        )
        hidden_roles_in_list = []
        for role in hidden_roles_in_db:
            hidden_roles_in_list.append(role[0])
        log.debug(f'`hidden_roles_in_list` is {hidden_roles_in_list}')
        if len(hidden_roles_in_list) > 0:
            headers_hidden_roles = [
                I18N.t('stats.commands.list.headers.hidden_roles.hidden_name'),
                I18N.t('stats.commands.list.headers.hidden_roles.hidden_id')
            ]
            populated_roles = []
            for role in hidden_roles_in_list:
                populated_roles.append(
                    (
                        get(
                            discord_commands.get_guild().roles,
                            id=int(role)
                        ), role
                    )
                )
            out += '\n## {}\n```{}```'.format(
                I18N.t('stats.commands.list.stats_msg_out.sub_hidden'),
                tabulate(populated_roles, headers=headers_hidden_roles)
            )
        await interaction.followup.send(content=out, ephemeral=True)

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @discord.app_commands.autocomplete(
        name_of_setting=name_of_settings_autocomplete
    )
    @stats_group.command(
        name='setting',
        description=locale_str(I18N.t('stats.commands.setting.command'))
    )
    async def stats_setting(
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
            template_info=envs.stats_db_settings_schema,
            select=('setting', 'value', 'value_check')
        )
        for setting in settings_in_db:
            if setting[0] == name_of_setting:
                if setting[2] == 'bool':
                    try:
                        value_in = eval(str(value_in).capitalize())
                    except NameError as _error:
                        log.error(f'Invalid input for `value_in`: {_error}')
                        await interaction.followup.send(I18N.t(
                            'stats.setting_input_reply'
                        ))
                        return
                log.debug(f'`value_in` is {value_in} ({type(value_in)})')
                log.debug(f'`setting[2]` is {setting[2]} ({type(setting[2])})')
                if type(value_in) is eval(setting[2]):
                    await db_helper.update_fields(
                        template_info=envs.stats_db_settings_schema,
                        where=[('setting', name_of_setting)],
                        updates=[('value', value_in)]
                    )
                await interaction.followup.send(
                    content=I18N.t('stats.commands.setting.update_confirmed'),
                    ephemeral=True
                )
                Stats.update_stats.restart()
                break
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @stats_group.command(
        name='hide_roles_add',
        description=locale_str(
            I18N.t('stats.commands.hide_roles_add.command')),
    )
    async def stats_add_hidden_roles(
        self, interaction: discord.Interaction,
        role_in: discord.Role
    ):
        '''
        Add roles to hide in stats

        Parameters
        ------------
        role_in: discord.Role
            The role to add/remove
        '''
        await interaction.response.defer(ephemeral=True)
        hidden_roles_in_db = await db_helper.get_output(
            template_info=envs.stats_db_hide_roles_schema
        )
        hidden_roles_in_list = []
        for role in hidden_roles_in_db:
            hidden_roles_in_list.append(role[0])
        if str(role_in.id) in hidden_roles_in_list:
            # TODO var msg
            await interaction.followup.send(
                I18N.t('stats.commands.hide_roles_add.msg.already_hidden')
            )
            return
        else:
            await db_helper.insert_many_all(
                template_info=envs.stats_db_hide_roles_schema,
                inserts=[
                    (str(role_in.id))
                ]
            )
            # TODO var msg
            await interaction.followup.send(
                content=I18N.t(
                    'stats.commands.hide_roles_add.msg.confirm_added'),
                ephemeral=True
            )
            Stats.update_stats.restart()
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @discord.app_commands.autocomplete(
        hidden_roles=hidden_roles_autocomplete
    )
    @stats_group.command(
        name='hide_roles_remove',
        description=locale_str(
            I18N.t('stats.commands.hide_roles_remove.command'))
    )
    async def stats_remove_hidden_roles(
        self, interaction: discord.Interaction,
        hidden_roles: str
    ):
        '''
        Remove roles to hide in stats

        Parameters
        ------------
        role_in: discord.Role
            The role to remove
        '''
        await interaction.response.defer(ephemeral=True)
        await db_helper.del_row_id(
            template_info=envs.stats_db_hide_roles_schema,
            numbers=hidden_roles
        )
        await interaction.followup.send(
            content=I18N.t(
                'stats.commands.hide_roles_remove.msg.confirm_removed'),
            ephemeral=True
        )
        Stats.update_stats.restart()
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @stats_group.command(
        name='restart',
        description=locale_str(I18N.t('stats.commands.restart.command'))
    )
    async def stats_restart(
        self, interaction: discord.Interaction
    ):
        '''Restart the stats task'''
        await interaction.response.defer(ephemeral=True)
        Stats.update_stats.restart()
        await interaction.followup.send(
            content=I18N.t('stats.commands.restart.msg.confirm_restarted'),
            ephemeral=True
        )
        return

    # Tasks
    @tasks.loop(
        minutes=config.env.int('STATS_LOOP', default=5)
    )
    async def update_stats():
        '''
        Update interesting stats in a channel post and write the info to
        the log db.
        The channel is defined in stats settings db.
        '''
        async def tabify(
            dict_in: dict,
            headers: list,
        ):
            hide_roles = await db_helper.get_output(
                template_info=envs.stats_db_settings_schema,
                select=('value'),
                where=[('setting', 'hide_roles')]
            )
            hide_roles_lower = [x[0].lower() for x in hide_roles]
            log.debug(
                f'Using this for filter:\n{hide_roles_lower}'
            )
            text_out = ''
            if isinstance(dict_in, dict):
                log.debug(
                    'Checking `sort_abc` ({}) and `sort_321` ({})'.format(
                        eval(stats_settings['sort_roles_abc']),
                        eval(stats_settings['sort_roles_321'])
                    )
                )
                if not eval(stats_settings['sort_roles_abc']) and\
                        not eval(stats_settings['sort_roles_321']):
                    log.debug(
                        'Could not decide whether sorting by `abc` or `123`. '
                        'Defaulting to `abc`.'
                    )
                    stats_settings['sort_roles_abc'] = True
                if eval(stats_settings['sort_roles_abc']):
                    dict_in = dict(sorted(
                        dict_in.items(), key=lambda x: x[1]['name']
                    ))
                    log.debug(
                        f'Sorting roles alphabetically: {list(dict_in)[0:4]}'
                    )
                elif eval(stats_settings['sort_roles_321']):
                    dict_in = dict(sorted(
                        dict_in.items(), key=lambda x: x[1]['members'],
                        reverse=True
                    ))
                    log.debug(
                        f'Sorting roles by number of members: '
                        f'{list(dict_in)[0:4]}'
                    )

                # Tabulate the output
                dict_out = {
                    'name': [],
                    'members': []
                }
                for role in dict_in:
                    if role.lower() not in hide_roles_lower:
                        if role != '@everyone':
                            # Check for `sort_min_role_members`
                            if stats_settings['sort_min_role_members']:
                                min_members = \
                                    stats_settings['sort_min_role_members']
                                if dict_in[role]['members'] >= \
                                        int(min_members):
                                    dict_out['name'].append(
                                        dict_in[role]['name'])
                                    dict_out['members'].append(
                                        dict_in[role]['members']
                                    )
                            else:
                                dict_out['name'].append(dict_in[role]['name'])
                                dict_out['members'].append(
                                    dict_in[role]['members']
                                )
                text_out = '{}'.format(
                    tabulate(
                        dict_out, headers=headers, numalign='center'
                    )
                )
                log.debug(f'Returning: {text_out[0:100]}...')
                return text_out
            else:
                log.more('`dict_in` is not a dict. Check the input.')

        upd_mins = config.env.int('STATS_LOOP', default=5)
        log.log(f'Starting `update_stats`, updating each {upd_mins} minute')
        stats_settings = dict(
            await db_helper.get_output(
                template_info=envs.stats_db_settings_schema,
                select=('setting', 'value')
            )
        )
        log.debug(f'`stats_settings` is {stats_settings}')
        if len(stats_settings['channel']) > 0:
            stats_channel = stats_settings['channel']
        else:
            stats_channel = 'stats'
        stats_log_inserts = []
        # Get stats about the code
        _codebase = get_stats_codebase()
        lines_in_codebase = _codebase['total_lines']
        files_in_codebase = _codebase['total_files']
        stats_hide_roles = await db_helper.get_output(
            template_info=envs.stats_db_hide_roles_schema
        )
        if stats_hide_roles:
            stats_hide_roles = list(stats_hide_roles)
        else:
            stats_hide_roles = None
        log.debug(f'`stats_hide_roles` is {stats_hide_roles}')
        # Get server members
        members = get_role_numbers(
            hide_bots=eval(stats_settings['hide_bot_roles']),
            hide_empties=eval(stats_settings['hide_empty_roles']),
            hide_roles=stats_hide_roles
        )
        # Update log database if not already this day
        log.debug('Logging stats')
        date_exist = await db_helper.get_output(
            template_info=envs.stats_db_log_schema,
            order_by=[('datetime', 'DESC')],
            single=True
        )
        log_stats = False
        if date_exist:
            date_now = await datetime_handling.get_dt(format='date')
            date_exist = await datetime_handling.get_dt(
                format='date', dt=date_exist
            )
            if date_now > date_exist:
                log_stats = True
            else:
                log.verbose('Today has already been logged, skipping...')
        elif date_exist is None:
            log_stats = True
        if log_stats:
            stats_log_inserts.append(
                (
                    str(await datetime_handling.get_dt('ISO8601')),
                    files_in_codebase, lines_in_codebase,
                    members['member_count']
                )
            )
            # Write changes to database
            await db_helper.insert_many_all(
                template_info=envs.stats_db_log_schema,
                inserts=stats_log_inserts
            )
        # Update the stats-msg
        if eval(stats_settings['show_role_stats']):
            total_members = members['member_count']
            roles_members = await tabify(
                dict_in=members['roles'], headers=['Rolle', 'Brukere']
            )
        dt_log = await datetime_handling.get_dt('datetimefull')
        stats_msg = ''
        log.debug('`show_role_stats` is {}'.format(
            stats_settings['show_role_stats']
        ))
        if eval(stats_settings['show_role_stats']):
            members_sub = I18N.t(
                'stats.tasks.update_stats.stats_msg.members_sub')
            members_num = I18N.t(
                'stats.tasks.update_stats.stats_msg.members_num')
            stats_msg += f'### {members_sub}\n```'\
                f'{members_num}: {total_members}\n\n'\
                f'{roles_members}```\n'
        log.debug('`show_code_stats` is {}'.format(
            stats_settings['show_code_stats']
        ))
        if eval(stats_settings['show_code_stats']):
            code_sub = I18N.t('stats.tasks.update_stats.stats_msg.code_sub')
            code_files = I18N.t(
                'stats.tasks.update_stats.stats_msg.code_files')
            code_lines = I18N.t(
                'stats.tasks.update_stats.stats_msg.code_lines')
            stats_msg += f'### {code_sub}\n```'\
                f'{code_files}: {files_in_codebase}\n'\
                f'{code_lines}: {lines_in_codebase}```\n'
        code_last_updated = I18N.t(
            'stats.tasks.update_stats.stats_msg.code_last_updated')
        stats_msg += f'```{code_last_updated} {dt_log}```\n'
        log.verbose(
            f'Trying to post stats to `{stats_channel}`:\n'
            f'{stats_msg[0:100]}...'
        )
        await discord_commands.update_stats_post(
            stats_msg, stats_channel
        )

    @update_stats.before_loop
    async def before_update_stats():
        '#autodoc skip#'
        log.verbose('`update_stats` waiting for bot to be ready...')
        await config.bot.wait_until_ready()


async def setup(bot):
    # Create necessary databases before starting
    cog_name = 'stats'
    log.log(envs.COG_STARTING.format(cog_name))
    log.verbose('Checking db')

    # Convert json to sqlite db-files if exists
    # Define inserts
    stats_file_inserts = None
    stats_log_inserts = None
    stats_hide_roles_inserts = None
    stats_settings_inserts = envs.stats_db_settings_schema['inserts']
    log.debug(f'`stats_settings_inserts` is {stats_settings_inserts}')
    stats_settings_prep_is_ok = False
    stats_log_prep_is_ok = False
    # Populate the inserts if json file exist
    if file_io.file_exist(envs.stats_file) or\
            file_io.file_exist(envs.stats_logs_file):
        log.verbose('Found old json files')
        stats_file_inserts = await db_helper.json_to_db_inserts(cog_name)
        stats_settings_inserts = stats_file_inserts['stats_inserts']
        stats_log_inserts = stats_file_inserts['stats_logs_inserts']
    log.debug(f'`stats_file_inserts` is \n{stats_file_inserts}')
    log.debug(f'`stats_settings_inserts` is {stats_settings_inserts}')

    # Prep of DBs should only be done if the db files does not exist
    if not file_io.file_exist(envs.stats_db_settings_schema['db_file']):
        log.verbose('Stats db does not exist')
        stats_settings_prep_is_ok = await db_helper.prep_table(
            table_in=envs.stats_db_settings_schema,
            old_inserts=stats_settings_inserts
        )
        log.verbose(f'`stats_prep_is_ok` is {stats_settings_prep_is_ok}')
        stats_hide_roles_prep_is_ok = await db_helper.prep_table(
            table_in=envs.stats_db_hide_roles_schema,
            old_inserts=stats_hide_roles_inserts
        )
        log.verbose(
            f'`stats_hide_roles_prep_is_ok` is {stats_hide_roles_prep_is_ok}'
        )
    else:
        log.verbose('Stats db exist!')
    if not file_io.file_exist(envs.stats_db_log_schema['db_file']):
        log.verbose('Stats log db does not exist')
        stats_log_prep_is_ok = await db_helper.prep_table(
            envs.stats_db_log_schema, stats_log_inserts
        )
    else:
        log.verbose('Stats db log exist!')

    # Delete old json files if they exist
    if stats_settings_prep_is_ok and file_io.file_exist(envs.stats_file):
        file_io.remove_file(envs.stats_file)
    if stats_log_prep_is_ok and file_io.file_exist(envs.stats_logs_file):
        file_io.remove_file(envs.stats_logs_file)

    log.verbose('Registering cog to bot')
    await bot.add_cog(Stats(bot))

    task_list = await db_helper.get_output(
        template_info=envs.tasks_db_schema,
        select=('task', 'status'),
        where=('cog', 'stats')
    )
    if len(task_list) == 0:
        await db_helper.insert_many_all(
            template_info=envs.tasks_db_schema,
            inserts=(
                ('stats', 'post_stats', 'stopped')
            )
        )
    for task in task_list:
        if task[0] == 'post_stats':
            if task[1] == 'started':
                log.debug(f'`{task[0]}` is set as `{task[1]}`, starting...')
                Stats.update_stats.start()
            elif task[1] == 'stopped':
                log.debug(f'`{task[0]}` is set as `{task[1]}`')
                Stats.update_stats.cancel()


async def teardown(bot):
    Stats.update_stats.cancel()
