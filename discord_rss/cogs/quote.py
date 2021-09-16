#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import discord
from discord.ext import commands
from random import randrange
import typing
from discord_rss import file_io, _vars, log
from discord_rss.datetime_funcs import get_dt


class Quotes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.group(name='sitat')
    async def sitat(self, ctx, number: typing.Optional[int] = None):
        '''Henter et tilfeldig sitat fra telegram-chaten (2019 - 
2021) og nyere sitater hentet fra Discord.'''

        def pretty_quote(quote, number):
            quote_out = '```#{}\n{}```'.format(number, quotes[str(number)])
            return quote_out
        
        if ctx.invoked_subcommand is None:
            quotes = file_io.import_file_as_dict(_vars.quote_file)
            if number is None:
                _rand = randrange(0, len(quotes))
                _quote = pretty_quote(quotes[str(_rand)], _rand)
                await ctx.send(_quote)
                return
            elif number:
                _quote = pretty_quote(quotes[str(number)], number)
                await ctx.send(_quote)
                return


    @sitat.group(name='add')
    @commands.has_permissions(administrator=True)
    async def add(self, ctx, quote_in):
        '''Legger til et sitat som kan hentes opp seinere.'''
        quotes = file_io.import_file_as_dict(_vars.quote_file)
        new_quote_number = int(list(quotes.keys())[-1])+1
        log.log_more('Prøver å legge til quote nummer {}'.format(new_quote_number))
        quote_in += '\n({}, {})'.format(get_dt('date'), get_dt('timefull', sep=':'))
        quotes[str(new_quote_number)] = quote_in
        log.log_more('#{}\n{}'.format(new_quote_number, quotes[str(new_quote_number)]))
        file_io.write_json(_vars.quote_file, quotes)
        await ctx.send('La til følgende sitat:#{}\n{}'.format(new_quote_number, quote_in))
        new_quote_number += 1
        return
    
    @sitat.group(name='count')
    async def count(self, ctx):
        '''Teller opp antall sitater som er tilgjengelig for øyeblikket'''
        quote_count = len(file_io.import_file_as_list(_vars.quote_file))-1
        await ctx.send('Jeg har {} sitater på lager'.format(quote_count))
        return


def setup(bot):
    bot.add_cog(Quotes(bot))