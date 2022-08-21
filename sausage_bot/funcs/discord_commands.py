#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from datetime import datetime

from sausage_bot.funcs import _config, _vars, file_io

from ..log import log
#
import sys
#


def get_guild():
    for guild in _config.bot.guilds:
        if str(guild.name).lower() == _config.GUILD.lower():
            log.log_more(f'Got guild {guild} ({type(guild)})')
            return guild
        else:
            log.log(_vars.GUILD_NOT_FOUND)
            return None


def get_text_channel_list():
    channel_dict = {}
    guild = get_guild()
    # Get all channels and their IDs
    for channel in guild.text_channels:
        channel_dict[channel.name] = channel.id
    return channel_dict


def get_voice_channel_list():
    channel_dict = {}
    guild = get_guild()
    # Get all channels and their IDs
    for channel in guild.voice_channels:
        channel_dict[channel.name] = channel.id
    return channel_dict


def get_scheduled_events():
    guild = get_guild()
    event_dict = {}
    if guild.scheduled_events is None:
        log.log(_vars.AUTOEVENT_NO_EVENTS_LISTED)
        return None
    for event in guild.scheduled_events:
        _event = guild.get_scheduled_event(event.id)
        epoch = _event.start_time.astimezone().timestamp()
        # Maintain a counter for the epoch in case of duplicates
        epoch_dup = {}
        if epoch in epoch_dup:
            epoch_dup[epoch] += 1
            epoch = f'{epoch}_{epoch_str}'
        else:
            epoch_str = str(epoch).zfill(2)
            epoch_dup[epoch] = 1
        epoch = f'{epoch_str}'
        event_dict[epoch] = {
            'name': _event.name,
            'start': _event.start_time.astimezone(),
            'id': _event.id,
            'users': _event.user_count
        }
    return event_dict


def get_sorted_scheduled_events():
    # Sort the dict based on epoch
    events_in = get_scheduled_events()
    if len(events_in) == 0:
        return None
    else:
        headers = {
            'name': 'KAMP',
            'start': 'DATO',
            'users': 'INTR.',
            'id': 'ID'
        }
        try:
            event_dict = dict(sorted(events_in.items()))
        except Exception as e:
            log.log(str(e))
            return None
        lengths = file_io.get_max_item_lengths(headers, event_dict)
        temp_line = '{name:{name_len}} | {start:{start_len}} | '\
            '{users:{users_len}} | {id:{id_len}} '
        # Add headers
        _h = headers
        _l = lengths
        out = temp_line.format(
            name=_h['name'], start=_h['start'], users=_h['users'],
            id=_h['id'], name_len=_l['name'], start_len=_l['start'],
            users_len=_l['users'], id_len=_l['id']
        )
        out += '\n'
        for item in event_dict:
            _e = event_dict[item]
            _id = _e['id']
            _name = _e['name']
            _start = _e['start'].strftime('%-d. %B, kl. %H:%M')
            _users = _e['users']
            out += temp_line.format(
                name=_name, start=_start, users=_users, id=_id,
                id_len=lengths['id'], name_len=lengths['name'],
                start_len=lengths['start'], users_len=lengths['users']
            )
            if item != list(event_dict)[-1]:
                out += '\n'
        out = '```{}```'.format(out)
        return out


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
        async for msg in channel_out.history(limit=30):
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


if __name__ == "__main__":
    pass
    print(get_guild(), (type(get_guild())))