#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"__main__: Set up the bot, have a few generic commands and controls cogs"

import discord
from discord.ext import commands, tasks
from discord.app_commands import locale_str
from discord.utils import get
from tabulate import tabulate
from pendulum import timezones as p_timezones
import os

from sausage_bot.util.args import args
from sausage_bot.util import config, envs, file_io, cogs, db_helper, net_io
from sausage_bot.util import discord_commands
from sausage_bot.util.datetime_handling import get_dt
from sausage_bot.util.i18n import I18N, available_languages
from sausage_bot.util.i18n import MyTranslator

logger = config.logger


async def reload_cogs():
    logger.debug("Reloading cogs")
    for filename in os.listdir(envs.COGS_DIR):
        if filename.endswith(".py") and not filename.startswith("_"):
            cog_name = filename[:-3]
            is_loaded = "{}.{}".format(
                envs.COGS_REL_DIR, f"{cog_name}" in config.bot.extensions
            )
            if is_loaded:
                await config.bot.unload_extension(
                    "{}.{}".format(envs.COGS_REL_DIR, f"{cog_name}")
                )
    for filename in os.listdir(envs.COGS_DIR):
        if filename.endswith(".py") and not filename.startswith("_"):
            cog_name = filename[:-3]
            await config.bot.load_extension(
                "{}.{}".format(envs.COGS_REL_DIR, f"{cog_name}")
            )


@tasks.loop(hours=1)
async def get_random_user_agent():
    await net_io.fetch_random_user_agent()


class SayTextInput(discord.ui.TextInput):
    def __init__(
        self, style_in, label_in, default_in=None, required_in=None, placeholder_in=None
    ):
        super().__init__(
            style=style_in,
            label=label_in,
            default=default_in,
            required=required_in,
            placeholder=placeholder_in,
        )


class SayModal(discord.ui.Modal):
    def __init__(self, title_in=None, channel=None):
        super().__init__(title=title_in, timeout=120)
        self.comment_out = None
        self.channel = channel
        self.error_out = None

        # Create elements
        label_in = I18N.t("main.commands.say.modal.comment")
        comment_text = SayTextInput(
            style_in=discord.TextStyle.paragraph,
            label_in=label_in,
            required_in=True,
            placeholder_in=I18N.t("main.commands.say.modal.comment"),
        )

        self.add_item(comment_text)

    async def on_submit(self, interaction: discord.Interaction):
        comment_out = discord_commands.check_user_channel_role(
            interaction.guild, self.children[0].value
        )
        logger.debug(f"Got `comment_out`: {comment_out}")
        msg_out = I18N.t("main.context_menu.edit_msg.edit_confirm")
        if len(comment_out["username_errors"]) > 0:
            msg_out += I18N.t(
                "main.context_menu.edit_msg.edit_confirm_with_errors",
                errors=", ".join(comment_out["username_errors"]),
            )
        if len(comment_out["channel_errors"]) > 0:
            if len(msg_out) == 0:
                msg_out += I18N.t(
                    "main.context_menu.edit_msg.edit_confirm_with_errors",
                    errors=", ".join(comment_out["channel_errors"]),
                )
            else:
                # TODO: i18n
                msg_out += "\nChannels: {}".format(
                    ", ".join(comment_out["channel_errors"])
                )
        await interaction.response.send_message(
            I18N.t("main.commands.say.modal.confirm", channel=self.channel.name),
            ephemeral=True,
        )
        self.comment_out = comment_out["text"]
        return

    async def on_error(self, interaction: discord.Interaction, error):
        logger.error(f"Error when editing message: {error}")
        await interaction.response.send_message(
            I18N.t(
                "main.commands.say.modal.error_sending",
                channel=self.channel.name,
                error=error,
            ),
            ephemeral=True,
        )


class EditModal(discord.ui.Modal):
    def __init__(self, title_in=None, comment_in=None):
        super().__init__(title=title_in, timeout=60)
        self.comment_in = comment_in
        self.comment_out = None
        self.error_out = None
        logger.debug(f"self.comment_in is: {self.comment_in}")

        # Create elements
        comment_text = SayTextInput(
            style_in=discord.TextStyle.paragraph,
            label_in=I18N.t("quote.modals.quote_text"),
            default_in=self.comment_in,
            required_in=True,
            placeholder_in="Text",
        )

        self.add_item(comment_text)

    async def on_submit(self, interaction: discord.Interaction):
        comment_out = discord_commands.check_user_channel_role(
            interaction.guild, self.children[0].value
        )
        logger.debug(f"Got `comment_out`: {comment_out}")
        msg_out = I18N.t("main.context_menu.edit_msg.edit_confirm")
        if len(comment_out["username_errors"]) > 0:
            msg_out += I18N.t(
                "main.context_menu.edit_msg.edit_confirm_with_errors",
                errors=", ".join(comment_out["username_errors"]),
            )
        if len(comment_out["channel_errors"]) > 0:
            if len(msg_out) == 0:
                msg_out += I18N.t(
                    "main.context_menu.edit_msg.edit_confirm_with_errors",
                    errors=", ".join(comment_out["channel_errors"]),
                )
            else:
                # TODO: i18n
                msg_out += "\nChannels: {}".format(
                    ", ".join(comment_out["channel_errors"])
                )

        self.comment_out = comment_out["text"]

        await interaction.response.send_message(msg_out, ephemeral=True)
        return

    async def on_error(self, interaction: discord.Interaction, error):
        logger.error(f"Error when editing message: {error}")
        self.error_out = error
        await interaction.response.send_message(
            I18N.t("main.context_menu.edit_msg.edit_error", error=error), ephemeral=True
        )


async def locales_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    locales = available_languages()
    logger.debug(f"locales: {locales}")
    return [
        discord.app_commands.Choice(name=locale, value=locale)
        for locale in locales
        if current.lower() in locale.lower()
    ][:25]


