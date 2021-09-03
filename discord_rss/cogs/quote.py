#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import discord
from discord.ext import commands
from random import randrange
from discord_rss import file_io, _vars
from discord_rss.datetime_funcs import get_dt


class Quotes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.group(name='sitat')
    async def sitat(self, ctx):
        '''Henter et tilfeldig sitat fra telegram-chaten (2019 - 
2021) og nyere sitater hentet fra Discord.'''
        if ctx.invoked_subcommand is None:
            quotes = file_io.import_file_as_list(_vars.quote_file)
            _rand = randrange(0, len(quotes))
            _quote = '```{}```'.format(quotes[_rand])
            await ctx.send(_quote)
            return


    @sitat.group(name='add')
    async def add(self, ctx, quote_in):
        quote_in += '\n({}, {})'.format(get_dt('date'), get_dt('timefull', sep=':'))
        file_io.add_to_list(_vars.quote_file, str(quote_in))
        await ctx.send('La til følgende sitat:\n{}'.format(quote_in))
        return

    @sitat.group(name='count')
    async def add(self, ctx):
        quote_count = len(file_io.import_file_as_list(_vars.quote_file))
        await ctx.send('Jeg har {} sitater på lager'.format(quote_count))
        return


def setup(bot):
    bot.add_cog(Quotes(bot))