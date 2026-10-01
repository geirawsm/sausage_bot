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
import json
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


async def resolve_autopost_channel(guild: discord.Guild, channel_value):
    """
    Turn a guild's stored `channel` setting into a usable text channel id.

    `/quote settings add|change channel` stores a channel *id*, but the
    settings table used to be seeded with the channel *name* `quotes`, and
    a stored id can point at a channel that has since been deleted. Both
    went unguarded into `int()` - which raised and took the whole shared
    autopost loop down with it - or into `post_to_channel()`, which quietly
    posted into nothing. Resolve it here instead: create the channel when
    it is missing, and write the resolved id back so the next tick is a
    plain lookup.

    Returns None when the channel could neither be found nor created.
    """
    return await resolve_setting_channel(
        guild,
        setting_name="channel",
        channel_value=channel_value,
        default_name="quotes",
        topic=I18N.t("quote.commands.settings.add_channel_topic"),
    )


async def resolve_setting_channel(
    guild: discord.Guild, setting_name, channel_value, default_name, topic
):
    """
    Turn a channel setting (`channel` or `suggest_channel`) into a usable
    text channel id, creating `default_name` when it is missing and
    writing the resolved id back to `setting_name`.

    Returns None when the channel could neither be found nor created.
    """
    if str(channel_value).isdigit():
        channel_object = get(guild.text_channels, id=int(channel_value))
        if channel_object is not None:
            return channel_object.id
        logger.info(
            f"Quote channel `{channel_value}` no longer exists in "
            f"`{guild.name}`, resolving it by name instead"
        )
        channel_name = default_name
    else:
        # An unset setting, or the old name-based default
        channel_name = str(channel_value) if channel_value else default_name
    channel_object = get(guild.text_channels, name=channel_name)
    if channel_object is None:
        try:
            # `create_missing_channel` locks the channel down itself, there
            # is no `overwrites` to pass in
            channel_object = await discord_commands.create_missing_channel(
                guild=guild,
                channel_name=channel_name,
                topic=topic,
            )
        except discord.DiscordException as error:
            logger.error(
                f"Could not create channel `{channel_name}` in `{guild.name}`: {error}"
            )
            channel_object = None
    if channel_object is None:
        await discord_commands.log_to_bot_channel(
            guild, I18N.t("quote.commands.autopost.errors.channel_error")
        )
        return None
    await db_helper.update_fields(
        template_info=envs.quote_db_settings_schema,
        where=[("setting", setting_name)],
        updates=[("value", channel_object.id)],
        guild_id=guild.id,
    )
    return channel_object.id


async def autopost_for_guild(guild: discord.Guild) -> None:
    """
    Run one autopost tick for a single guild: check that guild's own
    `autopost_time` window and, if this tick falls inside it, resolve the
    guild's quote channel and post a random quote there. Called once per
    approved, opted-in guild by `Quotes.task_autopost`.
    """
    async with db_helper.guild_locale_context(guild.id):
        settings_in_db = await db_helper.get_output(
            template_info=envs.quote_db_settings_schema,
            select=("setting", "value"),
            guild_id=guild.id,
        )
        settings_db_json = file_io.make_db_output_to_json(
            ["setting", "value"], settings_in_db
        )
        autopost_time_str = settings_db_json.get("autopost_time") or "12:00:00"
        try:
            target = datetime.strptime(autopost_time_str, "%H:%M:%S").time()
        except ValueError:
            logger.error(
                f"Invalid `autopost_time` for `{guild.name}`: {autopost_time_str}"
            )
            return
        now_dt = await get_dt(format="datetimeobject")
        now_minutes = now_dt.hour * 60 + now_dt.minute
        target_minutes = target.hour * 60 + target.minute
        # Post once per day, in the 5-minute window the target time
        # falls in (matches this loop's own polling interval)
        if (now_minutes - target_minutes) % (24 * 60) >= 5:
            return
        logger.info(f"Running autopost task for `{guild.name}`")
        # A guild with nothing to post should not have a channel created
        # for it either, so check the quotes first. Count the row ids
        # rather than drawing a quote: `get_random_quote` empties the log
        # table once the rotation is exhausted, and `post_random_quote`
        # draws its own quote anyway - drawing one here just to test for
        # emptiness perturbed the no-repeat rotation.
        quote_ids = await db_helper.get_row_ids(envs.quote_db_schema, guild_id=guild.id)
        if quote_ids is None or len(quote_ids) == 0:
            logger.debug(f"No quotes in db for `{guild.name}`, disabling autopost")
            await db_helper.update_fields(
                template_info=envs.tasks_db_schema,
                where=[("cog", "quotes"), ("task", "autopost")],
                updates=("status", "stopped"),
                guild_id=guild.id,
            )
            await discord_commands.log_to_bot_channel(
                guild,
                I18N.t("quote.commands.autopost.errors.no_quotes_stop_task"),
            )
            return
        channel = await resolve_autopost_channel(guild, settings_db_json.get("channel"))
        if channel is None:
            logger.error(f"No usable autopost channel for `{guild.name}`")
            return
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


