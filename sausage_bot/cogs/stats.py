#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
stats: Get interesting stats for the discord server and post them
to a channel
"""

import os
from discord.ext import commands, tasks
from discord.app_commands import locale_str, describe
import discord
from discord.utils import get
from tabulate import tabulate
import typing
import re
from pprint import pformat
import asyncio

from sausage_bot.util import envs, datetime_handling, file_io, config
from sausage_bot.util import discord_commands, db_helper
from sausage_bot.util.i18n import I18N

logger = config.logger


async def settings_db_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    settings_db = await db_helper.get_output(
        template_info=envs.stats_db_settings_schema,
        select=("setting", "value"),
        guild_id=interaction.guild.id,
    )
    settings_type = envs.stats_db_settings_schema["type_checking"]
    return [
        discord.app_commands.Choice(
            name="{} = {} ({})".format(
                setting["setting"], setting["value"], settings_type[setting["setting"]]
            ),
            value=str(setting["setting"]),
        )
        for setting in settings_db
        if current.lower()
        in "{}-{}".format(setting["setting"], setting["value"]).lower()
    ][:25]


async def env_settings_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    settings_info = envs.stats_db_settings_schema["inserts"]
    settings_type = envs.stats_db_settings_schema["type_checking"]
    return [
        discord.app_commands.Choice(
            name="{} ({})".format(settings_info[0], settings_type[settings_info[0]]),
            value=str(settings_info[0]),
        )
        for settings_info in settings_info
        if current.lower() in settings_info[0].lower()
    ][:25]


async def hidden_roles_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    hidden_roles_in_db = await db_helper.get_output(
        template_info=envs.stats_db_hide_roles_schema,
        get_row_ids=True,
        guild_id=interaction.guild.id,
    )
    logger.debug(f"hidden_roles_from_db:\n{pformat(hidden_roles_in_db)}")
    temp_hidden_roles = {}
    for i in hidden_roles_in_db:
        temp_hidden_roles[i["role_id"]] = {
            "rowid": i["rowid"],
            "name": get(interaction.guild.roles, id=int(i["role_id"])).name,
        }
    logger.debug("temp_hidden_roles:\n{pformat(temp_hidden_roles)}")
    return [
        discord.app_commands.Choice(
            name="{} ({})".format(temp_hidden_roles[hidden_role]["name"], hidden_role),
            value=str(temp_hidden_roles[hidden_role]["rowid"]),
        )
        for hidden_role in temp_hidden_roles
        if current
        in "{}-{}".format(hidden_role, temp_hidden_roles[hidden_role]["name"]).lower()
    ][:25]


def get_role_numbers(guild, settings_in):
    "Get roles from Discord server"
    logger.debug("Getting info from Discord about roles")
    return discord_commands.get_roles(
        guild,
        hide_empties=settings_in["hide_empty_roles"],
        filter_bots=settings_in["hide_bot_roles"],
    )


def get_stats_codebase():
    "Get statistics for the code base"
    total_lines = 0
    total_files = 0
    for root, _, files in os.walk(envs.ROOT_DIR):
        for filename in files:
            filename_without_extension, extension = os.path.splitext(filename)
            if extension == ".py":
                total_files += 1
                with open(os.path.join(root, filename), "r") as _file:
                    for _ in _file:
                        total_lines += 1
    return {"total_lines": total_lines, "total_files": total_files}


async def get_db_settings(guild):
    "#autodoc skip#"
    stats_settings_db = await db_helper.get_output(
        template_info=envs.stats_db_settings_schema,
        select=("setting", "value"),
        guild_id=guild.id,
    )
    logger.debug(f"`stats_settings_db` is {stats_settings_db}")
    stats_settings = {}
    for setting in stats_settings_db:
        stats_settings[setting["setting"]] = setting["value"]
    logger.debug(f"`stats_settings` is {stats_settings}")
    return stats_settings


async def get_db_hide_roles(guild):
    "#autodoc skip#"
    hide_roles_exist = await db_helper.table_exist(
        envs.stats_db_hide_roles_schema, guild_id=guild.id
    )
    if hide_roles_exist:
        stats_hide_roles = await db_helper.get_output(
            envs.stats_db_hide_roles_schema, guild_id=guild.id
        )
        stats_hide_roles = [role["role_id"] for role in stats_hide_roles]
        if len(stats_hide_roles) > 0:
            return list(stats_hide_roles)
    return None


async def log_guild_stats(guild, files_in_codebase, lines_in_codebase, total_members):
    "#autodoc skip#"
    stats_log_inserts = []
    date_exist = await db_helper.get_output(
        template_info=envs.stats_db_log_schema,
        order_by=[("datetime", "DESC")],
        select=("datetime"),
        single=True,
        guild_id=guild.id,
    )
    if not date_exist:
        # get_output(single=True) returns {} (not None) when no row matches
        date_exist = None
    else:
        logger.debug(f"`date_exist`: {date_exist}")
        date_exist = date_exist["datetime"]
    log_stats = False
    if date_exist:
        date_now = await datetime_handling.get_dt(format="date")
        date_exist = await datetime_handling.get_dt(format="date", dt=date_exist)
        if date_now > date_exist:
            log_stats = True
        else:
            logger.debug("Today has already been logged, skipping...")
    elif date_exist is None:
        log_stats = True
    if log_stats:
        stats_log_inserts.append(
            (
                str(await datetime_handling.get_dt("ISO8601")),
                files_in_codebase,
                lines_in_codebase,
                total_members,
            )
        )
        # Write changes to database
        await db_helper.insert_many_all(
            template_info=envs.stats_db_log_schema,
            inserts=stats_log_inserts,
            guild_id=guild.id,
        )


async def update_guild_stats(guild, files_in_codebase, lines_in_codebase):
    """
    Update interesting stats in a channel post and write the info to
    the log db, for `guild`. The channel is defined in that guild's
    stats settings db. The caller (`task_update_stats`) is responsible
    for checking whether stats posting is enabled for this guild.
    #autodoc skip#
    """
    stats_settings = await get_db_settings(guild)

    async def tabify(dict_in: dict, headers: list, hide_roles: list = None):
        text_out = ""
        if isinstance(dict_in, dict):
            logger.debug(
                "Checking `sort_abc` ({}) and `sort_321` ({})".format(
                    eval(stats_settings["sort_roles_abc"].capitalize()),
                    eval(stats_settings["sort_roles_321"].capitalize()),
                )
            )
            if not eval(stats_settings["sort_roles_abc"]) and not eval(
                stats_settings["sort_roles_321"]
            ):
                logger.debug(
                    "Could not decide whether sorting by `abc` or `123`. "
                    "Defaulting to `abc`."
                )
                stats_settings["sort_roles_abc"] = True
            if eval(stats_settings["sort_roles_abc"]):
                dict_in = dict(
                    sorted(dict_in.items(), key=lambda x: x[1]["name"].lower())
                )
                logger.debug(f"Sorting roles alphabetically: {list(dict_in)[0:4]}")
            elif eval(stats_settings["sort_roles_321"]):
                dict_in = dict(
                    sorted(dict_in.items(), key=lambda x: x[1]["members"], reverse=True)
                )
                logger.debug(
                    f"Sorting roles by number of members: {list(dict_in)[0:4]}"
                )

            # Tabulate the output
            dict_out = {"name": [], "members": []}
            for role in dict_in:
                if hide_roles is not None and str(dict_in[role]["id"]) in hide_roles:
                    continue
                # Check for `sort_min_role_members`
                if dict_in[role]["name"] != "@everyone":
                    if stats_settings["sort_min_role_members"]:
                        min_members = stats_settings["sort_min_role_members"]
                        if dict_in[role]["members"] >= int(min_members):
                            dict_out["name"].append(dict_in[role]["name"])
                            dict_out["members"].append(dict_in[role]["members"])
                    else:
                        dict_out["name"].append(dict_in[role]["name"])
                        dict_out["members"].append(dict_in[role]["members"])
            text_out = "{}".format(
                tabulate(dict_out, headers=headers, numalign="right")
            )
            logger.debug(f"Returning: {text_out[0:200]}...")
            return text_out
        else:
            logger.error("`dict_in` is not a dict. Check the input.")

    async def check_and_post_to_stats_msg_id(stats_settings, stats_info):
        # Get `stats_msg_id` from db to update stats post
        channel_setting = stats_settings.get("channel")
        if channel_setting is not None and not re.match(r"^\d+$", str(channel_setting)):
            # `channel` setting is still a channel name (not migrated to
            # an id yet) - try to resolve and persist it, then re-read
            # the fresh value instead of the now-stale `stats_settings`.
            await db_helper.db_single_channel_name_to_id(
                template_info=envs.stats_db_settings_schema,
                channel_row="setting",
                channel_col="value",
                guild=guild,
            )
            stats_settings = await get_db_settings(guild)
            channel_setting = stats_settings.get("channel")
        if channel_setting is None or not re.match(r"^\d+$", str(channel_setting)):
            logger.error("`stats_channel` is not a channel")
            return None
        stats_channel = guild.get_channel(int(channel_setting))
        logger.debug(f"Got `stats_channel` {stats_channel} ({type(stats_channel)})")
        # If `stats_msg_id` is not in db, check if `stats_msg` is in db
        # If `stats_msg` is not in db, add `stats_msg_id` to db
        stats_msg_id = None
        if "stats_msg_id" not in stats_settings:
            # Add new post and update db
            if "stats_msg" in stats_settings:
                stats_msg_id = stats_settings.get("stats_msg")
                # Change 'stats_msg' to 'stats_msg_id'
                await db_helper.update_fields(
                    envs.stats_db_settings_schema,
                    where=("setting", "stats_msg"),
                    updates=("setting", "stats_msg_id"),
                    guild_id=guild.id,
                )
            else:
                logger.error("Noe rart har skjedd?!")
        elif "stats_msg_id" in stats_settings:
            stats_msg_id = stats_settings.get("stats_msg_id")
        # Now we should have `stats_msg_id`, check it's value and
        # decide what to do
        post_new = False
        if stats_msg_id == "" or stats_msg_id is None:
            logger.debug("`stats_msg_id` is empty, is there already a stats msg?")
            # Look for a stats message
            stats_msgs = [
                message
                async for message in stats_channel.history(limit=20, oldest_first=True)
            ]
            for _msg in stats_msgs:
                last_update_text = I18N.t(
                    "stats.tasks.update_stats.stats_msg.code_last_updated"
                )
                if last_update_text in str(_msg.content):
                    logger.debug(f"Found stats message: {_msg.id}")
                    stats_msg_id = _msg.id
                    logger.debug("Updating db")
                    await db_helper.update_fields(
                        template_info=envs.stats_db_settings_schema,
                        where=("setting", "stats_msg_id"),
                        updates=("value", _msg.id),
                        guild_id=guild.id,
                    )
                    break
            if not re.match(r"^\d{19}$", str(stats_msg_id)):
                logger.debug("Did not find a stats message, posting a new one")
                post_new = True
        if re.match(r"^\d{19}$", str(stats_msg_id)):
            try:
                # Edit the stats message if found
                # Retry fetching and editing 3 times
                for i in range(3):
                    try:
                        stats_msg = await stats_channel.fetch_message(stats_msg_id)
                        await stats_msg.edit(content=stats_info)
                        logger.debug("Edited existing stats message")
                        break
                    except discord.DiscordServerError:
                        if i == 2:
                            raise
                        await asyncio.sleep(2)  # Wait 2 seconds before retrying
                    return
            except discord.errors.NotFound:
                logger.error(
                    "Could not find msg id `{stats_msg_id}` in channel "
                    "`{stats_channel}`"
                )
                post_new = True
                logger.debug("Creating new stats message")
        if post_new:
            # Post it
            stats_msg = await stats_channel.send(stats_info)
            stats_msg_id = stats_msg.id
            # Update db
            if "stats_msg_id" in stats_settings:
                await db_helper.update_fields(
                    template_info=envs.stats_db_settings_schema,
                    where=("setting", "stats_msg_id"),
                    updates=("value", stats_msg.id),
                    guild_id=guild.id,
                )
            else:
                await db_helper.insert_many_all(
                    template_info=envs.stats_db_settings_schema,
                    inserts=(("stats_msg_id", stats_msg.id)),
                    guild_id=guild.id,
                )
        return

    logger.info(f"Updating stats for `{guild.name}`")
    stats_hide_roles = await get_db_hide_roles(guild)
    logger.debug(f"`stats_hide_roles` is {stats_hide_roles}")
    # Get server members
    role_numbers = get_role_numbers(guild, stats_settings)
    logger.debug(f"Got {len(role_numbers)} roles")
    # Get total number of members
    total_members = 0
    if eval(stats_settings["show_members_total"]):
        total_members = guild.member_count
    # Update log database if not already this day
    logger.debug("Logging stats")
    await log_guild_stats(guild, files_in_codebase, lines_in_codebase, total_members)
    # Update the stats-msg
    dt_log = await datetime_handling.get_dt("datetimefull")
    stats_info = ""
    logger.debug("`show_role_stats` is {}".format(stats_settings["show_role_stats"]))
    if eval(stats_settings["show_members_total"]) or eval(
        stats_settings["show_role_stats"]
    ):
        roles_members = await tabify(
            dict_in=role_numbers,
            headers=["Rolle", "Brukere"],
            hide_roles=stats_hide_roles,
        )
        logger.debug(f"`roles_members`:\n{roles_members}")
        # Trim roles_members hvis stats_info vil overskride 2000 tegn
        # Beregn hvor mye plass de andre delene av stats_info tar
        msg_limit_check = ""
        members_sub = I18N.t("stats.tasks.update_stats.stats_msg.members_sub")
        msg_limit_check += f"### {members_sub}\n"
        if eval(stats_settings["show_members_total"]):
            members_num = I18N.t("stats.tasks.update_stats.stats_msg.members_num")
            msg_limit_check += f"```{members_num}: {total_members}```\n"
        if eval(stats_settings["show_code_stats"]):
            code_sub = I18N.t("stats.tasks.update_stats.stats_msg.code_sub")
            code_files = I18N.t("stats.tasks.update_stats.stats_msg.code_files")
            code_lines = I18N.t("stats.tasks.update_stats.stats_msg.code_lines")
            msg_limit_check += (
                f"### {code_sub}\n```"
                f"{code_files}: {files_in_codebase}\n"
                f"{code_lines}: {lines_in_codebase}```\n"
            )
        code_last_updated = I18N.t(
            "stats.tasks.update_stats.stats_msg.code_last_updated"
        )
        msg_limit_check += f"```{code_last_updated} {dt_log}```\n"
        available_space = 1950 - len(msg_limit_check)
        logger.debug(f"msg_limit_check: {len(msg_limit_check)}")
        if len(roles_members) > available_space:
            lines = roles_members.splitlines()
            while lines and len(f"```{chr(10).join(lines)}```\n") > available_space:
                lines.pop()
            roles_members = "\n".join(lines)
            logger.debug(f"Length roles_members after check: {len(roles_members)}")
            await discord_commands.log_to_bot_channel(
                guild,
                # TODO: i18n
                "Stats: Length of roles exceeded message limit, auto-truncated it. "
                "Maybe check it's settings?",
            )

        members_sub = I18N.t("stats.tasks.update_stats.stats_msg.members_sub")
        stats_info += f"### {members_sub}\n"
    if eval(stats_settings["show_members_total"]):
        members_num = I18N.t("stats.tasks.update_stats.stats_msg.members_num")
        stats_info += f"```{members_num}: {total_members}```\n"
    if eval(stats_settings["show_role_stats"]):
        stats_info += f"```{roles_members}```\n"
    logger.debug("`show_code_stats` is {}".format(stats_settings["show_code_stats"]))
    if eval(stats_settings["show_code_stats"]):
        code_sub = I18N.t("stats.tasks.update_stats.stats_msg.code_sub")
        code_files = I18N.t("stats.tasks.update_stats.stats_msg.code_files")
        code_lines = I18N.t("stats.tasks.update_stats.stats_msg.code_lines")
        stats_info += (
            f"### {code_sub}\n```"
            f"{code_files}: {files_in_codebase}\n"
            f"{code_lines}: {lines_in_codebase}```\n"
        )
    code_last_updated = I18N.t("stats.tasks.update_stats.stats_msg.code_last_updated")
    stats_info += f"```{code_last_updated} {dt_log}```\n"
    logger.debug(f"Trying to post stats to `stats_channel`:\n{stats_info[0:100]}")
    await check_and_post_to_stats_msg_id(stats_settings, stats_info)


class Stats(commands.Cog):
    "Get interesting stats for the discord server"

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    stats_group = discord.app_commands.Group(
        name="stats", description=locale_str(I18N.t("stats.commands.groups.stats"))
    )
    stats_posting_group = discord.app_commands.Group(
        name="posting",
        description=locale_str(I18N.t("stats.commands.groups.posting")),
        parent=stats_group,
    )
    stats_settings_group = discord.app_commands.Group(
        name="settings",
        description=locale_str(I18N.t("stats.commands.groups.settings")),
        parent=stats_group,
    )

    @discord_commands.is_owner_or_manage_guild()
    @stats_posting_group.command(
        name="start", description=locale_str(I18N.t("stats.commands.start.command"))
    )
    async def stats_posting_start(self, interaction: discord.Interaction):
        """
        Enable stats posting for this guild. The background loop itself
        is shared, always-running infrastructure (like rss/youtube) -
        this just flips this guild's own `tasks_db_schema` row.
        """
        await interaction.response.defer(ephemeral=True)
        logger.info(
            f"Enabling stats posting for `{interaction.guild.name}`: "
            f"{I18N.t('stats.commands.start.log_started')}"
        )
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[("cog", "stats"), ("task", "post_stats")],
            updates=("status", "started"),
            guild_id=interaction.guild.id,
        )
        await interaction.followup.send(I18N.t("stats.commands.start.confirm_started"))

    @discord_commands.is_owner_or_manage_guild()
    @stats_posting_group.command(
        name="stop", description=locale_str(I18N.t("stats.commands.stop.command"))
    )
    @describe(remove_post=I18N.t("stats.commands.stop.desc.remove_post"))
    async def stats_posting_stop(
        self, interaction: discord.Interaction, remove_post: typing.Literal["Yes", "No"]
    ):
        "Disable stats posting for this guild."
        await interaction.response.defer(ephemeral=True)
        logger.info(
            f"Disabling stats posting for `{interaction.guild.name}`: "
            f"{I18N.t('stats.commands.stop.log_stopped')}"
        )
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[("cog", "stats"), ("task", "post_stats")],
            updates=("status", "stopped"),
            guild_id=interaction.guild.id,
        )
        if remove_post.lower() == "yes":
            stats_settings = dict(
                await db_helper.get_output(
                    template_info=envs.stats_db_settings_schema,
                    select=("setting", "value"),
                    guild_id=interaction.guild.id,
                )
            )
            if len(stats_settings["channel"]) > 0:
                stats_channel = stats_settings["channel"]
            else:
                stats_channel = "stats"
            await discord_commands.remove_stats_post(interaction.guild, stats_channel)
        await interaction.followup.send(I18N.t("stats.commands.stop.confirm_stopped"))

    @discord_commands.is_owner()
    @stats_posting_group.command(
        name="restart", description=locale_str(I18N.t("stats.commands.restart.command"))
    )
    async def stats_posting_restart(self, interaction: discord.Interaction):
        """
        Restart the shared background stats loop (all guilds). Useful
        for troubleshooting - not guild-scoped, since the loop itself is
        shared infrastructure.
        """
        await interaction.response.defer(ephemeral=True)
        logger.info("Stats posting loop restarted")
        Stats.task_update_stats.restart()
        await interaction.followup.send(I18N.t("stats.commands.restart.log_restarted"))

    @discord_commands.is_owner_or_manage_guild()
    @stats_settings_group.command(
        name="list", description=locale_str(I18N.t("stats.commands.list.command"))
    )
    async def list_settings(self, interaction: discord.Interaction):
        """
        List the available settings for this cog
        """
        await interaction.response.defer(ephemeral=True)
        settings_in_db = await db_helper.get_output(
            template_info=envs.stats_db_settings_schema,
            select=("setting", "value"),
            guild_id=interaction.guild.id,
        )
        headers_settings = {
            "setting": I18N.t("stats.commands.list.headers.settings.setting"),
            "value": I18N.t("stats.commands.list.headers.settings.value"),
        }
        out = "## {}\n```{}```".format(
            I18N.t("stats.commands.list.stats_msg_out.sub_settings"),
            tabulate(settings_in_db, headers=headers_settings),
        )
        hidden_roles_in_db = await db_helper.get_output(
            template_info=envs.stats_db_hide_roles_schema, guild_id=interaction.guild.id
        )
        logger.debug(f"`hidden_roles_in_db` is {hidden_roles_in_db}")
        if hidden_roles_in_db is not None and len(hidden_roles_in_db) > 0:
            headers_hidden_roles = [
                I18N.t("stats.commands.list.headers.hidden_roles.hidden_name"),
                I18N.t("stats.commands.list.headers.hidden_roles.hidden_id"),
            ]
            populated_roles = []
            for role in hidden_roles_in_db:
                populated_roles.append(
                    (
                        get(interaction.guild.roles, id=int(role["role_id"])),
                        role["role_id"],
                    )
                )
            out += "\n## {}\n```{}```".format(
                I18N.t("stats.commands.list.stats_msg_out.sub_hidden"),
                tabulate(populated_roles, headers=headers_hidden_roles),
            )
        await interaction.followup.send(content=out, ephemeral=True)

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(name_of_setting=settings_db_autocomplete)
    @stats_settings_group.command(
        name="change", description=locale_str(I18N.t("stats.commands.change.command"))
    )
    @describe(
        name_of_setting=I18N.t("stats.commands.change.desc.name_of_setting"),
        value_in=I18N.t("stats.commands.change.desc.value_in"),
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
        value_in: str
            The value of the settings (default: None)
        """

        def bool_switch(bool_input):
            if bool_input.lower() == "true":
                return "False"
            elif bool_input.lower() == "false":
                return "True"

        await interaction.response.defer(ephemeral=True)
        settings_in_db = await db_helper.get_output(
            template_info=envs.stats_db_settings_schema,
            select=("setting", "value"),
            guild_id=interaction.guild.id,
        )
        settings_from_db = {}
        for setting in settings_in_db:
            settings_from_db[setting["setting"]] = setting["value"]
        logger.debug(f"settings_from_db:\n{pformat(settings_from_db)}")
        settings_type = envs.stats_db_settings_schema["type_checking"]
        for setting in settings_from_db:
            logger.debug(f"Checking '{name_of_setting}' against '{setting}'")
            if setting == name_of_setting:
                if settings_type[setting] == "bool":
                    if value_in.lower() in ["true", "false"]:
                        value_in = str(value_in).capitalize()
                        logger.debug(f"Changing as bool: {value_in}")
                    else:
                        logger.error(f"Invalid input for value_in: {value_in}")
                        await interaction.followup.send(
                            I18N.t("stats.setting_input_reply")
                        )
                        return
                # Sorting should actually behave like a switch, so if abc is
                # True, then 321 will turn False, and vice versa
                if setting in ["sort_roles_abc", "sort_roles_321"]:
                    if setting == "sort_roles_abc":
                        await db_helper.update_fields(
                            template_info=envs.stats_db_settings_schema,
                            where=[("setting", "sort_roles_abc")],
                            updates=[("value", value_in)],
                            guild_id=interaction.guild.id,
                        )
                        await db_helper.update_fields(
                            template_info=envs.stats_db_settings_schema,
                            where=[("setting", "sort_roles_321")],
                            updates=[("value", bool_switch((value_in)))],
                            guild_id=interaction.guild.id,
                        )
                    elif setting == "sort_roles_321":
                        await db_helper.update_fields(
                            template_info=envs.stats_db_settings_schema,
                            where=[("setting", "sort_roles_321")],
                            updates=[("value", value_in)],
                            guild_id=interaction.guild.id,
                        )
                        await db_helper.update_fields(
                            template_info=envs.stats_db_settings_schema,
                            where=[("setting", "sort_roles_abc")],
                            updates=[("value", bool_switch((value_in)))],
                            guild_id=interaction.guild.id,
                        )
                elif type(eval(value_in)) is eval(settings_type[setting]):
                    logger.debug(f"Updating '{setting}' with '{value_in}'")
                    await db_helper.update_fields(
                        template_info=envs.stats_db_settings_schema,
                        where=[("setting", name_of_setting)],
                        updates=[("value", value_in)],
                        guild_id=interaction.guild.id,
                    )
                await interaction.followup.send(
                    content=I18N.t("stats.commands.change.update_confirmed"),
                    ephemeral=True,
                )
                break
        return

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(setting_in=env_settings_autocomplete)
    @stats_settings_group.command(
        name="add", description=locale_str(I18N.t("stats.commands.add.command"))
    )
    @describe(
        setting_in=I18N.t("stats.commands.add.desc.name_of_setting"),
        value_in=I18N.t("stats.commands.add.desc.value_in"),
    )
    async def add_setting(
        self, interaction: discord.Interaction, setting_in: str, value_in: str
    ):
        """
        Add a setting for this cog
        """
        await interaction.response.defer(ephemeral=True)
        settings_in_db = await db_helper.get_output(
            template_info=envs.stats_db_settings_schema,
            select=("setting", "value"),
            guild_id=interaction.guild.id,
        )
        settings_db_json = file_io.make_db_output_to_json(
            ["setting", "value"], settings_in_db
        )
        settings_types = envs.stats_db_settings_schema["type_checking"]
        logger.debug("settings_db_json is `{}`".format(settings_db_json))
        if value_in.lower() in ["true", "false"]:
            value_in = value_in.capitalize()
            value_in_check = eval("{}({})".format(settings_types[setting_in], value_in))
        logger.debug(
            "Value is {} ({}) and setting type is {}".format(
                value_in, type(value_in_check), eval(settings_types[setting_in])
            )
        )
        if setting_in in settings_db_json:
            await interaction.followup.send(
                content=I18N.t("stats.commands.add.msg.setting_already_exists"),
                ephemeral=True,
            )
            return
        if type(value_in_check) is not eval(settings_types[setting_in]):
            await interaction.followup.send(
                content=I18N.t(
                    "stats.commands.add.msg.type_incorrect",
                    value_in=value_in,
                    value_type=type(value_in),
                    value_type_check=settings_types[setting_in],
                ),
                ephemeral=True,
            )
            return
        elif type(value_in_check) is eval(settings_types[setting_in]):
            if setting_in:
                await db_helper.insert_many_all(
                    template_info=envs.stats_db_settings_schema,
                    inserts=[(setting_in, value_in)],
                    guild_id=interaction.guild.id,
                )
                await interaction.followup.send(
                    content=I18N.t("stats.commands.add.msg.add_confirmed"),
                    ephemeral=True,
                )
                return
        else:
            logger.error("Something went wrong")
            await interaction.followup.send(
                content=I18N.t("stats.commands.add.msg.add_failed"), ephemeral=True
            )
            return

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(setting_in=settings_db_autocomplete)
    @stats_settings_group.command(
        name="remove", description=locale_str(I18N.t("stats.commands.remove.command"))
    )
    @describe(setting_in=I18N.t("stats.commands.remove.desc.name_of_setting"))
    async def remove_setting(self, interaction: discord.Interaction, setting_in: str):
        """
        Remove a setting for this cog
        """
        await interaction.response.defer(ephemeral=True)
        try:
            await db_helper.del_row_by_AND_filter(
                template_info=envs.stats_db_settings_schema,
                where=[("setting", setting_in)],
                guild_id=interaction.guild.id,
            )
            await interaction.followup.send(
                content=I18N.t("stats.commands.remove.msg.remove_confirmed"),
                ephemeral=True,
            )
        except Exception as error:
            logger.error(f"Error when removing setting: {error}")
            await interaction.followup.send(
                content=I18N.t("stats.commands.remove.msg.remove_failed"),
                ephemeral=True,
            )
        return

    @discord_commands.is_owner_or_manage_guild()
    @stats_group.command(
        name="hide_roles_add",
        description=locale_str(I18N.t("stats.commands.hide_roles_add.command")),
    )
    @describe(role_in=I18N.t("stats.commands.hide_roles_add.desc.role_in"))
    async def stats_add_hidden_roles(
        self, interaction: discord.Interaction, role_in: discord.Role
    ):
        """
        Add roles to hide in stats

        Parameters
        ------------
        role_in: discord.Role
            The role to add
        """
        await interaction.response.defer(ephemeral=True)
        hidden_roles_in_db = await db_helper.get_output(
            template_info=envs.stats_db_hide_roles_schema,
            select=("role_id"),
            guild_id=interaction.guild.id,
        )
        hidden_roles_in_list = []
        if type(hidden_roles_in_db) is not None:
            for role in hidden_roles_in_db:
                hidden_roles_in_list.append(role["role_id"])
            if str(role_in.id) in hidden_roles_in_list:
                await interaction.followup.send(
                    I18N.t("stats.commands.hide_roles_add.msg.already_hidden")
                )
                return
            else:
                await db_helper.insert_many_all(
                    template_info=envs.stats_db_hide_roles_schema,
                    inserts=[(str(role_in.id))],
                    guild_id=interaction.guild.id,
                )
                await interaction.followup.send(
                    content=I18N.t("stats.commands.hide_roles_add.msg.confirm_added"),
                    ephemeral=True,
                )
        else:
            await interaction.followup.send(
                # TODO: i18n
                content="No hidden roles exist",
                ephemeral=True,
            )
        return

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(hidden_roles=hidden_roles_autocomplete)
    @stats_group.command(
        name="hide_roles_remove",
        description=locale_str(I18N.t("stats.commands.hide_roles_remove.command")),
    )
    @describe(hidden_roles=I18N.t("stats.commands.hide_roles_remove.desc.role_in"))
    async def stats_remove_hidden_roles(
        self, interaction: discord.Interaction, hidden_roles: str
    ):
        """
        Remove roles to hide in stats

        Parameters
        ------------
        role_in: discord.Role
            The role to remove
        """
        await interaction.response.defer(ephemeral=True)
        await db_helper.del_row_id(
            template_info=envs.stats_db_hide_roles_schema,
            numbers=hidden_roles,
            guild_id=interaction.guild.id,
        )
        await interaction.followup.send(
            content=I18N.t("stats.commands.hide_roles_remove.msg.confirm_removed"),
            ephemeral=True,
        )
        return

    # Tasks
    @tasks.loop(minutes=config.STATS_LOOP, reconnect=True)
    async def task_update_stats():
        """
        Shared, always-running loop (like rss/youtube). Every tick, checks
        each approved guild's own `tasks_db_schema` row (cog="stats",
        task="post_stats") and updates that guild's stats post if enabled.
        """
        approved_guilds = await db_helper.get_output(
            envs.guilds_db_schema, where=("status", "approved")
        )
        # Stats about this bot's own codebase are guild-independent
        _codebase = get_stats_codebase()
        lines_in_codebase = _codebase["total_lines"]
        files_in_codebase = _codebase["total_files"]

        for guild_row in approved_guilds:
            guild = config.bot.get_guild(int(guild_row["guild_id"]))
            if guild is None:
                continue
            task_status = await db_helper.get_output(
                template_info=envs.tasks_db_schema,
                where=[("cog", "stats"), ("task", "post_stats")],
                select=("status"),
                single=True,
                guild_id=guild.id,
            )
            if task_status.get("status") != "started":
                continue
            async with db_helper.guild_locale_context(guild.id):
                await update_guild_stats(guild, files_in_codebase, lines_in_codebase)

    @task_update_stats.before_loop
    async def before_update_stats():
        "#autodoc skip#"
        logger.debug("`update_stats` waiting for bot to be ready...")
        await config.bot.wait_until_ready()


