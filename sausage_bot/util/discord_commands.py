#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"discord_commands: Helper functions for discord commands"

import discord
from discord.utils import get
from tabulate import tabulate
import re

from sausage_bot.util import config, envs, file_io
from sausage_bot.util.datetime_handling import get_dt
from sausage_bot.util.i18n import I18N

logger = config.logger


class OwnerOnlyCheckFailure(discord.app_commands.CheckFailure):
    """
    Raised by `is_owner()` when the invoking user is not the bot owner.
    A dedicated subclass of `discord.app_commands.CheckFailure` so the
    tree-level error handler in `__main__.py` can reply with a precise
    "bot owner only" message instead of the more general
    `common.msg_no_manage_guild_permission` used for the other checks.
    #autodoc skip#
    """


def is_owner_or_manage_guild():
    """
    App command check: allow the bot owner, or anyone with the "Manage
    Server" (`manage_guild`) permission in the guild the command is used
    in. Used to gate per-guild posting-task controls (start/stop for
    rss/youtube/stats/barca_news/quotes) so server admins can manage
    their own guild's background posting without needing bot-owner
    access. A `discord.app_commands.CheckFailure` raised by this is
    caught by the tree-level error handler in `__main__.py`, which
    replies with `common.msg_no_manage_guild_permission`.
    #autodoc skip#
    """

    async def predicate(interaction: discord.Interaction) -> bool:
        if await interaction.client.is_owner(interaction.user):
            return True
        return interaction.user.guild_permissions.manage_guild

    return discord.app_commands.check(predicate)


def is_owner():
    """
    App command check: allow only the bot owner. `discord.ext.commands`'
    own `commands.is_owner()` only works as a check on prefix commands -
    it silently does nothing useful on `app_commands` (slash commands),
    so this is the slash-command-safe equivalent for genuine bot-/
    cross-guild-administration commands (sync, guild approval, global
    task control, and the shared background loops' `*_restart`
    commands). Raises `OwnerOnlyCheckFailure` (a `CheckFailure`
    subclass) on rejection, rather than just returning `False`, so the
    tree-level error handler in `__main__.py` can reply with a precise
    "bot owner only" message.
    #autodoc skip#
    """

    async def predicate(interaction: discord.Interaction) -> bool:
        if await interaction.client.is_owner(interaction.user):
            return True
        raise OwnerOnlyCheckFailure()

    return discord.app_commands.check(predicate)


def is_owner_or_has_permission(permission: str):
    """
    App command check: allow the bot owner, or anyone with the named
    Discord permission (e.g. `"kick_members"`, `"ban_members"`,
    `"manage_messages"`) in the guild the command is used in. Used for
    real member-/message-moderation commands, which should be gated on
    Discord's own precise moderation permissions rather than the
    broader `manage_guild`. A `discord.app_commands.CheckFailure` raised
    by this is caught by the tree-level error handler in `__main__.py`.
    #autodoc skip#
    """

    async def predicate(interaction: discord.Interaction) -> bool:
        if await interaction.client.is_owner(interaction.user):
            return True
        return getattr(interaction.user.guild_permissions, permission, False)

    return discord.app_commands.check(predicate)


async def get_message_obj(guild: discord.Guild, msg_id: int, channel_id: int) -> dict:
    """
    Get a message object

    Parameters
    ------------
    guild: discord.Guild
        The guild the channel/message belongs to
    msg_id: int
        The message ID to look for
    channel_id: int
        Channel to get message from (default: None)
    """

    logger.debug(f"Getting channel with id `{channel_id}` ({type(channel_id)})")
    _channel = guild.get_channel(int(channel_id))
    logger.debug(f"Got channel `{_channel}`")
    try:
        if isinstance(msg_id, list) and len(msg_id) == 1:
            msg_id = msg_id[0]
        logger.debug(f"Getting message with id `{msg_id}` ({type(msg_id)})")
        msg_out = await _channel.fetch_message(int(msg_id))
        logger.debug(f"Got msg_out `{msg_out}`")
    except discord.errors.NotFound:
        msg_out = None
    return msg_out


def get_text_channel_list(guild: discord.Guild):
    """
    Get a dict of all text channels and their ID's
    #autodoc skip#
    """
    channel_dict = {}
    if guild is None:
        return None
    # Get all channels and their IDs
    for channel in guild.text_channels:
        channel_dict[channel.name] = channel.id
    return channel_dict


def channel_exist(guild: discord.Guild, channel_in):
    """
    Check if channel actually exist on server
    #autodoc skip#
    """
    all_channels = get_text_channel_list(guild)
    return channel_in in all_channels


