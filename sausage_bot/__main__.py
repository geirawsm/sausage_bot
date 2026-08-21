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
        self,
        style_in,
        label_in,
        default_in=None,
        required_in=None,
        placeholder_in=None,
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
                msg_out += I18N.t(
                    "main.context_menu.edit_msg.channel_errors",
                    errors=", ".join(comment_out["channel_errors"]),
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
                msg_out += I18N.t(
                    "main.context_menu.edit_msg.channel_errors",
                    errors=", ".join(comment_out["channel_errors"]),
                )

        self.comment_out = comment_out["text"]

        await interaction.response.send_message(msg_out, ephemeral=True)
        return

    async def on_error(self, interaction: discord.Interaction, error):
        logger.error(f"Error when editing message: {error}")
        self.error_out = error
        await interaction.response.send_message(
            I18N.t("main.context_menu.edit_msg.edit_error", error=error),
            ephemeral=True,
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


def guild_choice_label(guild_name, guild_id) -> str:
    """
    Label for a guild autocomplete choice: `name (id)`. Showing the id
    makes it obvious that the *value* behind a choice is the guild id,
    not the name. Discord caps choice labels at 100 characters, so the
    name is trimmed rather than the id.
    #autodoc skip#
    """
    suffix = " ({})".format(guild_id)
    name = str(guild_name or "")
    max_name_len = 100 - len(suffix)
    if len(name) > max_name_len:
        name = name[: max_name_len - 1] + "…"
    return "{}{}".format(name, suffix)


def guild_choice_matches(current: str, guild_name, guild_id) -> bool:
    """
    Whether a guild belongs in the autocomplete for what the user has
    typed so far. Both sides are lowercased - matching the typed text
    against a cased guild name meant a lowercase search returned no
    choices at all, which is what makes people type the guild name out
    in full instead of picking a choice.
    #autodoc skip#
    """
    haystack = "{} ({})".format(guild_name, guild_id).lower()
    return current.lower() in haystack


async def resolve_guild_row(guild_id: str) -> dict | None:
    """
    Look up a row in the guild registry by guild id, falling back to a
    case-insensitive guild name match.

    The guild autocompletes label their choices with the guild name but
    submit the guild id as the value. Typing the label instead of
    picking a choice therefore sends a guild *name* into a `guild_id`
    parameter, and matching is done here rather than in an SQL WHERE so
    that free text (quotes included) never reaches the query builder.

    Returns the matching row, or None when nothing matches.
    #autodoc skip#
    """
    all_guilds = await db_helper.get_output(envs.guilds_db_schema)
    if not all_guilds:
        return None
    wanted = str(guild_id).strip()
    for guild in all_guilds:
        if str(guild["guild_id"]) == wanted:
            return guild
    for guild in all_guilds:
        if str(guild["guild_name"] or "").lower() == wanted.lower():
            logger.debug(
                "Resolved `{}` to guild id `{}` by name".format(
                    wanted, guild["guild_id"]
                )
            )
            return guild
    return None


def resolve_guild_arg(guild_arg) -> discord.Guild | None:
    """
    Resolve a guild autocomplete value to a guild the bot is currently a
    member of, or None.

    Sibling to `resolve_guild_row()`, but answers a different question:
    that one looks in the guild *registry*, which also holds guilds the
    bot has left, while this one only ever returns a live
    `discord.Guild`. `/guild set_admin_guild` needs the live object -
    it has to read and possibly create channels there.

    Accepts a guild id or, since autocomplete never restricts what can
    be submitted, a typed guild name.
    #autodoc skip#
    """
    if guild_arg in (None, ""):
        return None
    wanted = str(guild_arg).strip()
    if wanted.isdigit():
        guild = config.bot.get_guild(int(wanted))
        if guild is not None:
            return guild
    for guild in config.bot.guilds:
        if str(guild.name).lower() == wanted.lower():
            return guild
    return None


async def pending_guilds_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    pending_guilds_db = await db_helper.get_output(
        template_info=envs.guilds_db_schema,
        where=[("status", "pending")],
        order_by=[("guild_name", "ASC")],
    )
    logger.debug(f"`pending_guilds_db`: {pending_guilds_db}")
    return [
        discord.app_commands.Choice(
            name=guild_choice_label(guild["guild_name"], guild["guild_id"]),
            value=guild["guild_id"],
        )
        for guild in pending_guilds_db
        if guild_choice_matches(current, guild["guild_name"], guild["guild_id"])
    ][:25]


async def all_guilds_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    all_guilds_db = await db_helper.get_output(
        template_info=envs.guilds_db_schema,
        order_by=[("guild_name", "ASC")],
    )
    logger.debug(f"`all_guilds_db`: {all_guilds_db}")
    return [
        discord.app_commands.Choice(
            name=guild_choice_label(guild["guild_name"], guild["guild_id"]),
            value=guild["guild_id"],
        )
        for guild in all_guilds_db
        if guild_choice_matches(current, guild["guild_name"], guild["guild_id"])
    ][:25]


# Marks an `admin_channel_autocomplete` choice as "create this channel"
# rather than "use this existing channel". Existing channels submit their
# id, so the prefix is what keeps a channel literally named like a
# snowflake from being ambiguous.
NEW_CHANNEL_PREFIX = "new:"


async def admin_guild_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    """
    Guilds the bot is a *member* of, for `/guild set_admin_guild`.

    Unlike `all_guilds_autocomplete` this reads `config.bot.guilds`
    rather than the registry: the admin guild has to be one the bot can
    actually read and post in, so guilds it has left don't belong here.
    #autodoc skip#
    """
    return [
        discord.app_commands.Choice(
            name=guild_choice_label(guild.name, guild.id),
            value=str(guild.id),
        )
        for guild in sorted(config.bot.guilds, key=lambda g: str(g.name).lower())
        if guild_choice_matches(current, guild.name, guild.id)
    ][:25]


def current_admin_guild() -> discord.Guild | None:
    """
    The guild `config.ADMIN_GUILD_ID` currently points at, or None when
    none is configured or the bot isn't in it.
    #autodoc skip#
    """
    return resolve_guild_arg(config.ADMIN_GUILD_ID)


def admin_channel_choices(
    guild: discord.Guild | None,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    """
    Autocomplete choices for a text channel in `guild`, shared by
    `/guild set_admin_guild` and `/guild set_admin_channel`.

    Existing channels submit their id. When what's typed doesn't name an
    existing channel, a "create this" choice is offered on top - the
    commands treat it as a new channel name and confirm before creating.
    Filtering on what's typed also means the 25 choice cap acts as a
    search limit rather than a ceiling on how many channels a guild may
    have.
    #autodoc skip#
    """
    if guild is None:
        return []
    typed = str(current or "").strip().lstrip("#")
    choices = [
        discord.app_commands.Choice(
            name="#{}".format(channel.name)[:100],
            value=str(channel.id),
        )
        for channel in guild.text_channels
        if typed.lower() in str(channel.name).lower()
    ][:24]
    already_exists = any(
        str(channel.name).lower() == typed.lower() for channel in guild.text_channels
    )
    if typed and not already_exists:
        choices.insert(
            0,
            discord.app_commands.Choice(
                name=I18N.t(
                    "main.commands.guild.admin_channel.ac_create_new",
                    channel=typed,
                )[:100],
                # Discord caps choice values at 100 chars, and so does a
                # channel name - trim the tail, the prefix has to survive.
                value="{}{}".format(NEW_CHANNEL_PREFIX, typed)[:100],
            ),
        )
    return choices[:25]


async def admin_channel_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    """
    Text channels in the guild picked in the `guild` parameter of
    `/guild set_admin_guild` - read off `interaction.namespace`, since
    the target guild is not the one the command is being run from. That
    is also why this can't be a `discord.ui.ChannelSelect` or a
    `TextChannel` parameter: both only ever resolve channels in the
    invoking guild.

    Returns nothing while `guild` is still empty. The user can type a
    channel name anyway - `set_admin_guild()` reports the missing guild.
    #autodoc skip#
    """
    guild = resolve_guild_arg(getattr(interaction.namespace, "guild", None))
    return admin_channel_choices(guild, current)


async def admin_channel_only_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    """
    Text channels in the guild that is *already* the admin guild, for
    `/guild set_admin_channel`. There is no `guild` parameter to read
    here - the target is whatever `config.ADMIN_GUILD_ID` points at.
    #autodoc skip#
    """
    return admin_channel_choices(current_admin_guild(), current)


async def register_guild(guild: discord.Guild):
    """
    Make sure `guild` has a row in the guild registry. New guilds are
    `pending` unless they are the configured ADMIN_GUILD_ID, which is
    auto-approved and never needs to go through `/approve-guild`.
    If guild is marked as `removed`, it resets to `pending` - unless it
    is the admin guild, which is auto-approved again on the way back in.
    Other existing rows are left untouched. Status change via
    `/approve-guild` or `on_guild_remove`.
    #autodoc skip#
    """
    # Defensive: on_ready() already preps this table, but on_guild_join()
    # can also reach this function directly - prep_table is a cheap,
    # idempotent CREATE TABLE IF NOT EXISTS.
    await db_helper.prep_table(envs.guilds_db_schema)
    existing_guilds = await db_helper.get_output(
        envs.guilds_db_schema, where=("guild_id", str(guild.id)), single=True
    )
    is_admin_guild = str(guild.id) == str(config.ADMIN_GUILD_ID)
    if existing_guilds:
        logger.info(existing_guilds)
        existing_status = existing_guilds["status"].lower()
        if is_admin_guild and existing_status != "approved":
            # The admin guild is auto-approved wherever it turns up in the
            # registry, not only the first time it's seen. Re-adding the
            # bot to it must not leave the guild that hosts
            # `/approve-guild` sitting in `pending`, unable to approve
            # itself back into service.
            #
            # `_approve_admin_guild()` calls back into `register_guild()`
            # when the row is missing - unreachable from here, since this
            # branch only runs when the row exists.
            await _approve_admin_guild(guild, config.BOT_ID)
            logger.info(f"Auto-approved admin guild `{guild.name}` ({guild.id})")
            await notify_admin_of_new_guild(
                guild,
                rejoined=existing_status == "removed",
                auto_approved=True,
            )
        elif existing_status == "removed":
            await db_helper.update_fields(
                envs.guilds_db_schema,
                where=("guild_id", str(guild.id)),
                updates=("status", "pending"),
            )
            await notify_admin_of_new_guild(guild, rejoined=True)
        return
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
        # Seeding the `admin_guild` table is deliberately *not* done here.
        # This branch is only reached the first time a guild is registered,
        # so an installation that has run before would never get a row.
        # `seed_admin_guild_from_env()` handles it from on_ready instead.
    else:
        logger.info(f"Registered new pending guild `{guild.name}` ({guild.id})")
        await notify_admin_of_new_guild(guild)


async def notify_admin_of_new_guild(
    guild: discord.Guild, rejoined=False, auto_approved=False
):
    "#autodoc skip#"
    if not config.ADMIN_CHANNEL_ID:
        return
    content = ""
    if rejoined:
        content += I18N.t("main.notify_new_guild.rejoined") + "\n"
    else:
        content += I18N.t("main.notify_new_guild.new") + "\n"
    content += (
        I18N.t(
            "main.notify_new_guild.details",
            guild_name=guild.name,
            guild_id=guild.id,
            member_count=guild.member_count,
            description=guild.description,
            vanity_url_code=guild.vanity_url_code,
        )
        + "\n"
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
        content += (
            I18N.t("main.notify_new_guild.invite_link", invite_url=invite_url) + "\n"
        )
    else:
        content += I18N.t("main.notify_new_guild.no_invite") + "\n"
    if auto_approved:
        content += "\n" + I18N.t("main.notify_new_guild.auto_approved")
    else:
        content += "\n" + I18N.t(
            "main.notify_new_guild.how_to_approve", guild_id=guild.id
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


async def seed_admin_guild_from_env() -> bool:
    """
    Write the env-configured admin guild into the empty `admin_guild`
    table, so a fresh install ends up with the same single row that
    `/guild set_admin_guild` would have written.

    Only called when the table is empty. A row that exists but does not
    validate is left alone on purpose - see `load_admin_guild_from_db()`.

    The env values are only seeded when the bot can actually see both the
    guild and the channel. Storing an unreachable pair would turn a
    typo in the env file into a db row that outlives the env file itself.

    Returns True when a row was written.
    #autodoc skip#
    """
    guild_id = str(config.ADMIN_GUILD_ID or "").strip()
    channel_id = str(config.ADMIN_CHANNEL_ID or "").strip()
    if not (guild_id.isdigit() and channel_id.isdigit()):
        logger.warning(
            f"Env ADMIN_GUILD_ID (`{guild_id}`) and ADMIN_CHANNEL_ID "
            f"(`{channel_id}`) must both be numeric ids to be stored in "
            "the database. Run `/guild set_admin_guild` instead."
        )
        return False
    guild = config.bot.get_guild(int(guild_id))
    if guild is None:
        logger.warning(
            f"Env ADMIN_GUILD_ID `{guild_id}` is not a guild the bot is in "
            "- not storing it in the database."
        )
        return False
    channel = guild.get_channel(int(channel_id))
    if channel is None:
        logger.warning(
            f"Env ADMIN_CHANNEL_ID `{channel_id}` does not exist in "
            f"`{guild.name}` - not storing it in the database."
        )
        return False
    if not await _persist_admin_guild(guild, channel):
        # `_persist_admin_guild` has already logged the failure. The env
        # values still apply for this run, they just are not persisted.
        return False
    logger.info(
        f"Admin guild from env stored in database: `{guild.name}` "
        f"({guild.id}), channel `#{channel.name}` ({channel.id}). The "
        "ADMIN_GUILD_ID/ADMIN_CHANNEL_ID env values are no longer needed."
    )
    return True


async def load_admin_guild_from_db() -> None:
    """
    Apply the `admin_guild` table to the running config, with the
    `ADMIN_GUILD_ID`/`ADMIN_CHANNEL_ID` env values as fallback.

    The table is the source of truth - `/guild set_admin_guild` writes
    it, and the env vars only bootstrap a fresh install. An empty table
    therefore leaves the env values alone and, when they point somewhere
    the bot can reach, `seed_admin_guild_from_env()` stores them as the
    first row.

    A row naming a guild the bot is no longer a member of, or a channel
    that has since been deleted, is left in the db but not applied. The
    env values are used instead and a warning is logged, since silently
    trusting a dangling row would point every admin notification at a
    channel that cannot receive it. `/guild set_admin_guild` is
    deliberately not gated on `_in_admin_guild()`, so the bot owner can
    always set a working one from wherever they are.

    Called from `on_ready()` *before* guilds are registered, because
    `register_guild()` decides auto-approval by comparing against
    `config.ADMIN_GUILD_ID`.
    #autodoc skip#
    """
    await db_helper.prep_table(envs.admin_guild_db_schema)
    admin_row = await db_helper.get_output(envs.admin_guild_db_schema, single=True)
    # Reset to the env values first, so this function is idempotent
    # rather than dependent on config still holding its import-time state.
    config.ADMIN_GUILD_ID = config.ENV_ADMIN_GUILD_ID
    config.ADMIN_CHANNEL_ID = config.ENV_ADMIN_CHANNEL_ID
    if not admin_row:
        logger.debug("No admin guild registered in db, using env values")
    else:
        db_guild_id = str(admin_row.get("guild_id") or "").strip()
        db_channel_id = str(admin_row.get("guild_channel") or "").strip()
        guild = None
        if db_guild_id.isdigit():
            guild = config.bot.get_guild(int(db_guild_id))
        channel = None
        if guild is not None and db_channel_id.isdigit():
            channel = guild.get_channel(int(db_channel_id))
        if guild is None:
            logger.warning(
                f"Admin guild `{db_guild_id}` from db is not a guild the bot is "
                "in - falling back to the env values. Run `/guild "
                "set_admin_guild` to point it somewhere the bot can reach."
            )
        elif channel is None:
            logger.warning(
                f"Admin channel `{db_channel_id}` no longer exists in "
                f"`{guild.name}` - falling back to the env values. Run "
                "`/guild set_admin_guild` to pick a new channel."
            )
        else:
            config.ADMIN_GUILD_ID = str(guild.id)
            config.ADMIN_CHANNEL_ID = str(channel.id)
            logger.info(
                f"Admin guild from db: `{guild.name}` ({guild.id}), "
                f"channel `#{channel.name}` ({channel.id})"
            )
    if config.ADMIN_GUILD_ID is None or config.ADMIN_CHANNEL_ID is None:
        # Not fatal - the bot runs fine, but new-guild notifications have
        # nowhere to go and every `_in_admin_guild()` command is
        # unreachable until this is set.
        logger.error(
            "No admin guild configured. Set ADMIN_GUILD_ID and "
            "ADMIN_CHANNEL_ID in the env file, or run `/guild "
            "set_admin_guild` to store one in the database."
        )
        return
    if not admin_row:
        # Runs on every start with an empty table, not just the first time
        # the admin guild happens to be registered, so an installation that
        # predates this gets its row too.
        await seed_admin_guild_from_env()


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

    # Has to happen before the `register_guild()` loop further down: that
    # decides auto-approval against `config.ADMIN_GUILD_ID`, which this
    # may replace with whatever `/guild set_admin_guild` last stored.
    await load_admin_guild_from_db()

    if config.bot.get_cog("Sync") is None:
        await config.bot.add_cog(Sync(config.bot))
    if config.bot.get_cog("Guild") is None:
        await config.bot.add_cog(Guild(config.bot))
    if config.bot.get_cog("Profile") is None:
        await config.bot.add_cog(Profile(config.bot))

    logger.debug("Deleting old json files")
    if file_io.file_exist(envs.cogs_status_file):
        logger.debug("Found old json file")
        file_io.remove_file(envs.cogs_status_file)

    for guild in config.bot.guilds:
        await register_guild(guild)

    await cogs.Cogs.load_and_clean_cogs_internal()

    # The loop refreshes the scraped user-agents `net_io.get_link()` uses.
    # It was declared but never started, so the headers file was never
    # written. Without an api key there is nothing to fetch, and `get_link`
    # falls back to aiohttp's own user-agent.
    if config.SCRAPEOPS_API_KEY and not get_random_user_agent.is_running():
        get_random_user_agent.start()

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
                    "main.msg.create_log_channel_logging",
                    botname=config.bot.user.name,
                ),
                overwrites=overwrites,
            )


@config.bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: discord.app_commands.AppCommandError,
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
        description=locale_str(I18N.t("main.commands.sync.group_desc")),
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
            I18N.t("main.commands.sync.msg_confirm_list", commands=_cmd),
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
            await interaction.response.send_message(
                I18N.t("main.commands.guild.leave.not_yours"), ephemeral=True
            )
            return False
        return True

    def disable_buttons(self):
        "#autodoc skip#"
        for _btn in self.children:
            _btn.disabled = True

    @discord.ui.button(
        label=I18N.t("main.commands.guild.leave.btn_leave"),
        style=discord.ButtonStyle.danger,
    )
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        "#autodoc skip#"
        self.value = True
        self.disable_buttons()
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(
        label=I18N.t("common.cancel"),
        style=discord.ButtonStyle.secondary,
    )
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        "#autodoc skip#"
        self.value = False
        self.disable_buttons()
        await interaction.response.edit_message(view=self)
        self.stop()

    async def on_timeout(self):
        "#autodoc skip#"
        self.disable_buttons()


class CreateAdminChannelConfirm_view(discord.ui.View):
    """
    Confirmation for creating a brand new admin channel in
    `/guild set_admin_guild`.

    The `channel` parameter is autocompleted but not restricted, so a
    typo arrives as free text and would otherwise silently create a
    channel nobody asked for. `value` is True when the owner confirmed,
    False when they cancelled, and stays None when the view timed out
    without a press.
    #autodoc skip#
    """

    def __init__(self, user_id: int, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.value = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only whoever ran the command may press the buttons
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                I18N.t("main.commands.guild.admin_channel.not_yours"),
                ephemeral=True,
            )
            return False
        return True

    def disable_buttons(self):
        "#autodoc skip#"
        for _btn in self.children:
            _btn.disabled = True

    @discord.ui.button(
        label=I18N.t("main.commands.guild.admin_channel.btn_create"),
        style=discord.ButtonStyle.green,
    )
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        "#autodoc skip#"
        self.value = True
        self.disable_buttons()
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(
        label=I18N.t("common.cancel"),
        style=discord.ButtonStyle.secondary,
    )
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        "#autodoc skip#"
        self.value = False
        self.disable_buttons()
        await interaction.response.edit_message(view=self)
        self.stop()

    async def on_timeout(self):
        "#autodoc skip#"
        self.disable_buttons()


async def resolve_admin_channel(
    interaction: discord.Interaction,
    target_guild: discord.Guild,
    channel_arg: str,
):
    """
    Turn the `channel` argument of `/guild set_admin_guild` and
    `/guild set_admin_channel` into a text channel in `target_guild`,
    creating one after confirmation when the name doesn't exist yet.

    The argument is autocompleted but not restricted, so it arrives as a
    channel id picked from the list, the name of an existing channel, or
    the name of one that doesn't exist. Only the last creates anything,
    and only once the owner confirms - a typo submits exactly like a
    deliberate new name.

    Returns `(channel, prompt)`. `channel` is None when the flow ended
    without one; the user has already been told why, so callers should
    just return. `prompt` is the confirmation message when one was
    shown, so callers can edit their own prompt into the final answer
    instead of stacking a second message below it.
    #autodoc skip#
    """
    channel_arg = str(channel_arg or "").strip()
    if not channel_arg:
        await interaction.followup.send(
            I18N.t("main.commands.guild.admin_channel.msg_no_channel"),
            ephemeral=True,
        )
        return None, None
    target_channel = None
    new_channel_name = None
    if channel_arg.startswith(NEW_CHANNEL_PREFIX):
        # Picked the "create this" choice from the autocomplete
        new_channel_name = channel_arg[len(NEW_CHANNEL_PREFIX) :].strip()
    elif channel_arg.isdigit():
        # An id can only come from the autocomplete, so a miss here means
        # the channel was deleted mid-command - not a name to create a
        # channel from.
        target_channel = target_guild.get_channel(int(channel_arg))
        if target_channel is None:
            await interaction.followup.send(
                I18N.t(
                    "main.commands.guild.admin_channel.msg_channel_not_found",
                    channel=channel_arg,
                    guild_name=target_guild.name,
                ),
                ephemeral=True,
            )
            return None, None
    else:
        wanted_name = channel_arg.lstrip("#")
        target_channel = get(target_guild.text_channels, name=wanted_name)
        if target_channel is None:
            new_channel_name = wanted_name
    if target_channel is not None and not isinstance(
        target_channel, discord.TextChannel
    ):
        await interaction.followup.send(
            I18N.t(
                "main.commands.guild.admin_channel.msg_not_text_channel",
                channel=target_channel.name,
            ),
            ephemeral=True,
        )
        return None, None
    if not new_channel_name:
        return target_channel, None
    view = CreateAdminChannelConfirm_view(user_id=interaction.user.id)
    confirm_msg = await interaction.followup.send(
        I18N.t(
            "main.commands.guild.admin_channel.confirm_create",
            channel=new_channel_name,
            guild_name=target_guild.name,
            guild_id=target_guild.id,
        ),
        view=view,
        ephemeral=True,
        wait=True,
    )
    await view.wait()
    if view.value is None:
        await confirm_msg.edit(
            content=I18N.t(
                "main.commands.guild.admin_channel.msg_timeout",
                channel=new_channel_name,
            ),
            view=None,
        )
        return None, confirm_msg
    if view.value is False:
        await confirm_msg.edit(
            content=I18N.t(
                "main.commands.guild.admin_channel.msg_cancelled",
                channel=new_channel_name,
            ),
            view=None,
        )
        return None, confirm_msg
    try:
        async with db_helper.guild_locale_context(target_guild.id):
            target_channel = await discord_commands.create_missing_channel(
                target_guild,
                channel_name=new_channel_name,
                topic=I18N.t(
                    "main.msg.create_log_channel_logging",
                    botname=config.bot.user.name,
                ),
            )
    except discord.HTTPException as e:
        logger.error(
            f"Could not create `{new_channel_name}` in "
            f"`{target_guild.name}` ({target_guild.id}): {e}"
        )
        await confirm_msg.edit(
            content=I18N.t(
                "main.commands.guild.admin_channel.msg_create_failed",
                channel=new_channel_name,
                error=e,
            ),
            view=None,
        )
        return None, confirm_msg
    if target_channel is None:
        # `create_missing_channel` returns None when it decided the
        # channel already existed - it was checked above, so this means
        # the two disagree rather than that all is well
        logger.error(
            f"No channel object back after creating `{new_channel_name}` "
            f"in `{target_guild.name}` ({target_guild.id})"
        )
        await confirm_msg.edit(
            content=I18N.t(
                "main.commands.guild.admin_channel.msg_create_failed",
                channel=new_channel_name,
                error="-",
            ),
            view=None,
        )
        return None, confirm_msg
    return target_channel, confirm_msg


async def _persist_admin_guild(
    guild: discord.Guild, channel: discord.abc.GuildChannel
) -> bool:
    """
    Store `guild`/`channel` as the bot's admin guild and apply it to the
    running config straight away, so `_in_admin_guild()` and the
    new-guild notifications follow along without a restart.
    `load_admin_guild_from_db()` picks the same row up on the next start.

    `admin_guild` holds a single row and `guild_id` is its primary key,
    so the table is emptied and re-inserted rather than updated in place.

    Returns True when the row was written, False when the insert failed.
    A failed write leaves the running config untouched rather than
    claiming an admin guild that is not stored anywhere - callers are
    expected to report that instead of confirming a change that did not
    happen. `--not-write-database` is not a failure: nothing is written,
    but the config still follows along so the rest of the run behaves.
    #autodoc skip#
    """
    await db_helper.prep_table(envs.admin_guild_db_schema)
    await db_helper.empty_table(envs.admin_guild_db_schema)
    written = await db_helper.insert_many_all(
        template_info=envs.admin_guild_db_schema,
        inserts=[(str(guild.id), str(guild.name), str(channel.id))],
    )
    if written is False:
        logger.error(
            f"Could not store admin guild `{guild.name}` ({guild.id}) with "
            f"channel `#{channel.name}` ({channel.id}) in the database"
        )
        return False
    config.ADMIN_GUILD_ID = str(guild.id)
    config.ADMIN_CHANNEL_ID = str(channel.id)
    return True


async def _approve_admin_guild(guild: discord.Guild, approved_by: int) -> None:
    """
    Make sure the new admin guild is `approved` in the guild registry,
    the same way `register_guild()` auto-approves the env-configured one.
    Without this the admin guild could sit as `pending` with no task
    rows, which would leave its own posting cogs inactive.

    A guild that is already approved keeps its original approver and
    timestamp.
    #autodoc skip#
    """
    guild_row = await resolve_guild_row(str(guild.id))
    if guild_row is None:
        logger.warning(
            f"`{guild.name}` ({guild.id}) was missing from the guild registry "
            "- registering it before approving"
        )
        await register_guild(guild)
        guild_row = await resolve_guild_row(str(guild.id))
    if guild_row is None or guild_row.get("status") != "approved":
        await db_helper.update_fields(
            envs.guilds_db_schema,
            where=("guild_id", str(guild.id)),
            updates=[
                ("status", "approved"),
                ("approved_by", str(approved_by)),
                ("approved_at", await get_dt(format="ISO8601")),
            ],
        )
    await db_helper.prep_table(
        envs.settings_db_schema,
        inserts=envs.settings_db_schema["inserts"],
        guild_id=guild.id,
    )
    await db_helper.ensure_guild_tasks_rows(guild.id)


class Guild(commands.Cog):
    "Administer guild settings"

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    guild_group = discord.app_commands.Group(
        name="guild",
        description=locale_str(I18N.t("main.commands.guild.group_desc")),
    )

    @discord_commands.is_owner()
    @guild_group.command(
        name="approve", description=locale_str(I18N.t("main.owner_only"))
    )
    @discord.app_commands.autocomplete(guild_id=pending_guilds_autocomplete)
    async def approve_guild(self, interaction: discord.Interaction, guild_id: str):
        "#autodoc skip#"
        await interaction.response.defer(ephemeral=True)
        if not _in_admin_guild(interaction):
            await interaction.followup.send(
                I18N.t("main.commands.tasks_global.msg_not_admin_guild"),
                ephemeral=True,
            )
            return
        guild_row = await resolve_guild_row(guild_id)
        if guild_row is None:
            # Nothing is written before this point on purpose: approving an
            # unknown id used to UPDATE nothing, create a bogus
            # `db/guild_<garbage>/` directory and only then crash on an empty
            # result.
            logger.error(f"No guild in the registry matches `{guild_id}`")
            await interaction.followup.send(
                I18N.t(
                    "main.commands.guild.approve.msg_not_found",
                    guild_id=guild_id,
                ),
                ephemeral=True,
            )
            return
        # Whatever was submitted, from here on work with the registry's own id
        guild_id = str(guild_row["guild_id"])
        guild_name = guild_row["guild_name"]
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
        await interaction.followup.send(
            I18N.t(
                "main.commands.guild.approve.msg_confirm",
                guild_name=guild_name,
                guild_id=guild_id,
            ),
            ephemeral=True,
        )

    @discord_commands.is_owner()
    @guild_group.command(
        name="leave", description=locale_str(I18N.t("main.owner_only"))
    )
    @discord.app_commands.autocomplete(guild_id=all_guilds_autocomplete)
    async def leave_guild(self, interaction: discord.Interaction, guild_id: str):
        "#autodoc skip#"
        await interaction.response.defer(ephemeral=True)
        if not _in_admin_guild(interaction):
            await interaction.followup.send(
                I18N.t("main.commands.tasks_global.msg_not_admin_guild"),
                ephemeral=True,
            )
            return
        if str(guild_id) == str(config.ADMIN_GUILD_ID):
            # Leaving the admin guild would lock the owner out of every
            # owner-only command - including this one.
            await interaction.followup.send(
                I18N.t("main.commands.guild.leave.msg_refuse_admin"),
                ephemeral=True,
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
            await interaction.followup.send(
                I18N.t(
                    "main.commands.guild.leave.msg_not_member",
                    guild_id=guild_id,
                ),
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
        confirm_msg = await interaction.followup.send(
            I18N.t(
                "main.commands.guild.leave.confirm_prompt",
                guild_name=guild_name,
                guild_id=guild.id,
            ),
            view=view,
            ephemeral=True,
            wait=True,
        )
        await view.wait()
        if view.value is None:
            await confirm_msg.edit(
                content=I18N.t(
                    "main.commands.guild.leave.msg_timeout",
                    guild_name=guild_name,
                    guild_id=guild.id,
                ),
                view=None,
            )
            return
        if view.value is False:
            await confirm_msg.edit(
                content=I18N.t(
                    "main.commands.guild.leave.msg_cancelled",
                    guild_name=guild_name,
                    guild_id=guild.id,
                ),
                view=None,
            )
            return
        try:
            await guild.leave()
        except discord.HTTPException as e:
            logger.error(f"Could not leave guild `{guild_name}` ({guild.id}): {e}")
            await confirm_msg.edit(
                content=I18N.t(
                    "main.commands.guild.leave.msg_failed",
                    guild_name=guild_name,
                    guild_id=guild.id,
                    error=e,
                ),
                view=None,
            )
            return
        logger.info(
            f"Left guild `{guild_name}` ({guild.id}) on request from `{interaction.user}`"
        )  # No db write here - `on_guild_remove` sets the status to `removed`.
        await confirm_msg.edit(
            content=I18N.t(
                "main.commands.guild.leave.msg_confirm",
                guild_name=guild_name,
                guild_id=guild.id,
            ),
            view=None,
        )

    @discord_commands.is_owner()
    @guild_group.command(name="list", description=locale_str(I18N.t("main.owner_only")))
    async def list_guilds(
        self,
        interaction: discord.Interaction,
    ):
        "#autodoc skip#"
        await interaction.response.defer(ephemeral=True)
        if not _in_admin_guild(interaction):
            await interaction.followup.send(
                I18N.t("main.commands.tasks_global.msg_not_admin_guild"),
                ephemeral=True,
            )
            return
        guilds = await db_helper.get_output(
            envs.guilds_db_schema,
            select=(
                "guild_name",
                "guild_id",
                "status",
                "joined_at",
                "approved_at",
                "approved_by",
            ),
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
                guild["joined_at"] = await get_dt(
                    dt=guild["joined_at"], format="datetime"
                )
        text_out = "```{}```".format(
            tabulate(
                guilds,
                # TODO: i18n
                headers={
                    "guild_name": "Name",
                    "guild_id": "Guild ID",
                    "status": "Status",
                    "joined_at": "Joined",
                    "approved_at": "Approved",
                    "approved_by": "Approved by",
                },
            )
        )
        await interaction.followup.send(text_out, ephemeral=True)

    @discord_commands.is_owner()
    @guild_group.command(
        name="set_admin_guild", description=locale_str(I18N.t("main.owner_only"))
    )
    @discord.app_commands.autocomplete(
        guild=admin_guild_autocomplete,
        channel=admin_channel_autocomplete,
    )
    async def set_admin_guild(
        self,
        interaction: discord.Interaction,
        guild: str,
        channel: str,
    ):
        """
        Point the bot's admin guild/channel at another guild.

        Both parameters are autocompleted, and neither is restricted to
        its suggestions - `channel` accepts a channel id picked from the
        list, the name of an existing channel, or the name of one to
        create. Creating is confirmed first, since a typo is
        indistinguishable from a deliberate new name.

        Not gated on `_in_admin_guild()`, unlike the other owner-only
        guild commands: this is the command that fixes a wrong admin
        guild, so requiring the admin guild to be right would lock the
        owner out of the only way back.
        #autodoc skip#
        """
        await interaction.response.defer(ephemeral=True)
        target_guild = resolve_guild_arg(guild)
        if target_guild is None:
            await interaction.followup.send(
                I18N.t(
                    "main.commands.guild.set_admin_guild.msg_not_member",
                    guild=guild,
                ),
                ephemeral=True,
            )
            return
        target_channel, confirm_msg = await resolve_admin_channel(
            interaction, target_guild, channel
        )
        if target_channel is None:
            # `resolve_admin_channel` has already explained why
            return
        if not await _persist_admin_guild(target_guild, target_channel):
            # `_persist_admin_guild` logged the reason and left the running
            # config alone, so nothing was changed anywhere.
            failed_out = I18N.t("main.commands.guild.set_admin_guild.msg_db_failed")
            if confirm_msg is not None:
                await confirm_msg.edit(content=failed_out, view=None)
            else:
                await interaction.followup.send(failed_out, ephemeral=True)
            return
        await _approve_admin_guild(target_guild, interaction.user.id)
        logger.info(
            f"Admin guild set to `{target_guild.name}` ({target_guild.id}), "
            f"channel `#{target_channel.name}` ({target_channel.id}) "
            f"by `{interaction.user}`"
        )
        text_out = I18N.t(
            "main.commands.guild.set_admin_guild.msg_confirm",
            guild_name=target_guild.name,
            guild_id=target_guild.id,
            channel=target_channel.name,
        )
        if confirm_msg is not None:
            await confirm_msg.edit(content=text_out, view=None)
        else:
            await interaction.followup.send(text_out, ephemeral=True)

    @discord_commands.is_owner()
    @guild_group.command(
        name="set_admin_channel", description=locale_str(I18N.t("main.owner_only"))
    )
    @discord.app_commands.autocomplete(channel=admin_channel_only_autocomplete)
    async def set_admin_channel(
        self,
        interaction: discord.Interaction,
        channel: str,
    ):
        """
        Move the admin channel within the guild that is already the
        admin guild. `/guild set_admin_guild` is the one that changes
        which guild that is.

        `channel` is autocompleted but not restricted, so it takes a
        channel id picked from the list, the name of an existing
        channel, or the name of one to create - creating is confirmed
        first, the same as in `/guild set_admin_guild`.

        Gated on `_in_admin_guild()`, unlike `/guild set_admin_guild`:
        this only ever touches the admin guild's own channel, so there
        is no lockout to escape from. A wrong *guild* is still fixed
        with `/guild set_admin_guild` from anywhere.
        #autodoc skip#
        """
        await interaction.response.defer(ephemeral=True)
        if not _in_admin_guild(interaction):
            await interaction.followup.send(
                I18N.t("main.commands.tasks_global.msg_not_admin_guild"),
                ephemeral=True,
            )
            return
        target_guild = current_admin_guild()
        if target_guild is None:
            # `_in_admin_guild` compares ids, so this only happens when
            # the bot is no longer in its own admin guild
            await interaction.followup.send(
                I18N.t("main.commands.guild.set_admin_channel.msg_no_admin_guild"),
                ephemeral=True,
            )
            return
        target_channel, confirm_msg = await resolve_admin_channel(
            interaction, target_guild, channel
        )
        if target_channel is None:
            # `resolve_admin_channel` has already explained why
            return
        # Same single-row write as `/guild set_admin_guild` - the guild
        # is unchanged, so there is nothing to approve or prep here.
        if not await _persist_admin_guild(target_guild, target_channel):
            failed_out = I18N.t("main.commands.guild.set_admin_channel.msg_db_failed")
            if confirm_msg is not None:
                await confirm_msg.edit(content=failed_out, view=None)
            else:
                await interaction.followup.send(failed_out, ephemeral=True)
            return
        logger.info(
            f"Admin channel set to `#{target_channel.name}` "
            f"({target_channel.id}) in `{target_guild.name}` "
            f"({target_guild.id}) by `{interaction.user}`"
        )
        text_out = I18N.t(
            "main.commands.guild.set_admin_channel.msg_confirm",
            guild_name=target_guild.name,
            channel=target_channel.name,
        )
        if confirm_msg is not None:
            await confirm_msg.edit(content=text_out, view=None)
        else:
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
    # No `clear_commands()` here. It only empties the tree in memory, so
    # clearing before syncing pushed an empty set to Discord and deleted
    # every global command instead of registering them - `syncglobal` did
    # exactly what `clearglobals` does. `sync()` already removes commands
    # that are no longer in the tree, so pushing the tree as-is is enough.
    for command in config.bot.tree.get_commands():
        logger.debug(f"Checking {command.name}")
    logger.debug("Syncing...")
    synced = await config.bot.tree.sync(guild=None)
    logger.debug(f"Synced {len(synced)} global commands")
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
    name="version",
    description=locale_str(I18N.t("main.commands.version.command")),
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
    name="delete",
    description=locale_str(I18N.t("main.commands.delete.command")),
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
            I18N.t("main.commands.delete.msg_confirm", amount=amount),
            ephemeral=True,
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
            I18N.t("main.commands.kick.msg_confirm", member=member),
            ephemeral=True,
        )
    except Exception as _error:
        await interaction.followup.send(
            I18N.t("main.commands.kick.msg_failed", error=_error),
            ephemeral=True,
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
            tasks_in_db,
            headers={"cog": "Cog", "task": "Task", "status": "Status"},
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
            I18N.t("main.commands.tasks_global.msg_not_admin_guild"),
            ephemeral=True,
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
        await interaction.followup.send(
            I18N.t("main.commands.language.msg_not_available", language=language),
            ephemeral=True,
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
        super().__init__(title=I18N.t("main.commands.bot_channel.create_modal.title"))
        # Kept as an attribute so on_submit can read the picked channel.
        self.channel_select = discord.ui.ChannelSelect(
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
            required=True,
            placeholder=I18N.t(
                "main.commands.bot_channel.create_modal.select_placeholder"
            ),
        )
        self.add_item(
            discord.ui.Label(
                text=I18N.t("main.commands.bot_channel.create_modal.copy_from_label"),
                component=self.channel_select,
            )
        )
        self.name_input = discord.ui.TextInput(
            label=I18N.t("main.commands.bot_channel.create_modal.name_label"),
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
            await interaction.followup.send(
                I18N.t("main.commands.bot_channel.create_modal.source_not_found"),
                ephemeral=True,
            )
            return
        new_channel = await interaction.guild.create_text_channel(
            name=new_name,
            category=source.category,
            position=source.position + 1,
            overwrites=source.overwrites,
            reason=I18N.t(
                "main.commands.bot_channel.create_modal.reason",
                source=source.name,
            ),
        )
        await _persist_bot_channel(interaction.guild, new_name)
        await interaction.followup.send(
            I18N.t(
                "main.commands.bot_channel.create_modal.msg_confirm",
                channel=new_channel.mention,
                source=source.name,
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

    @discord.ui.button(
        label=I18N.t("main.commands.bot_channel.btn_duplicate"),
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

    @discord.ui.button(
        label=I18N.t("main.commands.bot_channel.btn_fresh"),
        style=discord.ButtonStyle.secondary,
    )
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
            reason=I18N.t("main.commands.bot_channel.reason_fresh"),
        )
        await _persist_bot_channel(interaction.guild, self.channel_name)
        await interaction.followup.send(
            I18N.t(
                "main.commands.bot_channel.msg_confirm_fresh",
                channel=new_channel.mention,
            ),
            ephemeral=True,
        )
        self.stop()

    @discord.ui.button(
        label=I18N.t("common.cancel"),
        style=discord.ButtonStyle.danger,
    )
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content=I18N.t("main.commands.bot_channel.cancelled"), view=None
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
        await interaction.followup.send(
            I18N.t("main.commands.bot_channel.msg_not_exist", channel=bot_channel),
            view=CreateBotChannelView(bot_channel),
            ephemeral=True,
        )
        return
    # Channel already exists - just store it as the guild's bot channel.
    await _persist_bot_channel(interaction.guild, bot_channel)
    await interaction.followup.send(
        I18N.t("main.commands.bot_channel.msg_confirm", channel=bot_channel),
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
        I18N.t("main.commands.timezone.msg_confirm", timezone=timezone),
        ephemeral=True,
    )
    return


def _has_manage_bot_profile_permission(
    interaction: discord.Interaction,
) -> bool:
    "#autodoc skip#"
    perms = interaction.user.guild_permissions
    return perms.administrator or perms.manage_nicknames


class Profile(commands.Cog):
    "Administer bot profile"

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    profile_group = discord.app_commands.Group(
        name="profile",
        description=locale_str(I18N.t("main.commands.profile.group_desc")),
    )

    @profile_group.command(
        name="set",
        description=locale_str(I18N.t("main.commands.set_profile.command")),
    )
    async def set_profile(
        self,
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
                I18N.t("main.commands.set_profile.msg_no_permission"),
                ephemeral=True,
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
                I18N.t("main.commands.set_profile.msg_failed", error=_error),
                ephemeral=True,
            )
        return

    @profile_group.command(
        name="reset",
        description=locale_str(I18N.t("main.commands.reset_profile.command")),
    )
    async def reset_profile(
        self,
        interaction: discord.Interaction,
    ):
        """
        Reset all customizable attributes of the bot on this server (nickname, avatar, banner, bio).
        Requires the Administrator or Manage Nicknames permission.
        """
        if not _has_manage_bot_profile_permission(interaction):
            await interaction.response.send_message(
                I18N.t("main.commands.reset_profile.msg_no_permission"),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.guild.me.edit(
                nick=None, avatar=None, banner=None, bio=None
            )
            await interaction.followup.send(
                # TODO: Sjekk at denne stemmer
                I18N.t("main.commands.reset_profile.msg_confirm"),
                ephemeral=True,
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
        title_in=I18N.t("main.context_menu.edit_msg.name"),
        comment_in=message.content,
    )
    await interaction.response.send_modal(modal_in)
    await modal_in.wait()
    await message.edit(content=modal_in.comment_out)
    return


# Locale db is per-guild - created in `register_guild()` (see on_ready
# and on_guild_join above), not at import time here.
if config.DISCORD_TOKEN != "":
    try:
        config.bot.run(config.DISCORD_TOKEN)
    except Exception as _error:
        logger.error(f"Could not start bot: {_error}")
else:
    logger.error("DISCORD_TOKEN is not set in .env-file or docker envs")