async def timezones_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    logger.debug(f"p_timezones(): {p_timezones()}")
    return [
        discord.app_commands.Choice(name=timezone, value=timezone)
        for timezone in p_timezones()
        if current.lower() in timezone.lower()
    ][:25]


async def pending_guilds_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    pending_guilds_db = await db_helper.get_output(
        template_info=envs.guilds_db_schema,
        where=[("status", "pending")],
        order_by=[("guild_name", "ASC")],
    )
    temp_guilds = pending_guilds_db.copy()
    for guild in temp_guilds:
        list_num = pending_guilds_db.index(guild)
        temp_guilds[list_num]["name"] = guild["guild_name"]
        logger.debug(f"`pending_guilds_db`: {pending_guilds_db}")
    return [
        discord.app_commands.Choice(
            name="{}".format(guild["guild_name"]),
            value=guild["guild_id"],
        )
        for guild in temp_guilds
        if current.lower() in "{} ({})".format(guild["guild_name"], guild["guild_id"])
    ][:25]


async def all_guilds_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    all_guilds_db = await db_helper.get_output(
        template_info=envs.guilds_db_schema,
        order_by=[("guild_name", "ASC")],
    )
    all_guilds = all_guilds_db.copy()
    for guild in all_guilds:
        list_num = all_guilds_db.index(guild)
        all_guilds[list_num]["name"] = guild["guild_name"]
        logger.debug(f"`all_guilds_db`: {all_guilds_db}")
    return [
        discord.app_commands.Choice(
            name="{}".format(guild["guild_name"]),
            value=guild["guild_id"],
        )
        for guild in all_guilds
        if current.lower() in "{} ({})".format(guild["guild_name"], guild["guild_id"])
    ][:25]


async def register_guild(guild: discord.Guild):
    """
    Make sure `guild` has a row in the guild registry. New guilds are
    `pending` unless they are the configured ADMIN_GUILD_ID, which is
    auto-approved and never needs to go through `/approve-guild`.
    If guild is marked as `removed`, it resets to `pending`. Other
    existing rows are left untouched. Status change via
    `/approve-guild` or `on_guild_remove`.
    #autodoc skip#
    """
    # Defensive: on_ready() already preps this table, but on_guild_join()
    # can also reach this function directly - prep_table is a cheap,
    # idempotent CREATE TABLE IF NOT EXISTS.
    await db_helper.prep_table(envs.guilds_db_schema)
    existing = await db_helper.get_output(
        envs.guilds_db_schema, where=("guild_id", str(guild.id)), single=True
    )
    if existing:
        logger.info(existing)
        if existing["status"].lower() == "removed":
            await db_helper.update_fields(
                envs.guilds_db_schema,
                where=("guild_id", str(guild.id)),
                updates=("status", "pending"),
            )
            await notify_admin_of_new_guild(guild, rejoined=True)
        return
    is_admin_guild = str(guild.id) == str(config.ADMIN_GUILD_ID)
    now = await get_dt(format="ISO8601")
    status = "approved" if is_admin_guild else "pending"
    await db_helper.insert_many_some(
        envs.guilds_db_schema,
        rows=("guild_id", "guild_name", "status", "joined_at"),
        inserts=[(str(guild.id), guild.name, status, now)],
    )
    # Every registered guild gets its own settings table straight away, so
    # I18N.t()/get_dt() have sane defaults even before it's approved.
    await db_helper.prep_table(
        envs.settings_db_schema,
        inserts=envs.settings_db_schema["inserts"],
        guild_id=guild.id,
    )
    if is_admin_guild:
        # The admin guild is auto-approved and never goes through
        # `/approve-guild`, so it needs its posting-task rows prepped
        # here instead - `/approve-guild` does the same for other guilds.
        await db_helper.ensure_guild_tasks_rows(guild.id)
        logger.info(f"Registered admin guild `{guild.name}` ({guild.id})")
    else:
        logger.info(f"Registered new pending guild `{guild.name}` ({guild.id})")
        await notify_admin_of_new_guild(guild)


async def notify_admin_of_new_guild(guild: discord.Guild, rejoined=False):
    "#autodoc skip#"
    if not config.ADMIN_CHANNEL_ID:
        return
    # TODO: i18n
    content = ""
    if rejoined:
        content += "🔔 Rejoined guild:\n"
    else:
        content += "🔔 New guild wants to use the bot:\n"
    content += (
        f"**{guild.name}** (`{guild.id}`)\n"
        f"Members: {guild.member_count}\n"
        f"Description: {guild.description}\n"
        f"Vanity url code: {guild.vanity_url_code}\n"
    )
    # Try to create an invite link to the new guild and append it to the
    # content, so the admin can jump straight to the guild.
    invite_url = None
    for channel in guild.text_channels:
        if not channel.permissions_for(guild.me).create_instant_invite:
            continue
        try:
            invite = await channel.create_invite(
                max_age=0,
                max_uses=0,
                unique=False,
                reason="Admin notification of new guild",
            )
            invite_url = invite.url
            break
        except discord.HTTPException as e:
            logger.debug(f"Could not create invite in `{channel.name}`: {e}")
            continue
    if invite_url:
        content += f"Invite link: {invite_url}\n"
    else:
        content += "Could not create an invite link for this guild.\n"
    content += (
        f"\nUse `/approve-guild guild_id:{guild.id}` in this channel to activate it."
    )
    await discord_commands.post_to_channel(config.ADMIN_CHANNEL_ID, content_in=content)


@config.bot.event
async def on_guild_join(guild: discord.Guild):
    """
    Called when the bot is added to a new guild.
    #autodoc skip#
    """
    logger.info(f"Joined new guild:\nName: {guild.name}\nGuild ID: {guild.id}")
    await register_guild(guild)