async def create_missing_channel(
    guild: discord.Guild,
    channel_id=None,
    channel_name=None,
    topic=None,
    overwrites=None,
):
    channel_info = channel_name if channel_name else channel_id
    logger.debug("Checking if channel {} exists".format(channel_info))
    missing = None
    _guild = guild
    if channel_id:
        if get(_guild.text_channels, id=int(channel_id)) is None:
            missing = True
            logger.info(f"Could not find channel with id {channel_id}")
    elif not channel_id and channel_name:
        if get(_guild.text_channels, name=str(channel_id)) is None:
            missing = True
            logger.info(f"Could not find channel with name {channel_id}")
    else:
        logger.error(
            "Both 'channel_id' and 'channel_name' is None. This needs to be fixed."
        )
        return None
    if not missing:
        return
    if missing:
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
        channel_obj = await _guild.create_text_channel(
            name=channel_name, topic=topic, overwrites=overwrites
        )
        return channel_obj
    else:
        logger.error("Something unexpected went wrong in this function")
        return missing


def get_voice_channel_list(guild: discord.Guild):
    """
    Get a dict of all voice channels and their ID's
    #autodoc skip#
    #"""
    channel_dict = {}
    # Get all channels and their IDs
    for channel in guild.voice_channels:
        channel_dict[channel.name] = channel.id
    return channel_dict


async def get_scheduled_events(guild: discord.Guild):
    """
    Get all scheduled events from server
    #autodoc skip#
    """
    event_dict = {}
    if guild.scheduled_events is None:
        logger.info(envs.AUTOEVENT_NO_EVENTS_LISTED)
        return None
    logger.debug(f"`guild.scheduled_events`: {guild.scheduled_events}")
    _epochs = {}
    for event in guild.scheduled_events:
        _event = guild.get_scheduled_event(event.id)
        logger.debug(f"`_event`: {_event}")
        _dt = _event.start_time.astimezone()
        _dt_pend = await get_dt(format="datetimetextday", dt=_dt)
        epoch = int(_event.start_time.astimezone().timestamp())
        if epoch not in _epochs:
            _epochs[epoch] = 1
        elif epoch in _epochs:
            _epochs[epoch] += 1
        epoch_id = "{}-{}".format(epoch, _epochs[epoch])
        logger.debug(f"`epoch_id`: {epoch_id}")
        event_dict[epoch_id] = {
            "name": _event.name,
            "epoch": epoch,
            "start": _dt_pend,
            "id": _event.id,
            "users": _event.user_count,
        }
    return event_dict


async def get_sorted_scheduled_events(guild: discord.Guild):
    """
    Get a sorted list of events and prettify it
    #autodoc skip#
    """
    # Sort the dict based on epoch
    events_in = await get_scheduled_events(guild)
    logger.debug(f"`events_in`: {events_in}")
    if len(events_in) == 0:
        return None
    try:
        event_dict = dict(sorted(events_in.items()))
        logger.debug(f"`event_dict` is sorted: {event_dict}")
    except Exception as e:
        # events_in/get_scheduled_events() already describes the error
        logger.error(str(e))
        return None
    sched_dict = {"match": [], "start": [], "interest": [], "id": []}
    for event in event_dict:
        sched_dict["match"].append(event_dict[event]["name"])
        sched_dict["start"].append(event_dict[event]["start"])
        sched_dict["interest"].append(event_dict[event]["users"])
        sched_dict["id"].append(event_dict[event]["id"])
    out = tabulate(
        sched_dict,
        headers=[
            I18N.t("discord_commands.get_sorted_scheduled_events.headers.match"),
            I18N.t("discord_commands.get_sorted_scheduled_events.headers.date"),
            I18N.t("discord_commands.get_sorted_scheduled_events.headers.interest"),
            I18N.t("discord_commands.get_sorted_scheduled_events.headers.id"),
        ],
        numalign="center",
    )
    out = "```{}```".format(out)
    return out


