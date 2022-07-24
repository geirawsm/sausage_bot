#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands
import typing
import random
from sausage_bot.funcs.datetimefuncs import get_dt
from sausage_bot.funcs import _config, _vars, file_io, discord_commands
from sausage_bot.log import log


class Quotes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.group(name='sitat')
    async def sitat(self, ctx, number: typing.Optional[int] = None):
        '''Henter et tilfeldig sitat fra telegram-chaten (2019 - 2021) og nyere sitater hentet fra Discord.'''

        def pretty_quote(number, quote_in):
            log.log_more(f'quote_in: {quote_in}')
            quote_out = '```#{}\n{}\n({})```'.format(
                number, quote_in['quote'], quote_in['datetime']
            )
            return quote_out
        
        # If no `number` is given, get a random quote
        if ctx.invoked_subcommand is None:
            # Check if the message is a DM or guild-call
            if not ctx.guild:
                log_ctx = 'dm@{}'.format(ctx.message.author)
            else:
                log_ctx = '#{}@{}'.format(ctx.channel, ctx.guild)
            recent_quotes_log = file_io.import_file_as_dict(_vars.quote_log_file)
            if log_ctx not in recent_quotes_log:
                recent_quotes_log[log_ctx] = []
            quotes = file_io.import_file_as_dict(_vars.quote_file)
            if number is None:
                if len(recent_quotes_log[log_ctx]) == len(quotes):
                    recent_quotes_log[log_ctx] = []
                    file_io.write_json(_vars.quote_log_file, recent_quotes_log)
                _rand = random.choice([i for i in range(0, len(quotes)) if str(i) not in recent_quotes_log[log_ctx]])
                if str(_rand) not in recent_quotes_log[log_ctx]:
                    recent_quotes_log[log_ctx].append(str(_rand))
                    file_io.write_json(_vars.quote_log_file, recent_quotes_log)
                _quote = pretty_quote(_rand, quotes[str(_rand)])
                await ctx.send(_quote)
                return
            # If `number` is given, get that specific quote
            elif number:
                _quote = pretty_quote(number, quotes[str(number)])
                await ctx.send(_quote)
                return

    @sitat.group(name='add')
    async def add(self, ctx, quote_text, quote_date=None):
        '''Legger til et sitat som kan hentes opp seinere.'''
        # Sjekk om admin eller bot-eier
        if discord_commands.is_bot_owner(ctx) or discord_commands.is_admin(ctx):
            quotes = file_io.import_file_as_dict(_vars.quote_file)
            new_quote_number = int(list(quotes.keys())[-1])+1
            log.log_more('Legge til quote nummer {}'.format(new_quote_number))
            # If no date is specified through `quote_date`, use date and time
            # as of now
            if quote_date is None:
                quote_date = '{}, {}'.format(get_dt('date'), get_dt('time', sep=':'))
            # Add the quote
            quotes[str(new_quote_number)] = {'quote': '', 'datetime': ''}
            quotes[str(new_quote_number)]['quote'] = quote_text
            quotes[str(new_quote_number)]['datetime'] = quote_date
            file_io.write_json(_vars.quote_file, quotes)
            await ctx.message.reply('La til følgende sitat:#{}\n{}'.format(new_quote_number, quote_in))
            new_quote_number += 1
            return
        else:
            await ctx.message.reply('Nope. Du er verken admin eller bot-eier.')
            return

    @sitat.group(name='edit')
    async def edit(self, ctx, quote_number, quote_in, custom_date=None):
        '''Endrer et eksisterende sitat'''
        # Check if the command is run by a bot owner or admin
        if discord_commands.is_bot_owner(ctx) or discord_commands.is_admin(ctx):
            # Get the quote file
            quotes = file_io.import_file_as_dict(_vars.quote_file)
            existing_quotes_numbers = list(quotes.keys())
            # Check if the given `quote_number` even exist
            if quote_number not in existing_quotes_numbers:
                await ctx.message.reply('Det sitatnummeret finnes ikke.')
                return
            log.log_more('Endrer sitat nummer {}'.format(quote_number))
            # If no date is specified through `custom_date`, use date and time
            # as of now
            if custom_date is None:
                quote_date = quotes[quote_number]['datetime']
            else:
                # TODO Sanitize input?
                quote_date = custom_date
            old_q = quotes[str(quote_number)]['quote']
            old_dt = quotes[str(quote_number)]['datetime']
            await ctx.message.reply(
                f'Endret sitat #{quote_number} fra:\n```\n{old_q}\n'
                f'({old_dt})```\n...til:\n```\n{quote_in}\n'
                f'({quote_date})```'
            )
            quotes[str(new_quote_number)]['quote'] = quote_text
            quotes[str(new_quote_number)]['datetime'] = quote_date
            file_io.write_json(_vars.quote_file, quotes)
            return
        else:
            await ctx.message.reply('Nope. Du er verken admin eller bot-eier.')
            return
    
    @sitat.group(name='count')
    async def count(self, ctx):
        '''Teller opp antall sitater som er tilgjengelig for øyeblikket'''
        quote_count = len(file_io.import_file_as_list(_vars.quote_file))-1
        await ctx.send('Jeg har {} sitater på lager'.format(quote_count))
        return


def setup(bot):
    bot.add_cog(Quotes(bot))
