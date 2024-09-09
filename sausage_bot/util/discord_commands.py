#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import discord
from tabulate import tabulate

from sausage_bot.util import config, envs
from sausage_bot.util.datetime_handling import get_dt
from sausage_bot.util.i18n import I18N
from .log import log


async def get_message_obj(
        msg_id: str = None, channel: str = None
) -> dict:
    #TODO delete instances of this to convert to `from discord.utils import get`
    '''
    Get a message object

    Parameters
    ------------
    msg_id: int/str
        The message ID to look for, or name of the saved message in
        settings file
    channel: str
        Channel to get message from (default: None)
    '''

    _guild = get_guild()
    _channels = get_text_channel_list()
    _channel = _guild.get_channel(
        _channels[channel]
    )
    try:
        msg_out = await _channel.fetch_message(msg_id)
    except discord.errors.NotFound:
        msg_out = None
    return msg_out


def get_guild():
    '''
    Get the active guild object
    #autodoc skip#
    '''
    for guild in config.bot.guilds:
        if str(guild.name).lower() == config.DISCORD_GUILD.lower():
            log.debug(f'Got guild {guild} ({type(guild)})')
            return guild
        else:
            log.error(envs.GUILD_NOT_FOUND.format(
                str(config.DISCORD_GUILD)
            ))
            return None


def get_text_channel_list():
    '''
    Get a dict of all text channels and their ID's
    #autodoc skip#
    '''
    channel_dict = {}
    guild = get_guild()
    if guild is None:
        return None
    # Get all channels and their IDs
    for channel in guild.text_channels:
        channel_dict[channel.name] = channel.id
    return channel_dict


def channel_exist(channel_in):
    '''
    Check if channel actually exist on server
    #autodoc skip#
    '''
    all_channels = get_text_channel_list()
    if channel_in in all_channels:
        return True
    else:
        return False


def get_voice_channel_list():
    '''
    Get a dict of all voice channels and their ID's
    #autodoc skip#
    # '''
    channel_dict = {}
    guild = get_guild()
    # Get all channels and their IDs
    for channel in guild.voice_channels:
        channel_dict[channel.name] = channel.id
    return channel_dict


def get_scheduled_events():
    '''
    Get all scheduled events from server
    #autodoc skip#
    '''
    guild = get_guild()
    event_dict = {}
    if guild.scheduled_events is None:
        log.log(envs.AUTOEVENT_NO_EVENTS_LISTED)
        return None
    log.debug(f'`guild.scheduled_events`: {guild.scheduled_events}')
    _epochs = {}
    for event in guild.scheduled_events:
        _event = guild.get_scheduled_event(event.id)
        log.debug(f'`_event`: {_event}')
        _dt = _event.start_time.astimezone()
        _dt_pend = get_dt(format='datetimetextday', dt=_dt)
        epoch = int(_event.start_time.astimezone().timestamp())
        if epoch not in _epochs:
            _epochs[epoch] = 1
        elif epoch in _epochs:
            _epochs[epoch] += 1
        epoch_id = '{}-{}'.format(epoch, _epochs[epoch])
        log.debug(f'`epoch_id`: {epoch_id}')
        event_dict[epoch_id] = {
            'name': _event.name,
            'epoch': epoch,
            'start': _dt_pend,
            'id': _event.id,
            'users': _event.user_count
        }
    return event_dict


def get_sorted_scheduled_events():
    '''
    Get a sorted list of events and prettify it
    #autodoc skip#
    '''
    # Sort the dict based on epoch
    events_in = get_scheduled_events()
    log.debug(f'`events_in`: {events_in}')
    if len(events_in) == 0:
        return None
    try:
        event_dict = dict(sorted(events_in.items()))
        log.debug(f'`event_dict` is sorted: {event_dict}')
    except Exception as e:
        # events_in/get_scheduled_events() already describes the error
        log.error(str(e))
        return None
    sched_dict = {
        'match': [],
        'start': [],
        'interest': [],
        'id': []
    }
    for event in event_dict:
        sched_dict['match'].append(event_dict[event]['name'])
        sched_dict['start'].append(event_dict[event]['start'])
        sched_dict['interest'].append(event_dict[event]['users'])
        sched_dict['id'].append(event_dict[event]['id'])
    out = tabulate(
        sched_dict,
        headers=[
            I18N.t(
                'discord_commands.get_sorted_scheduled_events.headers.match'
            ),
            I18N.t(
                'discord_commands.get_sorted_scheduled_events.headers.date'
            ),
            I18N.t(
                'discord_commands.get_sorted_scheduled_events.headers.interest'
            ),
            I18N.t(
                'discord_commands.get_sorted_scheduled_events.headers.id'
            )
        ],
        numalign='center'
    )
    out = '```{}```'.format(out)
    return out