class EitherOrButtons(discord.ui.View):
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
        confirm_msg: str = None,
    ) -> None:
        super().__init__(title=title_in)

        self.msgs_in = msgs_in
        self.defaults = defaults
        self.msgs_out = []
        self.row_ids = row_ids
        # Overrides the "quote saved" reply, e.g. for suggestions that are
        # not saved until a moderator approves them
        self.confirm_msg = confirm_msg
        logger.debug(f"self.msgs_in: {self.msgs_in}")
        logger.debug(f"self.defaults: {self.defaults}")

        self.quote_prep = self.prep_dropdown(msgs_in, defaults)
        logger.debug(
            f"self.quote_prep ({len(self.quote_prep)}: {str(self.quote_prep)[0:500]}"
        )
        self.quote_dropdown = discord.ui.Select(
            placeholder=I18N.t("quote.modals.add.dropdown_placeholder"),
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
            if self.confirm_msg:
                msg_out = self.confirm_msg
            elif self.row_ids == 0:
                msg_out = I18N.t("quote.modals.add.msg_confirm")
            else:
                msg_out = I18N.t(
                    "quote.modals.add.msg_confirm_number",
                    quote_number=self.row_ids + 1,
                )
            await interaction.response.send_message(msg_out, ephemeral=True)
        return

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.response.send_message(
            I18N.t("quote.modals.error", error=error), ephemeral=True
        )


def channel_setting_saver(setting_name: str):
    """
    `on_created` callback for `discord_commands.CreateChannelView`: store
    the new channel's id in the quote setting `setting_name`
    """

    async def _save(guild: discord.Guild, new_channel, source) -> str:
        await db_helper.update_fields(
            template_info=envs.quote_db_settings_schema,
            where=[("setting", setting_name)],
            updates=[("value", new_channel.id)],
            guild_id=guild.id,
        )
        return I18N.t(
            "quote.commands.settings.channel_created",
            channel=new_channel.mention,
            setting=setting_name,
        )

    return _save


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


def get_quote_channel_name(guild: discord.Guild, quote: dict) -> str:
    """
    Resolve a quote's channel to a printable name.

    Imported/legacy quotes can have an empty `channel_id` (they were
    never posted in a Discord channel in the first place), so fall back
    to `channel_backup` both when the id is missing and when it no longer
    resolves to a channel in this guild.
    """
    channel_id = quote.get("channel_id")
    if channel_id in [None, ""]:
        return quote["channel_backup"]
    channel_object = get(guild.text_channels, id=int(channel_id))
    if channel_object is None:
        return quote["channel_backup"]
    return channel_object.name


async def delete_quote_with_content(guild_id, uuid: str, rowid) -> None:
    """
    Delete a quote and everything hanging off it: its comments, their
    images, and its posting log rows.

    Deleting the `quote` row on its own left orphaned `quote_content` and
    `quote_img` rows behind - the images in particular, since a single
    base64 image is by far the largest thing this database stores - plus
    log rows that kept a no longer existing uuid excluded from random
    picks for good.
    """
    comment_rows = await db_helper.get_output(
        template_info=envs.quote_content_db_schema,
        select=("comment_id"),
        where=[("uuid", uuid)],
        guild_id=guild_id,
    )
    # Imported comments have no message id, and `quote_img` is keyed by
    # message id alone, so they cannot have images to clean up
    comment_ids = [
        row["comment_id"]
        for row in comment_rows or []
        if row["comment_id"] not in [None, ""]
    ]
    logger.debug(f"Deleting quote `{uuid}` with comment ids: {comment_ids}")
    if len(comment_ids) > 0:
        await db_helper.del_row_by_OR_filter(
            template_info=envs.quote_img_db_schema,
            where=[("comment_id", c_id) for c_id in comment_ids],
            guild_id=guild_id,
        )
    await db_helper.del_row_by_AND_filter(
        template_info=envs.quote_content_db_schema,
        where=[("uuid", uuid)],
        guild_id=guild_id,
    )
    await db_helper.del_row_by_AND_filter(
        template_info=envs.quote_db_log_schema,
        where=[("uuid", uuid)],
        guild_id=guild_id,
    )
    await db_helper.del_row_id(envs.quote_db_schema, rowid, guild_id=guild_id)


async def get_random_quote(guild_id, testmode=False):
    """
    Return rowid for random quote
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
                I18N.t("quote.common.quote_db_empty"), ephemeral=_ephemeral
            )
        # Both branches are done here - continuing would index into the
        # empty `random_quote_number` below
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
        quote_channel = get_quote_channel_name(guild, quote)
        msg_in = ""
        if len(autopost) > 0 and autopost.get("prefix"):
            logger.debug("Adding prefix to msg_in")
            msg_in += "## {}\n".format(autopost["prefix"])
        # An autopost without a prefix set gets the same header as a
        # manually posted quote - it must never be left unassigned
        msg_in += "`# {} - #{}, {}`\n\n".format(quote["rowid"], quote_channel, quote_dt)
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
        quote_channel = get_quote_channel_name(interaction.guild, quote)
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
        # TODO: ephemeral funker ikke på denne? Må testes
        # await interaction.response.defer(ephemeral=_ephemeral)
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

    @discord_commands.is_owner_or_manage_guild()
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
        channel_out = None
        if quote_from_db["channel_id"] not in [None, ""]:
            channel_out = interaction.guild.get_channel(
                int(quote_from_db["channel_id"])
            )
        msg_defaults = [msg_id for msg_id in quote_from_db["comments"]]
        # Editing works by re-reading the messages the quote was built
        # from, so it needs both a readable channel and a real Discord
        # message id per comment. Imported quotes have neither (their
        # comments are keyed by `content_order` instead - see
        # `db_helper.get_imgs_with_quote()`).
        if channel_out is None or not all(
            isinstance(msg_id, int) for msg_id in msg_defaults
        ):
            logger.debug(
                "Quote `{}` has no channel/message ids to edit from".format(quote_in)
            )
            await interaction.response.send_message(
                I18N.t("quote.commands.edit.msg_not_editable", quote_in=quote_in),
                ephemeral=True,
            )
            return
        msgs = []
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
            title_in=I18N.t("quote.modals.edit.modal_title"),
            msgs_in=msgs,
            defaults=msg_defaults,
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

    @discord_commands.is_owner_or_manage_guild()
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
        confirm_buttons = EitherOrButtons(
            yes_label=I18N.t("common.literal_yes_no.lit_yes"),
            no_label=I18N.t("common.literal_yes_no.lit_no"),
        )
        paginated = []
        msg = ""
        trigger_pagination = False
        quote_dt = await get_dt(format="datetime", dt=quote["datetime"])
        quote_channel = get_quote_channel_name(interaction.guild, quote)
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
        confirm_buttons = EitherOrButtons(
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
                I18N.t("quote.commands.delete.msg_confirm_not_delete"),
                ephemeral=True,
            )
            return
        if True in btn_values:
            # Remove the quote
            await delete_quote_with_content(
                guild_id=interaction.guild.id,
                uuid=quote["uuid"],
                rowid=quote["rowid"],
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

    @discord_commands.is_owner_or_manage_guild()
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
                confirm_buttons = EitherOrButtons(
                    yes_label=I18N.t("common.literal_yes_no.lit_yes"),
                    no_label=I18N.t("common.literal_yes_no.lit_no"),
                )
                await interaction.followup.send(
                    I18N.t(
                        "quote.commands.list.confirm_post_all",
                        count=len(quote_rowids),
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

    @discord_commands.is_owner_or_manage_guild()
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
            quote_channel = get_quote_channel_name(interaction.guild, quote)
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

    @discord_commands.is_owner_or_manage_guild()
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
            as_settings_json=True,
        )
        channel_obj = discord_commands.get_user_channel_role_id(
            interaction.guild, settings_in_db["channel"]
        )
        if channel_obj is not None:
            settings_in_db["channel"] = f"{channel_obj.name} ({channel_obj.id})"
        else:
            logger.error("Channel in quote settings is not a Discord id")
            await discord_commands.log_to_bot_channel(
                guild=interaction.guild,
                # TODO: i18n
                content_in='Channel "{}" in quote settings is not a Discord id'.format(
                    settings_in_db["channel"]
                ),
            )
            return
        role_obj = discord_commands.get_user_channel_role_id(
            interaction.guild, settings_in_db["autopost_tag_role"]
        )
        if role_obj is not None:
            settings_in_db["autopost_tag_role"] = f"{role_obj.name} ({role_obj.id})"
        else:
            logger.error("autopost_tag_tole in quote settings is not a Discord id")
            await discord_commands.log_to_bot_channel(
                guild=interaction.guild,
                # TODO: i18n
                content_in='autopost_tag_role "{}" in quote settings is not a Discord id'.format(
                    settings_in_db["autopost_tag_role"]
                ),
            )
            return
        headers_settings = {
            "setting": I18N.t("common.settings.setting"),
            "value": I18N.t("common.settings.value"),
        }
        settings_out = [[item, settings_in_db[item]] for item in settings_in_db]
        out = "## {}\n```{}```".format(
            I18N.t("stats.commands.list.stats_msg_out.sub_settings"),
            tabulate(settings_out, headers=headers_settings),
        )
        await interaction.followup.send(content=out, ephemeral=True)

    @discord_commands.is_owner_or_manage_guild()
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
            if str(value_in).strip().lower() not in ["true", "false"]:
                logger.error(f"Invalid input for `value_in`: {value_in}")
                await interaction.followup.send(I18N.t("stats.setting_input_reply"))
                return
            value_in = str(value_in).strip().lower() == "true"
        elif name_of_setting in ["channel", "suggest_channel"]:
            # Channel settings hold a channel *id*, but a slash command
            # always hands us a string. Resolve names, mentions and raw ids
            # to an id here - before the generic `int` branch, which would
            # otherwise reject a channel name outright.
            channel_in = str(value_in).strip()
            channel_mention = re.fullmatch(r"<#(\d{17,22})>", channel_in)
            if channel_mention:
                channel_in = channel_mention.group(1)
            if channel_in.isdigit():
                channel_object = get(
                    interaction.guild.text_channels, id=int(channel_in)
                )
            else:
                channel_object = get(
                    interaction.guild.text_channels, name=channel_in.lstrip("#")
                )
            if channel_object is None and not channel_in.isdigit():
                # A name that does not exist yet - offer to create it, the
                # same way `/bot_channel` does. The view's buttons store the
                # setting once the channel exists.
                channel_name = channel_in.lstrip("#")
                await interaction.followup.send(
                    content=I18N.t(
                        "quote.commands.settings.channel_not_exist",
                        channel=channel_name,
                    ),
                    view=discord_commands.CreateChannelView(
                        channel_name,
                        on_created=channel_setting_saver(name_of_setting),
                        modal_title=I18N.t(
                            "quote.commands.settings.channel_modal_title"
                        ),
                        modal_name_label=I18N.t(
                            "quote.commands.settings.channel_name_label"
                        ),
                    ),
                    ephemeral=True,
                )
                return
            if channel_object is None:
                logger.error(
                    "Could not find channel `{}` in `{}`".format(
                        value_in, interaction.guild.name
                    )
                )
                await interaction.followup.send(
                    content=I18N.t("common.error.channel_not_found", channel=value_in),
                    ephemeral=True,
                )
                return
            value_in = channel_object.id
        elif setting_type == "int":
            try:
                value_in = int(value_in)
            except ValueError:
                logger.error(f"Invalid input for `value_in`: {value_in}")
                await interaction.followup.send(
                    content=I18N.t(
                        "quote.commands.settings.change_type_incorrect",
                        value_in=value_in,
                        value_type=type(value_in).__name__,
                        value_type_check=setting_type,
                    ),
                    ephemeral=True,
                )
                return
        elif setting_type == "role_id":
            value_in = int(re.fullmatch(r"<@&(\d+)>", value_in).group(1))
            setting_type = "int"
        elif name_of_setting == "autopost_time":
            # Stored as HH:MM:SS - task_autopost polls every 5 minutes and
            # checks each guild's own stored time, so there is no shared
            # loop interval to update here anymore.
            try:
                value_in = str(datetime.strptime(value_in, "%H:%M").astimezone().time())
            except ValueError:
                logger.error(f"Invalid input for `value_in`: {value_in}")
                await interaction.followup.send(
                    content=I18N.t(
                        "quote.commands.settings.change_type_incorrect",
                        value_in=value_in,
                        value_type=type(value_in).__name__,
                        value_type_check="HH:MM",
                    ),
                    ephemeral=True,
                )
                return
        logger.debug(f"`value_in` is {value_in} ({type(value_in)})")
        logger.debug(f"`setting_type` is {setting_type}")
        if type(value_in) is not eval(setting_type):
            logger.error(
                "`value_in` ({}) is not of type `{}`".format(value_in, setting_type)
            )
            await interaction.followup.send(
                content=I18N.t(
                    "quote.commands.settings.change_type_incorrect",
                    value_in=value_in,
                    value_type=type(value_in).__name__,
                    value_type_check=setting_type,
                ),
                ephemeral=True,
            )
            return
        if setting_type == "bool":
            # Store as "True"/"False" like the defaults - sqlite would turn
            # a Python bool into "1"/"0" in this TEXT column
            value_in = str(value_in)
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

    @discord_commands.is_owner_or_manage_guild()
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
        elif setting_in in ["channel", "suggest_channel"]:
            _guild = interaction.guild
            channel_object = get(_guild.text_channels, name=str(value_in))
            if channel_object is None:
                # `create_missing_channel` locks the channel down itself,
                # there is no `overwrites` to pass in
                channel_object = await discord_commands.create_missing_channel(
                    guild=_guild,
                    channel_name=value_in,
                    topic=(
                        I18N.t("quote.commands.settings.add_channel_topic")
                        if setting_in == "channel"
                        else I18N.t("quote.context_menu.suggest_quote.channel_topic")
                    ),
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

    @discord_commands.is_owner_or_manage_guild()
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

    @discord_commands.is_owner_or_manage_guild()
    @autopost_group.command(
        name="start",
        description=locale_str(I18N.t("quote.commands.autopost.start.cmd")),
    )
    async def autopost_quote_start(self, interaction: discord.Interaction):
        """
        Enable autopost for this guild. The background loop itself is
        shared, always-running infrastructure (like rss/youtube) - this
        just flips this guild's own `tasks_db_schema` row.
        """
        await interaction.response.defer(ephemeral=True)
        logger.info(f"Enabling autopost quote for `{interaction.guild.name}`")
        task_status = await db_helper.get_output(
            template_info=envs.tasks_db_schema,
            where=[("cog", "quotes"), ("task", "autopost")],
            select=("status"),
            single=True,
            guild_id=interaction.guild.id,
        )
        if task_status.get("status") == "started":
            await interaction.followup.send(
                I18N.t("quote.commands.autopost.start.msg_already_running"),
            )
            return
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[("cog", "quotes"), ("task", "autopost")],
            updates=("status", "started"),
            guild_id=interaction.guild.id,
        )
        _autopost_time = await get_autopost_time(interaction.guild.id)
        await interaction.followup.send(
            I18N.t(
                "quote.commands.autopost.start.msg_confirm_ok",
                time="{}:{}".format(_autopost_time.group(1), _autopost_time.group(2)),
            )
        )

    @discord_commands.is_owner_or_manage_guild()
    @autopost_group.command(
        name="stop", description=locale_str(I18N.t("quote.commands.autopost.stop.cmd"))
    )
    async def autopost_quote_stop(self, interaction: discord.Interaction):
        "Disable autopost for this guild."
        await interaction.response.defer(ephemeral=True)
        logger.info(f"Disabling autopost quote for `{interaction.guild.name}`")
        task_status = await db_helper.get_output(
            template_info=envs.tasks_db_schema,
            where=[("cog", "quotes"), ("task", "autopost")],
            select=("status"),
            single=True,
            guild_id=interaction.guild.id,
        )
        if task_status.get("status") != "started":
            await interaction.followup.send(
                I18N.t("quote.commands.autopost.stop.msg_already_stopped")
            )
            return
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[("cog", "quotes"), ("task", "autopost")],
            updates=("status", "stopped"),
            guild_id=interaction.guild.id,
        )
        await interaction.followup.send(
            I18N.t("quote.commands.autopost.stop.msg_confirm_ok")
        )

    @discord_commands.is_owner()
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

    @tasks.loop(minutes=5, reconnect=True)
    async def task_autopost():
        """
        Shared, always-running loop (like rss/youtube). Every 5 minutes,
        checks each approved guild's own `tasks_db_schema` row (cog=
        "quotes", task="autopost") and, if enabled, hands that guild to
        `autopost_for_guild()`, which posts a quote if this tick falls in
        that guild's target 5-minute window, in that guild's own timezone.
        """
        approved_guilds = await db_helper.get_output(
            envs.guilds_db_schema, where=("status", "approved")
        )
        for guild_row in approved_guilds:
            guild = config.bot.get_guild(int(guild_row["guild_id"]))
            if guild is None:
                logger.debug(f"Guild `{guild_row['guild_id']}` not in cache, skipping")
                continue
            try:
                task_status = await db_helper.get_output(
                    template_info=envs.tasks_db_schema,
                    where=[("cog", "quotes"), ("task", "autopost")],
                    select=("status"),
                    single=True,
                    guild_id=guild.id,
                )
                # A guild approved after the bot started has no row yet -
                # a missing row counts as "stopped", not as a crash
                if not task_status or task_status.get("status") != "started":
                    continue
                await autopost_for_guild(guild)
            except Exception as error:
                # One guild used to take the whole loop with it: an
                # unhandled error here ended `task_autopost` for every
                # other guild until someone restarted the bot.
                logger.error(f"Autopost failed for `{guild.name}`: {error}")
                try:
                    async with db_helper.guild_locale_context(guild.id):
                        await discord_commands.log_to_bot_channel(
                            guild,
                            I18N.t(
                                "quote.commands.autopost.errors.guild_failed",
                                error=error,
                            ),
                        )
                except Exception as log_error:
                    logger.error(
                        f"Could not report the autopost error to "
                        f"`{guild.name}`: {log_error}"
                    )
        return

    @task_autopost.before_loop
    async def before_task_autopost():
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


@discord_commands.is_owner_or_manage_guild()
@config.bot.tree.context_menu(
    name=locale_str(I18N.t("quote.context_menu.add_quote.name"))
)
async def quote_add(interaction: discord.Interaction, message: discord.Message):
    "Add a quote"
    msgs = await collect_context_msgs(interaction.channel, message)
    q_row_ids = len(
        await db_helper.get_row_ids(
            template_info=envs.quote_db_schema,
            sort=True,
            guild_id=interaction.guild.id,
        )
    )
    addquote_view = ModalQuoteAdd(
        title_in=I18N.t("quote.modals.add.modal_title"),
        msgs_in=msgs,
        defaults=[message.id],
        row_ids=q_row_ids,
    )
    await interaction.response.send_modal(addquote_view)
    await addquote_view.wait()
    quotes_out = await get_selected_msgs(interaction, addquote_view.msgs_out)
    if len(quotes_out) == 0:
        # The modal timed out or was dismissed - do not save an empty quote
        return
    _uuid = str(uuid.uuid4())
    content_rows, img_rows = build_quote_rows(_uuid, quotes_out)
    await save_quote(
        guild_id=interaction.guild.id,
        quote_uuid=_uuid,
        channel_id=int(interaction.channel.id),
        channel_name=str(interaction.channel.name),
        created_at=message.created_at,
        content_rows=content_rows,
        img_rows=img_rows,
    )
    return


async def collect_context_msgs(
    channel: discord.abc.Messageable, message: discord.Message
) -> list[discord.Message]:
    "Get `message` with up to 12 messages before and after it, oldest first"
    msgs = []
    logger.debug("Getting msg history")
    async for _msg in channel.history(limit=12, before=message):
        msgs.append(_msg)
    msgs.reverse()
    msgs.append(message)
    async for _msg in channel.history(limit=12, after=message):
        msgs.append(_msg)
    logger.debug(f"msgs is {msgs}")
    return msgs


async def get_selected_msgs(
    interaction: discord.Interaction, msg_ids: list
) -> list[discord.Message]:
    "Fetch the messages picked in `ModalQuoteAdd`, skipping deleted ones"
    msgs_out = []
    for msg_id in msg_ids:
        msg_object = await discord_commands.get_message_obj(
            guild=interaction.guild, msg_id=msg_id, channel_id=interaction.channel.id
        )
        if msg_object is not None:
            msgs_out.append(msg_object)
    return msgs_out


def build_quote_rows(quote_uuid: str, msgs: list[discord.Message]) -> tuple:
    """
    Turn the selected messages into rows for `quote_content` and
    `quote_img`, in the order they were selected
    """
    content_rows = []
    img_rows = []
    for content_order, _q in enumerate(msgs):
        content_rows.append(
            (
                quote_uuid,
                _q.id,
                _q.author.id,
                _q.author.name,
                _q.content,
                content_order,
            )
        )
        imgs_in = get_imgs_to_db_format(_q)
        if imgs_in:
            img_rows += imgs_in
    return content_rows, img_rows


async def save_quote(
    guild_id,
    quote_uuid: str,
    channel_id: int,
    channel_name: str,
    created_at,
    content_rows: list,
    img_rows: list,
) -> None:
    "Insert a quote with its comments and images"
    await db_helper.insert_many_all(
        template_info=envs.quote_db_schema,
        inserts=[(quote_uuid, channel_id, channel_name, created_at)],
        guild_id=guild_id,
    )
    await db_helper.insert_many_all(
        template_info=envs.quote_content_db_schema,
        inserts=[tuple(row) for row in content_rows],
        guild_id=guild_id,
    )
    if len(img_rows) > 0:
        await db_helper.insert_many_all(
            template_info=envs.quote_img_db_schema,
            inserts=[tuple(row) for row in img_rows],
            guild_id=guild_id,
        )


async def get_quote_settings(guild_id) -> dict:
    "Get this guild's quote settings as `{setting: value}`"
    settings_in_db = await db_helper.get_output(
        template_info=envs.quote_db_settings_schema,
        select=("setting", "value"),
        guild_id=guild_id,
    )
    return file_io.make_db_output_to_json(["setting", "value"], settings_in_db) or {}


def is_suggest_enabled(settings: dict) -> bool:
    return str(settings.get("suggest_enabled")).strip().lower() in ["true", "1"]


async def can_review_suggestions(interaction: discord.Interaction) -> bool:
    "Same rule as `discord_commands.is_owner_or_manage_guild()`"
    if await interaction.client.is_owner(interaction.user):
        return True
    return interaction.user.guild_permissions.manage_guild


def format_suggestion(content_rows: list, channel_name: str, suggested_by: str) -> str:
    "Text for the review message posted in the suggest channel"
    author_max_len = max(len(str(row[3])) for row in content_rows)
    lines = [
        "`{}: {}`".format(str(row[3]).ljust(author_max_len, " "), row[4])
        for row in content_rows
    ]
    msg_out = "{}\n\n{}".format(
        I18N.t(
            "quote.context_menu.suggest_quote.review_header",
            user=suggested_by,
            channel=channel_name,
        ),
        "\n".join(lines),
    )
    # Leave room for the "approved by"/"denied by" line added later
    if len(msg_out) > 1800:
        msg_out = f"{msg_out[:1797]}..."
    return msg_out


class DynamicSuggestButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"quote\.suggest:(?P<action>approve|deny):(?P<suggest_uuid>[0-9a-f-]+)",
):
    """
    Approve/deny button on a suggested quote. A `DynamicItem` so the
    buttons keep working after the bot restarts - see `setup()`.
    """

    def __init__(self, action: str, suggest_uuid: str) -> None:
        self.action = action
        self.suggest_uuid = suggest_uuid
        if action == "approve":
            label = I18N.t("quote.context_menu.suggest_quote.btn_approve")
            style = discord.ButtonStyle.green
        else:
            label = I18N.t("quote.context_menu.suggest_quote.btn_deny")
            style = discord.ButtonStyle.red
        super().__init__(
            discord.ui.Button(
                label=label,
                style=style,
                custom_id=f"quote.suggest:{action}:{suggest_uuid}",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ):
        return cls(str(match["action"]), str(match["suggest_uuid"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await can_review_suggestions(interaction):
            await interaction.response.send_message(
                I18N.t("quote.context_menu.suggest_quote.no_permission"),
                ephemeral=True,
            )
            return
        status, quote_number = await handle_suggestion(
            interaction.guild.id, self.suggest_uuid, self.action
        )
        if status == "approved":
            status_line = I18N.t(
                "quote.context_menu.suggest_quote.approved_by",
                user=interaction.user.mention,
                quote_number=quote_number,
            )
        elif status == "denied":
            status_line = I18N.t(
                "quote.context_menu.suggest_quote.denied_by",
                user=interaction.user.mention,
            )
        else:
            await interaction.response.send_message(
                I18N.t("quote.context_menu.suggest_quote.already_handled"),
                ephemeral=True,
            )
            return
        await interaction.response.edit_message(
            content=f"{interaction.message.content}\n\n{status_line}", view=None
        )


async def handle_suggestion(guild_id, suggest_uuid: str, action: str) -> tuple:
    """
    Approve or deny a pending suggestion.

    Returns `(status, quote_number)`: status is `approved`, `denied`,
    `already_handled` or `missing`, and `quote_number` is the new quote's
    rowid when it was approved.
    """
    rows = await db_helper.get_output(
        template_info=envs.quote_suggest_db_schema,
        where=[("uuid", suggest_uuid)],
        guild_id=guild_id,
    )
    if not rows:
        logger.error(f"Could not find quote suggestion `{suggest_uuid}`")
        return "missing", None
    suggestion = rows[0]
    if suggestion["status"] != "pending":
        return "already_handled", None
    if action == "deny":
        await db_helper.update_fields(
            template_info=envs.quote_suggest_db_schema,
            where=[("uuid", suggest_uuid)],
            updates=[("status", "denied")],
            guild_id=guild_id,
        )
        return "denied", None
    # Mark it first, so a second click while saving finds it handled
    await db_helper.update_fields(
        template_info=envs.quote_suggest_db_schema,
        where=[("uuid", suggest_uuid)],
        updates=[("status", "approved")],
        guild_id=guild_id,
    )
    payload = json.loads(suggestion["payload"])
    await save_quote(
        guild_id=guild_id,
        quote_uuid=suggest_uuid,
        channel_id=suggestion["channel_id"],
        channel_name=suggestion["channel_backup"],
        created_at=suggestion["datetime"],
        content_rows=payload["content"],
        img_rows=payload["imgs"],
    )
    quote_rows = await db_helper.get_output(
        template_info=envs.quote_db_schema,
        select=("rowid", "uuid"),
        where=[("uuid", suggest_uuid)],
        guild_id=guild_id,
    )
    quote_number = quote_rows[0]["rowid"] if quote_rows else None
    return "approved", quote_number


async def post_suggestion(
    guild: discord.Guild,
    suggest_uuid: str,
    channel,
    created_at,
    suggested_by: discord.abc.User,
    content_rows: list,
    img_rows: list,
    suggest_channel_value,
):
    """
    Save a suggestion as pending and post it with approve/deny buttons in
    the guild's suggest channel. Returns the posted review message, or
    None if there was no usable suggest channel.
    """
    await db_helper.insert_many_all(
        template_info=envs.quote_suggest_db_schema,
        inserts=[
            (
                suggest_uuid,
                int(channel.id),
                str(channel.name),
                str(created_at),
                int(suggested_by.id),
                "pending",
                None,
                json.dumps({"content": content_rows, "imgs": img_rows}),
            )
        ],
        guild_id=guild.id,
    )
    review_channel_id = await resolve_setting_channel(
        guild,
        setting_name="suggest_channel",
        channel_value=suggest_channel_value,
        default_name="quote-suggest",
        topic=I18N.t("quote.context_menu.suggest_quote.channel_topic"),
    )
    if review_channel_id is None:
        logger.error(f"No usable quote suggest channel for `{guild.name}`")
        return None
    review_channel = guild.get_channel(review_channel_id)
    # Discord allows at most 10 files per message
    files_out = [convert_b64_to_img_in_mem(str(img[2])) for img in img_rows][:10]
    files_out = [_file for _file in files_out if _file is not None]
    view = discord.ui.View(timeout=None)
    view.add_item(DynamicSuggestButton("approve", suggest_uuid))
    view.add_item(DynamicSuggestButton("deny", suggest_uuid))
    review_msg = await review_channel.send(
        content=format_suggestion(content_rows, channel.name, suggested_by.mention),
        files=files_out,
        view=view,
    )
    await db_helper.update_fields(
        template_info=envs.quote_suggest_db_schema,
        where=[("uuid", suggest_uuid)],
        updates=[("review_msg_id", review_msg.id)],
        guild_id=guild.id,
    )
    return review_msg


@config.bot.tree.context_menu(
    name=locale_str(I18N.t("quote.context_menu.suggest_quote.name"))
)
async def quote_suggest(interaction: discord.Interaction, message: discord.Message):
    "Suggest a quote for a moderator to approve"
    settings = await get_quote_settings(interaction.guild.id)
    if not is_suggest_enabled(settings):
        await interaction.response.send_message(
            I18N.t("quote.context_menu.suggest_quote.disabled"), ephemeral=True
        )
        return
    msgs = await collect_context_msgs(interaction.channel, message)
    suggest_view = ModalQuoteAdd(
        title_in=I18N.t("quote.context_menu.suggest_quote.modal_title"),
        msgs_in=msgs,
        defaults=[message.id],
        confirm_msg=I18N.t("quote.context_menu.suggest_quote.msg_sent"),
    )
    await interaction.response.send_modal(suggest_view)
    await suggest_view.wait()
    quotes_out = await get_selected_msgs(interaction, suggest_view.msgs_out)
    if len(quotes_out) == 0:
        return
    _uuid = str(uuid.uuid4())
    content_rows, img_rows = build_quote_rows(_uuid, quotes_out)
    await post_suggestion(
        guild=interaction.guild,
        suggest_uuid=_uuid,
        channel=interaction.channel,
        created_at=message.created_at,
        suggested_by=interaction.user,
        content_rows=content_rows,
        img_rows=img_rows,
        suggest_channel_value=settings.get("suggest_channel"),
    )
    return


async def ensure_guild_quote_tables(guild):
    """
    Prep this guild's quote tables, and fix up any legacy channel-name
    data. Safe to call repeatedly (idempotent).
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
    await db_helper.prep_table(table_in=envs.quote_suggest_db_schema, guild_id=guild.id)


# Uniform name so a guild approved while the bot is running can get its
# tables prepped without a restart - see `util/cogs.py`'s
# `ensure_guild_tables_for_loaded_cogs()`
ensure_guild_tables = ensure_guild_quote_tables


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
        await db_helper.ensure_guild_tasks_rows(guild.id)

    logger.debug("Registering cog to bot")
    await bot.add_cog(Quotes(bot))
    # Approve/deny buttons on pending suggestions must survive a restart
    bot.add_dynamic_items(DynamicSuggestButton)
    logger.info(envs.COG_STARTED.format(cog_name))

    # Shared, always-running loop - each tick checks every guild's own
    # tasks_db_schema row to decide whether to process that guild.
    Quotes.task_autopost.start()


async def teardown(bot):
    Quotes.task_autopost.cancel()