@config.bot.event
async def on_guild_remove(guild: discord.Guild):
    """
    Called when the bot is removed from a guild. Data is kept, not
    deleted - only the guild's status is updated, so re-adding the bot
    later does not require going through approval again.
    #autodoc skip#
    """
    logger.info(f"Removed from guild: `{guild.name}` ({guild.id})")
    await db_helper.update_fields(
        envs.guilds_db_schema,
        where=("guild_id", str(guild.id)),
        updates=("status", "removed"),
    )


@config.bot.event
async def on_ready():
    """
    When the bot is ready, it will notify in the log, register/reconcile
    every guild it's currently a member of (covers guilds joined while
    the bot was offline), and make sure the bot channel exists in every
    approved guild.
    #autodoc skip#
    """
    await config.bot.tree.set_translator(MyTranslator())
    logger.info(
        I18N.t(
            "main.msg.bot_connected",
            bot=config.bot.user,
            server=", ".join(guild.name for guild in config.bot.guilds),
        )
    )

    logger.debug("Checking guild registry db")
    await db_helper.prep_table(envs.guilds_db_schema)
    # `tasks_db_schema` is guild-scoped (see envs.py) - it is prepped per
    # guild in `register_guild()`/`approve_guild()` below and defensively
    # again in each posting cog's own `setup()`.
    if config.bot.get_cog("Sync") is None:
        await config.bot.add_cog(Sync(config.bot))
    logger.debug("Deleting old json files")
    if file_io.file_size(envs.cogs_status_file):
        logger.debug("Found old json file")
        file_io.remove_file(envs.cogs_status_file)

    for guild in config.bot.guilds:
        await register_guild(guild)

    await cogs.Cogs.load_and_clean_cogs_internal()
    if args.maintenance:
        logger.info("Maintenance mode activated", color="RED")
        await config.bot.change_presence(status=discord.Status.dnd)

    # Make sure that each approved guild's configured bot channel exists.
    # The channel name is the guild's own `bot_channel` setting, falling
    # back to the bot-wide default (config.BOT_CHANNEL) when unset.
    for guild in config.bot.guilds:
        if not await db_helper.is_guild_approved(guild.id):
            continue
        settings = await db_helper.get_output(
            envs.settings_db_schema, guild_id=guild.id, as_settings_json=True
        )
        bot_channel = settings.get("bot_channel") or config.BOT_CHANNEL
        channel_list = discord_commands.get_text_channel_list(guild) or {}
        if bot_channel in channel_list:
            continue
        logger.debug(
            f"Bot channel `{bot_channel}` does not exist in `{guild.name}`, creating..."
        )
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True),
        }
        async with db_helper.guild_locale_context(guild.id):
            # Permissions are applied via `overwrites=` at creation time,
            # so no follow-up set_permissions() call is needed.
            await guild.create_text_channel(
                name=str(bot_channel),
                topic=I18N.t(
                    "main.msg.create_log_channel_logging", botname=config.bot.user.name
                ),
                overwrites=overwrites,
            )


@config.bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: discord.app_commands.AppCommandError
):
    """
    Tree-wide error handler. Only meaningfully handles
    `discord.app_commands.CheckFailure` (raised by e.g.
    `discord_commands.is_owner()`, `is_owner_or_manage_guild()`, or
    `is_owner_or_has_permission()`) by replying with a "no permission"
    message - everything else falls back to the default behaviour (log
    and ignore), same as before this handler existed.
    `discord_commands.OwnerOnlyCheckFailure` (raised by `is_owner()`) is
    checked first, since it's a subclass of the generic
    `CheckFailure`, so it gets its own more precise message.
    #autodoc skip#
    """
    if isinstance(error, discord_commands.OwnerOnlyCheckFailure):
        msg = I18N.t("common.msg_owner_only")
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.errors.HTTPException as _error:
            logger.error(f"Could not send permission check error message: {_error}")
        return
    if isinstance(error, discord.app_commands.CheckFailure):
        msg = I18N.t("common.msg_no_manage_guild_permission")
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.errors.HTTPException as _error:
            logger.error(f"Could not send permission check error message: {_error}")
        return
    command = interaction.command
    if command is not None:
        logger.error(f"Ignoring exception in command `{command.name}`: {error}")
    else:
        logger.error(f"Ignoring exception in command tree: {error}")


class Sync(commands.Cog):
    "Administer syncing settings"

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    sync_group = discord.app_commands.Group(
        name="sync",
        # TODO: i18n
        # description=locale_str(I18N.t("stats.commands.groups.stats"))
        description="Sync slash commands",
    )

    @discord_commands.is_owner()
    @sync_group.command(
        name="global", description=locale_str(I18N.t("main.owner_only"))
    )
    async def sync_global(self, interaction: discord.Interaction):
        await config.bot.tree.sync()
        _cmd = ""
        for command in config.bot.tree.get_commands():
            slash_or_text = (
                "Slash Command"
                if isinstance(command, discord.app_commands.Command)
                else "Text Command"
            )
            _cmd += f"- {command.name} (Type: {slash_or_text})"
            if _cmd != "":
                _cmd += "\n"
        await interaction.response.send_message(
            # TODO: i18n
            f"Commands synched!\n{_cmd}",
            ephemeral=True,
        )
        return

    @discord_commands.is_owner()
    @sync_group.command(
        name="dev",
        description=locale_str(I18N.t("main.owner_only")),
    )
    async def sync_dev(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            content="✅💭 {}".format(I18N.t("main.commands.syncdev.msg_starting"))
        )
        config.bot.tree.copy_global_to(guild=interaction.guild)
        await config.bot.tree.sync(guild=interaction.guild)
        for command in config.bot.tree.get_commands():
            logger.debug(f"Checking {command.name}")
        await interaction.edit_original_response(
            content="✅✅ {}".format(I18N.t("main.commands.syncdev.msg_confirm"))
        )
        return


