#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'stats: Get interesting stats for the discord server and post them to a channel'
import os
from discord.ext import commands, tasks
from discord.app_commands import locale_str, describe
import discord
from discord.utils import get
from tabulate import tabulate
import typing
import re
from pprint import pformat

from sausage_bot.util import envs, datetime_handling, file_io, config
from sausage_bot.util import discord_commands, db_helper
from sausage_bot.util.i18n import I18N

logger = config.logger

async def settings_db_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    settings_db = await db_helper.get_output(
        template_info=envs.stats_db_settings_schema,
        select=('setting', 'value')
    )
    settings_type = envs.stats_db_settings_schema['type_checking']
    return [
        discord.app_commands.Choice(
            name='{} = {} ({})'.format(
                setting['setting'], setting['value'],
                settings_type[setting['setting']]
            ),
            value=str(setting['setting'])
        )
        for setting in settings_db if current.lower() in '{}-{}'.format(
            setting['setting'], setting['value']
        ).lower()
    ][:25]


async def env_settings_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    settings_info = envs.stats_db_settings_schema['inserts']
    settings_type = envs.stats_db_settings_schema['type_checking']
    return [
        discord.app_commands.Choice(
            name='{} ({})'.format(
                settings_info[0], settings_type[settings_info[0]]
            ), value=str(settings_info[0])
        )
        for settings_info in settings_info if current.lower()
        in settings_info[0].lower()
    ][:25]


async def hidden_roles_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    hidden_roles_in_db = await db_helper.get_output(
        template_info=envs.stats_db_hide_roles_schema,
        get_row_ids=True
    )
    logger.debug(f'hidden_roles_from_db:\n{pformat(hidden_roles_in_db)}')
    temp_hidden_roles = {}
    for i in hidden_roles_in_db:
        temp_hidden_roles[i['role_id']] = {
            'rowid': i['rowid'],
            'name': get(
                discord_commands.get_guild().roles,
                id=int(i['role_id'])
            ).name
        }
    logger.debug('temp_hidden_roles:\n{pformat(temp_hidden_roles)}')
    return [
        discord.app_commands.Choice(
            name="{} ({})".format(
                temp_hidden_roles[hidden_role]['name'],
                hidden_role
            ),
            value=str(temp_hidden_roles[hidden_role]['rowid'])
        ) for hidden_role in temp_hidden_roles if current
        in '{}-{}'.format(
            hidden_role, temp_hidden_roles[hidden_role]['name']
        ).lower()
    ][:25]


