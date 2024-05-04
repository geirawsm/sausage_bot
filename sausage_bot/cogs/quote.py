#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import discord
from discord.ext import commands
import typing
import uuid
from time import sleep
from asyncio import TimeoutError
from sausage_bot.util.datetime_handling import get_dt
from sausage_bot.util import config, envs, discord_commands, db_helper, file_io
from sausage_bot.util.log import log


class EditButtons(discord.ui.View):
    def __init__(self, *, timeout=10):
        super().__init__(timeout=None)
        self.value = None

    @discord.ui.button(
        label="Yes, edit", style=discord.ButtonStyle.green,
        custom_id='edit_yes'
    )
    async def edit_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.value = True
        # Disable all buttons
        buttons = [x for x in self.children]
        for _btn in buttons:
            _btn.disabled = True
        # Update message
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(
        label="Do not edit!", style=discord.ButtonStyle.red
    )
    async def do_not_edit_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.value = False
        # Disable all buttons
        buttons = [x for x in self.children]
        for _btn in buttons:
            _btn.disabled = True
        # Update message
        await interaction.response.edit_message(view=self)
        self.stop()


class Quotes(commands.Cog):
    'Administer or post quotes'

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    group = discord.app_commands.Group(
        name="quote", description='Quotes'
    )

    @group.command(
        name="post", description="Post a random quote"
    )
    async def quote(
            self, interaction: discord.Interaction,
            number: typing.Optional[int] = None
    ):
        '''
        Post quotes

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
            log.verbose(f'number: {number}')
            log.verbose(f'text: {text}')
            log.verbose(f'date: {date}')
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

        await interaction.response.defer()
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
            log.verbose(f'Posting this quote:\n{_quote}')
            quote_post = await interaction.followup.send(_quote)
            await db_helper.insert_many_some(
                envs.quote_db_log_schema,
                ('uuid', 'msg_id'),
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
            quote_row_check = await db_helper.get_row_ids(
                envs.quote_db_schema, sort=True
            )
            quote_index = range(0, len(quote_row_check)-1)
            quote = await db_helper.get_output_by_rowid(
                envs.quote_db_schema,
                rowid=quote_row_check[quote_index[number-1]]
            )
            if len(quote) > 0:
                quote_text = quote[0][2]
                quote_date = get_dt(
                    format='datetextfull',
                    dt=quote[0][3]
                )
                _quote = prettify(number, quote_text, quote_date)
                await interaction.followup.send(_quote)
                return
            else:
                await interaction.followup.send(
                    envs.QUOTE_DOES_NOT_EXIST.format(number)
                )
                return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @group.command(
        name="add", description="Add a quote"
    )
    async def quote_add(
        self, interaction: discord.Interaction,
        quote_text: str, quote_date: str = None
    ):
        '''
        Add a quote

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
        await interaction.response.defer(
            ephemeral=True
        )
        # Datetime will be saved as ISO8601:
        # YYYY-MM-DD HH:MM:SS.SSS
        if quote_date is None:
            iso_date = str(get_dt(format='ISO8601'))
        else:
            iso_date = get_dt(format='ISO8601', dt=quote_date)
        # Add the quote
        await db_helper.insert_many_some(
            envs.quote_db_schema,
            ('uuid', 'quote_text', 'datetime'),
            [
                (str(uuid.uuid4()), quote_text, iso_date)
            ]
        )
        _row_ids = await db_helper.get_row_ids(
            envs.quote_db_schema, sort=True
        )
        last_row_id = _row_ids[-1]
        # Confirm that the quote has been saved
        await interaction.followup.send(
            envs.QUOTE_ADD_CONFIRMATION.format(
                last_row_id, quote_text, get_dt(
                    format='datetextfull', dt=iso_date
                )
            ),
            ephemeral=True
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @group.command(
        name="edit", description="Edit an existing quote"
    )
    async def quote_edit(
        self, interaction: discord.Interaction, quote_number: int,
        quote_in: str, custom_date: str = None
    ):
        '''
        Edit an existing quote:
        `!quote edit [quote_number] [quote_in] [custom_date]`

        Parameters
        ------------
        quote_number: int
            The number of quote to edit
        quote_in: str
            The quote text
        custom_date: str
                Set a different date and time. Handles several inputs
                (check documentation) (default: None)
        '''
        await interaction.response.defer(ephemeral=True)
        if quote_number is None or 0 >= int(quote_number):
            log.log(envs.QUOTE_NO_NUMBER_GIVEN)
            await interaction.followup.send(
                envs.QUOTE_NO_NUMBER_GIVEN,
                ephemeral=True
            )
            return
        if quote_in is None:
            log.log(envs.QUOTE_EDIT_NO_TEXT_GIVEN)
            await interaction.followup.send(
                envs.QUOTE_EDIT_NO_TEXT_GIVEN,
                ephemeral=True
            )
            return
        quote_row_check = await db_helper.get_row_ids(
            envs.quote_db_schema, sort=True
        )
        quote_index = range(0, len(quote_row_check)-1)
        log.debug(f'`quote_row_check`: {quote_row_check}')
        if len(quote_row_check) <= 0:
            await interaction.followup.send(
                'Har ingen sitater', ephemeral=True)
            return
        show_quote = await db_helper.get_output_by_rowid(
            envs.quote_db_schema,
            rowid=quote_row_check[quote_index[quote_number-1]]
        )
        if custom_date:
            quote_date = custom_date
        else:
            quote_date = show_quote[0][3]
        view_buttons = EditButtons()
        await interaction.followup.send(
            envs.QUOTE_EDIT_NEED_CONFIRMATION.format(
                quote_number, show_quote[0][2],
                get_dt(
                    format='datetextfull',
                    dt=show_quote[0][3]
                ), quote_in,
                get_dt(
                    format='datetextfull',
                    dt=quote_date
                )
            ),
            view=view_buttons,
            ephemeral=True
        )
        await view_buttons.wait()
        log.debug(f'Got `view_buttons.value`: {view_buttons.value}')
        if view_buttons.value:
            log.verbose('Endrer sitat nummer {}'.format(quote_number))
            # Update quote
            await db_helper.update_fields(
                template_info=envs.quote_db_schema,
                where=[
                    ('rowid', quote_row_check[quote_number-1])
                ],
                updates=[
                    ('quote_text', quote_in),
                    ('datetime', get_dt(
                        format='ISO8601',
                        dt=quote_date
                    ))
                ]
            )
            await interaction.followup.send(
                envs.QUOTE_EDIT_CONFIRMED,
                ephemeral=True
            )
        elif not view_buttons.value:
            await interaction.followup.send(
                envs.QUOTE_NO_EDIT_CONFIRMED,
                ephemeral=True
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @group.command(
        name="show", description="Show an existing quote"
    )
    async def quote_show(
        self, interaction: discord.Interaction, quote_number: int,
        show_public: typing.Literal['Yes', 'No']
    ):
        '''
        Show an existing quote:
        `!quote show [quote_number]`

        Parameters
        ------------
        quote_number: int
            The number of quote to edit
        '''
        if show_public == 'Yes':
            _ephemeral = False
        elif show_public == 'No':
            _ephemeral = True
        await interaction.response.defer(ephemeral=_ephemeral)
        # Typecheck `quote_number`
        if quote_number is None or 0 >= int(quote_number):
            log.log(envs.QUOTE_NO_NUMBER_GIVEN)
            await interaction.followup.send(
                envs.QUOTE_NO_NUMBER_GIVEN,
                ephemeral=_ephemeral
            )
            return
        quote_row_check = await db_helper.get_row_ids(
            envs.quote_db_schema, sort=True
        )
        quote_index = range(0, len(quote_row_check)-1)
        old_quote = await db_helper.get_output_by_rowid(
            envs.quote_db_schema,
            rowid=quote_row_check[quote_index[quote_number-1]]
        )
        await interaction.followup.send(
            '```\n#{}\n{}\n({})```'.format(
                quote_number,
                old_quote[0][2],
                get_dt(
                    format='datetextfull',
                    dt=old_quote[0][3]
                )
            ),
            ephemeral=_ephemeral
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @group.command(
        name="delete", description="Delete a quote"
    )
    async def quote_delete(
            self, interaction: discord.Interaction,
            quote_number: int = None
    ):
        '''
        Delete an existing quote

        Parameters
        ------------
        quote_number: int
            The number of quote to edit (default: None)
        '''
        await interaction.response.defer()

        def check(interaction: discord.Interaction, reaction, user):
            '#autodoc skip#'
            return user == interaction.author and str(reaction.emoji) == '👍'

        quote = await db_helper.get_output_by_rowid(
            envs.quote_db_schema,
            quote_number
        )
        log.db(f'quote is: {quote}')
        await interaction.followup.send(
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
            await interaction.message.reply(
                envs.QUOTE_NO_CONFIRMATION_RECEIVED
            )
            sleep(3)
            await discord_commands.delete_bot_msgs(
                interaction, envs.QUOTE_KEY_PHRASES
            )
            await interaction.message.delete()
        else:
            # Remove the quote
            await db_helper.del_row_id(
                envs.quote_db_schema,
                quote_number
            )
            # Confirm that the quote has been deleted
            await interaction.message.reply(
                envs.QUOTE_DELETE_CONFIRMED.format(quote_number)
            )
            sleep(3)
            await discord_commands.delete_bot_msgs(
                interaction, envs.QUOTE_KEY_PHRASES
            )
            await interaction.message.delete()
            return

    @group.command(
        name="count", description="Count the number of quotes"
    )
    async def quote_count(self, interaction: discord.Interaction):
        'Count the number of quotes available: `!quote count`'
        await interaction.response.defer()
        quote_count = len(
            await db_helper.get_row_ids(
                envs.quote_db_schema
            )
        )
        await interaction.followup.send(
            envs.QUOTE_COUNT.format(quote_count)
        )
        return


async def setup(bot):
    # Create necessary databases before starting
    cog_name = 'quote'
    log.log(envs.COG_STARTING.format(cog_name))
    log.verbose('Checking db')

    # Convert json to sqlite db-files if exists
    # Define inserts
    quote_inserts = None
    # Populate the inserts if json file exist
    if file_io.file_exist(envs.quote_file):
        log.verbose('Found old json file')
        quote_inserts = db_helper.json_to_db_inserts(cog_name)

    # Prep of DB should only be done if the db files does not exist
    quote_prep_is_ok = False
    if not file_io.file_exist(envs.quote_db_schema['db_file']):
        log.verbose('Quote db does not exist')
        quote_prep_is_ok = await db_helper.prep_table(
            envs.quote_db_schema, quote_inserts
        )
        log.verbose(f'`quote_prep_is_ok` is {quote_prep_is_ok}')
        await db_helper.prep_table(
            envs.quote_db_log_schema
        )
    else:
        log.verbose('Quote db exist')

    # Delete old json files if they exist
    if quote_prep_is_ok and file_io.file_exist(envs.quote_file):
        file_io.remove_file(envs.quote_file)
    if quote_prep_is_ok and file_io.file_size(envs.quote_log_file):
        file_io.remove_file(envs.quote_log_file)
    log.verbose('Registering cog to bot')
    await bot.add_cog(Quotes(bot))