def get_roles(
    hide_empties=None, filter_bots=None, hide_roles=None
):
    '''
    Get a dict of all roles on server and their ID's
    #autodoc skip#
    '''
    log.debug(f'`hide_empties` is {hide_empties}')
    log.debug(f'`filter_bots` is {filter_bots}')
    log.debug(f'`hide_roles` is {hide_roles}')
    roles_dict = {}
    # Get all roles and their IDs
    for role in get_guild().roles:
        if hide_empties and len(role.members) == 0:
            continue
        if filter_bots:
            if role.is_bot_managed():
                continue
        if hide_roles:
            log.debug(f'Checking if {role.id} is in {hide_roles}')
            if str(role.id) in hide_roles[0]:
                continue
            else:
                log.debug(f'Not in {hide_roles}')
        roles_dict[role.name.lower()] = {
            'name': role.name,
            'id': role.id,
            'members': len(role.members),
            'premium': role.is_premium_subscriber(),
            'is_default': role.is_default(),
            'bot_managed': role.is_bot_managed()
        }
    log.verbose(
        'Got these roles: {}'.format(
            ', '.join(name for name in roles_dict)
        )
    )
    return roles_dict


async def post_to_channel(
    channel_in, content_in=None,
    embed_in=None
) -> discord.message.Message:
    '''
    Post `content_in` in plain text or `embed_in` to channel
    `channel_in`
    '''
    if embed_in:
        if isinstance(embed_in, dict):
            embed_in = discord.Embed.from_dict(embed_in)
    server_channels = get_text_channel_list()
    log.debug(f'Got these channels: {server_channels}')
    if channel_in in server_channels:
        channel_out = config.bot.get_channel(server_channels[channel_in])
        try:
            msg_out = await channel_out.send(
                content=content_in,
                embed=embed_in
            )
            return msg_out
        except discord.errors.HTTPException as e:
            log.error(
                f'{e} - this is the offending message:\n'
                f'`content`: {content_in}\n`embed`: {embed_in}'
            )
            return None
    else:
        log.log(
            envs.POST_TO_NON_EXISTING_CHANNEL.format(
                channel_in
            )
        )
        return None


async def replace_post(replace_content, replace_with, channel_in):
    '''
    Look through the bot's messages for `replace_content` in channel
    `channel_in` and replace it with `replace_with.`
    #autodoc skip#
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
        log.error(
            envs.CHANNEL_DOES_NOT_EXIST.format(
                channel_out
            )
        )
        return


async def update_stats_post(stats_info, stats_channel):
    '''
    Replace content in stats-post
    #autodoc skip#
    '''
    server_channels = get_text_channel_list()
    if stats_channel in server_channels:
        log.debug(f'Found stats channel {stats_channel}')
        channel_out = config.bot.get_channel(server_channels[stats_channel])
        found_stats_msg = False
        async for msg in channel_out.history(limit=10):
            log.debug(f'Got msg: ({msg.author.id}) {msg.content[0:50]}...')
            if str(msg.author.id) == config.BOT_ID:
                if 'Serverstats sist' in str(msg.content):
                    log.debug('Found post with `Serverstats sist`, editing...')
                    await msg.edit(content=stats_info)
                    found_stats_msg = True
                    return
        if found_stats_msg is False:
            log.debug('Creating stats message')
            await channel_out.send(stats_info)


async def remove_stats_post(stats_channel):
    '''
    Remove stats-post
    #autodoc skip#
    '''
    server_channels = get_text_channel_list()
    if stats_channel in server_channels:
        log.debug(f'Found stats channel {stats_channel}')
        channel_out = config.bot.get_channel(server_channels[stats_channel])
        found_stats_msg = False
        async for msg in channel_out.history(limit=10):
            log.debug(f'Got msg: ({msg.author.id}) {msg.content[0:50]}...')
            if str(msg.author.id) == config.BOT_ID:
                if 'Serverstats sist' in str(msg.content):
                    log.debug('Found post with `Serverstats sist`, removing...')
                    await msg.delete()
                    found_stats_msg = True
                    return
        if found_stats_msg is False:
            log.debug('No stats post found')


async def log_to_bot_channel(content_in=None):
    'Messages you want to send directly to a specific channel'
    log_channel = config.BOT_CHANNEL
    log.debug(f'`log_channel` er {log_channel}')
    guild = get_guild()

    channel_out = guild.get_channel(int(get_text_channel_list()[log_channel]))
    msg_out = await channel_out.send(
        content=content_in
    )
    return msg_out


if __name__ == "__main__":
    pass
