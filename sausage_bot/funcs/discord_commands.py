#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from sausage_bot.funcs import _config, _vars


def get_text_channel_list():
    channel_dict = {}
    for guild in _config.bot.guilds:
        if str(guild.name).lower() == _config.GUILD.lower():
            # Get all channels and their IDs
            for channel in guild.text_channels:
                channel_dict[channel.name] = channel.id
    return channel_dict


async def post_to_channel(content_in, channel_in):
    # Post link to channel
    server_channels = get_text_channel_list()
    channel_out = _config.bot.get_channel(server_channels[channel_in])
    if channel_in in server_channels:
        await channel_out.send(content_in)
    else:
        log.log(
            _vars.CHANNEL_DOES_NOT_EXIST.format(
                channel_out
            )
        )
        return


async def edit_post(replace_content, replace_with, channel_in):
    # Replace content in post
    server_channels = get_text_channel_list()
    channel_out = _config.bot.get_channel(server_channels[channel_in])
    if channel_in in server_channels:
        async for msg in channel_in.history(limit=30):
            if str(msg.author.id) == _config.BOT_ID:
                if replace_content == msg.content:
                    await msg.edit(content=replace_with)
                    return
    else:
        log.log(
            _vars.CHANNEL_DOES_NOT_EXIST.format(
                channel_out
            )
        )
        return
