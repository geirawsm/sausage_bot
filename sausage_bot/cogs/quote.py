#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'quote: Administer or post quotes'
import discord
from discord.ext import commands
from discord.app_commands import locale_str, describe
from discord.utils import get
import uuid
from tabulate import tabulate
import typing
from pprint import pformat

from sausage_bot.util.datetime_handling import get_dt
from sausage_bot.util import envs, db_helper, file_io, config, discord_commands
from sausage_bot.util.i18n import I18N

logger = config.logger


class EditButtons(discord.ui.View):
    def __init__(self, *, timeout=10):
        super().__init__(timeout=timeout)
        self.value = None

    @discord.ui.button(
        label="Yes, edit", style=discord.ButtonStyle.green
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
        super().__init__(timeout=timeout)
        self.value = None

    @discord.ui.button(
        label=I18N.t('common.literal_yes_no.yes'),
        style=discord.ButtonStyle.green
    )
    async def yes_button(
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
        label=I18N.t('common.literal_yes_no.no'),
        style=discord.ButtonStyle.red
    )
    async def no_button(
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
        self, public_in=False, title_in=None, quote_in=None,
        available_row_id=None
    ):
        super().__init__(
            title=title_in, timeout=120
        )
        self.quote_in = quote_in
        logger.debug(f'self.quote_in: {self.quote_in}')
        self.available_row_id = available_row_id
        self.quote_out = {
            'row_id': None,
            'uuid': str(uuid.uuid4()) if not quote_in else quote_in[0][1],
            'quote_text': None,
            'datetime': None
        }
        self.public_in = public_in
        if public_in in [None, False]:
            self.public_in_text = I18N.t('common.literal_yes_no.yes')
        elif public_in is True:
            self.public_in_text = I18N.t('common.literal_yes_no.no')
        logger.debug(f'self.public_in: {self.public_in}')
        logger.debug(f'self.public_in_text: {self.public_in_text}')

        # Create elements
        num_label = QuoteTextInput(
            style_in=discord.TextStyle.short,
            label_in=I18N.t('quote.modals.quote_num'),
            default_in=self.quote_in[0][0] if self.quote_in else
            self.available_row_id,
            required_in=not self.quote_in
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

        quote_public = QuoteTextInput(
            style_in=discord.TextStyle.short,
            label_in=I18N.t('quote.modals.quote_public'),
            default_in=self.public_in_text
        )

        self.add_item(num_label)
        self.add_item(quote_text)
        self.add_item(quote_date)
        self.add_item(quote_public)

    async def on_submit(self, interaction: discord.Interaction):
        self.quote_out['row_id'] = self.children[0].value
        self.quote_out['quote_text'] = self.children[1].value
        if self.children[2].value == '':
            self.quote_out['datetime'] = str(get_dt(format='ISO8601'))
        else:
            self.quote_out['datetime'] = get_dt(
                format='ISO8601', dt=self.children[2].value
            )

        tab_quote = tabulate(
            [
                [I18N.t('quote.tab_headers.quote_num'),
                 self.quote_out['row_id']],
                [I18N.t('quote.tab_headers.quote'),
                 self.quote_out['quote_text']],
                [I18N.t('quote.tab_headers.quote_date'),
                 get_dt(
                     format='datetime', dt=self.quote_out['datetime']
                )]
            ], tablefmt='plain'
        )
        msg_out = I18N.t(
            'quote.modals.add.msg_confirm'
        )
        if self.children[3].value == I18N.t('common.literal_yes_no.yes'):
            _ephemeral = False
        elif self.children[3].value == I18N.t('common.literal_yes_no.no'):
            _ephemeral = True
        await interaction.response.send_message(
            f'{msg_out}:\n```{tab_quote}```',
            ephemeral=_ephemeral
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
        logger.debug(f'self.quote_in is: {self.quote_in}')

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


async def settings_db_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    settings_db = await db_helper.get_output(
        template_info=envs.quote_db_settings_schema,
        select=('setting', 'value')
    )
    _guild = discord_commands.get_guild()
    settings_type = envs.quote_db_settings_schema['type_checking']
    return [
        discord.app_commands.Choice(
            name='{} = {} ({})'.format(
                setting['setting'],
                get(
                    _guild.text_channels, id=int(setting['value'])
                ) if setting['setting'] == 'channel' else setting['value'],
                settings_type[setting['setting']]
            ),
            value=str(setting['setting'])
        )
        for setting in settings_db if current.lower() in '{}-{}'.format(
            setting['setting'], setting['value']
        ).lower()
    ][:25]


async def env_settings_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    settings_info = envs.quote_db_settings_schema['inserts']
    settings_type = envs.quote_db_settings_schema['type_checking']
    return [
        discord.app_commands.Choice(
            name='{} ({})'.format(
                settings_info[0], settings_type[settings_info[0]]
            ), value=str(settings_info[0])
        )
        for settings_info in settings_info if current.lower()
        in settings_info[0].lower()
    ][:25]


async def get_quote_from_db(quote_number):
    # If `number` is given, get that specific quote
    logger.debug(f'Got quote number {quote_number}')
    quote_row_check = await db_helper.get_row_ids(
        envs.quote_db_schema, sort=True
    )
    logger.debug(f'quote_row_check: {quote_row_check}')
    if int(quote_number) in quote_row_check:
        logger.debug('Found quote_number in quote_row_check')
        db_out = await db_helper.get_output_by_rowid(
            envs.quote_db_schema,
            rowid=quote_number
        )
    else:
        db_out = None
    return db_out


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
    logger.debug(f'number: {number}')
    logger.debug(f'text: {text}')
    logger.debug(f'date: {date}')
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


async def post_random_quote(interaction, _ephemeral):
    random_quote = await get_random_quote()
    if len(random_quote) == 0:
        await db_helper.empty_table(envs.quote_db_log_schema)
        random_quote = await get_random_quote()
    logger.debug(f'Got `random_quote`: {random_quote}')
    # Post quote
    quote_number = random_quote[0][0]
    quote_text = random_quote[0][2]
    quote_date = get_dt(
        format='datetextfull',
        dt=random_quote[0][3]
    )
    _quote = prettify(quote_number, quote_text, quote_date)
    logger.debug(f'Posting this quote:\n{_quote}')
    quote_post = await interaction.followup.send(
        _quote, ephemeral=_ephemeral
    )
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


async def post_selected_quote(interaction, _ephemeral, quote_in):
    quote_out = await get_quote_from_db(quote_in)
    logger.debug(f'quote_out: {quote_out}')
    if quote_out:
        quote_text = quote_out[0]['quote_text']
        quote_date = get_dt(
            format='datetextfull',
            dt=quote_out[0]['datetime']
        )
        _quote = prettify(quote_in, quote_text, quote_date)
        await interaction.followup.send(
            _quote, ephemeral=_ephemeral
        )
        return
    else:
        await interaction.followup.send(
            I18N.t(
                'quote.commands.post.quote_not_exist',
                quote_in=quote_in
            ),
            ephemeral=_ephemeral
        )
        return


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

    settings_group = discord.app_commands.Group(
        name="settings",
        description=locale_str(
            I18N.t('quote.commands.settings.cmd')
        ),
        parent=group
    )

    @group.command(
        name="post", description=locale_str(I18N.t('quote.commands.post.cmd'))
    )
    @describe(
        quote_in=I18N.t('quote.commands.post.desc.number')
    )
    async def post(
        self, interaction: discord.Interaction,
        quote_in: str = None,
        public: typing.Literal[
            I18N.t('common.literal_yes_no.yes'),
            I18N.t('common.literal_yes_no.no')
        ] = None
    ):
        '''
        Post quotes
        '''
        if public == I18N.t('common.literal_yes_no.yes'):
            _ephemeral = False
        elif public == I18N.t('common.literal_yes_no.no') or\
                public is None:
            _ephemeral = True
        await interaction.response.defer(ephemeral=_ephemeral)
        # If no `quote_in` is given, get a random quote
        if not quote_in:
            logger.debug('No quote number given, posting random quote')
            await post_random_quote(interaction, _ephemeral)
            return
        elif quote_in:
            await post_selected_quote(interaction, _ephemeral, quote_in)
        return

    @commands.is_owner()
    @group.command(
        name="add", description=locale_str(I18N.t('quote.commands.add.cmd'))
    )
    async def quote_add(
        self, interaction: discord.Interaction,
        public: typing.Literal[
            I18N.t('common.literal_yes_no.yes'),
            I18N.t('common.literal_yes_no.no')
        ] = I18N.t('common.literal_yes_no.no')
    ):
        'Add a quote'
        if public == I18N.t('common.literal_yes_no.yes'):
            _ephemeral = False
        elif public == I18N.t('common.literal_yes_no.no'):
            _ephemeral = True
        # Get available row id
        _row_ids = await db_helper.get_row_ids(
            envs.quote_db_schema, sort=True
        )
        logger.debug(f'_row_ids: {_row_ids}')
        if len(_row_ids) <= 0:
            last_row_id = 1
        else:
            last_row_id = _row_ids[-1] + 1
        modal_in = QuoteAddModal(
            public_in=_ephemeral,
            title_in=I18N.t('quote.modals.add.modal_title'),
            available_row_id=last_row_id
        )
        await interaction.response.send_modal(modal_in)
        await modal_in.wait()
        # Parse the quote
        quote_out = modal_in.quote_out
        logger.debug(f'quote_out: {quote_out}')
        # Add the quote
        await db_helper.insert_many_all(
            template_info=envs.quote_db_schema,
            inserts=[
                (
                    quote_out['uuid'], quote_out['quote_text'],
                    quote_out['datetime']
                )
            ]
        )
        return

    @commands.is_owner()
    @group.command(
        name="edit", description=locale_str(I18N.t('quote.commands.edit.cmd'))
    )
    @describe(
        quote_in=I18N.t('quote.commands.edit.desc.quote_in')
    )
    async def quote_edit(
        self, interaction: discord.Interaction, quote_in: str,
    ):
        'Edit an existing quote'
        logger.debug(f'quote_in: ({type(quote_in)}) {quote_in}')
        quote_from_db = await get_quote_from_db(quote_in)
        logger.debug(f'quote_from_db: {quote_from_db}')
        modal_in = QuoteEditModal(
            title_in=I18N.t('quote.modals.edit.modal_title'),
            quote_in=quote_from_db
        )
        await interaction.response.send_modal(modal_in)
        await modal_in.wait()
        update_triggered = False
        # Check for changes in quote text or quote date
        if str(quote_from_db[0][2]) != str(modal_in.quote_out['quote_text'])\
                or str(quote_from_db[0][2]) !=\
                str(modal_in.quote_out['datetime']):
            update_triggered = True
        else:
            logger.error('No changes discovered in quote')
            await interaction.followup.send(
                I18N.t('quote.modals.edit.msg_no_change'),
                ephemeral=True
            )
            return
        if update_triggered:
            logger.debug(
                'Discovered changes in quote',
            )
            logger.debug(pformat(modal_in.quote_out))
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

    @commands.is_owner()
    @group.command(
        name="delete", description=locale_str(
            I18N.t('quote.commands.delete.cmd')
        )
    )
    @describe(
        quote_number=I18N.t('quote.commands.delete.desc.quote_number')
    )
    async def quote_delete(
            self, interaction: discord.Interaction,
            quote_number: str
    ):
        'Delete an existing quote'
        await interaction.response.defer(ephemeral=True)
        quote_from_db = await get_quote_from_db(quote_number)
        logger.debug(f'quote_from_db is: {quote_from_db}')
        if quote_from_db is None:
            await interaction.followup.send(
                I18N.t(
                    'quote.commands.delete.msg_nonexisting_quote',
                    quote_number=quote_number
                ),
                ephemeral=True
            )
            return
        quote = quote_from_db[0]
        logger.debug(f'quote is: {quote}')
        confirm_buttons = ConfirmButtons()
        tab_quote = tabulate(
            [
                [I18N.t('quote.tab_headers.quote_num'), quote['rowid']],
                [I18N.t('quote.tab_headers.quote'), quote['quote_text']],
                [I18N.t('quote.tab_headers.quote_date'), get_dt(
                    format='datetime',
                    dt=quote['datetime']
                )]
            ], tablefmt='plain'
        )
        await interaction.followup.send(
            '{}\n```{}```'.format(
                I18N.t(
                    'quote.commands.delete.confirm_delete'
                ),
                tab_quote
            ),
            view=confirm_buttons,
            ephemeral=True
        )
        await confirm_buttons.wait()
        logger.debug(f'Got `confirm_buttons.value`: {confirm_buttons.value}')
        if confirm_buttons.value is True:
            # Remove the quote
            await db_helper.del_row_id(
                envs.quote_db_schema,
                quote['rowid']
            )
            # Confirm that the quote has been deleted
            await interaction.followup.send(
                I18N.t(
                    'quote.commands.delete.msg_confirm_delete',
                    quote_num=quote['rowid']
                ),
                ephemeral=True
            )
        elif confirm_buttons.value is False:
            await interaction.followup.send(
                I18N.t('quote.commands.delete.msg_confirm_not_delete'),
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                I18N.t('quote.commands.delete.msg_fail'),
                ephemeral=True
            )
            return

    @commands.is_owner()
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

    @commands.is_owner()
    @group.command(
        name="list", description=locale_str(
            I18N.t('quote.commands.list.cmd')
        )
    )
    async def quote_list(
        self, interaction: discord.Interaction, keyword: str = None,
        quote_number: int = None, shortened: bool = False
    ):
        async def prep_quotes(
            keyword: str = None,
            quote_number: int = None,
            shortened: bool = False
        ):
            quotes_out = []
            if quote_number and not keyword:
                quote_in = await db_helper.get_output_by_rowid(
                    template_info=envs.quote_db_schema,
                    rowid=quote_number
                )
            elif keyword and not quote_number:
                quote_in = await db_helper.get_output(
                    envs.quote_db_schema,
                    get_row_ids=True,
                    rowid_sort=True,
                    like=('quote_text', keyword) if keyword else None
                )
            else:
                return None
            logger.debug('Got quotes: {}'.format(quote_in))
            for _q in quote_in:
                q_no = _q['rowid']
                if any(item is None for item in _q):
                    logger.error(
                        f'None-values discovered in DB-file (quotes): {_q}'
                    )
                    pass
                else:
                    if shortened:
                        q_text = '{}...'.format(
                            _q['quote_text'][0:100]
                        ) if len(_q['quote_text']) > 100 else _q['quote_text']
                    else:
                        q_text = _q['quote_text']
                    q_datetime = _q['datetime']
                    quotes_out.append(
                        (
                            q_no, q_text, q_datetime
                        )
                    )
            logger.debug(f'Returning this as `quotes_out`: {quotes_out}')
            return quotes_out

        await interaction.response.defer()
        quote_in = await prep_quotes(
            keyword=keyword,
            quote_number=quote_number,
            shortened=shortened
        )
        if quote_in is None:
            await interaction.followup.send(
                I18N.t(
                    'quote.commands.list.msg_nonexisting_quote'
                ),
                ephemeral=True
            )
        temp_out = []
        for quote in quote_in:
            temp_out.append(
                (quote[0], quote[1], get_dt(format='datetime', dt=quote[2]))
            )
        logger.debug(f'`temp_out` is {temp_out}')
        paginated = []
        msg = ''
        for quote in temp_out:
            msg_in = f'# {quote[0]}\n{quote[1]}\n({quote[2]})'
            if quote != temp_out[-1]:
                msg_in += '\n\n'
            if len(msg) + len(msg_in) > 1900:
                paginated.append(msg)
                msg = ''
            msg += msg_in
            if quote == temp_out[-1]:
                paginated.append(msg)
        for page in paginated:
            await interaction.followup.send(f'```{page}```')
        return

    @commands.is_owner()
    @settings_group.command(
        name='list',
        description=locale_str(I18N.t('common.settings.list_settings'))
    )
    async def list_settings(
        self, interaction: discord.Interaction
    ):
        '''
        List the available settings for this cog
        '''
        await interaction.response.defer(ephemeral=True)
        settings_in_db = await db_helper.get_output(
            template_info=envs.quote_db_settings_schema,
            select=('setting', 'value')
        )
        headers_settings = {
            'setting': I18N.t('common.settings.setting'),
            'value': I18N.t('common.settings.value')
        }
        out = '## {}\n```{}```'.format(
            I18N.t('stats.commands.list.stats_msg_out.sub_settings'),
            tabulate(settings_in_db, headers=headers_settings)
        )
        await interaction.followup.send(content=out, ephemeral=True)

    @commands.is_owner()
    @discord.app_commands.autocomplete(
        name_of_setting=settings_db_autocomplete
    )
    @settings_group.command(
        name='change',
        description=locale_str(
            I18N.t('common.settings.change_settings')
        )
    )
    @describe(
        name_of_setting=I18N.t('common.settings.name_of_setting'),
        value_in=I18N.t('common.settings.value_in')
    )
    async def change_setting(
        self, interaction: discord.Interaction, name_of_setting: str,
        value_in: str
    ):
        '''
        Change a setting for this cog

        Parameters
        ------------
        name_of_setting: str
            The names of the role to change (default: None)
        value_in: str
            The value of the settings (default: None)
        '''
        await interaction.response.defer(ephemeral=True)
        settings_in_db = await db_helper.get_output(
            template_info=envs.quote_db_settings_schema,
            select=('setting', 'value')
        )
        settings_from_db = {}
        for setting in settings_in_db:
            settings_from_db[setting['setting']] = setting['value']
        logger.debug(f'settings_from_db:\n{pformat(settings_from_db)}')
        settings_type = envs.quote_db_settings_schema['type_checking']
        for setting in settings_from_db:
            if settings_type[setting] == 'bool':
                try:
                    value_in = eval(str(value_in).capitalize())
                except NameError as _error:
                    logger.error(f'Invalid input for `value_in`: {_error}')
                    await interaction.followup.send(I18N.t(
                        'stats.setting_input_reply'
                    ))
                    return
            logger.debug(f'`value_in` is {value_in} ({type(value_in)})')
            logger.debug(
                f'`settings_type` is {settings_type[setting]} '
                f'({type(settings_type[setting])})'
            )
            if type(value_in) is eval(settings_type[setting]):
                await db_helper.update_fields(
                    template_info=envs.quote_db_settings_schema,
                    where=[('setting', name_of_setting)],
                    updates=[('value', value_in)]
                )
            await interaction.followup.send(
                content=I18N.t('quote.commands.settings.change_confirmed'),
                ephemeral=True
            )
            Quotes.task_autopost.restart()
            break
        return

    @commands.is_owner()
    @discord.app_commands.autocomplete(
        setting_in=env_settings_autocomplete
    )
    @settings_group.command(
        name='add',
        description=locale_str(I18N.t('common.settings.add_setting'))
    )
    @describe(
        setting_in=I18N.t('common.settings.setting'),
        value_in=I18N.t('common.settings.value'),
    )
    async def add_setting(
        self, interaction: discord.Interaction,
        setting_in: str, value_in: str
    ):
        '''
        Add a setting for this cog
        '''
        await interaction.response.defer(ephemeral=True)
        settings_in_db = await db_helper.get_output(
            template_info=envs.quote_db_settings_schema,
            select=('setting', 'value')
        )
        settings_db_json = file_io.make_db_output_to_json(
            ['setting', 'value'],
            settings_in_db
        )
        settings_types = envs.quote_db_settings_schema['type_checking']
        logger.debug('settings_db_json is `{}`'.format(settings_db_json))
        logger.debug(f'Value is {value_in}')
        if value_in.lower() in ['true', 'false']:
            value_in = value_in.capitalize()
            value_in_check = type(eval('{}({})'.format(
                settings_types[setting_in], value_in
            )))
        elif setting_in == 'channel':
            _guild = discord_commands.get_guild()
            channel_object = get(
                _guild.text_channels, name=str(value_in)
            )
            if channel_object is None:
                overwrites = {
                    _guild.default_role: discord.PermissionOverwrite(
                        send_messages=False,
                        read_messages=True,
                        send_tts_messages=False,
                        use_external_emojis=True,
                        send_messages_in_threads=False,
                        use_external_stickers=True,
                        create_polls=False
                    ),
                    _guild.me: discord.PermissionOverwrite(
                        send_messages=True,
                        read_messages=True
                    )
                }
                channel_object = await discord_commands.create_missing_channel(
                    channel=value_in, channel_name=value_in,
                    topic=I18N.t('quote.commands.settings.add_channel_topic'),
                    overwrites=overwrites
                )
            value_in = channel_object.id
            value_in_check = type(value_in)
        else:
            value_in_check = type(value_in)
        logger.debug(f'Value type is {value_in_check}')
        logger.debug(f'Setting type is {eval(settings_types[setting_in])}')
        if settings_db_json is not None and\
                setting_in in settings_db_json:
            await interaction.followup.send(
                content=I18N.t(
                    'quote.commands.settings.add_setting_exist'
                ),
                ephemeral=True
            )
            return
        try:
            if value_in_check is not eval(settings_types[setting_in]):
                await interaction.followup.send(
                    content=I18N.t(
                        'quote.commands.settings.add_type_incorrect',
                        value_in=value_in, value_type=type(value_in),
                        value_type_check=settings_types[setting_in]
                    ),
                    ephemeral=True
                )
                return
            elif value_in_check is eval(settings_types[setting_in]) and\
                    setting_in:
                await db_helper.insert_many_all(
                    template_info=envs.quote_db_settings_schema,
                    inserts=[(setting_in, value_in)]
                )
                await interaction.followup.send(
                    content=I18N.t('quote.commands.settings.add_confirmed'),
                    ephemeral=True
                )
                sleep(3)
                Quotes.task_autopost.restart()
                return
        except Exception as error:
            logger.error(f'Something went wrong: {error}')
            await interaction.followup.send(
                content=I18N.t('common.something_wrong', error=error),
                ephemeral=True
            )
            return

    @commands.is_owner()
    @discord.app_commands.autocomplete(
        setting_in=settings_db_autocomplete
    )
    @settings_group.command(
        name='remove',
        description=locale_str(I18N.t('common.settings.remove_setting'))
    )
    @describe(
        setting_in=I18N.t('common.settings.setting')
    )
    async def remove_setting(
        self, interaction: discord.Interaction, setting_in: str
    ):
        '''
        Remove a setting for this cog
        '''
        await interaction.response.defer(ephemeral=True)
        try:
            await db_helper.del_row_by_AND_filter(
                template_info=envs.quote_db_settings_schema,
                where=[('setting', setting_in)]
            )
            await interaction.followup.send(
                content=I18N.t('quote.commands.settings.remove_confirmed'),
                ephemeral=True
            )
            Quotes.task_autopost.restart()
        except Exception as error:
            logger.error(f'Error when removing setting: {error}')
            await interaction.followup.send(
                content=I18N.t('quote.commands.settings.remove_failed', error=error),
                ephemeral=True
            )
        return

async def setup(bot):
    # Create necessary databases before starting
    cog_name = 'quote'
    logger.info(envs.COG_STARTING.format(cog_name))
    logger.debug('Checking db')

    # Convert json to sqlite db-files if exists
    # Define inserts
    quote_inserts = None
    # Populate the inserts if json file exist
    if file_io.file_exist(envs.quote_file):
        logger.debug('Found old json file')
        quote_inserts = await db_helper.json_to_db_inserts(cog_name)

    quote_prep_is_ok = await db_helper.prep_table(
        envs.quote_db_schema, quote_inserts
    )
    await db_helper.prep_table(
        envs.quote_db_log_schema
    )
    await db_helper.prep_table(
        envs.quote_db_settings_schema
    )

    # Delete old json files if they exist
    if quote_prep_is_ok and file_io.file_exist(envs.quote_file):
        file_io.remove_file(envs.quote_file)
    if quote_prep_is_ok and file_io.file_size(envs.quote_log_file):
        file_io.remove_file(envs.quote_log_file)
    logger.debug('Registering cog to bot')
    await bot.add_cog(Quotes(bot))