async def ensure_guild_stats_tables(guild):
    """
    Prep this guild's stats tables, run legacy column/value fixups, and
    fix up any legacy channel-name data. Safe to call repeatedly
    (idempotent).
    #autodoc skip#
    """
    await db_helper.prep_table(
        table_in=envs.stats_db_settings_schema,
        inserts=envs.stats_db_settings_schema["inserts"],
        guild_id=guild.id,
    )
    await db_helper.prep_table(
        table_in=envs.stats_db_hide_roles_schema, guild_id=guild.id
    )
    await db_helper.prep_table(envs.stats_db_log_schema, guild_id=guild.id)

    await db_helper.add_missing_db_setup(
        envs.stats_db_settings_schema, guild_id=guild.id
    )
    await db_helper.db_fix_old_hide_roles_status(guild_id=guild.id)
    await db_helper.db_fix_old_stats_msg_name_status(guild_id=guild.id)
    await db_helper.db_fix_old_value_check_or_help(guild_id=guild.id)
    await db_helper.db_replace_numeral_bool_with_bool(
        envs.stats_db_settings_schema, guild_id=guild.id
    )
    await db_helper.db_remove_old_cols(envs.stats_db_settings_schema, guild_id=guild.id)
    # Change channel name to id
    channel_name_to_id = await db_helper.db_single_channel_name_to_id(
        template_info=envs.stats_db_settings_schema,
        channel_row="setting",
        channel_col="value",
        guild=guild,
    )
    if channel_name_to_id is None:
        logger.error(f"Stats channel not found for `{guild.name}`, disabling posting")
        # Make sure this guild's `tasks_db_schema` rows exist before
        # writing to them - `ensure_guild_tasks_rows` is idempotent, so
        # this is safe to call regardless of call order in `setup()`.
        await db_helper.ensure_guild_tasks_rows(guild.id)
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[("cog", "stats"), ("task", "post_stats")],
            updates=("status", "stopped"),
            guild_id=guild.id,
        )


async def setup(bot):
    cog_name = "stats"
    logger.info(envs.COG_STARTING.format(cog_name))
    logger.debug("Checking db")

    approved_guilds = await db_helper.get_output(
        envs.guilds_db_schema, where=("status", "approved")
    )
    for guild_row in approved_guilds:
        guild = config.bot.get_guild(int(guild_row["guild_id"]))
        if guild is None:
            continue
        await ensure_guild_stats_tables(guild)
        await db_helper.ensure_guild_tasks_rows(guild.id)

    logger.debug("Registering cog to bot")
    await bot.add_cog(Stats(bot))
    logger.info(envs.COG_STARTED.format(cog_name))

    # Shared, always-running loop - each tick checks every guild's own
    # tasks_db_schema row to decide whether to process that guild.
    Stats.task_update_stats.start()


async def teardown(bot):
    Stats.task_update_stats.cancel()
