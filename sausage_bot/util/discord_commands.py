#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from sausage_bot.util import config, mod_vars, file_io

from ..log import log

#
import sys
#

def get_guild():
    'Get the active guild object'
    for guild in config.bot.guilds:
        if str(guild.name).lower() == config.GUILD.lower():
            log.log_more(f'Got guild {guild} ({type(guild)})')
            return guild
        else:
            log.log(mod_vars.GUILD_NOT_FOUND)
            return None


def get_text_channel_list():
    'Get a dict of all text channels and their ID\'s'
    channel_dict = {}
    guild = get_guild()
    # Get all channels and their IDs
    for channel in guild.text_channels:
        channel_dict[channel.name] = channel.id
    return channel_dict


def channel_exist(channel_in):
    'Check if channel actually exist on server'
    all_channels = get_text_channel_list()
    if channel_in in all_channels:
        return True
    else:
        return False


def get_voice_channel_list():
    'Get a dict of all voice channels and their ID\'s'
    channel_dict = {}
    guild = get_guild()
    # Get all channels and their IDs
    for channel in guild.voice_channels:
        channel_dict[channel.name] = channel.id
    return channel_dict


def get_scheduled_events():
    'Get all scheduled events from server'
    guild = get_guild()
    event_dict = {}
    if guild.scheduled_events is None:
        log.log(mod_vars.AUTOEVENT_NO_EVENTS_LISTED)
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
    'Get a sorted list of events and prettify it'
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
            # events_in/get_scheduled_events() already describes the error
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


def get_roles():
    'Get a dict of all roles on server and their ID\'s'
    roles_dict = {}
    guild = get_guild()
    # Get all roles and their IDs
    for role in guild.roles:
        roles_dict[role.name] = {
            'name': role.name,
            'id': role.id,
            'members': len(role.members),
            'premium': role.is_premium_subscriber(),
            'is_default': role.is_default(),
            'bot_managed': role.is_bot_managed()
        }
    log.debug(f'Got these roles:\n{roles_dict}')
    return roles_dict


async def post_to_channel(
    channel_in, content_in=None,
    content_embed_in=None
):
    'Post `content_in` in plain text or `content_embed_in` to channel `channel_in`'
    server_channels = get_text_channel_list()
    if channel_in in server_channels:
        channel_out = config.bot.get_channel(server_channels[channel_in])
        if content_in:
            await channel_out.send(content_in)
        elif content_embed_in:
            # TODO Add embed function, should be a dict
            embed_json = {
                'title': 'Sample Embed',
                'url': 'https://realdrewdata.medium.com/',
                'description': 'This is an embed that will show how to '
                'build an embed and the different components',
                'color': 0xFF5733
            }
            await channel_out.send(
                embed=discord.Embed.from_dict(embed_json)
            )
    else:
        log.log(
            mod_vars.POST_TO_NON_EXISTING_CHANNEL.format(
                channel_in
            )
        )
        return None


async def replace_post(replace_content, replace_with, channel_in):
    '''
    Look through the bot's messages for `replace_content` in channel
    `channel_in` and replace it with `replace_with.`
    '''
    server_channels = get_text_channel_list()
    channel_out = config.bot.get_channel(server_channels[channel_in])
    if channel_in in server_channels:
        async for msg in channel_out.history(limit=30):
            if str(msg.author.id) == config.BOT_ID:
                if replace_content == msg.content:
                    await msg.edit(content=replace_with)
                    return
    else:
        log.log(
            mod_vars.CHANNEL_DOES_NOT_EXIST.format(
                channel_out
            )
        )
        return


async def update_stats_post(stats_info, stats_channel):
    'Replace content in stats-post'
    server_channels = get_text_channel_list()
    if stats_channel in server_channels:
        channel_out = config.bot.get_channel(server_channels[stats_channel])
        found_stats_msg = False
        async for msg in channel_out.history(limit=10):
            log.debug(f'Got msg: ({msg.author.id}) {msg.content}')
            if str(msg.author.id) == config.BOT_ID:
                if 'Serverstats' in str(msg.content):
                    log.debug('Found post with `Serverstats:`, editing...')
                    await msg.edit(content=stats_info)
                    found_stats_msg = True
                    return
        if found_stats_msg is False:
            log.debug('Found post with `Serverstats:`, editing...')
            await channel_out.send(stats_info)


if __name__ == "__main__":
    pass
