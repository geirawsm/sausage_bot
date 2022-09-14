#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands
import typing
import random
from sausage_bot.funcs.datetimefuncs import get_dt
from sausage_bot.funcs import _config, _vars, file_io
from sausage_bot.log import log


class Quotes(commands.Cog):
    'Administer or post quotes'
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='quote')
    async def quote(self, ctx, number: typing.Optional[int] = None):
        '''
        Administer quotes
        Add, edit, delete or count quotes
        '''
        def pretty_quote(number, quote_in):
            'Prettify a quote before posting'
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
            recent_quotes_log = file_io.read_json(_vars.quote_log_file)
            if recent_quotes_log is None:
                await ctx.send(_vars.UNREADABLE_FILE.format(_vars.quote_log_file))
                return
            if log_ctx not in recent_quotes_log:
                recent_quotes_log[log_ctx] = []
            quotes = file_io.read_json(_vars.quote_file)
            if quotes is None:
                await ctx.send(_vars.UNREADABLE_FILE.format(_vars.quote_file))
                return
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

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @sitat.group(name='add')
    async def add(self, ctx, quote_text, quote_date=None):
        '''
        Adding a quote

        `quote_text` should be enclosed in quotation marks
        `quote_date` is voluntary if you want to set a specific date and
            time for the quote added
        '''
        # Get file where all the quotes are stored
        quotes = file_io.read_json(_vars.quote_file)
        if quotes is None:
            await ctx.send(_vars.UNREADABLE_FILE.format(_vars.quote_file))
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
        file_io.write_json(_vars.quote_file, quotes)
        # Confirm that the quote has been saved
        await ctx.message.reply(
            # TODO lag _vars-msg
            'La til følgende sitat: ```#{}\n{}\n({})```'.format(
                new_quote_number, quote_text, quote_date))
        new_quote_number += 1
        return


    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @sitat.group(name='edit')
    async def edit(self, ctx, quote_number=None, quote_in=None, custom_date=None):
        '''
        Edit an existing quote

        `quote_number` is the quote to edit
        `quote_in` is the new text for the quote
        `custom_date` is for setting a different date than already set
        '''
        # Get the quote file
        quotes = file_io.read_json(_vars.quote_file)
        if quotes is None:
            await ctx.send(_vars.UNREADABLE_FILE.format(_vars.quote_file))
            return
        # Typecheck `quote_number`
        if quote_number is None or 0 >= int(quote_number):
            log.log(_vars.QUOTE_EDIT_NO_NUMBER_GIVEN)
            return
        if quote_in is None:
            log.log(_vars.QUOTE_EDIT_NO_TEXT_GIVEN)
            return
        existing_quotes_numbers = list(quotes.keys())
        # Check if the given `quote_number` even exist
        if quote_number not in existing_quotes_numbers:
            await ctx.message.reply('Det sitatnummeret finnes ikke.')
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
            # TODO _vars-msg
            f'Endret sitat #{quote_number} fra:\n```\n{old_q}\n'
            f'({old_dt})```\n...til:\n```\n{quote_in}\n'
            f'({quote_date})```'
        )
        quotes[str(quote_number)]['quote'] = quote_in
        quotes[str(quote_number)]['datetime'] = quote_date
        file_io.write_json(_vars.quote_file, quotes)
        return


    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @sitat.group(name='del')
    async def delete(self, ctx, quote_number):
        '''
        Deleting a quote by `quote_number`'''
        async def delete_logged_msgs(ctx):
            async for msg in ctx.history(limit=20):
                if str(msg.author.id) == _config.BOT_ID:
                    keyphrases = [
                        # TODO _var-msgs
                        'Er du sikker på at du vil slette følgende sitat',
                        'Ikke fått svar på 60 sekunder',
                        'Slettet sitat #'
                    ]
                    if any(phrase in msg.content for phrase in keyphrases):
                        await msg.delete()

        # Get file where all the quotes are stored
        quotes = file_io.read_json(_vars.quote_file)
        if quotes is None:
            await ctx.send(_vars.UNREADABLE_FILE.format(_vars.quote_file))
            return
        await ctx.message.reply(
            # TODO _var-msgs
            'Er du sikker på at du vil slette følgende sitat (Svar med '
            'reaksjon 👍 eller 👎):\n```#{}\n{}\n({})```\n'.format(
                quote_number, quotes[quote_number]['quote'],
                quotes[quote_number]['datetime'])
        )
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == '👍'

        try:
            reaction, user = await _config.bot.wait_for(
                'reaction_add', timeout=30.0, check=check
            )
        except asyncio.TimeoutError:
            # TODO _var-msgs
            await ctx.send('Ikke fått svar på 30 sekunder, stopper sletting')
            sleep(3)
            await delete_logged_msgs(ctx)
            await ctx.message.delete()
        else:
            # Remove the quote
            del quotes[str(quote_number)]
            file_io.write_json(_vars.quote_file, quotes)
            # Confirm that the quote has been deleted
            # TODO _var-msgs
            await ctx.message.reply('Slettet sitat #{}'.format(quote_number))
            sleep(3)
            await delete_logged_msgs(ctx)
            await ctx.message.delete()
            return

    
    @sitat.group(name='count')
    async def count(self, ctx):
        '''Counting the number of quotes available'''
        quote_count = len(file_io.import_file_as_list(_vars.quote_file))-1
        # TODO _var-msgs
        await ctx.send(f'Jeg har {quote_count} sitater på lager')
        return


async def setup(bot):
    log.log('Starting cog: `quote`')
    await bot.add_cog(Quotes(bot))
