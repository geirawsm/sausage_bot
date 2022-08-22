#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import os
from discord.ext import commands, tasks
from sausage_bot.funcs import _vars, file_io, _config
from sausage_bot.funcs import discord_commands, datetimefuncs
from sausage_bot.log import log
from sausage_bot.funcs.datetimefuncs import get_dt


def get_members():
    guild = discord_commands.get_guild()
    roles = discord_commands.get_roles()
    for role in roles:
        if str(role) == _config.PATREON_ROLE:
            patreon_count = 0
            _patreons = guild.get_role(roles[_config.PATREON_ROLE]).members
            for p in _patreons:
                patreon_count += 1
    member_count = guild.member_count
    return {
        'member_count': member_count,
        'patreon_count': patreon_count
    }

def get_stats_codebase():
    total_lines = 0
    for root, dirs, files in os.walk(_vars.ROOT_DIR):
        for filename in files:
            filename_without_extension, extension = os.path.splitext(filename)
            if extension == '.py':
                with open(os.path.join(root, filename), 'r') as f:
                    for l in f:
                        total_lines += 1
    return total_lines


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    #Tasks
    #@tasks.loop(time = time.fromisoformat('23:55:00+02:00'))
    @tasks.loop(minutes = 1)
    async def update_stats():
        log.log('Starting `update_stats`')
        stats_log = file_io.read_json(_vars.stats_logs_file)
        # Get server members as of now
        members = get_members()
        lines_in_codebase = get_stats_codebase()
        _y = datetimefuncs.get_dt('year')
        _m = datetimefuncs.get_dt('month')
        _d = datetimefuncs.get_dt('day')
        if _y not in stats_log:
            stats_log[_y] = {}
        if _m not in stats_log[_y]:
            stats_log[_y][_m] = {}
        if _d not in stats_log[_y][_m]:
            stats_log[_y][_m][_d] = {
                'members': {
                    'total': members['member_count'],
                    'patreon': members['patreon_count']
                },
                'lines_in_codebase': lines_in_codebase
            }
        # Update the stats-msg
        tot_members = members['member_count']
        patreon_members = members['patreon_count']
        dt_log = datetimefuncs.get_dt('datetimefull')
        stats_msg = f'Stats:\n'\
            f'Antall medlemmer: {tot_members}\n'\
            f'Antall Patreon-medlemmer: {patreon_members}\n'\
            f'Antall linjer med kode: {lines_in_codebase}\n'\
            f'(Siste oppdatering: {dt_log})'
        log.log_more('Trying to post stats...')
        await discord_commands.update_stats_post(stats_msg, _config.STATS_CHANNEL)

        # Write changes to file
        file_io.write_json(_vars.stats_logs_file, stats_log)


    @update_stats.before_loop
    async def before_update_stats():
        log.log_more('`update_stats` waiting for bot to be ready...')
        await _config.bot.wait_until_ready()

    update_stats.start()



async def setup(bot):
    # Starting the cog
    log.log('Starting cog: `stats`')
    check_and_create_files = [
            (_vars.stats_logs_file, '{}')
        ]
    file_io.create_necessary_files(check_and_create_files)
    await bot.add_cog(Stats(bot))
