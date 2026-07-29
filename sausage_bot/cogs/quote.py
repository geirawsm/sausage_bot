#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"quote: Administer or post quotes"

import discord
from discord.ext import commands, tasks
from discord.app_commands import (
    locale_str,
    describe,
)
from discord.utils import get
import uuid
from tabulate import tabulate
import typing
from pprint import pformat
import re
from datetime import datetime
import requests
import base64
import binascii
from io import BytesIO
from PIL import Image

from sausage_bot.util import datetime_handling
from sausage_bot.util.args import args
from sausage_bot.util import envs, db_helper, file_io, config, discord_commands
from sausage_bot.util.datetime_handling import get_dt
from sausage_bot.util.i18n import I18N
from sausage_bot.util.logger import truncate_for_log

logger = config.logger


async def get_autopost_time(guild_id):
    db_in = envs.quote_db_settings_schema
    db_settings = await db_helper.get_output(db_in, guild_id=guild_id)
    logger.debug("`db_settings` is: {}".format(db_settings))
    time_out = None
    if db_settings is not None:
        for setting in db_settings:
            if setting.get("setting") == "autopost_time":
                time_out = setting["value"]
                if time_out in [None, ""]:
                    time_out = "12:00:00"
                time_out = datetime.strptime(time_out, "%H:%M:%S").astimezone().time()
    logger.debug("`time_out` is: {}".format(time_out))
    if time_out in [None, ""]:
        time_out = "12:00:00"
        time_out = datetime.strptime(time_out, "%H:%M:%S").astimezone().time()
        await db_helper.update_fields(
            template_info=db_in,
            where=[("setting", "autopost_time")],
            updates=[("value", str(time_out))],
            guild_id=guild_id,
        )
    if time_out is not None:
        time_out = re.search(r"^(\d{2}):(\d{2}):\d{2}$", str(time_out))
    return time_out


class ConfirmButtons(discord.ui.View):
    def __init__(self, *, timeout=60, yes_label=None, no_label=None):
        super().__init__(timeout=timeout)
        self.yes_label = yes_label
        self.no_label = no_label
        self.value = None

        self.add_item(ButtonConfirm(label=self.yes_label))
        self.add_item(ButtonDeny(label=self.no_label))


class ButtonConfirm(discord.ui.Button):
    def __init__(self, label):
        super().__init__(label=label, style=discord.ButtonStyle.green)
        self.value = None

    async def callback(self, interaction: discord.Interaction):
        self.value = True
        # Disable all buttons
        buttons = [x for x in self.view.children]
        for _btn in buttons:
            _btn.disabled = True
        await interaction.response.edit_message(view=self.view)
        self.view.stop()


class ButtonDeny(discord.ui.Button):
    def __init__(self, label):
        super().__init__(label=label, style=discord.ButtonStyle.red)
        self.value = None

    async def callback(self, interaction: discord.Interaction):
        self.value = False
        # Disable all buttons
        buttons = [x for x in self.view.children]
        for _btn in buttons:
            _btn.disabled = True
        await interaction.response.edit_message(view=self.view)
        self.view.stop()


