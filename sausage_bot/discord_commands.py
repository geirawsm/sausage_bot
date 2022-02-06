#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from sausage_bot import _config


def get_channel_list():
    channel_dict = {}
    for guild in _config.bot.guilds:
        if guild.name == _config.GUILD:
            # Get all channels and their IDs
            for channel in guild.text_channels:
                channel_dict[channel.name] = channel.id
    return channel_dict


def is_admin(ctx):
    try:
        return ctx.message.author.guild_permissions.administrator
    except(AttributeError):
        return False


def is_bot_owner(ctx):
    if str(ctx.message.author) == _config.BOT_OWNER:
        return True
    else:
        return False