def get_role_numbers(settings_in):
    'Get roles and number of members'
    logger.debug(f'settings_in: {settings_in}')
    logger.debug('hide_empty_roles: {}'.format(settings_in['hide_empty_roles']))
    logger.debug('hide_bot_roles: {}'.format(settings_in['hide_bot_roles']))
    roles_info = discord_commands.get_roles(
        hide_empties=settings_in['hide_empty_roles'],
        filter_bots=settings_in['hide_bot_roles']
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
    for root, _, files in os.walk(envs.ROOT_DIR):
        for filename in files:
            filename_without_extension, extension = os.path.splitext(filename)
            if extension == '.py':
                total_files += 1
                with open(os.path.join(root, filename), 'r') as _file:
                    for _ in _file:
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
    stats_settings_group = discord.app_commands.Group(
        name="settings",
        description=locale_str(I18N.t('stats.commands.groups.settings')),
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
        logger.info(I18N.t('stats.commands.start.log_started'))
        Stats.task_update_stats.start()
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
    @describe(
        remove_post=I18N.t('stats.commands.stop.desc.remove_post')
    )
    async def stats_posting_stop(
        self, interaction: discord.Interaction,
        remove_post: typing.Literal['Yes', 'No']
    ):
        await interaction.response.defer(ephemeral=True)
        logger.info(I18N.t('stats.commands.stop.log_stopped'))
        Stats.task_update_stats.cancel()
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
            I18N.t('stats.commands.stop.confirm_stopped')
        )

    @stats_posting_group.command(
        name='restart',
        description=locale_str(I18N.t('stats.commands.restart.command'))
    )
    async def stats_posting_restart(
        self, interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)
        logger.info('Stats posting restarted')
        Stats.task_update_stats.restart()
        await interaction.followup.send(
            I18N.t('stats.commands.restart.log_restarted')
        )

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @stats_settings_group.command(
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
            select=('setting', 'value')
        )
        headers_settings = {
            'setting': I18N.t('stats.commands.list.headers.settings.setting'),
            'value': I18N.t('stats.commands.list.headers.settings.value')
        }
        out = '## {}\n```{}```'.format(
            I18N.t('stats.commands.list.stats_msg_out.sub_settings'),
            tabulate(settings_in_db, headers=headers_settings)
        )
        hidden_roles_in_db = await db_helper.get_output(
            template_info=envs.stats_db_hide_roles_schema
        )
        hidden_roles_in_db = []
        if hidden_roles_in_db is not None:
            for role in hidden_roles_in_db:
                hidden_roles_in_db.append(role[0])
        logger.debug(f'`hidden_roles_in_db` is {hidden_roles_in_db}')
        if len(hidden_roles_in_db) > 0:
            headers_hidden_roles = [
                I18N.t('stats.commands.list.headers.hidden_roles.hidden_name'),
                I18N.t('stats.commands.list.headers.hidden_roles.hidden_id')
            ]
            populated_roles = []
            for role in hidden_roles_in_db:
                populated_roles.append(
                    (
                        get(
                            discord_commands.get_guild().roles,
                            name=role
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
        name_of_setting=settings_db_autocomplete
    )
    @stats_settings_group.command(
        name='change',
        description=locale_str(
            I18N.t('stats.commands.change.command')
        )
    )
    @describe(
        name_of_setting=I18N.t('stats.commands.change.desc.name_of_setting'),
        value_in=I18N.t('stats.commands.change.desc.value_in')
    )
    async def change_setting(
        self, interaction: discord.Interaction, name_of_setting: str,
        value_in: str
    ):
        '''
        Change a setting for this cog

        Parameters
        ------------
        name_of_setting: str
            The names of the role to change (default: None)
        value_in: str
            The value of the settings (default: None)
        '''
        await interaction.response.defer(ephemeral=True)
        settings_in_db = await db_helper.get_output(
            template_info=envs.stats_db_settings_schema,
            select=('setting', 'value')
        )
        settings_from_db = {}
        for setting in settings_in_db:
            settings_from_db[setting['setting']] = setting['value']
        logger.debug(f'settings_from_db:\n{pformat(settings_from_db)}')
        settings_type = envs.stats_db_settings_schema['type_checking']
        for setting in settings_from_db:
            if settings_type[setting] == 'bool':
                try:
                    value_in = eval(str(value_in).capitalize())
                except NameError as _error:
                    logger.error(f'Invalid input for `value_in`: {_error}')
                    await interaction.followup.send(I18N.t(
                        'stats.setting_input_reply'
                    ))
                    return
            logger.debug(f'`value_in` is {value_in} ({type(value_in)})')
            logger.debug(
                f'`settings_type` is {settings_type[setting]} '
                f'({type(settings_type[setting])})'
            )
            if type(value_in) is eval(settings_type[setting]):
                await db_helper.update_fields(
                    template_info=envs.stats_db_settings_schema,
                    where=[('setting', name_of_setting)],
                    updates=[('value', value_in)]
                )
            await interaction.followup.send(
                content=I18N.t('stats.commands.change.update_confirmed'),
                ephemeral=True
            )
            Stats.task_update_stats.restart()
            break
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @discord.app_commands.autocomplete(
        setting_in=env_settings_autocomplete
    )
    @stats_settings_group.command(
        name='add',
        description=locale_str(I18N.t('stats.commands.add.command'))
    )
    @describe(
        setting_in=I18N.t('stats.commands.add.desc.name_of_setting'),
        value_in=I18N.t('stats.commands.add.desc.value_in'),
    )
    async def add_setting(
        self, interaction: discord.Interaction,
        setting_in: str, value_in: str
    ):
        '''
        Add a setting for this cog
        '''
        await interaction.response.defer(ephemeral=True)
        settings_in_db = await db_helper.get_output(
            template_info=envs.stats_db_settings_schema,
            select=('setting', 'value')
        )
        settings_db_json = file_io.make_db_output_to_json(
            ['setting', 'value'],
            settings_in_db
        )
        settings_types = envs.stats_db_settings_schema['type_checking']
        logger.debug('settings_db_json is `{}`'.format(settings_db_json))
        if value_in.lower() in ['true', 'false']:
            value_in = value_in.capitalize()
            value_in_check = eval('{}({})'.format(
                settings_types[setting_in], value_in
            ))
        logger.debug(
            'Value is {} ({}) and setting type is {}'.format(
                value_in, type(value_in_check),
                eval(settings_types[setting_in])
            )
        )
        if setting_in in settings_db_json:
            await interaction.followup.send(
                content=I18N.t(
                    'stats.commands.add.msg.setting_already_exists'
                ),
                ephemeral=True
            )
            return
        if type(value_in_check) is not eval(settings_types[setting_in]):
            await interaction.followup.send(
                content=I18N.t(
                    'stats.commands.add.msg.type_incorrect',
                    value_in=value_in, value_type=type(value_in),
                    value_type_check=settings_types[setting_in]
                ),
                ephemeral=True
            )
            return
        elif type(value_in_check) is eval(settings_types[setting_in]):
            if setting_in:
                await db_helper.insert_many_all(
                    template_info=envs.stats_db_settings_schema,
                    inserts=[(setting_in, value_in)]
                )
                await interaction.followup.send(
                    content=I18N.t('stats.commands.add.msg.add_confirmed'),
                    ephemeral=True
                )
                Stats.task_update_stats.restart()
                return
        else:
            logger.error('Something went wrong')
            await interaction.followup.send(
                content=I18N.t('stats.commands.add.msg.add_failed'),
                ephemeral=True
            )
            return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @discord.app_commands.autocomplete(
        setting_in=settings_db_autocomplete
    )
    @stats_settings_group.command(
        name='remove',
        description=locale_str(I18N.t('stats.commands.remove.command'))
    )
    @describe(
        setting_in=I18N.t('stats.commands.remove.desc.name_of_setting')
    )
    async def remove_setting(
        self, interaction: discord.Interaction, setting_in: str
    ):
        '''
        Remove a setting for this cog
        '''
        await interaction.response.defer(ephemeral=True)
        try:
            await db_helper.del_row_by_AND_filter(
                template_info=envs.stats_db_settings_schema,
                where=[('setting', setting_in)]
            )
            await interaction.followup.send(
                content=I18N.t('stats.commands.remove.msg.remove_confirmed'),
                ephemeral=True
            )
            Stats.task_update_stats.restart()
        except Exception as error:
            logger.error(f'Error when removing setting: {error}')
            await interaction.followup.send(
                content=I18N.t('stats.commands.remove.msg.remove_failed'),
                ephemeral=True
            )
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
    @describe(
        role_in=I18N.t('stats.commands.hide_roles_add.desc.role_in')
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
            The role to add
        '''
        await interaction.response.defer(ephemeral=True)
        hidden_roles_in_db = await db_helper.get_output(
            template_info=envs.stats_db_hide_roles_schema,
            select=('role_id')
        )
        hidden_roles_in_list = []
        if type(hidden_roles_in_db) is not None:
            for role in hidden_roles_in_db:
                hidden_roles_in_list.append(role['role_id'])
            if str(role_in.id) in hidden_roles_in_list:
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
                await interaction.followup.send(
                    content=I18N.t(
                        'stats.commands.hide_roles_add.msg.confirm_added'),
                    ephemeral=True
                )
                Stats.task_update_stats.restart()
        else:
            await interaction.followup.send(
                # TODO i18n
                content='No hidden roles exist',
                ephemeral=True
            )
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
    @describe(
        hidden_roles=I18N.t('stats.commands.hide_roles_remove.desc.role_in')
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
        Stats.task_update_stats.restart()
        return

    # Tasks
    @tasks.loop(
        minutes=config.env.int('STATS_LOOP', default=5)
    )
    async def task_update_stats():
        '''
        Update interesting stats in a channel post and write the info to
        the log db.
        The channel is defined in stats settings db.
        '''

        async def get_db_settings():
            stats_settings_db = await db_helper.get_output(
                template_info=envs.stats_db_settings_schema,
                select=('setting', 'value')
            )
            logger.debug(f'`stats_settings_db` is {stats_settings_db}')
            stats_settings = {}
            for setting in stats_settings_db:
                stats_settings[setting['setting']] = setting['value']
            logger.debug(f'`stats_settings` is {stats_settings}')
            return stats_settings

        async def get_db_hide_roles():
            hide_roles_exist = await db_helper.table_exist(
                envs.stats_db_hide_roles_schema
            )
            if hide_roles_exist:
                stats_hide_roles = await db_helper.get_output(
                    envs.stats_db_hide_roles_schema
                )
                stats_hide_roles = [
                    role['role_id'] for role in stats_hide_roles
                ]
                if len(stats_hide_roles) > 0:
                    return list(stats_hide_roles)
            return None

        async def log_stats():
            stats_log_inserts = []
            date_exist = await db_helper.get_output(
                template_info=envs.stats_db_log_schema,
                order_by=[('datetime', 'DESC')],
                select=('datetime'),
                single=True
            )
            if date_exist is not None:
                logger.debug(f'`date_exist`: {date_exist}')
                date_exist = date_exist['datetime']
            log_stats = False
            if date_exist:
                date_now = datetime_handling.get_dt(format='date')
                date_exist = datetime_handling.get_dt(
                    format='date', dt=date_exist
                )
                if date_now > date_exist:
                    log_stats = True
                else:
                    logger.debug('Today has already been logged, skipping...')
            elif date_exist is None:
                log_stats = True
            if log_stats:
                stats_log_inserts.append(
                    (
                        str(datetime_handling.get_dt('ISO8601')),
                        files_in_codebase, lines_in_codebase,
                        members['member_count']
                    )
                )
                # Write changes to database
                await db_helper.insert_many_all(
                    template_info=envs.stats_db_log_schema,
                    inserts=stats_log_inserts
                )

        async def tabify(
            dict_in: dict,
            headers: list,
            hide_roles: list = None
        ):
            text_out = ''
            if isinstance(dict_in, dict):
                logger.debug(
                    'Checking `sort_abc` ({}) and `sort_321` ({})'.format(
                        eval(stats_settings['sort_roles_abc']),
                        eval(stats_settings['sort_roles_321'])
                    )
                )
                if not eval(stats_settings['sort_roles_abc']) and\
                        not eval(stats_settings['sort_roles_321']):
                    logger.debug(
                        'Could not decide whether sorting by `abc` or `123`. '
                        'Defaulting to `abc`.'
                    )
                    stats_settings['sort_roles_abc'] = True
                if eval(stats_settings['sort_roles_abc']):
                    dict_in = dict(sorted(
                        dict_in.items(), key=lambda x: x[1]['name'].lower()
                    ))
                    logger.debug(
                        f'Sorting roles alphabetically: {list(dict_in)[0:4]}'
                    )
                elif eval(stats_settings['sort_roles_321']):
                    dict_in = dict(sorted(
                        dict_in.items(), key=lambda x: x[1]['members'],
                        reverse=True
                    ))
                    logger.debug(
                        f'Sorting roles by number of members: '
                        f'{list(dict_in)[0:4]}'
                    )

                # Tabulate the output
                dict_out = {
                    'name': [],
                    'members': []
                }
                for role in dict_in:
                    if hide_roles is not None and\
                            str(dict_in[role]['id']) in hide_roles:
                        continue
                    # Check for `sort_min_role_members`
                    if dict_in[role]['name'] != '@everyone':
                        if stats_settings['sort_min_role_members']:
                            min_members = \
                                stats_settings['sort_min_role_members']
                            if dict_in[role]['members'] >= \
                                    int(min_members):
                                dict_out['name'].append(
                                    dict_in[role]['name']
                                )
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
                logger.debug(f'Returning: {text_out[0:200]}...')
                return text_out
            else:
                logger.error('`dict_in` is not a dict. Check the input.')

        async def check_and_post_to_stats_msg_id(
                stats_settings, stats_info
        ):
            # Get `stats_msg_id` from db to update stats post
            stats_channel = get(
                _guild.channels,
                name=stats_settings.get('channel', 'stats')
            )
            logger.debug(
                f'Got `stats_channel` {stats_channel} ({type(stats_channel)})'
            )
            # If `stats_msg_id` is not in db, check if `stats_msg` is in db
            # If `stats_msg` is not in db, add `stats_msg_id` to db
            if 'stats_msg_id' not in stats_settings:
                stats_msg_id = None
                if 'stats_msg' not in stats_settings:
                    # Add new post and update db
                    stats_msg_id = None
                elif 'stats_msg' in stats_settings:
                    stats_msg_id = stats_settings.get('stats_msg')
                    # Change 'stats_msg' to 'stats_msg_id'
                    await db_helper.update_fields(
                        envs.stats_db_settings_schema,
                        where=('setting', 'stats_msg'),
                        updates=('setting', 'stats_msg_id')
                    )
                else:
                    logger.error('Noe rart har skjedd?!')
            elif 'stats_msg_id' in stats_settings:
                stats_msg_id = stats_settings.get('stats_msg_id')
            # Now we should have `stats_msg_id`, check it's value and
            # decide what to do
            post_new = False
            if stats_msg_id == '' or stats_msg_id is None:
                logger.debug(
                    '`stats_msg_id` is empty, is there already a stats msg?'
                )
                # Look for a stats message
                stats_msgs = [
                    message async for message in stats_channel.history(
                        limit=20, oldest_first=True
                    )
                ]
                for _msg in stats_msgs:
                    last_update_text = I18N.t(
                        'stats.tasks.update_stats.stats_msg.code_last_updated'
                    )
                    if last_update_text in str(_msg.content):
                        logger.debug(f'Found stats message: {_msg.id}')
                        stats_msg_id = _msg.id
                        logger.debug('Updating db')
                        await db_helper.update_fields(
                            template_info=envs.stats_db_settings_schema,
                            where=('setting', 'stats_msg_id'),
                            updates=('value', _msg.id)
                        )
                        break
                if not re.match(r'^\d{19}$', str(stats_msg_id)):
                    logger.debug(
                        'Did not find a stats message, posting a new one'
                    )
                    post_new = True
            if re.match(r'^\d{19}$', str(stats_msg_id)):
                try:
                    # Edit the stats message if found
                    stats_msg = await stats_channel.fetch_message(stats_msg_id)
                    await stats_msg.edit(content=stats_info)
                    return
                except discord.errors.NotFound:
                    logger.error(
                        'Could not find msg id `{stats_msg_id}` in channel '
                        '`{stats_channel}`'
                    )
                    post_new = True
                    logger.debug('Creating new stats message')
            if post_new:
                # Post it
                stats_msg = await stats_channel.send(stats_info)
                stats_msg_id = stats_msg.id
                # Update db
                if 'stats_msg_id' in stats_settings:
                    await db_helper.update_fields(
                        template_info=envs.stats_db_settings_schema,
                        where=('setting', 'stats_msg_id'),
                        updates=('value', stats_msg.id)
                    )
                else:
                    await db_helper.insert_many_all(
                        template_info=envs.stats_db_settings_schema,
                        inserts=(
                            ('stats_msg_id', stats_msg.id)
                        )
                    )
            else:
                logger.error('Could not find stats_msg_id')
            return

        upd_mins = config.env.int('STATS_LOOP', default=5)
        logger.info(f'Starting `update_stats`, updating each {upd_mins} minute')
        stats_settings = await get_db_settings()
        # Get stats about the code
        _codebase = get_stats_codebase()
        lines_in_codebase = _codebase['total_lines']
        files_in_codebase = _codebase['total_files']
        stats_hide_roles = await get_db_hide_roles()
        logger.debug(f'`stats_hide_roles` is {stats_hide_roles}')
        # Get server members
        members = get_role_numbers(stats_settings)
        logger.debug(f'Got {len(members)} members')
        # Update log database if not already this day
        logger.debug('Logging stats')
        log_stats = await log_stats()
        # Update the stats-msg
        if eval(stats_settings['show_role_stats']):
            total_members = members['member_count']
            roles_members = await tabify(
                dict_in=members['roles'], headers=['Rolle', 'Brukere'],
                hide_roles=stats_hide_roles
            )
            logger.debug(f'`roles_members`:\n{roles_members}')
        dt_log = datetime_handling.get_dt('datetimefull')
        stats_info = ''
        logger.debug('`show_role_stats` is {}'.format(
            stats_settings['show_role_stats']
        ))
        if eval(stats_settings['show_role_stats']):
            members_sub = I18N.t(
                'stats.tasks.update_stats.stats_msg.members_sub')
            members_num = I18N.t(
                'stats.tasks.update_stats.stats_msg.members_num')
            stats_info += f'### {members_sub}\n```'\
                f'{members_num}: {total_members}\n\n'\
                f'{roles_members}```\n'
        logger.debug('`show_code_stats` is {}'.format(
            stats_settings['show_code_stats']
        ))
        if eval(stats_settings['show_code_stats']):
            code_sub = I18N.t('stats.tasks.update_stats.stats_msg.code_sub')
            code_files = I18N.t(
                'stats.tasks.update_stats.stats_msg.code_files')
            code_lines = I18N.t(
                'stats.tasks.update_stats.stats_msg.code_lines')
            stats_info += f'### {code_sub}\n```'\
                f'{code_files}: {files_in_codebase}\n'\
                f'{code_lines}: {lines_in_codebase}```\n'
        code_last_updated = I18N.t(
            'stats.tasks.update_stats.stats_msg.code_last_updated')
        stats_info += f'```{code_last_updated} {dt_log}```\n'
        logger.debug(
            f'Trying to post stats to `stats_channel`:\n'
            f'{stats_info[0:100]}'
        )
        _guild = discord_commands.get_guild()
        check_and_post_to_stats_msg_id = \
            await check_and_post_to_stats_msg_id(
                stats_settings, stats_info
            )

    @task_update_stats.before_loop
    async def before_update_stats():
        '#autodoc skip#'
        logger.debug('`update_stats` waiting for bot to be ready...')
        await config.bot.wait_until_ready()


async def setup(bot):
    # Create necessary databases before starting
    cog_name = 'stats'
    logger.info(envs.COG_STARTING.format(cog_name))
    logger.debug('Checking db')

    # Convert json to sqlite db-files if exists
    # Define inserts
    stats_file_inserts = None
    stats_log_inserts = None
    stats_hide_roles_inserts = None
    stats_settings_inserts = envs.stats_db_settings_schema['inserts']
    logger.debug(f'`stats_settings_inserts` is {stats_settings_inserts}')
    stats_settings_prep_is_ok = False
    stats_log_prep_is_ok = False
    # Populate the inserts if json file exist
    if file_io.file_exist(envs.stats_file) or\
            file_io.file_exist(envs.stats_logs_file):
        logger.debug('Found old json files')
        stats_file_inserts = await db_helper.json_to_db_inserts(cog_name)
        stats_settings_inserts = stats_file_inserts['stats_inserts']
        stats_log_inserts = stats_file_inserts['stats_logs_inserts']
    logger.debug(f'`stats_file_inserts` is \n{stats_file_inserts}')
    logger.debug(f'`stats_settings_inserts` is {stats_settings_inserts}')
    # Cleaning DB if irregularities from previous instances of database
    if file_io.file_exist(envs.stats_db_settings_schema['db_file']):
        await db_helper.add_missing_db_setup(
            envs.stats_db_settings_schema
        )
        await db_helper.db_fix_old_hide_roles_status()
        await db_helper.db_fix_old_stats_msg_name_status()
        await db_helper.db_fix_old_value_check_or_help()
        await db_helper.db_replace_numeral_bool_with_bool(
            envs.stats_db_settings_schema
        )
        await db_helper.db_remove_old_cols(
            envs.stats_db_settings_schema
        )
    stats_settings_prep_is_ok = await db_helper.prep_table(
        table_in=envs.stats_db_settings_schema,
        inserts=stats_settings_inserts
    )
    logger.debug(f'`stats_prep_is_ok` is {stats_settings_prep_is_ok}')
    stats_hide_roles_prep_is_ok = await db_helper.prep_table(
        table_in=envs.stats_db_hide_roles_schema,
        inserts=stats_hide_roles_inserts
    )
    logger.debug(
        f'`stats_hide_roles_prep_is_ok` is {stats_hide_roles_prep_is_ok}'
    )
    stats_log_prep_is_ok = await db_helper.prep_table(
        envs.stats_db_log_schema, stats_log_inserts
    )
    # Delete old json files if they exist
    if stats_settings_prep_is_ok and file_io.file_exist(envs.stats_file):
        file_io.remove_file(envs.stats_file)
    if stats_log_prep_is_ok and file_io.file_exist(envs.stats_logs_file):
        file_io.remove_file(envs.stats_logs_file)
    logger.debug('Registering cog to bot')
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
        if task['task'] == 'post_stats':
            if task['status'] == 'started':
                logger.debug(
                    '`{}` is set as `{}`, starting...'.format(
                        task['task'], task['status']
                    )
                )
                Stats.task_update_stats.start()
            elif task['status'] == 'stopped':
                logger.debug(
                    '`{}` is set as `{}`'.format(
                        task['task'], task['status']
                    )
                )
                Stats.task_update_stats.cancel()


async def teardown(bot):
    Stats.task_update_stats.cancel()