class ModalQuoteAdd(discord.ui.Modal):
    def prep_dropdown(
        self, msgs_in: list[discord.Message], defaults: list[int]
    ) -> list[discord.SelectOption] | None:
        "Prepare dropdown selections"
        list_out = []
        if len(msgs_in) == 0:
            return None
        for _msg in msgs_in:
            oneliner = f"{_msg.author.name}: {_msg.content[:90]}..."
            logger.debug(f"Checking quote: {oneliner}")
            if isinstance(defaults, list) and _msg.id in defaults:
                _default_in = True
            else:
                _default_in = False
            if len(str(oneliner)) >= 100:
                oneliner = f"{str(oneliner):.90}..."
            list_out.append(
                discord.SelectOption(
                    label=oneliner, value=str(_msg.id), default=_default_in
                )
            )
        return list_out

    def __init__(
        self,
        msgs_in: list = [],
        defaults: list = [],
        title_in: str = "Dummy title",
        row_ids: int = 0,
    ) -> None:
        super().__init__(title=title_in)

        self.msgs_in = msgs_in
        self.defaults = defaults
        self.msgs_out = []
        self.row_ids = row_ids
        logger.debug(f"self.msgs_in: {self.msgs_in}")
        logger.debug(f"self.defaults: {self.defaults}")

        self.quote_prep = self.prep_dropdown(msgs_in, defaults)
        logger.debug(
            f"self.quote_prep ({len(self.quote_prep)}: {str(self.quote_prep)[0:500]}"
        )
        self.quote_dropdown = discord.ui.Select(
            placeholder="Select quotes...",
            options=self.quote_prep,
            max_values=int(len(self.quote_prep) if self.quote_prep else 25),
            required=True,
        )
        self.add_item(
            discord.ui.Label(text="Quote message", component=self.quote_dropdown)
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not self.quote_dropdown.values:
            await interaction.response.send_message(
                I18N.t("quote.modals.add.msg_request_quote"), ephemeral=True
            )
        else:
            self.msgs_out = self.quote_dropdown.values
            if self.row_ids == 0:
                msg_out = I18N.t("quote.modals.add.msg_confirm")
            else:
                msg_out = (f"Sitat lagret som nr {self.row_ids + 1}!",)
            await interaction.response.send_message(msg_out, ephemeral=True)
        return

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.response.send_message(
            I18N.t("quote.modals.error", error=error), ephemeral=True
        )


async def settings_db_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    settings_in_db = await db_helper.get_output(
        template_info=envs.quote_db_settings_schema,
        select=("setting", "value"),
        guild_id=interaction.guild.id,
    )
    settings_type = envs.quote_db_settings_schema["type_checking"]
    return [
        discord.app_commands.Choice(
            name="{setting_name} = {object}({value_type})".format(
                setting_name=setting["setting"],
                object="{object_value} ({actual_value}) ".format(
                    object_value=discord_commands.get_user_channel_role_id(
                        interaction.guild, setting["value"]
                    ),
                    actual_value=setting["value"],
                )
                if discord_commands.get_user_channel_role_id(
                    interaction.guild, setting["value"]
                )
                is not None
                else "{} ".format(setting["value"]),
                value_type=settings_type[setting["setting"]],
            ),
            value=str(setting["setting"]),
        )
        for setting in settings_in_db
        if current.lower()
        in "{}-{}".format(setting["setting"], setting["value"]).lower()
    ][:25]


async def env_settings_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    settings_info = envs.quote_db_settings_schema["inserts"]
    settings_type = envs.quote_db_settings_schema["type_checking"]
    return [
        discord.app_commands.Choice(
            name="{} ({})".format(settings_info[0], settings_type[settings_info[0]]),
            value=str(settings_info[0]),
        )
        for settings_info in settings_info
        if current.lower() in settings_info[0].lower()
    ][:25]


async def get_random_quote(guild_id, testmode=False):
    """
    Return rowid for random quote
    #autodoc skip#
    """
    row_id = await db_helper.get_row_ids(envs.quote_db_schema, guild_id=guild_id)
    if row_id is None or len(row_id) == 0:
        return None
    if testmode:
        row_id = row_id[0]
        logger.debug(f"Got `row_id`: {row_id}")
        quote = await db_helper.get_output_by_rowid(
            envs.quote_db_schema,
            rowid=row_id,
            fields_out=("rowid", "uuid", "quote_text", "datetime"),
            guild_id=guild_id,
        )
        return quote
    random_quote = await db_helper.get_random_left_exclude_output(
        envs.quote_db_schema,
        envs.quote_db_log_schema,
        "uuid",
        ("rowid", "uuid", "datetime"),
        guild_id=guild_id,
    )
    if random_quote is None or len(random_quote) == 0:
        await db_helper.empty_table(envs.quote_db_log_schema, guild_id=guild_id)
        random_quote = await db_helper.get_random_left_exclude_output(
            envs.quote_db_schema,
            envs.quote_db_log_schema,
            "uuid",
            ("rowid", "uuid", "datetime"),
            guild_id=guild_id,
        )
    return random_quote


async def post_random_quote(
    guild: discord.Guild,
    interaction=None,
    _ephemeral=None,
    autopost={},
    channel: int = 0,
):
    random_quote_number = await get_random_quote(guild.id, testmode=args.testmode)
    if random_quote_number is None or len(random_quote_number) == 0:
        logger.debug("No quotes found in database")
        if len(autopost) > 0:
            await discord_commands.post_to_channel(
                channel_id=channel,
                content_in=I18N.t("quote.common.quote_db_empty"),
            )
        else:
            await interaction.followup.send(
                I18N.t("quote.commands.post.quote_db_empty"), ephemeral=_ephemeral
            )
            return
    logger.debug(f"Got `random_quote_number`: {random_quote_number}")
    # Post quote
    random_quote = await db_helper.get_imgs_with_quote(
        envs.quote_db_schema,
        where=[("quote.rowid", str(random_quote_number[0][0]))],
        guild_id=guild.id,
    )
    logger.debug(f"random_quote: {random_quote}")
    channel_id = interaction.channel.id if interaction else channel
    if random_quote is None:
        if len(autopost) > 0:
            await discord_commands.post_to_channel(
                channel_id=channel_id,
                content_in=I18N.t("quote.commands.list.msg_nonexisting_quote"),
            )
        else:
            await interaction.followup.send(
                I18N.t("quote.commands.list.msg_nonexisting_quote"),
                ephemeral=_ephemeral,
            )
        return
    elif len(random_quote) == 0:
        if len(autopost) > 0:
            await discord_commands.post_to_channel(
                channel_id=channel_id,
                content_in=I18N.t("quote.common.quote_db_empty"),
            )
        else:
            await interaction.followup.send(
                I18N.t("quote.common.quote_db_empty"),
                ephemeral=_ephemeral,
            )
        return
    random_quote = random_quote[0]
    if random_quote is not None:
        quote = random_quote
        paginated = []
        msg = ""
        trigger_pagination = False
        logger.debug(f"trigger_pagination is {trigger_pagination}")
        quote_dt = await get_dt(format="datetime", dt=quote["datetime"])
        # Get max len of author
        author_max_len = 0
        for comment in quote["comments"]:
            if len(quote["comments"][comment]["author_backup"]) > author_max_len:
                author_max_len = len(quote["comments"][comment]["author_backup"])
        quote_channel = ""
        quote_channel_object = get(guild.text_channels, id=int(quote["channel_id"]))
        if quote_channel_object is None:
            quote_channel = quote["channel_backup"]
        else:
            quote_channel = quote_channel_object.name
        if len(autopost) > 0:
            if autopost["prefix"]:
                logger.debug("Adding prefix to msg_in")
                msg_in = "## {}\n`# {} - #{}, {}`\n\n".format(
                    autopost["prefix"], quote["rowid"], quote_channel, quote_dt
                )
        else:
            msg_in = "`# {} - #{}, {}`\n\n".format(
                quote["rowid"], quote_channel, quote_dt
            )
        comment_last_key = next(reversed(quote["comments"]))
        for _comment_id in quote["comments"]:
            comment = quote["comments"][_comment_id]
            _author = comment["author_backup"].ljust(author_max_len, " ")
            msg_in += "`{}: {}`".format(_author, comment["content"])
            if len(comment["imgs"]) > 0:
                logger.debug(f"trigger_pagination is {trigger_pagination}")
                trigger_pagination = True
                img_list = []
                for _img_id in comment["imgs"]:
                    img = comment["imgs"][_img_id]
                    img_object = convert_b64_to_img_in_mem(str(img))
                    img_list.append(img_object)
                if len(autopost) > 0:
                    await discord_commands.post_to_channel(
                        channel_id=channel_id, content_in=msg_in, files_in=img_list
                    )
                else:
                    await interaction.followup.send(
                        msg_in, files=img_list, ephemeral=_ephemeral
                    )
                await db_helper.insert_many_all(
                    envs.quote_db_log_schema,
                    [
                        (
                            quote["uuid"],
                            channel_id,
                            str(
                                await datetime_handling.get_dt(
                                    format="datetimeobject", no_timezone=True
                                )
                            ),
                        )
                    ],
                    guild_id=guild.id,
                )
                msg_in = ""
                trigger_pagination = False
            else:
                if _comment_id != list(quote["comments"])[-1]:
                    msg_in += "\n"
        if len(autopost) > 0:
            if autopost["tag_role"]:
                logger.debug("Adding tag_role to msg_in")
                msg_in += "\nPing <@&{}>".format(autopost["tag_role"])
        if len(msg_in) > 0:
            if len(autopost) > 0:
                await discord_commands.post_to_channel(
                    channel_id=channel_id,
                    content_in=msg_in,
                )
            else:
                await interaction.followup.send(msg_in, ephemeral=_ephemeral)
            await db_helper.insert_many_all(
                envs.quote_db_log_schema,
                [
                    (
                        quote["uuid"],
                        channel_id,
                        str(
                            await datetime_handling.get_dt(
                                format="datetimeobject", no_timezone=True
                            )
                        ),
                    )
                ],
                guild_id=guild.id,
            )
            msg_in = ""
        logger.debug(f"trigger_pagination is {trigger_pagination}")
        if len(msg) + len(msg_in) > 1900 or trigger_pagination:
            paginated.append(msg)
            msg = ""
        if not trigger_pagination and len(msg) > 0:
            msg += "\n\n"
            msg += msg_in
            if _comment_id == comment_last_key and msg != "":
                logger.debug("paginating after quote_last_key")
                paginated.append(msg)
        trigger_pagination = False
        logger.debug(f"trigger_pagination is {trigger_pagination}")
        logger.debug(f"paginated: {paginated}")
        if len(paginated) > 0:
            for page in paginated:
                if len(autopost) > 0:
                    await discord_commands.post_to_channel(
                        channel_id=channel_id,
                        content_in=str(page),
                    )
                else:
                    await interaction.followup.send(str(page), ephemeral=_ephemeral)
                await db_helper.insert_many_all(
                    envs.quote_db_log_schema,
                    [
                        (
                            quote["uuid"],
                            channel_id,
                            str(
                                await datetime_handling.get_dt(
                                    format="datetimeobject", no_timezone=True
                                )
                            ),
                        )
                    ],
                    guild_id=guild.id,
                )
        return


async def post_selected_quote(interaction, _ephemeral, quote_in):
    quote = await db_helper.get_imgs_with_quote(
        envs.quote_db_schema,
        where=[("quote.rowid", int(quote_in))],
        guild_id=interaction.guild.id,
    )
    logger.debug(f"quote: {quote}")
    if len(quote) == 0:
        await interaction.followup.send(
            I18N.t("quote.commands.list.msg_nonexisting_quote"),
            ephemeral=_ephemeral,
        )
        return
    quote_out = quote[0]
    if quote_out is not None:
        quote = quote_out
        paginated = []
        msg = ""
        trigger_pagination = False
        logger.debug(f"trigger_pagination is {trigger_pagination}")
        quote_dt = await get_dt(format="datetime", dt=quote["datetime"])
        # Get max len of author
        author_max_len = 0
        for comment in quote["comments"]:
            if len(quote["comments"][comment]["author_backup"]) > author_max_len:
                author_max_len = len(quote["comments"][comment]["author_backup"])
        quote_channel = ""
        quote_channel_object = get(
            interaction.guild.text_channels, id=int(quote["channel_id"])
        )
        if quote_channel_object is None:
            quote_channel = quote["channel_backup"]
        else:
            quote_channel = quote_channel_object.name
        msg_in = "`# {} - #{}, {}`\n\n".format(quote["rowid"], quote_channel, quote_dt)
        comment_last_key = next(reversed(quote["comments"]))
        for _comment_id in quote["comments"]:
            comment = quote["comments"][_comment_id]
            _author = comment["author_backup"].ljust(author_max_len, " ")
            msg_in += "`{}: {}`".format(_author, comment["content"])
            if len(comment["imgs"]) > 0:
                logger.debug(f"trigger_pagination is {trigger_pagination}")
                trigger_pagination = True
                img_list = []
                for _img_id in comment["imgs"]:
                    img = comment["imgs"][_img_id]
                    img_object = convert_b64_to_img_in_mem(str(img))
                    img_list.append(img_object)
                await interaction.followup.send(
                    msg_in, files=img_list, ephemeral=_ephemeral
                )
                await db_helper.insert_many_all(
                    envs.quote_db_log_schema,
                    [
                        (
                            quote["uuid"],
                            interaction.channel.id,
                            str(
                                await datetime_handling.get_dt(
                                    format="datetimeobject", no_timezone=True
                                )
                            ),
                        )
                    ],
                    guild_id=interaction.guild.id,
                )
                msg_in = ""
                trigger_pagination = False
            else:
                if _comment_id != list(quote["comments"])[-1]:
                    msg_in += "\n"
        if len(msg_in) > 0:
            await interaction.followup.send(msg_in, ephemeral=_ephemeral)
            await db_helper.insert_many_all(
                envs.quote_db_log_schema,
                [
                    (
                        quote["uuid"],
                        interaction.channel.id,
                        str(
                            await datetime_handling.get_dt(
                                format="datetimeobject", no_timezone=True
                            )
                        ),
                    )
                ],
                guild_id=interaction.guild.id,
            )
            msg_in = ""
        logger.debug(f"trigger_pagination is {trigger_pagination}")
        if len(msg) + len(msg_in) > 1900 or trigger_pagination:
            logger.debug("paginating after quote_last_key")
            paginated.append(msg)
            msg = ""
        if not trigger_pagination and len(msg) > 0:
            msg += "\n\n"
            msg += msg_in
            if _comment_id == comment_last_key and msg != "":
                logger.debug("paginating")
                paginated.append(msg)
        trigger_pagination = False
        logger.debug(f"trigger_pagination is {trigger_pagination}")
        logger.debug(f"paginated: {paginated}")
        if len(paginated) > 0:
            for page in paginated:
                await interaction.followup.send(str(page), ephemeral=_ephemeral)
                await db_helper.insert_many_all(
                    envs.quote_db_log_schema,
                    [
                        (
                            quote["uuid"],
                            interaction.channel.id,
                            str(
                                await datetime_handling.get_dt(
                                    format="datetimeobject", no_timezone=True
                                )
                            ),
                        )
                    ],
                    guild_id=interaction.guild.id,
                )
        return


class Quotes(commands.Cog):
    "Administer or post quotes"

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    group = discord.app_commands.Group(
        name="quote", description=locale_str(I18N.t("quote.commands.quote.cmd"))
    )

    autopost_group = discord.app_commands.Group(
        name="autopost",
        description=locale_str(I18N.t("quote.commands.autopost.cmd")),
        parent=group,
    )

    settings_group = discord.app_commands.Group(
        name="settings",
        description=locale_str(I18N.t("quote.commands.settings.cmd")),
        parent=group,
    )

    @group.command(
        name="post", description=locale_str(I18N.t("quote.commands.post.cmd"))
    )
    @describe(quote_in=I18N.t("quote.commands.post.desc.number"))
    @describe(quote_in=I18N.t("quote.commands.post.desc.number"))
    async def post(
        self,
        interaction: discord.Interaction,
        quote_in: str = None,
        public: typing.Literal[
            I18N.t("common.literal_yes_no.lit_yes"),
            I18N.t("common.literal_yes_no.lit_no"),
        ] = I18N.t("common.literal_yes_no.lit_no"),
    ):
        """
        Post quotes
        """
        if public == I18N.t("common.literal_yes_no.lit_yes"):
            _ephemeral = False
        else:
            _ephemeral = True
        await interaction.response.defer(ephemeral=_ephemeral)
        # If no `quote_in` is given, get a random quote
        if not quote_in:
            logger.debug("No quote number given, posting random quote")
            await post_random_quote(
                guild=interaction.guild,
                interaction=interaction,
                _ephemeral=_ephemeral,
            )
            return
        elif quote_in:
            await post_selected_quote(interaction, _ephemeral, quote_in)
        return

    @commands.is_owner()
    @group.command(
        name="edit", description=locale_str(I18N.t("quote.commands.edit.cmd"))
    )
    @describe(quote_in=I18N.t("quote.commands.edit.desc.quote_in"))
    async def quote_edit(self, interaction: discord.Interaction, quote_in: str):
        "Edit an existing quote"
        logger.debug(f"quote_in: ({type(quote_in)}) {quote_in}")
        quote_from_db = await db_helper.get_imgs_with_quote(
            envs.quote_db_schema,
            where=[("quote.rowid", int(quote_in))],
            guild_id=interaction.guild.id,
        )
        quote_from_db = quote_from_db[0]
        logger.debug(f"quote_from_db: {quote_from_db}")
        channel_out = interaction.guild.get_channel(quote_from_db["channel_id"])
        msgs = []
        msg_defaults = [msg_id for msg_id in quote_from_db["comments"]]
        # Get quote middle message for history fetch
        middle_msg = await discord_commands.get_message_obj(
            guild=interaction.guild,
            msg_id=msg_defaults[len(msg_defaults) // 2],
            channel_id=quote_from_db["channel_id"],
        )
        # Get quotes before
        msgs_before = channel_out.history(limit=12, before=middle_msg)
        async for _msg in msgs_before:
            msgs.append(_msg)
        msgs.reverse()
        msgs.append(middle_msg)
        msgs_after = channel_out.history(limit=12, after=middle_msg)
        async for _msg in msgs_after:
            msgs.append(_msg)
        editquote_view = ModalQuoteAdd(
            title_in="Endre sitat", msgs_in=msgs, defaults=msg_defaults
        )
        await interaction.response.send_modal(editquote_view)
        await editquote_view.wait()
        # Get quotes and add to db
        quote_msgs_out = editquote_view.msgs_out
        logger.debug(f"msg_defaults: {msg_defaults}")
        logger.debug(f"quote_msgs_out: {quote_msgs_out}")
        # Edit the quote
        quotes_out = []
        for quote in quote_msgs_out:
            quote_object = await discord_commands.get_message_obj(
                guild=interaction.guild,
                msg_id=quote,
                channel_id=quote_from_db["channel_id"],
            )
            quotes_out.append(quote_object)
        # Remove quote comments
        quote_comments_remove = list(set(msg_defaults) - set(quote_msgs_out))
        # Prepare the edited quote
        prep_quote_to_db = []
        quote_to_db = []
        imgs_to_db = []
        quote_insert_order = 0
        for quote in sorted(quote_msgs_out):
            _q_object = await discord_commands.get_message_obj(
                guild=interaction.guild,
                msg_id=quote,
                channel_id=quote_from_db["channel_id"],
            )
            prep_quote_to_db.append(_q_object)
            content = _q_object.content
            quote_to_db.append(
                (
                    quote_from_db["uuid"],
                    _q_object.id,
                    _q_object.author.id,
                    _q_object.author.name,
                    content,
                    quote_insert_order,
                )
            )
            quote_insert_order += 1
            imgs_in = get_imgs_to_db_format(_q_object)
            if imgs_in:
                imgs_to_db += imgs_in
        # Delete old comments
        if len(quote_comments_remove) > 0:
            await db_helper.del_row_by_OR_filter(
                template_info=envs.quote_content_db_schema,
                where=[("comment_id", c_id) for c_id in quote_comments_remove],
                guild_id=interaction.guild.id,
            )
            await db_helper.del_row_by_OR_filter(
                template_info=envs.quote_img_db_schema,
                where=[("comment_id", c_id) for c_id in quote_comments_remove],
                guild_id=interaction.guild.id,
            )

        # Add new comments
        await db_helper.insert_many_all(
            template_info=envs.quote_content_db_schema,
            inserts=quote_to_db,
            guild_id=interaction.guild.id,
        )
        if len(imgs_to_db) > 0:
            await db_helper.insert_many_all(
                template_info=envs.quote_img_db_schema,
                inserts=imgs_to_db,
                guild_id=interaction.guild.id,
            )
        return

    @commands.is_owner()
    @group.command(
        name="delete", description=locale_str(I18N.t("quote.commands.delete.cmd"))
    )
    @describe(quote_number=I18N.t("quote.commands.delete.desc.quote_number"))
    async def quote_delete(self, interaction: discord.Interaction, quote_number: int):
        "Delete an existing quote"
        quote_number = int(quote_number)
        await interaction.response.defer(ephemeral=True)
        quote_from_db = await db_helper.get_imgs_with_quote(
            envs.quote_db_schema,
            where=[("quote.rowid", str(quote_number))],
            guild_id=interaction.guild.id,
        )
        logger.debug(f"quote_from_db is: {truncate_for_log(quote_from_db)}")
        if quote_from_db == []:
            await interaction.followup.send(
                I18N.t(
                    "quote.commands.delete.msg_nonexisting_quote",
                    quote_number=quote_number,
                ),
                ephemeral=True,
            )
            return
        quote = quote_from_db[0]
        logger.debug(f"quote is: {truncate_for_log(quote)}")
        confirm_buttons = ConfirmButtons(
            yes_label=I18N.t("common.literal_yes_no.lit_yes"),
            no_label=I18N.t("common.literal_yes_no.lit_no"),
        )
        paginated = []
        msg = ""
        trigger_pagination = False
        quote_dt = await get_dt(format="datetime", dt=quote["datetime"])
        quote_channel = ""
        quote_channel_object = get(
            interaction.guild.text_channels, id=int(quote["channel_id"])
        )
        if quote_channel_object is None:
            quote_channel = quote["channel_backup"]
        else:
            quote_channel = quote_channel_object.name
        msg_in = "`# {} - #{}, {}`\n\n".format(quote["rowid"], quote_channel, quote_dt)
        for _comment_id in quote["comments"]:
            comment = quote["comments"][_comment_id]
            msg_in += "`{}: {}`".format(comment["author_backup"], comment["content"])
            if len(comment["imgs"]) > 0:
                trigger_pagination = True
                img_list = []
                for _img_id in comment["imgs"]:
                    img = comment["imgs"][_img_id]
                    img_object = convert_b64_to_img_in_mem(str(img))
                    img_list.append(img_object)
                await interaction.followup.send(msg_in, files=img_list, ephemeral=True)
                msg_in = ""
                trigger_pagination = False
            else:
                if _comment_id != list(quote["comments"])[-1]:
                    msg_in += "\n"
        if len(msg_in) > 0:
            await interaction.followup.send(msg_in, ephemeral=True)
            msg_in = ""
        logger.debug(f"trigger_pagination is {trigger_pagination}")
        if len(msg) + len(msg_in) > 1900 or trigger_pagination:
            logger.debug("paginating")
            paginated.append(msg)
            msg = ""
        if not trigger_pagination and len(msg) > 0:
            msg += "\n\n"
            msg += msg_in
        trigger_pagination = False
        logger.debug(f"trigger_pagination is {trigger_pagination}")
        logger.debug(f"paginated: {paginated}")
        if len(paginated) > 0:
            for page in paginated:
                await interaction.followup.send(str(page), ephemeral=True)
        confirm_buttons = ConfirmButtons(
            yes_label=I18N.t("common.literal_yes_no.lit_yes"),
            no_label=I18N.t("common.literal_yes_no.lit_no"),
        )
        await interaction.followup.send(
            I18N.t("quote.commands.delete.confirm_delete"),
            view=confirm_buttons,
            ephemeral=True,
        )
        await confirm_buttons.wait()
        btn_values = [ch.value for ch in confirm_buttons.children]
        logger.debug(f"btn_values is {btn_values}")
        if False in btn_values:
            # Confirm not deleting quote
            await interaction.followup.send(
                I18N.t("quote.delete.msg_confirm_not_delete"),
                ephemeral=True,
            )
            return
        if True in btn_values:
            # Remove the quote
            await db_helper.del_row_id(
                envs.quote_db_schema, quote["rowid"], guild_id=interaction.guild.id
            )
            # Confirm that the quote has been deleted
            await interaction.followup.send(
                I18N.t(
                    "quote.commands.delete.msg_confirm_delete",
                    quote_num=quote["rowid"],
                ),
                ephemeral=True,
            )
        elif False in btn_values:
            await interaction.followup.send(
                I18N.t("quote.commands.delete.msg_confirm_not_delete"),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                I18N.t("quote.commands.delete.msg_fail"), ephemeral=True
            )

    @commands.is_owner()
    @group.command(
        name="count", description=locale_str(I18N.t("quote.commands.count.cmd"))
    )
    async def quote_count(self, interaction: discord.Interaction):
        "Count the number of quotes available"
        await interaction.response.defer()
        quote_count = len(
            await db_helper.get_output(
                template_info=envs.quote_db_schema,
                select=("uuid"),
                guild_id=interaction.guild.id,
            )
        )
        await interaction.followup.send(
            I18N.t("quote.commands.count.msg_confirm", count=quote_count)
        )
        return

    async def prep_quotes_for_posting(
        self,
        interaction: discord.Interaction,
        keyword: str = "",
    ):
        quote_rowids = await db_helper.get_row_ids(
            template_info=envs.quote_db_schema, guild_id=interaction.guild.id
        )
        # List based on keyword
        if keyword:
            logger.debug("Using keyword")
            quote_in = await db_helper.get_imgs_with_quote(
                envs.quote_content_db_schema,
                like=[
                    ("quote_content.author_backup", keyword, "OR"),
                    ("quote_content.content_text", keyword),
                ],
                order_by=[("quote.rowid", "ASC")],
                guild_id=interaction.guild.id,
            )
            return quote_in
        # List all quotes
        else:
            if len(quote_rowids) == 0:
                return []
            else:
                logger.debug("List all quotes")
                confirm_buttons = ConfirmButtons(
                    yes_label=I18N.t("common.literal_yes_no.lit_yes"),
                    no_label=I18N.t("common.literal_yes_no.lit_no"),
                )
                await interaction.followup.send(
                    "This will post all {} quotes. Are you sure about this?".format(
                        len(quote_rowids)
                    ),
                    view=confirm_buttons,
                    ephemeral=True,
                )
                await confirm_buttons.wait()
                btn_values = [ch.value for ch in confirm_buttons.children]
                logger.debug(f"btn_values is {btn_values}")
                if True in btn_values:
                    quote_in = await db_helper.get_imgs_with_quote(
                        envs.quote_content_db_schema,
                        order_by=[("quote.rowid", "ASC")],
                        guild_id=interaction.guild.id,
                    )
                    return quote_in
                if False in btn_values:
                    return False

    @commands.is_owner()
    @group.command(
        name="list", description=locale_str(I18N.t("quote.commands.list.cmd"))
    )
    async def quote_list(
        self,
        interaction: discord.Interaction,
        keyword: str = "",
        public: typing.Literal[
            I18N.t("common.literal_yes_no.lit_yes"),
            I18N.t("common.literal_yes_no.lit_no"),
        ] = I18N.t("common.literal_yes_no.lit_no"),
    ):

        if public == I18N.t("common.literal_yes_no.lit_yes"):
            _ephemeral = False
        else:
            _ephemeral = True
        await interaction.response.defer(ephemeral=_ephemeral)
        quote_in = await self.prep_quotes_for_posting(
            interaction=interaction, keyword=keyword
        )
        if quote_in is None:
            await interaction.followup.send(
                I18N.t("quote.commands.list.msg_nonexisting_quote"),
                ephemeral=_ephemeral,
            )
            return
        elif quote_in is False:
            await interaction.followup.send(
                I18N.t("quote.commands.list.msg_listing_cancelled"),
                ephemeral=_ephemeral,
            )
            return
        elif len(quote_in) == 0:
            await interaction.followup.send(
                I18N.t("quote.common.quote_db_empty"),
                ephemeral=_ephemeral,
            )
            return
        paginated = []
        msg = ""
        trigger_pagination = False
        quote_last_key = next(reversed(quote_in))
        for quote in quote_in:
            logger.debug(f"trigger_pagination is {trigger_pagination}")
            quote_dt = await get_dt(format="datetime", dt=quote["datetime"])
            # Get max len of author
            author_max_len = 0
            for comment in quote["comments"]:
                if len(quote["comments"][comment]["author_backup"]) > author_max_len:
                    author_max_len = len(quote["comments"][comment]["author_backup"])
            quote_channel = ""
            quote_channel_object = get(
                interaction.guild.text_channels, id=int(quote["channel_id"])
            )
            if quote_channel_object is None:
                quote_channel = quote["channel_backup"]
            else:
                quote_channel = quote_channel_object.name
            msg_in = "`# {} - #{}, {}`\n\n".format(
                quote["rowid"], quote_channel, quote_dt
            )
            for _comment_id in quote["comments"]:
                comment = quote["comments"][_comment_id]
                _author = comment["author_backup"].ljust(author_max_len, " ")
                msg_in += "`{}: {}`".format(_author, comment["content"])
                if len(comment["imgs"]) > 0:
                    logger.debug(f"trigger_pagination is {trigger_pagination}")
                    trigger_pagination = True
                    img_list = []
                    for _img_id in comment["imgs"]:
                        img = comment["imgs"][_img_id]
                        img_object = convert_b64_to_img_in_mem(str(img))
                        img_list.append(img_object)
                    await interaction.followup.send(
                        msg_in, files=img_list, ephemeral=_ephemeral
                    )
                    msg_in = ""
                    trigger_pagination = False
                else:
                    if _comment_id != list(quote["comments"])[-1]:
                        msg_in += "\n"
            if len(msg_in) > 0:
                await interaction.followup.send(msg_in, ephemeral=_ephemeral)
                msg_in = ""
            logger.debug(f"trigger_pagination is {trigger_pagination}")
            if len(msg) + len(msg_in) > 1900 or trigger_pagination:
                logger.debug("paginating after quote_last_key")
                paginated.append(msg)
                msg = ""
            if not trigger_pagination and len(msg) > 0:
                msg += "\n\n"
                msg += msg_in
                if quote == quote_last_key and msg != "":
                    logger.debug("paginating after quote_last_key")
                    paginated.append(msg)
            trigger_pagination = False
            logger.debug(f"trigger_pagination is {trigger_pagination}")
        logger.debug(f"paginated: {paginated}")
        if len(paginated) > 0:
            for page in paginated:
                await interaction.followup.send(str(page), ephemeral=_ephemeral)
        return

    @commands.is_owner()
    @settings_group.command(
        name="list", description=locale_str(I18N.t("common.settings.list_settings"))
    )
    async def list_settings(self, interaction: discord.Interaction):
        """
        List the available settings for this cog
        """
        await interaction.response.defer(ephemeral=True)
        settings_in_db = await db_helper.get_output(
            template_info=envs.quote_db_settings_schema,
            select=("setting", "value"),
            guild_id=interaction.guild.id,
        )
        for setting in enumerate(settings_in_db):
            object = None
            if re.match(r"\d{19,22}", setting[1]["value"]):
                object = discord_commands.get_user_channel_role_id(
                    interaction.guild, setting[1]["value"]
                )
                if object is not None:
                    settings_in_db[setting[0]]["value"] = f"{object.name} ({object.id})"
        headers_settings = {
            "setting": I18N.t("common.settings.setting"),
            "value": I18N.t("common.settings.value"),
        }
        out = "## {}\n```{}```".format(
            I18N.t("stats.commands.list.stats_msg_out.sub_settings"),
            tabulate(settings_in_db, headers=headers_settings),
        )
        await interaction.followup.send(content=out, ephemeral=True)

    @commands.is_owner()
    @discord.app_commands.autocomplete(name_of_setting=settings_db_autocomplete)
    @settings_group.command(
        name="change", description=locale_str(I18N.t("common.settings.change_settings"))
    )
    @describe(
        name_of_setting=I18N.t("common.settings.name_of_setting"),
        value_in=I18N.t("common.settings.value_in"),
    )
    async def change_setting(
        self, interaction: discord.Interaction, name_of_setting: str, value_in: str
    ):
        """
        Change a setting for this cog

        Parameters
        ------------
        name_of_setting: str
            The names of the role to change (default: None)
        value_in: str/role
            The value of the settings (default: None)
        """
        await interaction.response.defer(ephemeral=True)
        settings_in_db = await db_helper.get_output(
            template_info=envs.quote_db_settings_schema,
            select=("setting", "value"),
            guild_id=interaction.guild.id,
        )
        settings_from_db = {}
        for setting in settings_in_db:
            settings_from_db[setting["setting"]] = setting["value"]
        logger.debug(f"settings_from_db:\n{pformat(settings_from_db)}")
        settings_type = envs.quote_db_settings_schema["type_checking"]
        setting_type = settings_type[name_of_setting]
        if setting_type == "bool":
            try:
                value_in = eval(str(value_in).capitalize())
            except NameError as _error:
                logger.error(f"Invalid input for `value_in`: {_error}")
                await interaction.followup.send(I18N.t("stats.setting_input_reply"))
                return
        if setting_type == "role_id":
            value_obj = discord_commands.get_user_channel_role_name(
                interaction.guild, value_in
            )
            value_in = value_obj.id
            setting_type = "int"
        if name_of_setting == "autopost_time":
            # Stored as HH:MM:SS - task_autopost polls every 5 minutes and
            # checks each guild's own stored time, so there is no shared
            # loop interval to update here anymore.
            time_out = datetime.strptime(value_in, "%H:%M").astimezone().time()
            await db_helper.update_fields(
                template_info=envs.quote_db_settings_schema,
                where=[("setting", name_of_setting)],
                updates=[("value", str(time_out))],
                guild_id=interaction.guild.id,
            )
        logger.debug(f"`value_in` is {value_in} ({type(value_in)})")
        logger.debug(
            f"`settings_type` is {settings_type[name_of_setting]} "
            f"({type(settings_type[name_of_setting])})"
        )
        if type(value_in) is eval(setting_type) and name_of_setting != "autopost_time":
            await db_helper.update_fields(
                template_info=envs.quote_db_settings_schema,
                where=[("setting", name_of_setting)],
                updates=[("value", value_in)],
                guild_id=interaction.guild.id,
            )
        await interaction.followup.send(
            content=I18N.t("quote.commands.settings.change_confirmed"), ephemeral=True
        )
        return

    @commands.is_owner()
    @discord.app_commands.autocomplete(setting_in=env_settings_autocomplete)
    @settings_group.command(
        name="add", description=locale_str(I18N.t("common.settings.add_setting"))
    )
    @describe(
        setting_in=I18N.t("common.settings.setting"),
        value_in=I18N.t("common.settings.value"),
    )
    async def add_setting(
        self, interaction: discord.Interaction, setting_in: str, value_in: str
    ):
        """
        Add a setting for this cog
        """
        await interaction.response.defer(ephemeral=True)
        settings_in_db = await db_helper.get_output(
            template_info=envs.quote_db_settings_schema,
            select=("setting", "value"),
            guild_id=interaction.guild.id,
        )
        settings_db_json = file_io.make_db_output_to_json(
            ["setting", "value"], settings_in_db
        )
        settings_types = envs.quote_db_settings_schema["type_checking"]
        logger.debug("settings_db_json is `{}`".format(settings_db_json))
        logger.debug(f"Value is {value_in}")
        if value_in.lower() in ["true", "false"]:
            value_in = value_in.capitalize()
            value_in_check = type(
                eval("{}({})".format(settings_types[setting_in], value_in))
            )
        elif setting_in == "channel":
            _guild = interaction.guild
            channel_object = get(_guild.text_channels, name=str(value_in))
            if channel_object is None:
                overwrites = {
                    _guild.default_role: discord.PermissionOverwrite(
                        send_messages=False,
                        read_messages=True,
                        send_tts_messages=False,
                        use_external_emojis=True,
                        send_messages_in_threads=False,
                        use_external_stickers=True,
                        create_polls=False,
                    ),
                    _guild.me: discord.PermissionOverwrite(
                        send_messages=True, read_messages=True
                    ),
                }
                channel_object = await discord_commands.create_missing_channel(
                    guild=_guild,
                    channel_name=value_in,
                    topic=I18N.t("quote.commands.settings.add_channel_topic"),
                    overwrites=overwrites,
                )
            value_in = channel_object.id
            value_in_check = type(value_in)
        else:
            value_in_check = type(value_in)
        logger.debug(f"Value type is {value_in_check}")
        logger.debug(f"Setting type is {eval(settings_types[setting_in])}")
        if settings_db_json is not None and setting_in in settings_db_json:
            await interaction.followup.send(
                content=I18N.t("quote.commands.settings.add_setting_exist"),
                ephemeral=True,
            )
            return
        try:
            if value_in_check is not eval(settings_types[setting_in]):
                await interaction.followup.send(
                    content=I18N.t(
                        "quote.commands.settings.add_type_incorrect",
                        value_in=value_in,
                        value_type=type(value_in),
                        value_type_check=settings_types[setting_in],
                    ),
                    ephemeral=True,
                )
                return
            elif value_in_check is eval(settings_types[setting_in]) and setting_in:
                await db_helper.insert_many_all(
                    template_info=envs.quote_db_settings_schema,
                    inserts=[(setting_in, value_in)],
                    guild_id=interaction.guild.id,
                )
                await interaction.followup.send(
                    content=I18N.t("quote.commands.settings.add_confirmed"),
                    ephemeral=True,
                )
                return
        except Exception as error:
            logger.error(f"Something went wrong: {error}")
            await interaction.followup.send(
                content=I18N.t("common.something_wrong", error=error), ephemeral=True
            )
            return

    @commands.is_owner()
    @discord.app_commands.autocomplete(setting_in=settings_db_autocomplete)
    @settings_group.command(
        name="remove", description=locale_str(I18N.t("common.settings.remove_setting"))
    )
    @describe(setting_in=I18N.t("common.settings.setting"))
    async def remove_setting(self, interaction: discord.Interaction, setting_in: str):
        """
        Remove a setting for this cog
        """
        await interaction.response.defer(ephemeral=True)
        try:
            await db_helper.del_row_by_AND_filter(
                template_info=envs.quote_db_settings_schema,
                where=[("setting", setting_in)],
                guild_id=interaction.guild.id,
            )
            await interaction.followup.send(
                content=I18N.t("quote.commands.settings.remove_confirmed"),
                ephemeral=True,
            )
        except Exception as error:
            logger.error(f"Error when removing setting: {error}")
            await interaction.followup.send(
                content=I18N.t("quote.commands.settings.remove_failed", error=error),
                ephemeral=True,
            )
        return

    @autopost_group.command(
        name="start",
        description=locale_str(I18N.t("quote.commands.autopost.start.cmd")),
    )
    async def autopost_quote_start(self, interaction: discord.Interaction):
        """
        Enable autopost for this guild. The background loop itself is
        shared, always-running infrastructure (like rss/youtube) - this
        just flips this guild's own `autopost_enabled` setting.
        """
        await interaction.response.defer(ephemeral=True)
        logger.info(f"Enabling autopost quote for `{interaction.guild.name}`")
        enabled = await db_helper.get_output(
            template_info=envs.quote_db_settings_schema,
            where=("setting", "autopost_enabled"),
            select=("value"),
            single=True,
            guild_id=interaction.guild.id,
        )
        if enabled and str(enabled.get("value")).lower() == "true":
            await interaction.followup.send(
                I18N.t("quote.commands.autopost.start.msg_already_running"),
            )
            return
        await db_helper.update_fields(
            template_info=envs.quote_db_settings_schema,
            where=[("setting", "autopost_enabled")],
            updates=[("value", "True")],
            guild_id=interaction.guild.id,
        )
        _autopost_time = await get_autopost_time(interaction.guild.id)
        await interaction.followup.send(
            I18N.t(
                "quote.commands.autopost.start.msg_confirm_ok",
                time="{}:{}".format(_autopost_time.group(1), _autopost_time.group(2)),
            )
        )

    @autopost_group.command(
        name="stop", description=locale_str(I18N.t("quote.commands.autopost.stop.cmd"))
    )
    async def autopost_quote_stop(self, interaction: discord.Interaction):
        "Disable autopost for this guild."
        await interaction.response.defer(ephemeral=True)
        logger.info(f"Disabling autopost quote for `{interaction.guild.name}`")
        enabled = await db_helper.get_output(
            template_info=envs.quote_db_settings_schema,
            where=("setting", "autopost_enabled"),
            select=("value"),
            single=True,
            guild_id=interaction.guild.id,
        )
        if not enabled or str(enabled.get("value")).lower() != "true":
            await interaction.followup.send(
                I18N.t("quote.commands.autopost.stop.msg_already_stopped")
            )
            return
        await db_helper.update_fields(
            template_info=envs.quote_db_settings_schema,
            where=[("setting", "autopost_enabled")],
            updates=[("value", "False")],
            guild_id=interaction.guild.id,
        )
        await interaction.followup.send(
            I18N.t("quote.commands.autopost.stop.msg_confirm_ok")
        )

    @commands.is_owner()
    @autopost_group.command(
        name="restart",
        description=locale_str(I18N.t("quote.commands.autopost.restart.cmd")),
    )
    async def autopost_quote_restart(self, interaction: discord.Interaction):
        """
        Restart the shared background autopost loop (all guilds). Useful
        for troubleshooting - not guild-scoped, since the loop itself is
        shared infrastructure.
        """
        await interaction.response.defer(ephemeral=True)
        logger.info("Autopost loop restarted")
        Quotes.task_autopost.restart()
        await interaction.followup.send(
            I18N.t(
                "quote.commands.autopost.restart.msg_confirm_ok",
                time=Quotes.task_autopost.next_iteration.astimezone(),
            )
        )

    @tasks.loop(minutes=5)
    async def task_autopost():
        """
        Shared, always-running loop (like rss/youtube). Every 5 minutes,
        checks each approved guild's own `autopost_enabled`/`autopost_time`
        settings and posts a quote if this tick falls in that guild's
        target 5-minute window, in that guild's own timezone.
        """
        approved_guilds = await db_helper.get_output(
            envs.guilds_db_schema, where=("status", "approved")
        )
        for guild_row in approved_guilds:
            guild = config.bot.get_guild(int(guild_row["guild_id"]))
            if guild is None:
                continue
            async with db_helper.guild_locale_context(guild.id):
                settings_in_db = await db_helper.get_output(
                    template_info=envs.quote_db_settings_schema,
                    select=("setting", "value"),
                    guild_id=guild.id,
                )
                settings_db_json = file_io.make_db_output_to_json(
                    ["setting", "value"], settings_in_db
                )
                if str(settings_db_json.get("autopost_enabled", "False")).lower() != (
                    "true"
                ):
                    continue
                if settings_db_json.get("channel") is None:
                    logger.debug(f"No autopost channel set for `{guild.name}`")
                    continue
                autopost_time_str = settings_db_json.get("autopost_time") or "12:00:00"
                try:
                    target = datetime.strptime(autopost_time_str, "%H:%M:%S").time()
                except ValueError:
                    logger.error(
                        f"Invalid `autopost_time` for `{guild.name}`: "
                        f"{autopost_time_str}"
                    )
                    continue
                now_dt = await get_dt(format="datetimeobject")
                now_minutes = now_dt.hour * 60 + now_dt.minute
                target_minutes = target.hour * 60 + target.minute
                # Post once per day, in the 5-minute window the target time
                # falls in (matches this loop's own polling interval)
                if (now_minutes - target_minutes) % (24 * 60) >= 5:
                    continue
                channel = settings_db_json["channel"]
                logger.info(f"Running autopost task for `{guild.name}`")
                # Create the channel if it does not exist
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(
                        send_messages=False,
                        read_messages=True,
                        send_tts_messages=False,
                        use_external_emojis=True,
                        send_messages_in_threads=False,
                        use_external_stickers=True,
                        create_polls=False,
                    ),
                    guild.me: discord.PermissionOverwrite(
                        send_messages=True, read_messages=True
                    ),
                }
                await discord_commands.create_missing_channel(
                    guild=guild,
                    channel_id=channel,
                    channel_name="quotes",
                    topic="Posting quotes",
                    overwrites=overwrites,
                )
                # Load quote from database
                # If in testmode, get the same quote every time
                rand_quote = await get_random_quote(guild.id, testmode=args.testmode)
                logger.debug(f"rand_quote is `{rand_quote}`")
                if rand_quote is None or len(rand_quote) <= 0:
                    logger.debug(
                        f"No quotes in db for `{guild.name}`, disabling autopost"
                    )
                    await db_helper.update_fields(
                        template_info=envs.quote_db_settings_schema,
                        where=[("setting", "autopost_enabled")],
                        updates=[("value", "False")],
                        guild_id=guild.id,
                    )
                    await discord_commands.log_to_bot_channel(
                        guild,
                        I18N.t("quote.commands.autopost.errors.no_quotes_stop_task"),
                    )
                    continue
                logger.debug("Got quote, posting it")
                rand_quote = rand_quote[0]
                logger.debug(f"rand_quote: {rand_quote}")
                autopost_settings = {"prefix": "", "tag_role": ""}
                if settings_db_json.get("autopost_prefix"):
                    autopost_settings["prefix"] = settings_db_json["autopost_prefix"]
                if settings_db_json.get("autopost_tag_role") and re.match(
                    r"\d{19,22}", settings_db_json["autopost_tag_role"]
                ):
                    _role = guild.get_role(int(settings_db_json["autopost_tag_role"]))
                    if _role is not None:
                        autopost_settings["tag_role"] = _role.id
                await post_random_quote(
                    guild=guild, autopost=autopost_settings, channel=channel
                )
        return

    @task_autopost.before_loop
    async def before_task_autopost():
        "#autodoc skip#"
        logger.debug("`task_autopost` waiting for bot to be ready...")
        await config.bot.wait_until_ready()


def get_imgs_to_db_format(msg: discord.Message):
    imgs_out = []
    if len(msg.attachments) > 0:
        att_counter = 0
        for att in msg.attachments:
            if att.url is not None and att.url != "":
                if att.filename.split(".")[-1] in ["jpg", "png", "gif"]:
                    logger.debug(f"Found attachment: {att.url}")
                    att_counter += 1
                    base_img = convert_img_to_b64(att.url)
                    imgs_out.append((str(msg.id), att_counter, base_img))
        return imgs_out
    else:
        return None


def convert_img_to_b64(image_url: str) -> str | None:
    """
    Converts an image from a url to base64-string
    """
    try:
        # Get image from url
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()

        # Validate image
        image_data = BytesIO(response.content)
        with Image.open(image_data) as img:
            img.verify()

        # Convert image to base64
        image_data.seek(0)
        base64_str = base64.b64encode(response.content).decode("utf-8")
        return base64_str

    except requests.exceptions.RequestException as e:
        logger.error(f"Could not fetch URL: {e}")
    except (IOError, SyntaxError) as e:
        logger.error(f"The URL does not giva a valid image: {e}")
    except Exception as e:
        logger.error(f"Unknown error: {e}")

    return None


def convert_b64_to_img_in_mem(b64string: str):
    """
    Converts a base64-string to image file
    """
    try:
        image_data = base64.b64decode(b64string)
        with BytesIO(image_data) as image_binary:
            discord_file = discord.File(fp=image_binary, filename="image.png")
            return discord_file
    except (binascii.Error, ValueError) as e:
        logger.error(f"Invalid Base64 string: {e}")
    except (IOError, SyntaxError) as e:
        logger.error(f"Data is not a valid image: {e}")
    except Exception as e:
        logger.error(f"Unknown error: {e}")
    return None


@commands.is_owner()
@config.bot.tree.context_menu(
    name=locale_str(I18N.t("quote.context_menu.add_quote.name"))
)
async def quote_add(interaction: discord.Interaction, message: discord.Message):
    "Add a quote"
    channel_out = interaction.channel
    msgs = []
    msg_defaults = []
    logger.debug("Getting msg history")
    async for msg in channel_out.history(limit=100):
        logger.debug(f"msg.id ({msg.id}) vs message.id ({message.id})")
        if int(msg.id) == int(message.id):
            main_msg = msg
            msg_defaults.append(main_msg.id)
            break
        else:
            main_msg = None
    if not main_msg:
        logger.debug("Got no main_msg")
        return
    msgs_before = channel_out.history(limit=12, before=main_msg)
    async for _msg in msgs_before:
        msgs.append(_msg)
    msgs.reverse()
    msgs.append(main_msg)
    msgs_after = channel_out.history(limit=12, after=main_msg)
    logger.debug(f"msgs is {msgs}")
    logger.debug(f"msg_defaults is {msg_defaults}")
    async for _msg in msgs_after:
        msgs.append(_msg)
    q_row_ids = len(
        await db_helper.get_row_ids(
            template_info=envs.quote_db_schema,
            sort=True,
            guild_id=interaction.guild.id,
        )
    )
    addquote_view = ModalQuoteAdd(
        title_in="Legg til sitat",
        msgs_in=msgs,
        defaults=msg_defaults,
        row_ids=q_row_ids,
    )
    await interaction.response.send_modal(addquote_view)
    await addquote_view.wait()
    # Get quotes and add to db
    quote_msgs_out = addquote_view.msgs_out
    quotes_out = []
    for quote in quote_msgs_out:
        quote_object = await discord_commands.get_message_obj(
            guild=interaction.guild, msg_id=quote, channel_id=interaction.channel.id
        )
        quotes_out.append(quote_object)
    # Add the quote
    _uuid = str(uuid.uuid4())
    quote_to_db = []
    imgs_to_db = []
    quote_insert_order = 0
    for _q in quotes_out:
        content = _q.content
        quote_to_db.append(
            (
                _uuid,
                _q.id,
                _q.author.id,
                _q.author.name,
                content,
                quote_insert_order,
            )
        )
        quote_insert_order += 1
        imgs_in = get_imgs_to_db_format(_q)
        if imgs_in:
            imgs_to_db += imgs_in
    await db_helper.insert_many_all(
        template_info=envs.quote_db_schema,
        inserts=[
            (
                _uuid,
                int(interaction.channel.id),
                str(interaction.channel.name),
                main_msg.created_at,
            )
        ],
        guild_id=interaction.guild.id,
    )
    await db_helper.insert_many_all(
        template_info=envs.quote_content_db_schema,
        inserts=quote_to_db,
        guild_id=interaction.guild.id,
    )
    if len(imgs_to_db) > 0:
        await db_helper.insert_many_all(
            template_info=envs.quote_img_db_schema,
            inserts=imgs_to_db,
            guild_id=interaction.guild.id,
        )
    return


async def ensure_guild_quote_tables(guild):
    """
    Prep this guild's quote tables, and fix up any legacy channel-name
    data. Safe to call repeatedly (idempotent).
    #autodoc skip#
    """
    await db_helper.prep_table(table_in=envs.quote_db_schema, guild_id=guild.id)
    await db_helper.prep_table(table_in=envs.quote_db_log_schema, guild_id=guild.id)
    await db_helper.prep_table(
        table_in=envs.quote_db_settings_schema,
        inserts=envs.quote_db_settings_schema["inserts"],
        guild_id=guild.id,
    )
    await db_helper.prep_table(table_in=envs.quote_content_db_schema, guild_id=guild.id)
    await db_helper.prep_table(table_in=envs.quote_img_db_schema, guild_id=guild.id)

    # Change channel name to id
    await db_helper.db_single_channel_name_to_id(
        template_info=envs.quote_db_settings_schema,
        channel_row="setting",
        channel_col="value",
        guild=guild,
    )


async def setup(bot):
    cog_name = "quote"
    logger.info(envs.COG_STARTING.format(cog_name))
    logger.debug("Checking db")

    approved_guilds = await db_helper.get_output(
        envs.guilds_db_schema, where=("status", "approved")
    )
    for guild_row in approved_guilds:
        guild = config.bot.get_guild(int(guild_row["guild_id"]))
        if guild is None:
            continue
        await ensure_guild_quote_tables(guild)

    logger.debug("Registering cog to bot")
    await bot.add_cog(Quotes(bot))
    logger.info(envs.COG_STARTED.format(cog_name))

    task_list = await db_helper.get_output(
        template_info=envs.tasks_db_schema,
        select=("task", "status"),
        where=("cog", "quotes"),
    )

    _tasks = ["autopost"]
    inserts = []
    for task in _tasks:
        if task not in [_["task"] for _ in task_list]:
            inserts.append(("quotes", task, "stopped"))
    if len(inserts) > 0:
        await db_helper.insert_many_all(
            template_info=envs.tasks_db_schema, inserts=inserts
        )
    for task in task_list:
        if task["task"] == "autopost":
            if task["status"] == "started":
                logger.debug(
                    "`{}` is set as `{}`, starting...".format(
                        task["task"], task["status"]
                    )
                )
                Quotes.task_autopost.start()
            elif task["status"] == "stopped":
                logger.debug("`{}` is set as `{}`".format(task["task"], task["status"]))
                Quotes.task_autopost.cancel()
