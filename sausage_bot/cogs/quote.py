#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands
from discord.ext.commands.errors import InvalidEndOfQuotedStringError
import typing
import random
from time import sleep
import asyncio
from sausage_bot.util.datetime_handling import get_dt
from sausage_bot.util import config, envs, file_io
from sausage_bot.util.log import log


class Quotes(commands.Cog):
    'Administer or post quotes'

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='quote')
    async def quote(
            self, ctx, number: typing.Optional[int] = commands.param(
                default=None,
                description="Chose a number if you want a specific quote"
            )):
        '''
        Post, add, edit, delete or count quotes
        To post a specific quote: `!quote ([number])`
        '''

        def pretty_quote(number: int, quote_in: str) -> str:
            '''
            Prettify a quote before posting
            #autodoc skip#
            '''
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
            recent_quotes_log = file_io.read_json(envs.quote_log_file)
            if recent_quotes_log is None:
                await ctx.send(envs.UNREADABLE_FILE.format(envs.quote_log_file))
                return
            if log_ctx not in recent_quotes_log:
                recent_quotes_log[log_ctx] = []
            quotes = file_io.read_json(envs.quote_file)
            if quotes is None:
                await ctx.send(envs.UNREADABLE_FILE.format(envs.quote_file))
                return
            if number is None:
                if len(recent_quotes_log[log_ctx]) == len(quotes):
                    recent_quotes_log[log_ctx] = []
                    file_io.write_json(envs.quote_log_file, recent_quotes_log)
                _rand = random.choice(
                    [i for i in range(0, len(quotes))
                        if str(i) not in recent_quotes_log[log_ctx]
                     ]
                )
                if str(_rand) not in recent_quotes_log[log_ctx]:
                    recent_quotes_log[log_ctx].append(str(_rand))
                    file_io.write_json(envs.quote_log_file, recent_quotes_log)
                _quote = pretty_quote(_rand, quotes[str(_rand)])
                await ctx.send(_quote)
                return
            # If `number` is given, get that specific quote
            elif number:
                _quote = pretty_quote(number, quotes[str(number)])
                await ctx.send(_quote)
                return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @quote.group(name='add')
    async def add(
        self, ctx, quote_text: str = commands.param(
            description="The quote text (must be enclosed in quotation marks)"
        ),
        quote_date: str = commands.param(
            default=None,
            description="Set a custom date and time for the quote added (dd.mm.yyyy, HH:MM)"
        )
    ):
        'Add a quote: `!quote add [quote_text] ([quote_date])`'
        # Get file where all the quotes are stored
        quotes = file_io.read_json(envs.quote_file)
        if quotes is None:
            await ctx.send(envs.UNREADABLE_FILE.format(envs.quote_file))
            return
        # Find the next availabel quote number
        new_quote_number = int(list(quotes.keys())[-1])+1
        # If no date is specified through `quote_date`, use date and time
        # as of now
        if quote_date is None:
            quote_date = '{}, {}'.format(
                get_dt('date'), get_dt('time', sep=':')
            )
        # Add the quote
        quotes[str(new_quote_number)] = {'quote': '', 'datetime': ''}
        quotes[str(new_quote_number)]['quote'] = quote_text
        quotes[str(new_quote_number)]['datetime'] = quote_date
        file_io.write_json(envs.quote_file, quotes)
        # Confirm that the quote has been saved
        await ctx.message.reply(
            envs.QUOTE_ADD_CONFIRMATION.format(
                new_quote_number, quote_text, quote_date
            )
        )
        new_quote_number += 1
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @quote.group(name='edit')
    async def edit(
            self, ctx, quote_number: int = commands.param(
                default=None,
                description="The number of quote to edit"
            ),
            quote_in: str = commands.param(
                default=None,
                description="The quote text (must be enclosed in quotation marks)"
            ),
            custom_date: str = commands.param(
                default=None,
                description="Set a different date and time"
            )):
        'Edit an existing quote: `!quote edit [quote_number] [quote_in] [custom_date]`'
        # Get the quote file
        quotes = file_io.read_json(envs.quote_file)
        if quotes is None:
            await ctx.send(envs.UNREADABLE_FILE.format(envs.quote_file))
            return
        # Typecheck `quote_number`
        if quote_number is None or 0 >= int(quote_number):
            log.log(envs.QUOTE_EDIT_NO_NUMBER_GIVEN)
            return
        if quote_in is None:
            log.log(envs.QUOTE_EDIT_NO_TEXT_GIVEN)
            return
        # Check if the given `quote_number` even exist
        log.debug(
            f'Checking if `quote_number` ({quote_number}) is in '
            f'`list(quotes.keys())`:\n{list(quotes.keys())}'
        )
        if str(quote_number) not in list(quotes.keys()):
            await ctx.message.reply(
                f'Sitat nummer {quote_number} finnes ikke.'
            )
            return
        log.log_more('Endrer sitat nummer {}'.format(quote_number))
        # If no date is specified through `custom_date`, use the existing
        # date and time
        if custom_date is None:
            quote_date = quotes[quote_number]['datetime']
        else:
            quote_date = custom_date
        old_q = quotes[str(quote_number)]['quote']
        old_dt = quotes[str(quote_number)]['datetime']
        await ctx.message.reply(
            envs.QUOTE_EDIT_CONFIRMATION.format(
                quote_number, old_q, old_dt, quote_in, quote_date
            )
        )
        quotes[str(quote_number)]['quote'] = quote_in
        quotes[str(quote_number)]['datetime'] = quote_date
        file_io.write_json(envs.quote_file, quotes)
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @quote.group(name='del')
    async def delete(
            self, ctx, quote_number: int = commands.param(
                description="The number of quote to edit"
            )):
        'Delete an existing quote: `!quote delete [quote_number]`'
        async def delete_logged_msgs(ctx):
            '#autodoc skip#'
            async for msg in ctx.history(limit=20):
                if str(msg.author.id) == config.BOT_ID:
                    keyphrases = envs.QUOTE_KEY_PHRASES
                    if any(phrase in msg.content for phrase in keyphrases):
                        await msg.delete()

        # Get file where all the quotes are stored
        quotes = file_io.read_json(envs.quote_file)
        if quotes is None:
            await ctx.send(envs.UNREADABLE_FILE.format(envs.quote_file))
            return
        await ctx.message.reply(
            envs.QUOTE_CONFIRM_DELETE.format(
                quote_number, quotes[quote_number]['quote'],
                quotes[quote_number]['datetime'])
        )

        def check(reaction, user):
            '#autodoc skip#'
            return user == ctx.author and str(reaction.emoji) == '👍'

        try:
            reaction, user = await config.bot.wait_for(
                'reaction_add', timeout=10.0, check=check
            )
        except asyncio.TimeoutError:
            await ctx.send(envs.QUOTE_NO_CONFIRMATION_RECEIVED)
            sleep(3)
            await delete_logged_msgs(ctx)
            await ctx.message.delete()
        else:
            # Remove the quote
            del quotes[str(quote_number)]
            file_io.write_json(envs.quote_file, quotes)
            # Confirm that the quote has been deleted
            await ctx.message.reply(envs.QUOTE_DELETE_CONFIRMED.format(quote_number))
            sleep(3)
            await delete_logged_msgs(ctx)
            await ctx.message.delete()
            return

    @quote.group(name='count')
    async def count(self, ctx):
        'Count the number of quotes available: `!quote count`'
        quote_count = len(file_io.import_file_as_list(envs.quote_file))-1
        await ctx.send(envs.QUOTE_COUNT.format(quote_count))
        return


async def setup(bot):
    log.log(envs.COG_STARTING.format('quote'))
    await bot.add_cog(Quotes(bot))
