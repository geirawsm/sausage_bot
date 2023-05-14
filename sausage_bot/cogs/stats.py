#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import os
from discord.ext import commands, tasks

from sausage_bot.util import envs, datetime_handling, file_io, config
from sausage_bot.util import discord_commands
from sausage_bot.util.args import args
from sausage_bot.util.log import log


def get_members():
    'Get number of members and number of Patreon-members'
    guild = discord_commands.get_guild()
    member_count = guild.member_count
    return {
        'member_count': member_count,
        'roles': discord_commands.get_roles()
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
            dict_in: dict, _key: str, _item: str, prefix='', suffix='',
            split='', filter_away: bool = False
        ):
            text_out = ''
            _key_len = 0
            _item_len = 0
            if isinstance(dict_in, dict):
                for role in dict_in:
                    _key_count = len(str(dict_in[role][_key])) + 2
                    if _key_count > _key_len:
                        _key_len = _key_count
                    _item_count = len(str(dict_in[role][_item])) + 2
                    if _item_count > _item_len:
                        _item_len = _item_count
                for role in dict_in:
                    if role not in filter_away:
                        _k = dict_in[role][_key]
                        _i = dict_in[role][_item]
                        text_out += f'{prefix}{_k:<{_key_len}}{split}{_i:<{_item_len}}{suffix}'
                        if dict_in[role][_key] != dict_in.keys():
                            text_out += '\n'
            log.debug(f'Returning:```{text_out}```')
            return text_out

        log.log('Starting `update_stats`')
        stats_channel = config.env('STATS_CHANNEL', default='stats')
        stats_log = file_io.read_json(envs.stats_logs_file)
        # Get server members as of now
        members = get_members()
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
            stats_log[_y][_m][_d] = {
                'members': {
                    'total': members['member_count'],
                    'roles': members['roles']
                },
                'files_in_codebase': files_in_codebase,
                'lines_in_codebase': lines_in_codebase
            }
        # Update the stats-msg
        total_members = members['member_count']
        roles_members = tabify(
            members['roles'], 'name', 'members', prefix='  ', split=': ',
            filter_away=config.env('STATS_HIDE_ROLES')
        )
        dt_log = datetime_handling.get_dt('datetimefull')
        stats_msg = f'> Medlemmer\n```'\
            f'Antall medlemmer: {total_members}\n'\
            f'Antall per rolle:\n{roles_members}```\n'\
            f'> Kodebase\n```'\
            f'Antall filer med kode: {files_in_codebase}\n'\
            f'Antall linjer med kode: {lines_in_codebase}```\n'\
            f'```(Serverstats sist oppdatert: {dt_log})'\
            f'```\n'
        log.log_more(
            f'Trying to post stats to `{stats_channel}`:\n'
            '{stats_msg}'
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
        log.log_more('`update_stats` waiting for bot to be ready...')
        await config.bot.wait_until_ready()

    update_stats.start()


async def setup(bot):
    # Starting the cog
    log.log(envs.COG_STARTING.format('stats'))
    log.log_more(envs.CREATING_FILES)
    check_and_create_files = [
        (envs.stats_logs_file, {})
    ]
    file_io.create_necessary_files(check_and_create_files)
    await bot.add_cog(Stats(bot))
