#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands
import random
from sausage_bot.funcs import discord_commands
from sausage_bot.funcs import _vars, file_io
from sausage_bot.log import log


class Dilemmas(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.group(name='dilemmas')
    async def dilemmas(self, ctx):
        '''Henter et tilfeldig dilemmas.'''

        def prettify(dilemmas_in):
            out = '```{}```'.format(dilemmas_in)
            return out
        
        
        # Get a random dilemmas
        if ctx.invoked_subcommand is None:
            # Check if the message is a DM or guild-call
            if not ctx.guild:
                log_ctx = 'dm@{}'.format(ctx.message.author)
            else:
                log_ctx = '#{}@{}'.format(ctx.channel, ctx.guild)
            recent_dilemmas_log = file_io.read_json(_vars.dilemmas_log_file)
            if recent_dilemmas_log is None:
                await ctx.send(_vars.UNREADABLE_FILE.format(_vars.dilemmas_log_file))
                return
            if log_ctx not in recent_dilemmas_log:
                recent_dilemmas_log[log_ctx] = []
            dilemmas = file_io.read_json(_vars.dilemmas_file)
            if dilemmas is None:
                await ctx.send(_vars.UNREADABLE_FILE.format(_vars.dilemmas_file))
                return
            if len(recent_dilemmas_log[log_ctx]) == len(dilemmas):
                recent_dilemmas_log[log_ctx] = []
                file_io.write_json(_vars.dilemmas_log_file, recent_dilemmas_log)
            _rand = random.choice([i for i in range(0, len(dilemmas)) if str(i) not in recent_dilemmas_log[log_ctx]])
            if str(_rand) not in recent_dilemmas_log[log_ctx]:
                recent_dilemmas_log[log_ctx].append(str(_rand))
                file_io.write_json(_vars.dilemmas_log_file, recent_dilemmas_log)
            _dilemma = prettify(dilemmas[str(_rand)])
            await ctx.send(_dilemma)
            return


    @dilemmas.group(name='add')
    async def add(self, ctx, dilemmas_in):
        '''Legger til et dilemmas som kan hentes opp seinere.'''
        # Sjekk om admin eller bot-eier
        if discord_commands.is_bot_owner(ctx) or discord_commands.is_admin(ctx):
            dilemmas = file_io.read_json(_vars.dilemmas_file)
            new_dilemmas_number = int(list(dilemmas.keys())[-1]) + 1
            log.log_more('Prøver å legge til dilemmas nummer {}'.format(new_dilemmas_number))
            dilemmas[str(new_dilemmas_number)] = dilemmas_in
            log.log_more('#{}: {}'.format(new_dilemmas_number, dilemmas[str(new_dilemmas_number)]))
            file_io.write_json(_vars.dilemmas_file, dilemmas)
            await ctx.message.reply('La til følgende dilemmas: {}'.format(dilemmas_in))
            new_dilemmas_number += 1
            return
        else:
            await ctx.message.reply('Nope. Du er verken admin eller bot-eier.')
            return
    
async def setup(bot):
    log.log('Starting cog: `dilemmas`')
    await bot.add_cog(Dilemmas(bot))