def _in_admin_guild(interaction: discord.Interaction) -> bool:
    return str(interaction.guild_id) == str(config.ADMIN_GUILD_ID)


guild_group = discord.app_commands.Group(
    name="guild",
    # TODO: i18n
    # description=locale_str(I18N.t("stats.commands.groups.stats")),
    description="Administrer guilder",
)


@discord_commands.is_owner()
@guild_group.command(name="approve", description=locale_str(I18N.t("main.owner_only")))
@discord.app_commands.autocomplete(guild_id=pending_guilds_autocomplete)
async def approve_guild(interaction: discord.Interaction, guild_id: str):
    "#autodoc skip#"
    await interaction.response.defer(ephemeral=True)
    if not _in_admin_guild(interaction):
        # TODO: i18n
        await interaction.followup.send(
            "This command can only be used in the admin guild.", ephemeral=True
        )
        return
    pending_guilds_db = await db_helper.get_output(
        envs.guilds_db_schema, select=("guild_name"), where=[("guild_id", guild_id)]
    )
    now = await get_dt(format="ISO8601")
    await db_helper.update_fields(
        envs.guilds_db_schema,
        where=("guild_id", guild_id),
        updates=[
            ("status", "approved"),
            ("approved_by", str(interaction.user.id)),
            ("approved_at", now),
        ],
    )
    await db_helper.prep_table(
        envs.settings_db_schema,
        inserts=envs.settings_db_schema["inserts"],
        guild_id=guild_id,
    )
    await db_helper.ensure_guild_tasks_rows(guild_id)
    # TODO: i18n
    await interaction.followup.send(
        f"✅ Approved guild {pending_guilds_db[0]['guild_name']} ({guild_id}).",
        ephemeral=True,
    )


