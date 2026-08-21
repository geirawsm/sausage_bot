#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
rss: Administer RSS-feeds that will autopost to a given channel
when published
"""

import discord
from discord.ext import commands, tasks
from discord.app_commands import locale_str, describe
from discord.utils import get
import typing
from time import sleep
import re
from pprint import pformat

from sausage_bot.util import config, envs, feeds_core, net_io
from sausage_bot.util import db_helper, discord_commands
from sausage_bot.util.i18n import I18N

logger = config.logger

# The `typing.Literal` choices for the list commands are evaluated once, at
# import time, and discord hands the picked *value* back untranslated -
# only the name shown in the client is localized. Compare against the same
# constants the Literal was built from, and not a fresh `I18N.t()` call in
# whatever locale the guild happens to use, or nothing ever matches.
LIST_TYPE_NORMAL = I18N.t("rss.commands.list.literal_type.normal")
LIST_TYPE_ADDED = I18N.t("rss.commands.list.literal_type.added")
LIST_TYPE_FILTER = I18N.t("rss.commands.list.literal_type.filter")


async def rss_feed_name_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[discord.app_commands.Choice[str]]:
    db_feeds = await db_helper.get_output(
        template_info=envs.rss_db_schema,
        select=("uuid", "feed_name", "url", "channel"),
        where=(("feed_type", "rss")),
        order_by=[("feed_name", "ASC")],
        guild_id=interaction.guild.id,
    )
    logger.debug(f"db_feeds:\n{pformat(db_feeds)}")
    feeds = db_feeds.copy()
    for feed in feeds:
        _counter = 87
        _counter -= len(str(feed["feed_name"]))
        _counter -= len(str(feed["channel"]))
        feed["length_counter"] = _counter
    return [
        discord.app_commands.Choice(
            name="{feed_name}: #{channel} ({url})".format(
                feed_name=feed["feed_name"],
                channel=feed["channel"],
                url=str(feed["url"]),
            )[0 : feed["length_counter"]],
            value=str(feed["feed_name"]),
        )
        for feed in feeds
        if current.lower()
        in "{}-{}-{}-{}".format(
            feed["uuid"], feed["feed_name"], feed["url"], feed["channel"]
        ).lower()
    ][:25]


async def podcast_name_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[discord.app_commands.Choice[str]]:
    db_feeds = await db_helper.get_output(
        template_info=envs.rss_db_schema,
        select=("uuid", "feed_name", "url", "channel"),
        where=(("feed_type", "podcast")),
        order_by=[("feed_name", "ASC")],
        guild_id=interaction.guild.id,
    )
    logger.debug(f"db_feeds:\n{pformat(db_feeds)}")
    feeds = db_feeds.copy()
    for feed in feeds:
        _counter = 87
        _counter -= len(str(feed["feed_name"]))
        _counter -= len(str(feed["channel"]))
        feed["length_counter"] = _counter
    return [
        discord.app_commands.Choice(
            name="{feed_name}: #{channel} ({url})".format(
                feed_name=feed["feed_name"],
                channel=feed["channel"],
                url=str(feed["url"]),
            )[0 : feed["length_counter"]],
            value=str(feed["feed_name"]),
        )
        for feed in feeds
        if current.lower()
        in "{}-{}-{}-{}".format(
            feed["uuid"], feed["feed_name"], feed["url"], feed["channel"]
        ).lower()
    ][:25]


async def feed_uuid_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[discord.app_commands.Choice[str]]:
    db_feeds = await db_helper.get_output(
        template_info=envs.rss_db_schema,
        select=("uuid", "feed_name", "url", "channel"),
        order_by=[("feed_name", "ASC")],
        guild_id=interaction.guild.id,
    )
    logger.debug(f"db_feeds:\n{pformat(db_feeds)}")
    feeds = db_feeds.copy()
    for feed in feeds:
        _counter = 87
        _counter -= len(str(feed["feed_name"]))
        _counter -= len(str(feed["channel"]))
        feed["length_counter"] = _counter
    return [
        discord.app_commands.Choice(
            name="{feed_name}: #{channel} ({url})".format(
                feed_name=feed["feed_name"],
                channel=feed["channel"],
                url=str(feed["url"]),
            )[0 : feed["length_counter"]],
            value=str(feed["uuid"]),
        )
        for feed in feeds
        if current.lower()
        in "{}-{}-{}-{}".format(
            feed["uuid"], feed["feed_name"], feed["url"], feed["channel"]
        ).lower()
    ][:25]


async def rss_filter_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[discord.app_commands.Choice[str]]:
    db_filters = await db_helper.get_combined_output(
        template_info_1=envs.rss_db_schema,
        template_info_2=envs.rss_db_filter_schema,
        key="uuid",
        select=["feed_name", "allow_or_deny", "filter"],
        order_by=[("allow_or_deny", "ASC"), ("filter", "ASC")],
        guild_id=interaction.guild.id,
    )
    filters = []
    for filter in db_filters:
        filters.append((filter["uuid"], filter["allow_or_deny"], filter["filter"]))
    logger.debug(f"filters: {filters}")
    return [
        discord.app_commands.Choice(
            name="{} - {} - {}".format(
                filter["uuid"], filter["allow_or_deny"], filter["filter"]
            ),
            value=str(filter["filter"]),
        )
        for filter in filters
        if current.lower() in filter["filter"].lower()
    ][:25]


async def rss_settings_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[discord.app_commands.Choice[str]]:
    settings_in_db = await db_helper.get_output(
        template_info=envs.rss_db_settings_schema,
        select=("setting", "value"),
        guild_id=interaction.guild.id,
    )
    logger.debug(f"settings_in_db: {settings_in_db}")
    return [
        discord.app_commands.Choice(
            name="{}: {}".format(setting["setting"], setting["value"]),
            value=str(setting["setting"]),
        )
        for setting in settings_in_db
        if current.lower() in setting["setting"].lower()
    ][:25]


async def control_posting(feed_type, action, guild_id=None):
    """
    `action` is "start"/"stop": flip `guild_id`'s own `tasks_db_schema`
    row(s) for `feed_type` ("feeds"/"podcasts"/"ALL") - the shared
    background loops keep running and simply skip guilds whose row says
    "stopped" on their next tick.

    `action` is "restart": actually restarts the shared loop object(s)
    themselves, which affects every guild's processing, not just
    `guild_id` - see `feeds_posting_restart` (owner-only).
    """
    feed_type_in = []
    failed_list = []
    feed_statuses = []
    feed_types = ""
    actions = {
        "start": {"status_update": "started"},
        "stop": {"status_update": "stopped"},
        "restart": {"status_update": "restarted"},
    }
    if feed_type == "ALL":
        feed_type_in.append("feeds")
        feed_type_in.append("podcasts")
    else:
        feed_type_in.append(feed_type)
    for feed_type in feed_type_in:
        if action in actions:
            try:
                if action == "restart":
                    eval("RSSfeed.task_post_{}.restart()".format(feed_type))
                else:
                    await db_helper.update_fields(
                        template_info=envs.tasks_db_schema,
                        where=[
                            ("cog", "rss"),
                            ("task", "post_{}".format(feed_type)),
                        ],
                        updates=("status", actions[action]["status_update"]),
                        guild_id=guild_id,
                    )
                feed_statuses.append(
                    {"feed_type": feed_type, "status": actions[action]["status_update"]}
                )
            except RuntimeError as e:
                logger.error(
                    "Error when {}ing feed `{}`: {}".format(
                        actions[action]["status_update"], feed_type, e
                    )
                )
                failed_list.append(feed_type)
    if len(feed_statuses) > 0:
        for feed_type in feed_statuses:
            logger.info(
                "Task {}: {}".format(feed_type["feed_type"], feed_type["status"])
            )
        feed_types = ", ".join(feed_type["feed_type"] for feed_type in feed_statuses)
    if len(failed_list) > 0:
        failed_list_text = ", ".join(failed_list)
    _msg = ""
    if len(feed_types) > 0:
        _msg += I18N.t(f"rss.commands.{action}.msg_confirm_ok", feed_type=feed_types)
    if len(failed_list) > 0:
        _msg += I18N.t(
            f"rss.commands.{action}.msg_confirm_fail_suffix", feed_type=failed_list_text
        )
    if len(feed_types) == 0 and len(failed_list) > 0:
        _msg = I18N.t(f"rss.commands.{action}.msg_confirm_fail", feed_type=failed_list)
    return _msg


class RSSfeed(commands.Cog):
    """
    Administer RSS-feeds that will autopost to a given channel when published
    """

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    config.bot.add_dynamic_items(feeds_core.DynamicRatingSelect)

    rss_group = discord.app_commands.Group(
        name="rss", description=locale_str(I18N.t("rss.groups.rss"))
    )
    podcast_group = discord.app_commands.Group(
        name="podcast", description=locale_str(I18N.t("rss.groups.podcast"))
    )
    rss_filter_group = discord.app_commands.Group(
        name="filter",
        description=locale_str(I18N.t("rss.groups.filter")),
        parent=rss_group,
    )
    rss_posting_group = discord.app_commands.Group(
        name="posting",
        description=locale_str(I18N.t("rss.groups.posting")),
        parent=rss_group,
    )
    rss_settings_group = discord.app_commands.Group(
        name="settings",
        description=locale_str(I18N.t("rss.groups.settings")),
        parent=rss_group,
    )

    @discord_commands.is_owner_or_manage_guild()
    @rss_posting_group.command(
        name="start", description=locale_str(I18N.t("rss.commands.start.cmd"))
    )
    async def feeds_posting_start(
        self,
        interaction: discord.Interaction,
        feed_type: typing.Literal["feeds", "podcasts", "ALL"],
    ):
        await interaction.response.defer(ephemeral=True)
        msg = await control_posting(feed_type, "start", guild_id=interaction.guild.id)
        await interaction.followup.send(msg)

    @discord_commands.is_owner_or_manage_guild()
    @rss_posting_group.command(
        name="stop", description=locale_str(I18N.t("rss.commands.stop.cmd"))
    )
    async def feeds_posting_stop(
        self,
        interaction: discord.Interaction,
        feed_type: typing.Literal["feeds", "podcasts", "ALL"],
    ):
        await interaction.response.defer(ephemeral=True)
        msg = await control_posting(feed_type, "stop", guild_id=interaction.guild.id)
        await interaction.followup.send(msg)

    @discord_commands.is_owner()
    @rss_posting_group.command(
        name="restart", description=locale_str(I18N.t("rss.commands.restart.cmd"))
    )
    async def feeds_posting_restart(
        self,
        interaction: discord.Interaction,
        feed_type: typing.Literal["feeds", "podcasts", "ALL"],
    ):
        await interaction.response.defer(ephemeral=True)
        msg = await control_posting(feed_type, "restart", guild_id=interaction.guild.id)
        await interaction.followup.send(msg)

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(feed_name=rss_feed_name_autocomplete)
    @rss_group.command(
        name="add", description=locale_str(I18N.t("rss.commands.add.cmd"))
    )
    @describe(
        feed_name=I18N.t("rss.commands.add.desc.feed_name"),
        feed_link=I18N.t("rss.commands.add.desc.feed_link"),
        channel=I18N.t("rss.commands.add.desc.channel"),
    )
    async def rss_add(
        self,
        interaction: discord.Interaction,
        feed_name: str,
        feed_link: str,
        channel: discord.TextChannel,
    ):
        """Add a RSS feed"""
        await interaction.response.defer(ephemeral=True)
        AUTHOR = interaction.user.name
        # Verify that the url is a proper feed
        valid_feed = await feeds_core.check_feed_validity(
            feed_link, guild=interaction.guild
        )
        if not valid_feed:
            await interaction.followup.send(
                I18N.t("rss.commands.add.msg_feed_failed"), ephemeral=True
            )
            return
        logger.debug("Adding feed to db")
        await feeds_core.add_to_feed_db(
            "rss",
            str(feed_name),
            str(feed_link),
            channel.id,
            AUTHOR,
            guild_id=interaction.guild.id,
        )
        await discord_commands.log_to_bot_channel(
            interaction.guild,
            I18N.t(
                "rss.commands.add.log_feed_confirm",
                user_name=AUTHOR,
                feed_name=feed_name,
                channel_name=channel.name,
            ),
        )
        await interaction.followup.send(
            I18N.t(
                "rss.commands.add.msg_feed_confirm",
                feed_name=feed_name,
                channel_name=channel.name,
            ),
            ephemeral=True,
        )
        return

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(feed_name=rss_feed_name_autocomplete)
    @rss_group.command(
        name="remove", description=locale_str(I18N.t("rss.commands.remove.cmd"))
    )
    @describe(feed_name=I18N.t("rss.commands.remove.desc.feed_name"))
    async def rss_remove(self, interaction: discord.Interaction, feed_name: str):
        """Remove a RSS feed"""
        await interaction.response.defer()
        AUTHOR = interaction.user.name
        removal = await feeds_core.remove_feed_from_db(
            feed_type="rss", feed_name=feed_name, guild_id=interaction.guild.id
        )
        if removal:
            await discord_commands.log_to_bot_channel(
                interaction.guild,
                I18N.t(
                    "rss.commands.remove.log_feed_removed",
                    feed_name=feed_name,
                    user_name=AUTHOR,
                ),
            )
            await interaction.followup.send(
                I18N.t("rss.commands.remove.msg_feed_removed", feed_name=feed_name)
            )
        elif removal is False:
            # Couldn't remove the feed
            await interaction.followup.send(
                I18N.t(
                    "rss.commands.remove.msg_feed_remove_failed", feed_name=feed_name
                )
            )
            # Also log and send error to bot-channel
            await discord_commands.log_to_bot_channel(
                interaction.guild,
                I18N.t(
                    "rss.commands.remove.log_feed_remove_failed",
                    user_name=AUTHOR,
                    feed_name=feed_name,
                ),
            )
        return

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(feed_name=rss_feed_name_autocomplete)
    @rss_group.command(
        name="edit", description=locale_str(I18N.t("rss.commands.edit.cmd"))
    )
    @describe(
        feed_name=I18N.t("rss.commands.edit.desc.feed_name"),
        new_feed_name=I18N.t("rss.commands.edit.desc.new_feed_name"),
        channel=I18N.t("rss.commands.edit.desc.channel"),
        url=I18N.t("rss.commands.edit.desc.url"),
    )
    async def rss_edit(
        self,
        interaction: discord.Interaction,
        feed_name: str,
        new_feed_name: str = None,
        channel: discord.TextChannel = None,
        url: str = None,
    ):
        await interaction.response.defer()
        feed_info = await db_helper.get_output(
            template_info=envs.rss_db_schema,
            select=("feed_name", "channel", "url"),
            where=(("feed_name", feed_name)),
            guild_id=interaction.guild.id,
        )
        logger.debug(f"`feed_info` is {feed_info}")
        changes_out = I18N.t("rss.commands.edit.changes_out.msg", feed_name=feed_name)
        updates_in = []
        if new_feed_name:
            updates_in.append(("feed_name", new_feed_name))
            changes_out += "\n- {}: `{}` -> `{}`".format(
                I18N.t("rss.commands.edit.changes_out.feed_name"),
                feed_info[0]["feed_name"],
                new_feed_name,
            )
        if channel:
            updates_in.append(("channel", channel))
            changes_out += "\n- {}: `{}` -> `{}`".format(
                I18N.t("rss.commands.edit.changes_out.channel"),
                feed_info[0]["channel"],
                channel,
            )
        if url:
            updates_in.append(("url", url))
            changes_out += "\n- {}: `{}` -> `{}`".format(
                I18N.t("rss.commands.edit.changes_out.url"), feed_info[0]["url"], url
            )
        await db_helper.update_fields(
            template_info=envs.rss_db_schema,
            where=("feed_name", feed_name),
            updates=updates_in,
            guild_id=interaction.guild.id,
        )
        await interaction.followup.send(changes_out, ephemeral=True)
        return

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(feed_name=rss_feed_name_autocomplete)
    @rss_filter_group.command(
        name="add", description=locale_str(I18N.t("rss.commands.filter_add.cmd"))
    )
    @describe(
        feed_name=I18N.t("rss.commands.filter_add.desc.feed_name"),
        allow_deny=I18N.t("rss.commands.filter_add.desc.allow_deny"),
        filters_in=I18N.t("rss.commands.filter_add.desc.filters"),
    )
    async def rss_filter_add(
        self,
        interaction: discord.Interaction,
        feed_name: str,
        allow_deny: typing.Literal[
            I18N.t("common.literal_allow_deny.allow"),
            I18N.t("common.literal_allow_deny.deny"),
        ],
        filters_in: str,
    ):
        """
        Add filter for feed (deny/allow)
        """
        await interaction.response.defer(ephemeral=True)
        # Make sure that the filter input can be split
        _filters_in = re.split(envs.input_split_regex, filters_in)
        _uuid = await db_helper.get_output(
            template_info=envs.rss_db_schema,
            select=("uuid"),
            where=(("feed_name", feed_name)),
            single=True,
            guild_id=interaction.guild.id,
        )
        temp_inserts = []
        for _index, filter in enumerate(_filters_in):
            temp_inserts.append((_uuid, allow_deny, filter))
        adding_filter = await db_helper.insert_many_all(
            template_info=envs.rss_db_filter_schema,
            inserts=temp_inserts,
            guild_id=interaction.guild.id,
        )
        if adding_filter:
            msg_out = I18N.t(
                "rss.commands.filter_add.msg_confirm", allow_deny=allow_deny
            )
            for filter in _filters_in:
                msg_out += f"\n- {filter}"
            await interaction.followup.send(msg_out, ephemeral=True)
        else:
            await interaction.followup.send(
                I18N.t("rss.commands.filter_add.msg_error"), ephemeral=True
            )
        return

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(feed_name=rss_feed_name_autocomplete)
    @discord.app_commands.autocomplete(filter_in=rss_filter_autocomplete)
    @rss_filter_group.command(
        name="remove", description=locale_str(I18N.t("rss.commands.filter_remove.cmd"))
    )
    @describe(
        feed_name=I18N.t("rss.commands.filter_remove.desc.feed_name"),
        filter_in=I18N.t("rss.commands.filter_remove.desc.filter"),
    )
    async def rss_filter_remove(
        self, interaction: discord.Interaction, feed_name: str, filter_in: str
    ):
        """
        Remove filter for feed
        """
        await interaction.response.defer(ephemeral=True)
        _uuid = await db_helper.get_output(
            template_info=envs.rss_db_schema,
            select=("uuid"),
            where=(("feed_name", feed_name)),
            single=True,
            guild_id=interaction.guild.id,
        )
        removing_filter = await db_helper.del_row_by_AND_filter(
            template_info=envs.rss_db_filter_schema,
            where=(("uuid", _uuid), ("filter", filter_in)),
            guild_id=interaction.guild.id,
        )
        if removing_filter:
            await interaction.followup.send(
                I18N.t("rss.commands.filter_remove.msg_confirm", filter=filter_in),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                I18N.t("rss.commands.filter_remove.msg_error", filter=filter_in),
                ephemeral=True,
            )
        return

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(name_of_setting=rss_settings_autocomplete)
    @rss_settings_group.command(
        name="change", description=locale_str(I18N.t("rss.commands.setting.cmd"))
    )
    @describe(
        name_of_setting=I18N.t("rss.commands.setting.desc.name_of_setting"),
        value_in=I18N.t("rss.commands.setting.desc.value_in"),
    )
    async def rss_settings_change(
        self, interaction: discord.Interaction, name_of_setting: str, value_in: str
    ):
        """
        Change a setting for this cog
        """
        await interaction.response.defer(ephemeral=True)
        settings_in_db = await db_helper.get_output(
            template_info=envs.rss_db_settings_schema,
            select=("setting", "value", "value_check"),
            guild_id=interaction.guild.id,
        )
        for setting in settings_in_db:
            if setting["setting"] == name_of_setting:
                if setting["value_check"] == "bool":
                    try:
                        value_in = eval(str(value_in).capitalize())
                    except NameError as _error:
                        logger.error(f"Invalid input for `value_in`: {_error}")
                        await interaction.followup.send(
                            I18N.t(
                                "rss.commands.setting.value_in_input_invalid",
                                error=_error,
                            )
                        )
                        return
                logger.debug(
                    "`value_in` is {value_in} ({type_value_in})".format(
                        value_in=value_in, type_value_in=type(value_in)
                    )
                )
                logger.debug(
                    "`setting['value_check']` is {value_check} "
                    "({type_value_check})".format(
                        value_check=setting["value_check"],
                        type_value_check=type(setting["value_check"]),
                    )
                )
                if type(value_in) is eval(setting["value_check"]):
                    await db_helper.update_fields(
                        template_info=envs.rss_db_settings_schema,
                        where=[("setting", name_of_setting)],
                        updates=[("value", value_in)],
                        guild_id=interaction.guild.id,
                    )
                await interaction.followup.send(
                    I18N.t("rss.commands.setting.msg_confirm"), ephemeral=True
                )
                RSSfeed.task_post_feeds.restart()
                break
        return

    @discord_commands.is_owner_or_manage_guild()
    @rss_group.command(
        name="list", description=locale_str(I18N.t("rss.commands.list.cmd"))
    )
    @describe(list_type=I18N.t("rss.commands.list.desc.list_type"))
    async def rss_list(
        self,
        interaction: discord.Interaction,
        list_type: typing.Literal[
            LIST_TYPE_NORMAL,
            LIST_TYPE_ADDED,
            LIST_TYPE_FILTER,
        ],
    ):
        """
        List all active rss feeds
        """
        await interaction.response.defer()
        if list_type == LIST_TYPE_ADDED:
            formatted_list = await feeds_core.get_feed_list(
                guild=interaction.guild,
                db_in=envs.rss_db_schema,
                # `get_feed_list` expects the untranslated list type, so
                # don't pass the localized literal along
                list_type="added",
                feed_type="rss",
            )
        elif list_type == LIST_TYPE_FILTER:
            formatted_list = await feeds_core.get_feed_list(
                guild=interaction.guild,
                db_in=envs.rss_db_schema,
                db_filter_in=envs.rss_db_filter_schema,
                list_type="filter",
                feed_type="rss",
            )
        else:
            formatted_list = await feeds_core.get_feed_list(
                guild=interaction.guild, db_in=envs.rss_db_schema, feed_type="rss"
            )
        if formatted_list is not None:
            page_counter = 0
            for page in formatted_list:
                page_counter += 1
                logger.debug(f"Sending page ({page_counter} / {len(formatted_list)})")
                await interaction.followup.send(f"```{page}```")
                sleep(1)
        else:
            await interaction.followup.send(
                I18N.t("rss.commands.list.msg_error"), ephemeral=True
            )
        return

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(feed_name=feed_uuid_autocomplete)
    @rss_group.command(
        name="test_feed", description=locale_str(I18N.t("rss.commands.test.cmd"))
    )
    @describe(
        feed_name=I18N.t("rss.commands.test.desc.feed_name"),
    )
    async def rss_test_feed(
        self,
        interaction: discord.Interaction,
        feed_name: str,
        public: typing.Literal[
            I18N.t("common.literal_yes_no.lit_yes"),
            I18N.t("common.literal_yes_no.lit_no"),
        ] = None,
    ):
        """
        Test an added feed manually. Creates a report that is posted
        after the test is done.
        """

        def enclose_status_out(status_out):
            return "```{}```".format(status_out)

        if public == I18N.t("common.literal_yes_no.lit_yes"):
            _ephemeral = False
        else:
            _ephemeral = True
        status_out = ""
        await interaction.response.defer(ephemeral=_ephemeral)
        feed = await db_helper.get_output(
            template_info=envs.rss_db_schema,
            order_by=[("feed_name", "DESC")],
            where=[("uuid", feed_name)],
            not_like=[("feed_type", "podcast")],
            single=True,
            guild_id=interaction.guild.id,
        )
        status_out += "💭 Checking URL: {}".format(feed["url"])
        status_msg = await interaction.followup.send(
            enclose_status_out(status_out), ephemeral=_ephemeral
        )
        # Reading url, what code?
        req = await net_io.get_link(feed["url"], status_out=True)
        logger.debug("Got this response from url:\n{pformat(req)}")
        if req["status"] != 200:
            status_out += "\n❌ Got http status {}".format(req["status"])
            if req["content"]:
                status_out += ":\n\t{}".format(req["content"])
            status_msg = await interaction.followup.edit_message(
                message_id=status_msg.id, content=enclose_status_out(status_out)
            )
            return
        else:
            status_out += "\n✅ Got HTTP status {}".format(req["status"])
            status_msg = await interaction.followup.edit_message(
                message_id=status_msg.id, content=enclose_status_out(status_out)
            )
        rss_items = await feeds_core.get_items_from_rss(
            req=req["content"],
            url=feed["url"],
        )
        if rss_items is None or len(rss_items) <= 0:
            status_out += "\n❌ Unable to get feed items"
            status_msg = await interaction.followup.edit_message(
                message_id=status_msg.id, content=enclose_status_out(status_out)
            )
            return
        else:
            rss_items[0].pop("type")
            status_out += "\n✅ Got {} feed items:".format(len(rss_items))
            for item in rss_items[0]:
                status_out += "\n\t- {}: {}".format(item, rss_items[0][item])
            status_msg = await interaction.followup.edit_message(
                message_id=status_msg.id, content=enclose_status_out(status_out)
            )
        # Get link hash
        _hash = await net_io.get_page_hash(rss_items[0]["link"])
        if _hash is None:
            status_out += f'\n❌ Could not make hash, got "{_hash}"'
            status_msg = await interaction.followup.edit_message(
                message_id=status_msg.id, content=enclose_status_out(status_out)
            )
            return
        # Get log
        _FEED_DB = await db_helper.get_output(
            template_info=envs.rss_db_log_schema,
            select=("url", "hash"),
            guild_id=interaction.guild.id,
        )
        FEED_HASH = [item["hash"] for item in _FEED_DB]
        if _hash in FEED_HASH:
            status_out += f"\n✅ Found hash in log ({_hash})"
        else:
            status_out += f"\n❌ Did not find hash in log ({_hash})"
        status_msg = await interaction.followup.edit_message(
            message_id=status_msg.id, content=enclose_status_out(status_out)
        )
        FEED_LOG = [item["url"] for item in _FEED_DB]
        if feed["url"] in FEED_LOG:
            status_out += "\n✅ Found link in log"
        else:
            status_out += "\n❌ Did not find link in log"
        status_msg = await interaction.followup.edit_message(
            message_id=status_msg.id, content=enclose_status_out(status_out)
        )
        return

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(podcast_name=podcast_name_autocomplete)
    @podcast_group.command(
        name="add", description=locale_str(I18N.t("rss.commands.add.cmd"))
    )
    @describe(
        podcast_name=I18N.t("rss.commands.add.desc.feed_name"),
        feed_link=I18N.t("rss.commands.add.desc.feed_link"),
        channel=I18N.t("rss.commands.add.desc.channel"),
    )
    async def podcast_add(
        self,
        interaction: discord.Interaction,
        podcast_name: str,
        feed_link: str,
        channel: discord.TextChannel,
    ):
        """Add a Podcast"""
        await interaction.response.defer(ephemeral=True)
        AUTHOR = interaction.user.name
        # Verify that the url is a proper feed
        valid_feed = await feeds_core.check_feed_validity(
            feed_link, guild=interaction.guild
        )
        if not valid_feed:
            await interaction.followup.send(
                I18N.t("rss.commands.add.msg_feed_failed"), ephemeral=True
            )
            return
        logger.debug("Adding feed to db")
        feed_type = "podcast"
        if net_io.url_hostname_matches(
            feed_link, "acast.com"
        ) and not net_io.url_hostname_matches(feed_link, "feeds.acast.com"):
            logger.debug("Found Acast, but not the rss feed. Changing url")
            base_feed_url = "https://feeds.acast.com/public/shows/{}"
            feed_link = re.sub(r"/episodes.*", "", feed_link)
            pod_url_name = re.search(r".*/(.*)", feed_link).group(1)
            feed_link = base_feed_url.format(pod_url_name)
        await feeds_core.add_to_feed_db(
            feed_type,
            str(podcast_name),
            str(feed_link),
            channel.id,
            AUTHOR,
            guild_id=interaction.guild.id,
        )
        await discord_commands.log_to_bot_channel(
            interaction.guild,
            I18N.t(
                "rss.commands.add.log_feed_confirm",
                user_name=AUTHOR,
                feed_name=podcast_name,
                channel_name=channel.name,
            ),
        )
        await interaction.followup.send(
            I18N.t(
                "rss.commands.add.msg_feed_confirm",
                feed_name=podcast_name,
                channel_name=channel.name,
            ),
            ephemeral=True,
        )
        return

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(podcast_name=podcast_name_autocomplete)
    @podcast_group.command(
        name="remove", description=locale_str(I18N.t("rss.commands.remove.cmd"))
    )
    @describe(podcast_name=I18N.t("rss.commands.remove.desc.feed_name"))
    async def podcast_remove(self, interaction: discord.Interaction, podcast_name: str):
        """Remove a podcast"""
        await interaction.response.defer()
        AUTHOR = interaction.user.name
        removal = await feeds_core.remove_feed_from_db(
            feed_type="podcast",
            feed_name=podcast_name,
            guild_id=interaction.guild.id,
        )
        if removal:
            await discord_commands.log_to_bot_channel(
                interaction.guild,
                I18N.t(
                    "rss.commands.remove.log_feed_removed",
                    feed_name=podcast_name,
                    user_name=AUTHOR,
                ),
            )
            await interaction.followup.send(
                I18N.t("rss.commands.remove.msg_feed_removed", feed_name=podcast_name)
            )
        elif removal is False:
            # Couldn't remove the feed
            await interaction.followup.send(
                I18N.t(
                    "rss.commands.remove.msg_feed_remove_failed", feed_name=podcast_name
                )
            )
            # Also log and send error to bot-channel
            await discord_commands.log_to_bot_channel(
                interaction.guild,
                I18N.t(
                    "rss.commands.remove.log_feed_remove_failed",
                    user_name=AUTHOR,
                    feed_name=podcast_name,
                ),
            )
        return

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(podcast_name=podcast_name_autocomplete)
    @podcast_group.command(
        name="edit", description=locale_str(I18N.t("rss.commands.edit.cmd"))
    )
    @describe(
        podcast_name=I18N.t("rss.commands.edit.desc.feed_name"),
        new_podcast_name=I18N.t("rss.commands.edit.desc.new_feed_name"),
        channel=I18N.t("rss.commands.edit.desc.channel"),
        url=I18N.t("rss.commands.edit.desc.url"),
    )
    async def pocast_edit(
        self,
        interaction: discord.Interaction,
        podcast_name: str,
        new_podcast_name: str = None,
        channel: discord.TextChannel = None,
        url: str = None,
    ):
        await interaction.response.defer()
        feed_info = await db_helper.get_output(
            template_info=envs.rss_db_schema,
            select=("feed_name", "channel", "url"),
            where=(("feed_name", podcast_name)),
            guild_id=interaction.guild.id,
        )
        logger.debug(f"`feed_info` is {feed_info}")
        changes_out = I18N.t(
            "rss.commands.edit.changes_out.msg", feed_name=podcast_name
        )
        updates_in = []
        if new_podcast_name:
            updates_in.append(("feed_name", new_podcast_name))
            changes_out += "\n- {}: `{}` -> `{}`".format(
                I18N.t("rss.commands.edit.changes_out.feed_name"),
                feed_info[0]["feed_name"],
                new_podcast_name,
            )
        if channel:
            updates_in.append(("channel", channel))
            changes_out += "\n- {}: `{}` -> `{}`".format(
                I18N.t("rss.commands.edit.changes_out.channel"),
                feed_info[0]["channel"],
                channel,
            )
        if url:
            updates_in.append(("url", url))
            changes_out += "\n- {}: `{}` -> `{}`".format(
                I18N.t("rss.commands.edit.changes_out.url"), feed_info[0]["url"], url
            )
        await db_helper.update_fields(
            template_info=envs.rss_db_schema,
            where=("feed_name", podcast_name),
            updates=updates_in,
            guild_id=interaction.guild.id,
        )
        await interaction.followup.send(changes_out, ephemeral=True)
        return

    @discord_commands.is_owner_or_manage_guild()
    @podcast_group.command(
        name="list", description=locale_str(I18N.t("rss.commands.list.cmd"))
    )
    @describe(list_type=I18N.t("rss.commands.list.desc.list_type"))
    async def podcast_list(
        self,
        interaction: discord.Interaction,
        list_type: typing.Literal[
            LIST_TYPE_NORMAL,
            LIST_TYPE_ADDED,
            LIST_TYPE_FILTER,
        ],
    ):
        """
        List all active podcast feeds
        """
        await interaction.response.defer()
        if list_type == LIST_TYPE_ADDED:
            formatted_list = await feeds_core.get_feed_list(
                guild=interaction.guild,
                db_in=envs.rss_db_schema,
                # `get_feed_list` expects the untranslated list type, so
                # don't pass the localized literal along
                list_type="added",
                feed_type="podcast",
            )
        elif list_type == LIST_TYPE_FILTER:
            formatted_list = await feeds_core.get_feed_list(
                guild=interaction.guild,
                db_in=envs.rss_db_schema,
                db_filter_in=envs.rss_db_filter_schema,
                list_type="filter",
                feed_type="podcast",
            )
        else:
            formatted_list = await feeds_core.get_feed_list(
                guild=interaction.guild, db_in=envs.rss_db_schema, feed_type="podcast"
            )
        if formatted_list is not None:
            page_counter = 0
            for page in formatted_list:
                page_counter += 1
                logger.debug(f"Sending page ({page_counter} / {len(formatted_list)})")
                await interaction.followup.send(f"```{page}```")
                sleep(1)
        else:
            await interaction.followup.send(
                I18N.t("rss.commands.list.msg_error"), ephemeral=True
            )
        return

    # Tasks
    @tasks.loop(minutes=config.RSS_LOOP, reconnect=True)
    async def task_post_feeds():
        logger.info("Starting `post_feeds`")
        approved_guilds = await db_helper.get_output(
            envs.guilds_db_schema, where=("status", "approved")
        )
        for guild_row in approved_guilds:
            guild = config.bot.get_guild(int(guild_row["guild_id"]))
            if guild is None:
                logger.debug(f"Guild `{guild_row['guild_id']}` not in cache, skipping")
                continue
            task_status = await db_helper.get_output(
                template_info=envs.tasks_db_schema,
                where=[("cog", "rss"), ("task", "post_feeds")],
                select=("status"),
                single=True,
                guild_id=guild.id,
            )
            if task_status.get("status") != "started":
                logger.debug(f"`post_feeds` is not enabled for `{guild.name}`, skipping")
                continue
            async with db_helper.guild_locale_context(guild.id):
                # Start processing feeds
                feeds = await db_helper.get_output(
                    template_info=envs.rss_db_schema,
                    order_by=[("feed_name", "DESC")],
                    where=[
                        ("status_url", envs.FEEDS_URL_SUCCESS),
                        ("status_channel", envs.CHANNEL_STATUS_SUCCESS),
                    ],
                    not_like=[("feed_type", "podcast")],
                    guild_id=guild.id,
                )
                if len(feeds) == 0:
                    logger.debug(f"No feeds found for `{guild.name}`")
                    continue
                logger.debug(f"Got these feeds for `{guild.name}`:")
                for feed in feeds:
                    logger.debug("- {}".format(feed["feed_name"]))
                # Start processing per feed settings
                for feed in feeds:
                    UUID = feed["uuid"]
                    FEED_NAME = feed["feed_name"]
                    CHANNEL = feed["channel"]
                    channel_obj = guild.get_channel(int(CHANNEL))
                    logger.debug(f"Found channel `{channel_obj.name}` in `{FEED_NAME}`")
                    FEED_POSTS = await feeds_core.get_feed_links(
                        feed_type="rss", feed_info=feed, guild_id=guild.id
                    )
                    if FEED_POSTS is None or isinstance(FEED_POSTS, int):
                        logger.info(f"Feed {FEED_NAME} returned {FEED_POSTS}")
                        await db_helper.update_fields(
                            template_info=envs.rss_db_schema,
                            where=("uuid", UUID),
                            updates=("status_url", envs.FEEDS_URL_ERROR),
                            guild_id=guild.id,
                        )
                        await discord_commands.log_to_bot_channel(
                            guild,
                            I18N.t(
                                "rss.tasks.feed_posts_is_none",
                                feed_name=FEED_NAME,
                                return_value=str(FEED_POSTS),
                            ),
                        )
                    else:
                        logger.debug(
                            "Got {} items for `FEED_POSTS`: {}".format(
                                len(FEED_POSTS),
                                ", ".join([pod_ep["title"] for pod_ep in FEED_POSTS]),
                            )
                        )
                        await feeds_core.process_links_for_posting_or_editing(
                            feed_name=FEED_NAME,
                            feed_type="rss",
                            uuid=UUID,
                            FEED_POSTS=FEED_POSTS,
                            CHANNEL=CHANNEL,
                            guild=guild,
                        )
        logger.info("Done with posting")
        return

    @task_post_feeds.before_loop
    async def before_post_new_feeds():
        "#autodoc skip#"
        logger.debug("`post_feeds` waiting for bot to be ready...")
        await config.bot.wait_until_ready()

    @tasks.loop(minutes=config.POD_LOOP, reconnect=True)
    async def task_post_podcasts():
        logger.info("Starting `post_podcasts`")
        approved_guilds = await db_helper.get_output(
            envs.guilds_db_schema, where=("status", "approved")
        )
        for guild_row in approved_guilds:
            guild = config.bot.get_guild(int(guild_row["guild_id"]))
            if guild is None:
                logger.debug(f"Guild `{guild_row['guild_id']}` not in cache, skipping")
                continue
            task_status = await db_helper.get_output(
                template_info=envs.tasks_db_schema,
                where=[("cog", "rss"), ("task", "post_podcasts")],
                select=("status"),
                single=True,
                guild_id=guild.id,
            )
            if task_status.get("status") != "started":
                logger.debug(
                    f"`post_podcasts` is not enabled for `{guild.name}`, skipping"
                )
                continue
            async with db_helper.guild_locale_context(guild.id):
                # Check for new episodes of Spotify podcasts
                spotify_check = await net_io.check_for_new_spotify_podcast_episodes(
                    guild
                )
                logger.debug("spotify_check is {}".format(spotify_check))
                # Get feeds of other podcasts
                pod_check = await net_io.check_other_podcast_episodes(guild)
                logger.debug("pod_check is {}".format(pod_check))
                logger.debug(f"Got these feeds for `{guild.name}`:")
                if len(spotify_check) > 0:
                    for feed in spotify_check:
                        logger.debug("  Spotify:")
                        logger.debug("- {}".format(spotify_check[feed]["name"]))
                if len(pod_check) > 0:
                    for feed in pod_check:
                        logger.debug("  Other podcasts:")
                        logger.debug("- {}".format(pod_check[feed]["name"]))
                # Start processing per feed settings
                # Spotify links first
                if len(spotify_check) > 0:
                    for feed in spotify_check:
                        POD_ID = feed
                        UUID = spotify_check[feed]["uuid"]
                        FEED_NAME = spotify_check[feed]["name"]
                        CHANNEL = spotify_check[feed]["channel"]
                        NUM_EPISODES = spotify_check[feed]["num_episodes_new"]
                        channel_obj = get(guild.channels, id=int(CHANNEL))
                        logger.debug(
                            f"Found channel `{channel_obj.name}` in `{FEED_NAME}`"
                        )
                        FEED_POSTS = await net_io.get_spotify_podcast_links(
                            feed_id=POD_ID, uuid=UUID, num_items=3, guild=guild
                        )
                        logger.debug(
                            "Got {} items for `FEED_POSTS`: {}".format(
                                len(FEED_POSTS) if FEED_POSTS else 0,
                                [pod_ep["title"] for pod_ep in FEED_POSTS]
                                if FEED_POSTS
                                else None,
                            )
                        )
                        if FEED_POSTS is None:
                            logger.info(f"Feed {FEED_NAME} returned NoneType")
                            await discord_commands.log_to_bot_channel(
                                guild,
                                I18N.t(
                                    "rss.tasks.feed_posts_is_none", feed_name=FEED_NAME
                                ),
                            )
                        else:
                            await feeds_core.process_links_for_posting_or_editing(
                                feed_name=FEED_NAME,
                                feed_type="podcast",
                                uuid=UUID,
                                FEED_POSTS=FEED_POSTS,
                                CHANNEL=CHANNEL,
                                guild=guild,
                            )
                            await db_helper.update_fields(
                                template_info=envs.rss_db_schema,
                                where=("uuid", UUID),
                                updates=("num_episodes", NUM_EPISODES),
                                guild_id=guild.id,
                            )
                # ...then other podcasts
                if len(pod_check) > 0:
                    for feed in pod_check:
                        UUID = pod_check[feed]["uuid"]
                        FEED_NAME = pod_check[feed]["name"]
                        CHANNEL = pod_check[feed]["channel"]
                        URL = pod_check[feed]["url"]
                        logger.debug(
                            "Found channel `{} ({})` in `{}`".format(
                                get(guild.channels, id=int(CHANNEL)).name,
                                CHANNEL,
                                FEED_NAME,
                            )
                        )
                        req = await net_io.get_link(URL)
                        FEED_POSTS = await net_io.get_other_podcast_links(
                            req=req, url=URL, uuid=UUID, num_items=3, guild=guild
                        )
                        logger.debug(
                            "Got {} items for `FEED_POSTS`: {}".format(
                                len(FEED_POSTS) if FEED_POSTS else 0,
                                [pod_ep["title"] for pod_ep in FEED_POSTS]
                                if FEED_POSTS
                                else None,
                            )
                        )
                        if FEED_POSTS is None:
                            logger.info(f"Feed {FEED_NAME} returned NoneType")
                            await discord_commands.log_to_bot_channel(
                                guild,
                                I18N.t(
                                    "rss.tasks.feed_posts_is_none", feed_name=FEED_NAME
                                ),
                            )
                        else:
                            await feeds_core.process_links_for_posting_or_editing(
                                feed_name=FEED_NAME,
                                feed_type="podcast",
                                uuid=UUID,
                                FEED_POSTS=FEED_POSTS,
                                CHANNEL=CHANNEL,
                                guild=guild,
                            )
        logger.info("Done with posting")

    @task_post_podcasts.before_loop
    async def before_post_new_podcasts():
        "#autodoc skip#"
        logger.debug("`task_post_podcasts` waiting for bot to be ready...")
        await config.bot.wait_until_ready()


async def ensure_guild_rss_tables(guild):
    """
    Prep this guild's RSS/podcast tables, and fix up any legacy
    channel-name/feed-type data. Safe to call repeatedly (idempotent).
    #autodoc skip#
    """
    missing_tbl_cols = {}
    await db_helper.prep_table(table_in=envs.rss_db_schema, guild_id=guild.id)
    await db_helper.prep_table(table_in=envs.rss_db_filter_schema, guild_id=guild.id)
    await db_helper.prep_table(
        table_in=envs.rss_db_settings_schema,
        inserts=envs.rss_db_settings_schema["inserts"],
        guild_id=guild.id,
    )
    await db_helper.prep_table(table_in=envs.rss_db_ratings_schema, guild_id=guild.id)
    await db_helper.prep_table(table_in=envs.rss_db_log_schema, guild_id=guild.id)

    await db_helper.add_missing_db_setup(
        envs.rss_db_schema, missing_tbl_cols, guild_id=guild.id
    )
    await db_helper.add_missing_db_setup(
        envs.rss_db_settings_schema, missing_tbl_cols, guild_id=guild.id
    )
    await db_helper.add_missing_db_setup(
        envs.rss_db_log_schema, missing_tbl_cols, guild_id=guild.id
    )
    await db_helper.add_missing_db_setup(
        envs.rss_db_ratings_schema, missing_tbl_cols, guild_id=guild.id
    )
    logger.debug(f"rss db for `{guild.name}`: `missing_tbl_cols` is {missing_tbl_cols}")
    if any(len(missing_tbl_cols[table]) > 0 for table in missing_tbl_cols):
        missing_tbl_cols_text = ""
        for _tbl in missing_tbl_cols:
            missing_tbl_cols_text += "{}:".format(_tbl)
            for col in missing_tbl_cols[_tbl]:
                missing_tbl_cols_text += "\n{}".format(" - ".join(col))
            if _tbl != list(missing_tbl_cols.keys())[-1]:
                missing_tbl_cols_text += "\n\n"
        await discord_commands.log_to_bot_channel(
            guild,
            "Missing columns in rss db: {}\n"
            "Make sure to populate missing information".format(missing_tbl_cols_text),
        )
    # Change channel name to id
    await db_helper.db_channel_names_to_ids(
        template_info=envs.rss_db_schema, id_col="uuid", channel_col="channel",
        guild=guild,
    )
    await db_helper.db_update_to_correct_feed_types(
        template_info=envs.rss_db_schema, guild_id=guild.id
    )


async def setup(bot):
    cog_name = "rss"
    logger.info(envs.COG_STARTING.format(cog_name))
    logger.debug("Checking db")

    approved_guilds = await db_helper.get_output(
        envs.guilds_db_schema, where=("status", "approved")
    )
    for guild_row in approved_guilds:
        guild = config.bot.get_guild(int(guild_row["guild_id"]))
        if guild is None:
            continue
        await ensure_guild_rss_tables(guild)
        await db_helper.ensure_guild_tasks_rows(guild.id)

    logger.debug("Registering cog to bot")
    await bot.add_cog(RSSfeed(bot))
    logger.info(envs.COG_STARTED.format(cog_name))

    # The loops are shared, always-running infrastructure - each tick
    # checks every guild's own tasks_db_schema row to decide whether to
    # process that guild (see task_post_feeds/task_post_podcasts above).
    RSSfeed.task_post_feeds.start()
    RSSfeed.task_post_podcasts.start()


async def teardown(bot):
    RSSfeed.task_post_feeds.cancel()
    RSSfeed.task_post_podcasts.cancel()
