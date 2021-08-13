#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord_rss import _config

def get_channel_list():
    channel_dict = {}
    for guild in _config.bot.guilds:
        if guild.name == _config.GUILD:
            # Get all channels and their IDs
            for channel in guild.text_channels:
                channel_dict[channel.name] = channel.id
    return channel_dict