class LeaveGuildConfirm_view(discord.ui.View):
    """
    Yes/no confirmation for `/leave_guild`. `value` is True when the
    owner confirmed, False when they cancelled, and stays None when the
    view timed out without a press.
    #autodoc skip#
    """

    def __init__(self, user_id: int, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.value = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only whoever ran the command may press the buttons
        if interaction.user.id != self.user_id:
            # TODO: i18n
            await interaction.response.send_message(
                "This confirmation isn't yours.", ephemeral=True
            )
            return False
        return True

    def disable_buttons(self):
        "#autodoc skip#"
        for _btn in self.children:
            _btn.disabled = True

    # TODO: i18n
    @discord.ui.button(label="Leave guild", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        "#autodoc skip#"
        self.value = True
        self.disable_buttons()
        await interaction.response.edit_message(view=self)
        self.stop()

    # TODO: i18n
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        "#autodoc skip#"
        self.value = False
        self.disable_buttons()
        await interaction.response.edit_message(view=self)
        self.stop()

    async def on_timeout(self):
        "#autodoc skip#"
        self.disable_buttons()


@discord_commands.is_owner()
@guild_group.command(name="leave", description=locale_str(I18N.t("main.owner_only")))
@discord.app_commands.autocomplete(guild_id=all_guilds_autocomplete)
async def leave_guild(interaction: discord.Interaction, guild_id: str):
    "#autodoc skip#"
    await interaction.response.defer(ephemeral=True)
    if not _in_admin_guild(interaction):
        # TODO: i18n
        await interaction.followup.send(
            "This command can only be used in the admin guild.", ephemeral=True
        )
        return
    if str(guild_id) == str(config.ADMIN_GUILD_ID):
        # Leaving the admin guild would lock the owner out of every
        # owner-only command - including this one.
        # TODO: i18n
        await interaction.followup.send(
            "❌ Refusing to leave the admin guild.", ephemeral=True
        )
        return
    try:
        guild = config.bot.get_guild(int(guild_id))
    except (TypeError, ValueError):
        # Someone typed free text instead of picking from the autocomplete
        guild = None
    if guild is None:
        # `all_guilds_autocomplete` lists every row in the guild registry,
        # including guilds the bot is no longer a member of.
        # TODO: i18n
        await interaction.followup.send(
            f"❌ The bot is not a member of a guild with id `{guild_id}`.",
            ephemeral=True,
        )
        return
    guilds_db = await db_helper.get_output(
        envs.guilds_db_schema,
        select=("guild_name"),
        where=[("guild_id", str(guild.id))],
    )
    guild_name = guilds_db[0]["guild_name"] if guilds_db else guild.name
    view = LeaveGuildConfirm_view(user_id=interaction.user.id)
    # TODO: i18n
    confirm_msg = await interaction.followup.send(
        f"⚠️ Leave guild **{guild_name}** (`{guild.id}`)?\n"
        "The guild's data is kept - its status is only set to `removed`. "
        "The bot has to be invited back in to rejoin.",
        view=view,
        ephemeral=True,
        wait=True,
    )
    await view.wait()
    if view.value is None:
        # TODO: i18n
        await confirm_msg.edit(
            content=f"⏲️ Timed out - still in {guild_name} ({guild.id}).", view=None
        )
        return
    if view.value is False:
        # TODO: i18n
        await confirm_msg.edit(
            content=f"❌ Cancelled - still in {guild_name} ({guild.id}).", view=None
        )
        return
    try:
        await guild.leave()
    except discord.HTTPException as e:
        logger.error(f"Could not leave guild `{guild_name}` ({guild.id}): {e}")
        # TODO: i18n
        await confirm_msg.edit(
            content=f"❌ Could not leave {guild_name} ({guild.id}): {e}", view=None
        )
        return
    logger.info(
        f"Left guild `{guild_name}` ({guild.id}) on request from `{interaction.user}`"
    )  # No db write here - `on_guild_remove` sets the status to `removed`.
    # TODO: i18n
    await confirm_msg.edit(
        content=f"✅ Left guild {guild_name} ({guild.id}).", view=None
    )


@discord_commands.is_owner()
@guild_group.command(name="list", description=locale_str(I18N.t("main.owner_only")))
async def list_guilds(
    interaction: discord.Interaction,
):
    "#autodoc skip#"
    await interaction.response.defer(ephemeral=True)
    if not _in_admin_guild(interaction):
        # TODO: i18n
        await interaction.followup.send(
            "This command can only be used in the admin guild.", ephemeral=True
        )
        return
    guilds = await db_helper.get_output(
        envs.guilds_db_schema,
        select=("guild_name", "status", "joined_at", "approved_at", "approved_by"),
        order_by=[("guild_name", "ASC")],
    )
    for guild in guilds:
        if guild["approved_by"] not in [None, ""]:
            guild["approved_by"] = get(
                interaction.guild.members, id=int(guild["approved_by"])
            )
        if guild["approved_at"] not in [None, ""]:
            guild["approved_at"] = await get_dt(
                dt=guild["approved_at"], format="datetime"
            )
        if guild["joined_at"] not in [None, ""]:
            guild["joined_at"] = await get_dt(dt=guild["joined_at"], format="datetime")
    text_out = "```{}```".format(
        tabulate(
            guilds,
            headers={
                "guild_name": "Name",
                "status": "Status",
                "joined_at": "Joined",
                "approved_at": "Approved",
                "approved_by": "Approved by",
            },
        )
    )
    await interaction.followup.send(text_out, ephemeral=True)


# This needs to be used to init the first sync so
# `syncglobal` and `syncdev` will be visible
@commands.is_owner()
@config.bot.command(name="synclocal")
async def synclocal(ctx):
    # sync to the guild where the command was used
    _reply = await ctx.reply(
        "💭💭 {}".format(I18N.t("main.commands.synclocal.msg_starting"))
    )
    # logger.debug('Clearing commands...')
    # config.bot.tree.clear_commands(guild=None)
    config.bot.tree.clear_commands(guild=ctx.guild)
    await _reply.edit(
        content="✅💭 {}".format(I18N.t("main.commands.synclocal.msg_cont_copy"))
    )
    # logger.debug('Copying global commands...')
    config.bot.tree.copy_global_to(guild=ctx.guild)
    # for command in config.bot.tree.get_commands():
    #    logger.debug(f'Checking {command.name}')
    logger.debug("Syncing...")
    await config.bot.tree.sync(guild=ctx.guild)
    await _reply.edit(
        content="✅✅ {}".format(I18N.t("main.commands.synclocal.msg_confirm"))
    )
    logger.debug("Done")


@commands.is_owner()
@config.bot.command(name="syncglobal")
async def syncglobal(ctx):
    _reply = await ctx.reply(
        "💭💭 {}".format(I18N.t("main.commands.syncglobal.msg_starting"))
    )
    logger.debug("Clearing commands...")
    config.bot.tree.clear_commands(guild=None)
    for command in config.bot.tree.get_commands():
        logger.debug(f"Checking {command.name}")
    logger.debug("Syncing...")
    await config.bot.tree.sync(guild=None)
    await _reply.edit(
        content="✅✅ {}".format(I18N.t("main.commands.syncglobal.msg_confirm"))
    )
    logger.debug("Done")


@commands.is_owner()
@config.bot.command(name="clearglobals")
async def clear_globals(ctx):
    logger.debug("Deleting global commands...")
    _reply = await ctx.reply(
        "💭 {}".format(I18N.t("main.commands.clearglobals.msg_starting"))
    )
    config.bot.tree.clear_commands(guild=None)
    await config.bot.tree.sync(guild=None)
    logger.debug("Commands deleted")
    await _reply.edit(
        content="✅ {}".format(I18N.t("main.commands.clearglobals.msg_confirm"))
    )


@commands.is_owner()
@config.bot.command(name="clearlocals")
async def clear_locals(ctx):
    logger.debug("Deleting local commands...")
    _reply = await ctx.reply(
        "💭 {}".format(I18N.t("main.commands.clearlocals.msg_starting"))
    )
    config.bot.tree.clear_commands(guild=ctx.guild)
    await config.bot.tree.sync(guild=ctx.guild)
    logger.debug("Commands deleted")
    await _reply.edit(
        content="✅ {}".format(I18N.t("main.commands.clearlocals.msg_confirm"))
    )


@config.bot.tree.command(
    name="version", description=locale_str(I18N.t("main.commands.version.command"))
)
async def get_version(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    version_in = file_io.read_json(envs.version_file)
    logger.debug(f"Got `version_in`: {version_in}")
    await interaction.followup.send(
        "Branch: {}\n"
        "Last commit message: {}\n"
        "Last commit: {}\n"
        "Last run number: {}".format(
            version_in["BRANCH"],
            version_in["LAST_COMMIT_MSG"],
            version_in["LAST_COMMIT"],
            version_in["LAST_RUN_NUMBER"],
        ),
        ephemeral=True,
    )
    return


# Commands
@config.bot.tree.command(
    name="ping", description=locale_str(I18N.t("main.commands.ping.command"))
)
async def ping(interaction: discord.Interaction):
    "Checks the bot latency"
    await interaction.response.send_message(
        f"Pong! {round(config.bot.latency * 1000)} ms", ephemeral=True
    )


@discord_commands.is_owner_or_has_permission("manage_messages")
@config.bot.tree.command(
    name="delete", description=locale_str(I18N.t("main.commands.delete.command"))
)
async def delete(interaction: discord.Interaction, amount: int):
    "Delete `amount` number of messages in the chat"
    if amount <= 0:
        await interaction.response.send_message(
            I18N.t("main.commands.delete.less_than_0"),
        )
    else:
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.purge(
            limit=amount, reason=I18N.t("main.commands.delete.log_confirm")
        )
        await interaction.followup.send(
            I18N.t("main.commands.delete.msg_confirm", amount=amount), ephemeral=True
        )
    return


@discord_commands.is_owner_or_has_permission("kick_members")
@config.bot.tree.command(
    name="kick", description=locale_str(I18N.t("main.commands.kick.command"))
)
async def kick(
    interaction: discord.Interaction,
    member: discord.Member = None,
    *,
    reason: str = None,
):
    """
    Kick a member from the server

    Parameters
    ------------
    member: discord.Member
        Name of Discord user you want to kick (default: None)
    reason: str
        Reason for kicking user (default: None)
    """
    await interaction.response.defer(ephemeral=True)
    try:
        await member.kick(reason=reason)
        await interaction.followup.send(
            I18N.t("main.commands.kick.msg_confirm", member=member), ephemeral=True
        )
    except Exception as _error:
        await interaction.followup.send(
            I18N.t("main.commands.kick.msg_failed", error=_error), ephemeral=True
        )


@discord_commands.is_owner_or_has_permission("ban_members")
@config.bot.tree.command(
    name="ban", description=locale_str(I18N.t("main.commands.ban.command"))
)
async def ban(
    interaction: discord.Interaction,
    member: discord.Member = None,
    *,
    reason: str = None,
):
    """
    Ban a member from the server

    Parameters
    ------------
    member: discord.Member
        Name of Discord user you want to ban (default: None)
    reason: str
        Reason for banning user (default: None)
    """
    await interaction.response.defer(ephemeral=True)
    try:
        await member.ban(reason=reason)
        await interaction.followup.send(
            I18N.t(
                "main.commands.ban.msg_confirm",
                member=member,
            ),
            ephemeral=True,
        )
    except Exception as _error:
        await interaction.followup.send(
            I18N.t("main.commands.ban.msg_failed", error=_error), ephemeral=True
        )


@discord_commands.is_owner_or_manage_guild()
@config.bot.tree.command(
    name="say", description=locale_str(I18N.t("main.commands.say.command"))
)
async def say(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    message_id: str = None,
):
    reply_msg = None
    logger.debug(f"`channel` is {channel} ({type(channel)})")
    if message_id:
        reply_msg = await discord_commands.get_message_obj(
            guild=interaction.guild, msg_id=message_id, channel_id=channel.id
        )
        logger.debug(f"Got `reply_msg`: {reply_msg}")
    modal_in = SayModal(
        title_in=I18N.t("main.commands.say.modal.title"), channel=channel
    )
    await interaction.response.send_modal(modal_in)
    await modal_in.wait()
    if reply_msg:
        await reply_msg.reply(modal_in.comment_out)
    elif channel:
        await channel.send(modal_in.comment_out)
    return


@discord_commands.is_owner_or_manage_guild()
@config.bot.tree.command(
    name="tasks", description=locale_str(I18N.t("main.commands.tasks.command"))
)
async def get_tasks_list(interaction: discord.Interaction):
    """
    Get a pretty list of this guild's own posting tasks and their status.
    #autodoc skip#
    """
    await interaction.response.defer(ephemeral=True)
    tasks_in_db = await db_helper.get_output(
        template_info=envs.tasks_db_schema,
        order_by=[("cog", "ASC"), ("task", "ASC")],
        guild_id=interaction.guild.id,
    )
    logger.debug(f"Got this from `tasks_in_db`: {tasks_in_db}")
    text_out = "```{}```".format(
        tabulate(
            tasks_in_db, headers={"cog": "Cog", "task": "Task", "status": "Status"}
        )
    )
    logger.debug(f"Returning:\n{text_out}")
    await interaction.followup.send(text_out, ephemeral=True)
    return


@discord_commands.is_owner()
@config.bot.tree.command(
    name="tasks-global",
    description=locale_str(I18N.t("main.commands.tasks_global.command")),
)
async def get_tasks_global_list(interaction: discord.Interaction):
    """
    Get a pretty, aggregated list of every approved guild's posting
    tasks and their status. Admin-guild only.
    #autodoc skip#
    """
    await interaction.response.defer(ephemeral=True)
    if not _in_admin_guild(interaction):
        await interaction.followup.send(
            I18N.t("main.commands.tasks_global.msg_not_admin_guild"), ephemeral=True
        )
        return
    approved_guilds = await db_helper.get_output(
        envs.guilds_db_schema,
        select=("guild_id", "guild_name"),
        where=("status", "approved"),
        order_by=[("guild_name", "ASC")],
    )
    rows = []
    for guild_row in approved_guilds:
        guild_tasks = await db_helper.get_output(
            template_info=envs.tasks_db_schema,
            order_by=[("cog", "ASC"), ("task", "ASC")],
            guild_id=guild_row["guild_id"],
        )
        for task in guild_tasks:
            rows.append(
                {
                    "guild_name": guild_row["guild_name"],
                    "cog": task["cog"],
                    "task": task["task"],
                    "status": task["status"],
                }
            )
    if len(rows) == 0:
        await interaction.followup.send(
            I18N.t("main.commands.tasks_global.msg_empty"), ephemeral=True
        )
        return
    table_text = tabulate(
        rows,
        headers={
            "guild_name": "Guild",
            "cog": "Cog",
            "task": "Task",
            "status": "Status",
        },
    )
    # Discord messages are capped at 2000 chars - split on line
    # boundaries and repeat the header/separator (the first two lines of
    # `tabulate`'s output) on every page.
    lines = table_text.split("\n")
    header = "\n".join(lines[0:2])
    pages = []
    current_page = header
    for line in lines[2:]:
        candidate = f"{current_page}\n{line}"
        if len(candidate) + 6 > 2000:
            pages.append(current_page)
            current_page = f"{header}\n{line}"
        else:
            current_page = candidate
    pages.append(current_page)
    for page in pages:
        await interaction.followup.send(f"```{page}```", ephemeral=True)
    return


@discord_commands.is_owner_or_manage_guild()
@config.bot.tree.command(
    name="language", description=locale_str(I18N.t("main.owner_only"))
)
@discord.app_commands.autocomplete(language=locales_autocomplete)
async def language(interaction: discord.Interaction, language: str):
    await interaction.response.defer(ephemeral=True)
    logger.debug(f"Setting language for `{interaction.guild.name}` to {language}")
    if language not in available_languages():
        # TODO: i18n
        await interaction.followup.send(
            f"`{language}` is not an available language.", ephemeral=True
        )
        return
    await db_helper.update_fields(
        envs.settings_db_schema,
        where=("setting", "language"),
        updates=("value", language),
        guild_id=interaction.guild.id,
    )
    async with db_helper.guild_locale_context(interaction.guild.id):
        await interaction.followup.send(
            I18N.t("main.commands.language.confirm_language_set", language=language),
            ephemeral=True,
        )
    return


async def _persist_bot_channel(guild: discord.Guild, name: str) -> None:
    "Store `name` as the guild's `bot_channel` setting. #autodoc skip#"
    await db_helper.update_fields(
        envs.settings_db_schema,
        where=("setting", "bot_channel"),
        updates=("value", name),
        guild_id=guild.id,
    )


class DuplicateChannelModal(discord.ui.Modal):
    """
    Lets the user pick an existing text channel to copy from and name the
    new bot channel. The new channel inherits the source channel's
    permission overwrites and category, and is placed right after the
    source in the channel list.
    #autodoc skip#
    """

    def __init__(self, default_name: str):
        # TODO: i18n
        super().__init__(title="Lag bot-kanal fra en eksisterende kanal")
        # Kept as an attribute so on_submit can read the picked channel.
        self.channel_select = discord.ui.ChannelSelect(
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
            required=True,
            # TODO: i18n
            placeholder="Velg kanalen tillatelsene skal kopieres fra",
        )
        self.add_item(
            discord.ui.Label(
                # TODO: i18n
                text="Kopier tillatelser fra:",
                component=self.channel_select,
            )
        )
        self.name_input = discord.ui.TextInput(
            # TODO: i18n
            label="Navn på den nye bot-kanalen",
            default=default_name,
            max_length=100,
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        # ChannelSelect.values holds partial AppCommandChannels; resolve the
        # full channel so we can read overwrites/category/position.
        picked = self.channel_select.values[0]
        source = interaction.guild.get_channel(picked.id)
        new_name = str(self.name_input.value).strip()
        if source is None:
            # TODO: i18n
            await interaction.followup.send(
                "Fant ikke kilde-kanalen. Prøv igjen.", ephemeral=True
            )
            return
        new_channel = await interaction.guild.create_text_channel(
            name=new_name,
            category=source.category,
            position=source.position + 1,
            overwrites=source.overwrites,
            # TODO: i18n
            reason="Oppretter bot-kanal (kopiert fra #{})".format(source.name),
        )
        await _persist_bot_channel(interaction.guild, new_name)
        # TODO: i18n
        await interaction.followup.send(
            "✅✅ Laget {} (tillatelser kopiert fra #{}) og satt som bot-kanal.".format(
                new_channel.mention, source.name
            ),
            ephemeral=True,
        )


class CreateBotChannelView(discord.ui.View):
    """
    Shown when the requested bot channel does not exist yet. Offers to
    duplicate an existing channel (opens `DuplicateChannelModal`), create a
    fresh empty channel, or cancel.
    #autodoc skip#
    """

    def __init__(self, channel_name: str):
        super().__init__(timeout=120)
        self.channel_name = channel_name

    # TODO: i18n button labels
    @discord.ui.button(
        # TODO: i18n
        label="Dupliser eksisterende",
        style=discord.ButtonStyle.secondary,
    )
    async def duplicate(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # A modal must be the response to this button interaction.
        await interaction.response.send_modal(
            DuplicateChannelModal(default_name=self.channel_name)
        )
        self.stop()

    @discord.ui.button(label="Lag helt ny", style=discord.ButtonStyle.secondary)
    async def fresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(
                read_messages=False
            ),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True),
        }
        new_channel = await interaction.guild.create_text_channel(
            name=self.channel_name,
            overwrites=overwrites,
            # TODO: i18n
            reason="Oppretter ny bot-kanal",
        )
        await _persist_bot_channel(interaction.guild, self.channel_name)
        await interaction.followup.send(
            # TODO: i18n
            "✅✅ Laget {} og satt som bot-kanal.".format(new_channel.mention),
            ephemeral=True,
        )
        self.stop()

    @discord.ui.button(label="Avbryt", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        # TODO: i18n
        await interaction.response.edit_message(
            content="Avbrutt. Lager ingen kanal.", view=None
        )
        self.stop()


@discord_commands.is_owner_or_manage_guild()
@config.bot.tree.command(
    name="bot_channel", description=locale_str(I18N.t("main.owner_only"))
)
async def set_bot_channel(interaction: discord.Interaction, bot_channel: str):
    await interaction.response.defer(ephemeral=True)
    logger.debug(f"Setting bot_channel for `{interaction.guild.name}` to {bot_channel}")
    channel_list = discord_commands.get_text_channel_list(interaction.guild) or {}
    if bot_channel not in channel_list:
        # Channel doesn't exist yet - let the user duplicate an existing
        # channel, create a fresh one, or cancel. Each button on the view
        # finishes the flow (creating the channel + storing the setting).
        # TODO: i18n
        await interaction.followup.send(
            "Kanalen #{} finnes ikke ennå. Hva vil du gjøre?".format(bot_channel),
            view=CreateBotChannelView(bot_channel),
            ephemeral=True,
        )
        return
    # Channel already exists - just store it as the guild's bot channel.
    await _persist_bot_channel(interaction.guild, bot_channel)
    # TODO: i18n
    await interaction.followup.send(
        "✅✅ Satt bot-kanal til #{}.".format(bot_channel),
        ephemeral=True,
    )
    return


@discord_commands.is_owner_or_manage_guild()
@config.bot.tree.command(
    name="timezone", description=locale_str(I18N.t("main.owner_only"))
)
@discord.app_commands.autocomplete(timezone=timezones_autocomplete)
async def timezone(interaction: discord.Interaction, timezone: str):
    await interaction.response.defer(ephemeral=True)
    logger.debug(f"Setting timezone for `{interaction.guild.name}` to {timezone}")
    await db_helper.update_fields(
        envs.settings_db_schema,
        where=("setting", "timezone"),
        updates=("value", timezone),
        guild_id=interaction.guild.id,
    )
    await interaction.followup.send(
        # TODO: i18n
        "Set timezone to `{}`".format(timezone),
        ephemeral=True,
    )
    return


def _has_manage_bot_profile_permission(interaction: discord.Interaction) -> bool:
    "#autodoc skip#"
    perms = interaction.user.guild_permissions
    return perms.administrator or perms.manage_nicknames


@config.bot.tree.command(
    name="set_profile",
    description=locale_str(I18N.t("main.commands.set_profile.command")),
)
async def set_profile(
    interaction: discord.Interaction,
    nickname: str = None,
    avatar: discord.Attachment = None,
    banner: discord.Attachment = None,
    bio: str = None,
):
    """
    Change the bot's nickname, avatar, banner or bio in this server.
    Requires the Administrator or Manage Nicknames permission.

    Parameters
    ------------
    nickname: str
        New nickname for the bot in this server (default: None)
    avatar: discord.Attachment
        New per-server avatar image for the bot (default: None)
    banner: discord.Attachment
        New per-server banner image for the bot (default: None)
    bio: str
        New per-server bio/about-me for the bot (default: None)
    """
    if not _has_manage_bot_profile_permission(interaction):
        await interaction.response.send_message(
            I18N.t("main.commands.set_profile.msg_no_permission"), ephemeral=True
        )
        return
    if nickname is None and avatar is None and banner is None and bio is None:
        await interaction.response.send_message(
            I18N.t("common.too_few_arguments"), ephemeral=True
        )
        return
    await interaction.response.defer(ephemeral=True)
    edits = {}
    if nickname is not None:
        edits["nick"] = nickname
    if avatar is not None:
        edits["avatar"] = await avatar.read()
    if banner is not None:
        edits["banner"] = await banner.read()
    if bio is not None:
        edits["bio"] = bio
    try:
        await interaction.guild.me.edit(**edits)
        await interaction.followup.send(
            I18N.t("main.commands.set_profile.msg_confirm"), ephemeral=True
        )
    except discord.HTTPException as _error:
        await interaction.followup.send(
            I18N.t("main.commands.set_profile.msg_failed", error=_error), ephemeral=True
        )
    return


@config.bot.tree.command(
    name="reset_profile",
    description=locale_str(I18N.t("main.commands.reset_profile.command")),
)
async def reset_profile(
    interaction: discord.Interaction,
    nickname: bool = False,
    avatar: bool = False,
    banner: bool = False,
    bio: bool = False,
):
    """
    Reset the bot's nickname, avatar, banner or bio in this server.
    Requires the Administrator or Manage Nicknames permission.

    Parameters
    ------------
    nickname: bool
        Reset nickname (default: False)
    avatar: bool
        Reset avatar (default: False)
    banner: bool
        Reset banner (default: False)
    bio: bool
        Reset bio (default: False)
    """
    if not _has_manage_bot_profile_permission(interaction):
        await interaction.response.send_message(
            I18N.t("main.commands.reset_profile.msg_no_permission"), ephemeral=True
        )
        return
    if nickname is False and avatar is False and banner is False and bio is False:
        await interaction.response.send_message(
            I18N.t("common.too_few_arguments"), ephemeral=True
        )
        return
    await interaction.response.defer(ephemeral=True)
    edits = {}
    if nickname is True:
        edits["nick"] = None
    if avatar is True:
        edits["avatar"] = None
    if banner is True:
        edits["banner"] = None
    if bio is True:
        edits["bio"] = None
    try:
        await interaction.guild.me.edit(**edits)
        await interaction.followup.send(
            I18N.t("main.commands.reset_profile.msg_confirm"), ephemeral=True
        )
    except discord.HTTPException as _error:
        await interaction.followup.send(
            I18N.t("main.commands.reset_profile.msg_failed", error=_error),
            ephemeral=True,
        )
    return


@discord_commands.is_owner_or_manage_guild()
@config.bot.tree.context_menu(
    name=locale_str(I18N.t("main.context_menu.edit_msg.name"))
)
async def edit_bot_say_msg(interaction: discord.Interaction, message: discord.Message):
    logger.debug(
        f"`message.author.id` {message.author.id} "
        f"({type(message.author.id)})) vs `config.bot.user.id` "
        f"{config.bot.user.id} ({type(config.bot.user.id)}))"
    )
    if message.author.id != config.bot.user.id:
        await interaction.response.send_message(
            I18N.t("main.context_menu.edit_msg.not_bot"), ephemeral=True
        )
        return
    modal_in = EditModal(
        title_in=I18N.t("main.context_menu.edit_msg.name"), comment_in=message.content
    )
    await interaction.response.send_modal(modal_in)
    await modal_in.wait()
    await message.edit(content=modal_in.comment_out)
    return


# Locale db is per-guild - created in `register_guild()` (see on_ready
# and on_guild_join above), not at import time here.
try:
    config.bot.run(config.DISCORD_TOKEN)
except Exception as _error:
    logger.error(f"Could not start bot: {_error}")
