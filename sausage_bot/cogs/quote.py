#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands
from discord.ext.commands.errors import InvalidEndOfQuotedStringError
import typing
import uuid
from time import sleep
from asyncio import TimeoutError
from sausage_bot.util.datetime_handling import get_dt
from sausage_bot.util import config, envs, file_io, discord_commands, db_helper
from sausage_bot.util.log import log


class Quotes(commands.Cog):
    'Administer or post quotes'

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='quote')
    async def quote(
            self, ctx, number: typing.Optional[int] = None
    ):
        '''
        Post, add, edit, delete or count quotes
        To post a specific quote: `!quote ([number])`

        Parameters
        ------------
        number: int
            Chose a number if you want a specific quote (default: None)
        '''

        def prettify(number: str, text: str, date: str) -> str:
            '''
            Prettify a quote before posting
            #autodoc skip#

            Parameters
            ------------
            number: str
                Quote number
            text: str
                Quote text
            date: str
                Quote datetime

            Returns
            ------------
            str
                ```
                #7
                This is the quote text
                (Date and time)
                ```
            '''
            log.log_more(f'number: {number}')
            log.log_more(f'text: {text}')
            log.log_more(f'date: {date}')
            out = '```\n#{}\n{}\n({})\n```'.format(
                number, text, date
            )
            return out

        async def get_random_quote():
            '''
            Return rowid, `uuid`, `quote_text` and `datetime`
            #autodoc skip#
            '''
            return await db_helper.get_random_left_exclude_output(
                envs.quote_db_schema,
                envs.quote_db_log_schema,
                'uuid',
                ('rowid', 'uuid', 'quote_text', 'datetime')
            )

        if ctx.invoked_subcommand is None:
            # If no `number` is given, get a random quote
            if not number:
                log.debug('No quote number given')
                random_quote = await get_random_quote()
                if len(random_quote) == 0:
                    await db_helper.empty_table(envs.quote_db_log_schema)
                    random_quote = await get_random_quote()
                log.db(f'Got `random_quote`: {random_quote}')
                # Post quote
                quote_number = random_quote[0][0]
                quote_text = random_quote[0][2]
                quote_date = get_dt(
                    format='datetextfull',
                    dt=random_quote[0][3]
                )
                _quote = prettify(quote_number, quote_text, quote_date)
                log.log_more(f'Posting this quote:\n{_quote}')
                quote_post = await ctx.send(_quote)
                await db_helper.insert_many_some(
                    envs.quote_db_log_schema,
                    ('uuid', 'ctx_id'),
                    [
                        (
                            random_quote[0][1],
                            quote_post.id
                        )
                    ]
                )
                return
            # If `number` is given, get that specific quote
            elif number:
                log.debug(f'Got quote number {number}')
                quote = await db_helper.get_output_by_rowid(
                    envs.quote_db_schema, number
                )
                if len(quote) > 0:
                    quote_text = quote[0][2]
                    quote_date = get_dt(
                        format='datetextfull',
                        dt=quote[0][3]
                    )
                    _quote = prettify(number, quote_text, quote_date)
                    await ctx.send(_quote)
                    return
                else:
                    await ctx.send(envs.QUOTE_DOES_NOT_EXIST.format(number))
                    return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @quote.group(name='add')
    async def quote_add(
        self, ctx, quote_text: str,
        quote_date: str = None
    ):
        '''
        Add a quote: `!quote add [quote_text] ([quote_date])`

        Parameters
        ------------
        quote_text: str
            The quote text (must be enclosed in quotation marks)
        quote_date: str
                Set a custom date and time for the quote added:
                (dd.mm.yyyy, HH:MM)

        Returns
        ------------
        int or float
            Expected results.
        '''
        # Datetime will be saved as ISO8601:
        # YYYY-MM-DD HH:MM:SS.SSS
        if quote_date is None:
            iso_date = str(get_dt(format='ISO8601'))
        else:
            iso_date = get_dt(format='ISO8601', dt=quote_date)
        # Add the quote
        row_id = await db_helper.insert_many_some(
            envs.quote_db_schema,
            ('uuid', 'quote_text', 'datetime'),
            [
                (str(uuid.uuid4()), quote_text, iso_date)
            ]
        )
        # Confirm that the quote has been saved
        await ctx.message.reply(
            envs.QUOTE_ADD_CONFIRMATION.format(
                row_id, quote_text, iso_date
            )
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @quote.group(name='edit')
    async def quote_edit(
        self, ctx, quote_number: int = None,
        quote_in: str = None, custom_date: str = None
    ):
        '''
        Edit an existing quote:
        `!quote edit [quote_number] [quote_in] [custom_date]`

        Parameters
        ------------
        quote_number: int
            The number of quote to edit (default: None)
        quote_in: str
            The quote text (must be enclosed in quotation marks)
            (default: None)
        custom_date: str
                Set a different date and time (default: None)
        '''
        # Typecheck `quote_number`
        if quote_number is None or 0 >= int(quote_number):
            log.log(envs.QUOTE_EDIT_NO_NUMBER_GIVEN)
            return
        if quote_in is None:
            log.log(envs.QUOTE_EDIT_NO_TEXT_GIVEN)
            return
        quote_check = await db_helper.get_output_by_rowid(
            envs.quote_db_schema,
            quote_number
        )
        if len(quote_check) <= 0:
            await ctx.message.reply(
                f'Sitat nummer {quote_number} finnes ikke.'
            )
            return
        log.log_more('Endrer sitat nummer {}'.format(quote_number))
        # If no date is specified through `custom_date`, use the existing
        # date and time
        if custom_date is None:
            quote_date = quote_check[0][3]
        else:
            quote_date = custom_date
        old_qt = quote_check[0][2]
        old_dt = quote_date
        await ctx.message.reply(
            envs.QUOTE_EDIT_CONFIRMATION.format(
                quote_number, old_qt,
                get_dt(
                    format='datetextfull',
                    dt=old_dt
                ), quote_in,
                get_dt(
                    format='datetextfull',
                    dt=quote_date
                )
            )
        )
        # Update quote
        await db_helper.update_fields(
            envs.quote_db_schema,
            [
                ('rowid', quote_number)
            ],
            [
                ('quote_text', quote_in),
                ('datetime', quote_date)
            ]
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @quote.group(name='delete', aliases=['del'])
    async def quote_delete(
            self, ctx, quote_number: int = None):
        '''
        Delete an existing quote: `!quote delete [quote_number]`

        Parameters
        ------------
        quote_number: int
            The number of quote to edit (default: None)
        '''
        def check(reaction, user):
            '#autodoc skip#'
            return user == ctx.author and str(reaction.emoji) == '👍'

        quote = await db_helper.get_output_by_rowid(
            envs.quote_db_schema,
            quote_number
        )
        log.db(f'quote is: {quote}')
        await ctx.message.reply(
            envs.QUOTE_CONFIRM_DELETE.format(
                quote_number, quote[0][2],
                get_dt(
                    format='datetextfull',
                    dt=quote[0][3]
                )
            )
        )

        try:
            reaction, user = await config.bot.wait_for(
                'reaction_add', timeout=15.0, check=check
            )
        except TimeoutError:
            await ctx.send(envs.QUOTE_NO_CONFIRMATION_RECEIVED)
            sleep(3)
            await discord_commands.delete_bot_msgs(ctx, envs.QUOTE_KEY_PHRASES)
            await ctx.message.delete()
        else:
            # Remove the quote
            await db_helper.del_row_id(
                envs.quote_db_schema,
                quote_number
            )
            # Confirm that the quote has been deleted
            await ctx.message.reply(
                envs.QUOTE_DELETE_CONFIRMED.format(quote_number)
            )
            sleep(3)
            await discord_commands.delete_bot_msgs(ctx, envs.QUOTE_KEY_PHRASES)
            await ctx.message.delete()
            return

    @quote.group(name='count')
    async def quote_count(self, ctx):
        'Count the number of quotes available: `!quote count`'
        quote_count = len(
            await db_helper.get_row_ids(
                envs.quote_db_schema
            )
        )
        await ctx.send(envs.QUOTE_COUNT.format(quote_count))
        return


async def setup(bot):
    log.log(envs.COG_STARTING.format('quote'))
    log.log_more('Checking db')
    await db_helper.prep_table(
        envs.quote_db_schema
    )
    await db_helper.prep_table(
        envs.quote_db_log_schema
    )
    await bot.add_cog(Quotes(bot))
