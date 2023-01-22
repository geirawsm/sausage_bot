#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands
import random
from sausage_bot.util import config, envs
from sausage_bot.util import file_io
from sausage_bot.util.log import log


class Dilemmas(commands.Cog):
    'Post a random dilemma'

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='dilemmas')
    async def dilemmas(self, ctx):
        f'''
        Post a random dilemma:
        `{config.PREFIX}dilemmas`
        '''

        def prettify(dilemmas_in):
            'Enclosing `dilemmas_in` in quotation marks'
            out = '```{}```'.format(dilemmas_in)
            return out

        # Get a random dilemmas
        if ctx.invoked_subcommand is None:
            # Check if the message is a DM or guild-call
            if not ctx.guild:
                log_ctx = 'dm@{}'.format(ctx.message.author)
            else:
                log_ctx = '#{}@{}'.format(ctx.channel, ctx.guild)
            recent_dilemmas_log = file_io.read_json(envs.dilemmas_log_file)
            if recent_dilemmas_log is None:
                await ctx.send(envs.UNREADABLE_FILE.format(envs.dilemmas_log_file))
                return
            if log_ctx not in recent_dilemmas_log:
                recent_dilemmas_log[log_ctx] = []
            dilemmas = file_io.read_json(envs.dilemmas_file)
            if dilemmas is None:
                await ctx.send(envs.UNREADABLE_FILE.format(envs.dilemmas_file))
                return
            if len(recent_dilemmas_log[log_ctx]) == len(dilemmas):
                recent_dilemmas_log[log_ctx] = []
                file_io.write_json(
                    envs.dilemmas_log_file, recent_dilemmas_log
                )
            _rand = random.choice(
                [i for i in range(0, len(dilemmas))
                    if str(i) not in recent_dilemmas_log[log_ctx]]
            )
            if str(_rand) not in recent_dilemmas_log[log_ctx]:
                recent_dilemmas_log[log_ctx].append(str(_rand))
                file_io.write_json(
                    envs.dilemmas_log_file, recent_dilemmas_log
                )
            _dilemma = prettify(dilemmas[str(_rand)])
            await ctx.send(_dilemma)
            return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @dilemmas.group(name='add')
    async def add(self, ctx, dilemmas_in):
        'Add a dilemma: `!dilemmas add [dilemmas_in]`'
        dilemmas = file_io.read_json(envs.dilemmas_file)
        new_dilemmas_number = int(list(dilemmas.keys())[-1]) + 1
        log.log_more(
            'Trying to add dilemma number {}'.format(
                new_dilemmas_number
            )
        )
        dilemmas[str(new_dilemmas_number)] = dilemmas_in
        log.log_more(
            '#{}: {}'.format(
                new_dilemmas_number, dilemmas[str(new_dilemmas_number)]
            )
        )
        file_io.write_json(envs.dilemmas_file, dilemmas)
        await ctx.message.reply('Added the following dilemma: {}'.format(dilemmas_in))
        new_dilemmas_number += 1
        return


async def setup(bot):
    log.log(envs.COG_STARTING.format('dilemmas'))
    await bot.add_cog(Dilemmas(bot))
