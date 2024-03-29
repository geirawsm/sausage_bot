#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import os
from discord.ext import commands, tasks
from tabulate import tabulate

from sausage_bot.util import envs, datetime_handling, file_io, config
from sausage_bot.util import discord_commands, db_helper
from sausage_bot.util.log import log


def get_role_numbers(hide_bots: bool = None):
    'Get roles and number of members'
    log.debug(f'`hide_bots` is {hide_bots}')
    roles_info = discord_commands.get_roles(
        filter_zeroes=True, filter_bots=hide_bots
    )
    return {
        'member_count': len(roles_info),
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

    @commands.group(name='stats')
    async def stats_cmd(self, ctx):
        'Administer statistikk'
        pass

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @stats_cmd.group(name='list', invoke_without_command=True)
    async def list_settings(self, ctx):
        '''
        List the available settings for this cog
        '''
        settings_in_db = await db_helper.get_output(
            template_info=envs.stats_db_schema,
            select=('setting', 'value', 'value_help')
        )
        headers = ['Setting', 'Value', 'Value type']
        await ctx.reply(
            '```{}```'.format(
                tabulate(settings_in_db, headers=headers)
            )
        )

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @stats_cmd.group(name='setting', invoke_without_command=True)
    async def stats_setting(
        self, ctx, name_of_setting: str = None, value_in: str = None
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
        settings_in_db = await db_helper.get_output(
            template_info=envs.stats_db_schema,
            select=('setting', 'value', 'value_check')
        )
        if name_of_setting not in [name[0] for name in settings_in_db]:
            await ctx.reply('Setting is not found')
            return
        for setting in settings_in_db:
            if setting[0] == name_of_setting:
                if setting[2] == 'bool':
                    try:
                        value_in = eval(str(value_in).capitalize())
                    except NameError as e:
                        log.log(f'Invalid input for `value_in`: {e}')
                        # TODO var msg
                        await ctx.reply(
                            'Input `value_in` needs to be `True` or `False`'
                        )
                        return
                log.debug(f'`value_in` is {value_in} ({type(value_in)})')
                log.debug(f'`setting[2]` is {setting[2]} ({type(setting[2])})')
                if type(value_in) is eval(setting[2]):
                    await db_helper.update_fields(
                        template_info=envs.stats_db_schema,
                        where=[('setting', name_of_setting)],
                        updates=[('value', value_in)]
                    )
                await ctx.message.add_reaction('✅')
                Stats.update_stats.restart()
                break
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @stats_cmd.group(name='reload', invoke_without_command=True)
    async def stats_reload(self, ctx):
        '''Reload the stats task'''
        await ctx.message.add_reaction('✅')
        Stats.update_stats.restart()
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
                template_info=envs.stats_db_schema,
                select=('value'),
                where=[('setting', 'hide_role')]
            )
            hide_roles_lower = [x[0].lower() for x in hide_roles]
            # TODO var msg
            log.debug(f'Using this for filter:\n{hide_roles_lower}')
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
                    stats_settings['sort_roles_abc'] = True
                if stats_settings['sort_roles_abc']:
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
                            # Add an if to check for filter bot roles

                            dict_out['name'].append(dict_in[role]['name'])
                            dict_out['members'].append(
                                dict_in[role]['members']
                            )
                text_out = '{}'.format(
                    tabulate(
                        dict_out, headers=headers, numalign='center'
                    )
                )
                log.debug(f'Returning: {text_out}')
                return text_out
            else:
                log.more('`dict_in` is not a dict. Check the input.')

        log.log('Starting `update_stats`')
        stats_settings = dict(
            await db_helper.get_output(
                template_info=envs.stats_db_schema,
                select=('setting', 'value')
            )
        )
        log.debug(f'`stats_settings` is {stats_settings}')
        if stats_settings['channel']:
            stats_channel = stats_settings['channel']
        else:
            stats_channel = 'stats'
        stats_log_inserts = []
        # Get stats about the code
        _codebase = get_stats_codebase()
        lines_in_codebase = _codebase['total_lines']
        files_in_codebase = _codebase['total_files']
        # Get server members
        members = get_role_numbers(
            hide_bots=eval(stats_settings['hide_bot_roles'])
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
            if datetime_handling.get_dt(
                format='date'
            ) > datetime_handling.get_dt(
                format='date', dt=date_exist
            ):
                log_stats = True
            else:
                log.verbose('Today has already been logged, skipping...')
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
        # Update the stats-msg
        if eval(stats_settings['show_role_stats']):
            total_members = members['member_count']
            roles_members = await tabify(
                dict_in=members['roles'], headers=['Rolle', 'Brukere']
            )
        dt_log = datetime_handling.get_dt('datetimefull')
        stats_msg = ''
        log.debug('`show_role_stats` is {})'.format(
            stats_settings['show_role_stats']
        ))
        if eval(stats_settings['show_role_stats']):
            stats_msg += f'### Medlemmer\n```'\
                f'Antall medlemmer: {total_members}\n\n'\
                f'{roles_members}```\n'
        log.debug('`show_code_stats` is {}'.format(
            stats_settings['show_code_stats']
        ))
        if eval(stats_settings['show_code_stats']):
            stats_msg += f'### Kodebase\n```'\
                f'Antall filer med kode: {files_in_codebase}\n'\
                f'Antall linjer med kode: {lines_in_codebase}```\n'
        stats_msg += f'```(Serverstats sist oppdatert: {dt_log})```\n'
        log.verbose(
            f'Trying to post stats to `{stats_channel}`:\n'
            f'{stats_msg}'
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
    cog_name = 'stats'
    log.log(envs.COG_STARTING.format(cog_name))
    log.verbose('Checking db')
    # Convert json to sqlite db-files if exists
    stats_file_inserts = None
    stats_settings_inserts = envs.stats_db_schema['inserts']
    stats_log_inserts = None
    if file_io.file_size(envs.stats_file):
        log.verbose('Found old json file')
        stats_file_inserts = db_helper.json_to_db_inserts(cog_name)
        stats_settings_inserts = stats_file_inserts['stats_inserts']
        stats_log_inserts = stats_file_inserts['stats_logs_inserts']
    stats_prep_is_ok = await db_helper.prep_table(
        envs.stats_db_schema, stats_settings_inserts
    )
    stats_log_prep_is_ok = await db_helper.prep_table(
        envs.stats_db_log_schema, stats_log_inserts
    )
    # Delete old json files if they exist
    if stats_prep_is_ok and stats_log_prep_is_ok:
        file_io.remove_file(envs.stats_file)
        file_io.remove_file(envs.stats_logs_file)
    log.verbose('Registering cog to bot')
    await bot.add_cog(Stats(bot))
    Stats.update_stats.start()


async def teardown(bot):
    Stats.update_stats.stop()
