#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import os
from discord.ext import commands, tasks
from tabulate import tabulate

from sausage_bot.util import envs, datetime_handling, file_io, config
from sausage_bot.util import discord_commands
from sausage_bot.util.args import args
from sausage_bot.util.log import log


def get_role_numbers():
    'Get roles and number of members'
    guild = discord_commands.get_guild()
    member_count = guild.member_count
    return {
        'member_count': member_count,
        'roles': discord_commands.get_roles(filter_zeroes=True)
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

    # Tasks
    @tasks.loop(minutes=5)
    async def update_stats():
        '''
        Update interesting stats in a channel post and write the info to
        `mod_vars.stats_logs_file`.
        The channel is defined in the .env file (stats_channel).
        '''
        def tabify(
            dict_in: dict,
            headers: list,
        ):
            hide_roles = stats_settings['hide_roles']
            hide_roles_lower = [x.lower() for x in hide_roles]
            # TODO var msg
            log.debug(f'Using this for filter:\n{hide_roles_lower}')
            text_out = ''
            if isinstance(dict_in, dict):
                log.debug(
                    'Checking `sort_abc` ({}) and `sort_321` ({})'.format(
                        stats_settings['sort_roles_abc'],
                        stats_settings['sort_roles_321']
                    )
                )
                if stats_settings['sort_roles_abc']:
                    dict_in = dict(sorted(
                        dict_in.items(), key=lambda x: x[1]['name']
                    ))
                    log.debug(
                        f'Sorting roles alphabetically: {list(dict_in)[0:4]}'
                    )
                if stats_settings['sort_roles_321']:
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
        stats_settings = file_io.read_json(envs.stats_file)
        stats_log = file_io.read_json(envs.stats_logs_file)
        if stats_settings['channel']:
            stats_channel = stats_settings['channel']
        else:
            stats_channel = 'stats'
        if stats_settings['show_code_stats']:
            # Get stats about the code
            _codebase = get_stats_codebase()
            lines_in_codebase = _codebase['total_lines']
            files_in_codebase = _codebase['total_files']
        _y = datetime_handling.get_dt('year')
        _m = datetime_handling.get_dt('month')
        _d = datetime_handling.get_dt('day')
        if _y not in stats_log:
            stats_log[_y] = {}
        if _m not in stats_log[_y]:
            stats_log[_y][_m] = {}
        if _d not in stats_log[_y][_m]:
            stats_log[_y][_m][_d] = {}
        if stats_settings['show_role_stats']:
            # Get server members
            members = get_role_numbers()
            stats_log[_y][_m][_d]['members'] = {
                'total': members['member_count'],
                'roles': members['roles']
            }
        if stats_settings['show_code_stats']:
            # Get info about the codebase
            stats_log[_y][_m][_d]['files_in_codebase'] = files_in_codebase
            stats_log[_y][_m][_d]['lines_in_codebase'] = lines_in_codebase
        # Update the stats-msg
        if stats_settings['show_role_stats']:
            total_members = members['member_count']
            roles_members = tabify(
                dict_in=members['roles'], headers=['Rolle', 'Brukere']
            )
        dt_log = datetime_handling.get_dt('datetimefull')
        stats_msg = ''
        if stats_settings['show_role_stats']:
            stats_msg += f'> Medlemmer\n```'\
                f'Antall medlemmer: {total_members}\n\n'\
                f'{roles_members}```\n'
        if stats_settings['show_code_stats']:
            stats_msg += f'> Kodebase\n```'\
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

        # Write changes to file
        if not args.maintenance:
            file_io.write_json(envs.stats_logs_file, stats_log)
        else:
            log.log('Did not write changes to file', color='RED')

    @update_stats.before_loop
    async def before_update_stats():
        '#autodoc skip#'
        log.verbose('`update_stats` waiting for bot to be ready...')
        await config.bot.wait_until_ready()

    update_stats.start()

    def cog_unload():
        'Cancel task if unloaded'
        log.log('Unloaded, cancelling tasks...')
        Stats.update_stats.cancel()


async def setup(bot):
    # Starting the cog
    log.log(envs.COG_STARTING.format('stats'))
    log.verbose(envs.CREATING_FILES)
    check_and_create_files = [
        (envs.stats_logs_file, {}),
        (envs.stats_file, envs.stats_template)
    ]
    file_io.create_necessary_files(check_and_create_files)
    await bot.add_cog(Stats(bot))