def get_roles(guild: discord.Guild, hide_empties=None, filter_bots=None, hide_roles=None):
    """
    Get a dict of all roles on server and their ID's
    #autodoc skip#
    """
    hide_empties = eval(hide_empties) if hide_empties else False
    filter_bots = eval(filter_bots) if filter_bots else False
    logger.debug(f"hide_empties: {hide_empties} {type(hide_empties)}")
    logger.debug(f"filter_bots: {filter_bots} {type(filter_bots)}")
    logger.debug(f"hide_roles: {hide_roles} {type(hide_roles)}")
    # Get all roles and their IDs
    roles_dict = {}
    for role in guild.roles:
        if hide_empties is True and len(role.members) <= 0:
            continue
        if filter_bots and role.is_bot_managed():
            continue
        if hide_roles and str(role.id) in hide_roles:
            continue
        roles_dict[role.name.lower()] = {
            "name": role.name,
            "id": role.id,
            "members": len(role.members),
            "premium": role.is_premium_subscriber(),
            "is_default": role.is_default(),
            "bot_managed": role.is_bot_managed(),
        }
    logger.debug("Got these roles: {}".format(", ".join(name for name in roles_dict)))
    return roles_dict


async def post_to_channel(
    channel_id: int, content_in=None, embed_in=None, files_in=None, view=None
) -> discord.message.Message:
    """
    Post `content_in` in plain text or `embed_in` to channel
    `channel_id`
    """
    if embed_in and isinstance(embed_in, dict):
        embed_in = discord.Embed.from_dict(embed_in)
    channel_out = config.bot.get_channel(int(channel_id))
    try:
        msg_out = await channel_out.send(
            content=content_in, embed=embed_in, files=files_in, view=view
        )
        return msg_out
    except discord.errors.HTTPException as e:
        logger.error(
            f"{e} - this is the offending message:\n"
            f"`content`: {content_in}\n`embed`: {embed_in}\n`view`: {view}"
        )
    return None


async def replace_post(guild: discord.Guild, replace_content, replace_with, channel_in):
    """
    Look through the bot's messages for `replace_content` in channel
    `channel_in` and replace it with `replace_with.`
    #autodoc skip#
    """
    channel_out = guild.get_channel(int(channel_in))
    async for msg in channel_out.history(limit=30):
        if str(msg.author.id) == config.BOT_ID:
            if isinstance(replace_content, str):
                if replace_content in msg.content:
                    await msg.edit(content=replace_with)
                    return
            elif isinstance(replace_content, list) and any(
                _cont in msg.content for _cont in replace_content
            ):
                await msg.edit(content=replace_with)
                return
    return


async def remove_stats_post(guild: discord.Guild, stats_channel):
    """
    Remove stats-post
    #autodoc skip#
    """
    server_channels = get_text_channel_list(guild)
    if stats_channel in server_channels:
        logger.debug(f"Found stats channel {stats_channel}")
        channel_out = config.bot.get_channel(server_channels[stats_channel])
        found_stats_msg = False
        async for msg in channel_out.history(limit=10):
            logger.debug(f"Got msg: ({msg.author.id}) {msg.content[0:50]}...")
            if str(msg.author.id) == config.BOT_ID and "Serverstats sist" in str(
                msg.content
            ):
                logger.debug("Found post with `Serverstats sist`, removing...")
                await msg.delete()
                found_stats_msg = True
                return
        if found_stats_msg is False:
            logger.debug("No stats post found")


async def log_to_bot_channel(guild: discord.Guild, content_in=None):
    "Messages you want to send directly to a specific channel"
    log_channel = config.BOT_CHANNEL
    logger.debug(f"`log_channel` er {log_channel}")
    channel_out = guild.get_channel(int(get_text_channel_list(guild)[log_channel]))
    msg_out = await channel_out.send(content=content_in)
    return msg_out


def get_user_channel_role_id(guild: discord.Guild, id_in):
    if re.match(r"\d{19,22}", id_in):
        object_out = None
        # Try user
        object_out = get(guild.members, id=int(id_in))
        if object_out is None:
            # Try role
            object_out = get(guild.roles, id=int(id_in))
        if object_out is None:
            # Try channel
            object_out = get(guild.channels, id=int(id_in))
        return object_out


def get_user_channel_role_name(guild: discord.Guild, name_in):
    if isinstance(name_in, str):
        object_out = None
        # Try user
        object_out = get(guild.members, name=name_in)
        if object_out is None:
            # Try role
            object_out = get(guild.roles, name=name_in)
        if object_out is None:
            # Try channel
            object_out = get(guild.channels, name=name_in)
        return object_out


