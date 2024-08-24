#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import discord
from discord.ext import commands
from discord.utils import get
from discord.app_commands import locale_str
import typing
import uuid
from asyncio import TimeoutError

from sausage_bot.util.datetime_handling import get_dt
from sausage_bot.util import envs, db_helper, file_io
from sausage_bot.util.i18n import I18N
from sausage_bot.util.log import log


async def quotes_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    quotes_db = await db_helper.get_output(
        template_info=envs.quote_db_schema,
        get_row_ids=True
    )
    log.debug(f'`quotes_db`: {quotes_db}')
    log.debug(f'`quotes_db[0]`: {quotes_db[0]}')
    log.debug(f'`quotes_db[0][1]`: {quotes_db[0][1]}')
    return [
        discord.app_commands.Choice(
            name='{}. ({}) {}'.format(
                quote[0],
                str(get_dt(format='datetextfull', dt=quote[3])),
                quote[2][0:55]
            ),
            value=str(quote[0])
        ) for quote in quotes_db if current.lower() in '{}{}{}'.format(
            str(quote[0]),
            str(quote[3]),
            str(quote[2]).lower()
        )
    ]


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


class ConfirmButtons(discord.ui.View):
    def __init__(self, *, timeout=10):
        super().__init__(timeout=None)
        self.value = None

    @discord.ui.button(
        label="Yes", style=discord.ButtonStyle.green
    )
    async def confirm_button(
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
        label="No", style=discord.ButtonStyle.red
    )
    async def deny_button(
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


class QuoteTextInput(discord.ui.TextInput):
    def __init__(
            self, style_in, label_in, default_in=None, required_in=None,
            placeholder_in=None
    ):
        super().__init__(
            style=style_in,
            label=label_in,
            default=default_in,
            required=required_in,
            placeholder=placeholder_in
        )


class QuoteAddModal(discord.ui.Modal):
    def __init__(
        self, title_in=None, quote_in=None, available_row_id=None
    ):
        super().__init__(
            title=title_in, timeout=120
        )
        self.quote_in = quote_in
        self.available_row_id = available_row_id
        self.quote_out = {
            'row_id': None,
            'uuid': str(uuid.uuid4()) if not quote_in else quote_in[0][1],
            'quote_text': None,
            'datetime': None
        }
        log.verbose(f'self.quote_in is: {self.quote_in}')

        # Create elements
        num_label = QuoteTextInput(
            style_in=discord.TextStyle.short,
            label_in=I18N.t('quote.modals.quote_num'),
            default_in=self.quote_in[0][0] if self.quote_in else
            self.available_row_id,
            required_in=False if self.quote_in else True
        )

        quote_text = QuoteTextInput(
            style_in=discord.TextStyle.paragraph,
            label_in=I18N.t('quote.modals.quote_text'),
            default_in=self.quote_in[0][2] if self.quote_in else '',
            required_in=True,
            placeholder_in='Text'
        )

        quote_date = QuoteTextInput(
            style_in=discord.TextStyle.short,
            label_in=I18N.t('quote.modals.quote_date'),
            default_in=self.quote_in[0][3] if self.quote_in else '',
            required_in=False,
            placeholder_in=I18N.t('quote.modals.date_placeholder')
        )

        self.add_item(num_label)
        self.add_item(quote_text)
        self.add_item(quote_date)

    async def on_submit(self, interaction: discord.Interaction):
        self.quote_out['row_id'] = self.children[0].value
        self.quote_out['quote_text'] = self.children[1].value
        self.quote_out['datetime'] = self.children[2].value

        await interaction.response.send_message(
            I18N.t('quote.modals.add.msg_confirm'),
            ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error):
        await interaction.response.send_message(
            I18N.t('quote.modals.error', error=error),
            ephemeral=True
        )


class QuoteEditModal(discord.ui.Modal):
    def __init__(
        self, title_in=None, quote_in=None, available_row_id=None
    ):
        super().__init__(
            title=title_in, timeout=120
        )
        self.quote_in = quote_in
        self.available_row_id = available_row_id
        self.quote_out = {
            'row_id': quote_in[0][0],
            'uuid': str(uuid.uuid4()) if not quote_in else quote_in[0][1],
            'quote_text': None,
            'datetime': None
        }
        log.verbose(f'self.quote_in is: {self.quote_in}')

        # Create elements
        quote_text = QuoteTextInput(
            style_in=discord.TextStyle.paragraph,
            label_in=I18N.t('quote.modals.quote_text'),
            default_in=self.quote_in[0][2] if self.quote_in else '',
            required_in=True,
            placeholder_in='Text'
        )

        quote_date = QuoteTextInput(
            style_in=discord.TextStyle.short,
            label_in=I18N.t('quote.modals.quote_date'),
            default_in=self.quote_in[0][3] if self.quote_in else '',
            required_in=False,
            placeholder_in=I18N.t('quote.modals.date_placeholder')
        )

        self.add_item(quote_text)
        self.add_item(quote_date)

    async def on_submit(self, interaction: discord.Interaction):
        self.quote_out['row_id'] = self.quote_in[0][0]
        self.quote_out['quote_text'] = self.children[0].value
        self.quote_out['datetime'] = self.children[1].value

        await interaction.response.send_message(
            I18N.t('quote.modals.edit.msg_confirm'),
            ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error):
        await interaction.response.send_message(
            I18N.t('quote.modals.error', error=error),
            ephemeral=True
        )


async def get_quote_from_db(quote_number):
    # If `number` is given, get that specific quote
    log.debug(f'Got quote number {quote_number}')
    quote_row_check = await db_helper.get_row_ids(
        envs.quote_db_schema, sort=True
    )
    log.verbose(f'quote_row_check: {quote_row_check}')
    if int(quote_number) in quote_row_check:
        log.debug('Found quote_number in quote_row_check')
        db_out = await db_helper.get_output_by_rowid(
            envs.quote_db_schema,
            rowid=quote_number
        )
    else:
        db_out = None
    return db_out


class Quotes(commands.Cog):
    'Administer or post quotes'

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    group = discord.app_commands.Group(
        name="quote", description=locale_str(
            I18N.t('quote.commands.quote.cmd')
        )
    )

    @group.command(
        name="post", description=locale_str(I18N.t('quote.commands.post.cmd'))
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
        elif number:
            quote_out = await get_quote_from_db(number)
            log.verbose(f'quote_out: {quote_out}')
            if quote_out:
                quote_text = quote_out[0][2]
                quote_date = get_dt(
                    format='datetextfull',
                    dt=quote_out[0][3]
                )
                _quote = prettify(number, quote_text, quote_date)
                await interaction.followup.send(_quote)
                return
            else:
                await interaction.followup.send(
                    I18N.t(
                        'quote.commands.post.quote_not_exist',
                        number=number
                    )
                )
                return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @group.command(
        name="add", description=locale_str(I18N.t('quote.commands.add.cmd'))
    )
    async def quote_add(
        self, interaction: discord.Interaction,
    ):
        'Add a quote'
        # Get available row id
        _row_ids = await db_helper.get_row_ids(
            envs.quote_db_schema, sort=True
        )
        log.verbose(f'_row_ids: {_row_ids}')
        if len(_row_ids) <= 0:
            last_row_id = 1
        else:
            last_row_id = _row_ids[-1]+1
        modal_in = QuoteAddModal(
            title_in=I18N.t('quote.modals.add.modal_title'),
            available_row_id=last_row_id
        )
        await interaction.response.send_modal(modal_in)
        await modal_in.wait()
        # Parse the quote
        quote_out = modal_in.quote_out
        log.verbose(f'quote_out: {quote_out}')
        # Datetime will be saved as ISO8601:
        # YYYY-MM-DD HH:MM:SS.SSS
        if not quote_out['datetime']:
            iso_date = str(get_dt(format='ISO8601'))
        else:
            iso_date = get_dt(format='ISO8601', dt=quote_out['datetime'])
        log.verbose(f'iso_date: {iso_date}')
        # Add the quote
        await db_helper.insert_many_all(
            template_info=envs.quote_db_schema,
            inserts=[
                (quote_out['uuid'], quote_out['quote_text'], iso_date)
            ]
        )
        await interaction.followup.send(
            I18N.t(
                'quote.commands.add.msg_confirm'),
            ephemeral=True
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @discord.app_commands.autocomplete(quote_in=quotes_autocomplete)
    @group.command(
        name="edit", description=locale_str(I18N.t('quote.commands.edit.cmd'))
    )
    async def quote_edit(
        self, interaction: discord.Interaction, quote_in: str,
    ):
        'Edit an existing quote'
        log.verbose(f'quote_in: ({type(quote_in)}) {quote_in}')
        quote_from_db = await get_quote_from_db(quote_in)
        log.verbose(f'quote_from_db: {quote_from_db}')
        modal_in = QuoteEditModal(
            title_in=I18N.t('quote.modals.edit.modal_title'),
            quote_in=quote_from_db
        )
        await interaction.response.send_modal(modal_in)
        await modal_in.wait()
        update_triggered = False
        # Check for changes in quote text
        if str(quote_from_db[0][2]) != str(modal_in.quote_out['quote_text']):
            update_triggered = True
        # Check for changes in quote date
        elif str(quote_from_db[0][2]) != str(modal_in.quote_out['datetime']):
            update_triggered = True
        else:
            log.error('No changes discovered in quote')
            await interaction.followup.send(
                I18N.t('quote.modals.edit.no_change'),
                ephemeral=True
            )
            return
        if update_triggered:
            log.verbose('Discovered changes in quote:', pretty=modal_in.quote_out)
            # Update quote
            await db_helper.update_fields(
                template_info=envs.quote_db_schema,
                where=[
                    ('rowid', str(modal_in.quote_out['row_id']))
                ],
                updates=[
                    ('quote_text', modal_in.quote_out['quote_text']),
                    ('datetime', get_dt(
                        format='ISO8601',
                        dt=modal_in.quote_out['datetime']
                    ))
                ]
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @discord.app_commands.autocomplete(quote_in=quotes_autocomplete)
    @group.command(
        name="delete", description=locale_str(
            I18N.t('quote.commands.delete.cmd')
        )
    )
    async def quote_delete(
            self, interaction: discord.Interaction,
            quote_in: str
    ):
        'Delete an existing quote'
        await interaction.response.defer(ephemeral=True)
        quote_from_db = await get_quote_from_db(quote_in)
        log.db(f'quote_from_db is: {quote_from_db}')
        quote = quote_from_db[0]
        log.db(f'quote is: {quote}')
        confirm_buttons = ConfirmButtons()
        await interaction.followup.send(
            I18N.t(
                'quote.commands.delete.confirm_delete',
                quote_num=quote[0],
                quote_text=quote[2],
                quote_date=get_dt(
                    format='datetextfull',
                    dt=quote[3]
                )
            ),
            view=confirm_buttons,
            ephemeral=True
        )
        await confirm_buttons.wait()
        log.debug(f'Got `confirm_buttons.value`: {confirm_buttons.value}')
        if confirm_buttons.value:
            # Remove the quote
            await db_helper.del_row_id(
                envs.quote_db_schema,
                quote[0]
            )
            # Confirm that the quote has been deleted
            await interaction.followup.send(
                I18N.t(
                    'quote.commands.delete.msg_confirm',
                    quote_num=quote[0]
                ),
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                I18N.t('quote.commands.delete.msg_fail'),
                ephemeral=True
            )
            return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @group.command(
        name="count", description=locale_str(
            I18N.t('quote.commands.count.cmd')
        )
    )
    async def quote_count(self, interaction: discord.Interaction):
        'Count the number of quotes available'
        await interaction.response.defer()
        quote_count = len(
            await db_helper.get_row_ids(
                envs.quote_db_schema
            )
        )
        await interaction.followup.send(
            I18N.t(
                'quote.commands.count.msg_confirm',
                num_quotes=quote_count
            )
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