def check_user_channel_role(guild: discord.Guild, text_in):
    def check_discord_username(username_in):
        if isinstance(username_in, re.Match):
            username_in = username_in.group(0)
        logger.debug(f"Got username_in: {username_in}")
        _user_in = username_in.strip().replace("@", "").replace('"', "")
        logger.debug(f"Stripped and fixed _user_in: {_user_in}")
        user_obj = get(guild.members, name=_user_in)
        logger.debug(f"Got user_obj: {user_obj}")
        return user_obj

    def check_similar_discord_usernames(
        username_in, similar_floor=None, similar_roof=None
    ):
        _members = [member.name for member in guild.members]
        logger.debug(f"Comparing {username_in} with {_members}")
        similars = file_io.check_similarity(
            username_in, _members, ratio_floor=similar_floor, ratio_roof=similar_roof
        )
        return similars

    def check_discord_channel(channel_in):
        if isinstance(channel_in, re.Match):
            channel_in = channel_in.group(0)
        logger.debug(f"Got channel_in: {channel_in}")
        _channel_in = channel_in.strip().replace("#", "")
        logger.debug(f"Stripped and fixed _channel_in: {_channel_in}")
        channel_obj = get(guild.channels, name=_channel_in)
        logger.debug(f"Got channel_obj: {channel_obj}")
        return channel_obj

    def check_discord_roles(rolename_in):
        if isinstance(rolename_in, re.Match):
            rolename_in = rolename_in.group(0)
        logger.debug(f"Got rolename_in: {rolename_in}")
        _role_in = rolename_in.strip().replace("@", "").replace('"', "")
        logger.debug(f"Stripped and fixed _role_in: {_role_in}")
        role_obj = get(guild.roles, name=_role_in)
        logger.debug(f"Got role_obj: {role_obj}")
        return role_obj

    # Check for @'s (users or roles)
    _users = re.finditer(r"\"(?<!<)@([\w\-_\' ]+)\"|(?<!<)@[\w\-_\']+", text_in)
    username_errors = []
    for _user in _users:
        logger.debug(f"`_user`: {_user.group(0)}")
        # Check if username exist on discord server
        user_obj = check_discord_username(_user)
        # If it is not found, add to `username_errors`
        if user_obj is None:
            logger.debug("Appending to username_errors")
            # Add username to error list
            username_errors.append(_user)
        else:
            logger.debug(f"Got this text:\n{text_in}")
            logger.debug(f"Want to replace `{_user}`")
            text_in = text_in.replace(
                str(_user.group(0)).strip(), "<@{}>".format(user_obj.id)
            )
    logger.debug(f"`text_in` after user check: {text_in}")
    # Check for #'s (channels)
    _channels = re.finditer(
        r"(?<!<)#[\w\-_\d『』︰┃・「」┇《》【】╏〚〛〘〙〈〉]+", text_in
    )
    channel_errors = []
    for _channel in _channels:
        logger.debug(f"`_channel`: {_channel.group(0)}")
        # Check if channel exist on discord server
        channel_obj = check_discord_channel(_channel)
        # If it is not found, add to `channel_errors`
        if channel_obj is None:
            logger.debug("Appending to channel_errors")
            # Add channel to error list
            channel_errors.append(_channel)
        else:
            logger.debug(f"Got this text:\n{text_in}")
            logger.debug(f"Want to replace `{_channel}`")
            text_in = text_in.replace(
                str(_channel.group(0)).strip(), "<#{}>".format(channel_obj.id)
            )
    logger.debug(f"`text_in` after channel check: {text_in}")
    logger.debug(f"username_errors: {username_errors}")
    if len(username_errors) > 0:
        for _user in enumerate(username_errors):
            logger.debug(f"Checking {_user[1].group(0)} ({_user})")
            logger.debug("Check as a user")
            user_check = _user[1].group(0).strip().replace("@", "").replace('"', "")
            similar_users = check_similar_discord_usernames(
                username_in=user_check, similar_floor=0.7, similar_roof=0.95
            )
            logger.debug(f"similar_users: {similar_users}")
            if similar_users is not False:
                user_obj = check_discord_username(similar_users)
                logger.debug(f"Want to replace `{str(similar_users)}`")
                text_in = text_in.replace(
                    str(_user[1].group(0)).strip(), "<@{}>".format(user_obj.id)
                )
                username_errors.pop(_user[0])
            else:
                logger.debug("Check as a role")
                role_check = _user[1].group(0).strip().replace("@", "").replace('"', "")
                role_obj = check_discord_roles(role_check)
                logger.debug(f"Want to replace `{str(role_obj)}`")
                text_in = text_in.replace(
                    str(_user[1].group(0)).strip(), "<@&{}>".format(role_obj.id)
                )
                username_errors.pop(_user[0])
    return {
        "text": text_in,
        "username_errors": username_errors,
        "channel_errors": channel_errors,
    }


if __name__ == "__main__":
    pass
