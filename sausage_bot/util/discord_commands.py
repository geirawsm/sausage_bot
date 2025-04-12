#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'discord_commands: Helper functions for discord commands'
import discord
from tabulate import tabulate

from sausage_bot.util import config, envs
from sausage_bot.util.datetime_handling import get_dt
from sausage_bot.util.i18n import I18N

logger = config.logger

async def get_message_obj(
        msg_id: int, channel_id: int
) -> dict:
    '''
    Get a message object

    Parameters
    ------------
    msg_id: int
        The message ID to look for
    channel_id: int
        Channel to get message from (default: None)
    '''

    _guild = get_guild()
    logger.debug(f'Getting channel with id `{channel_id}` ({type(channel_id)})')
    _channel = _guild.get_channel(int(channel_id))
    logger.debug(f'Got channel `{_channel}`')
    try:
        logger.debug(f'Getting message with id `{msg_id}` ({type(msg_id)})')
        msg_out = await _channel.fetch_message(int(msg_id))
        logger.debug(f'Got msg_out `{msg_out}`')
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
            logger.debug(f'Got guild {guild} ({type(guild)})')
            return guild
        else:
            logger.error(envs.GUILD_NOT_FOUND.format(
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
    return channel_in in all_channels


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
        logger.info(envs.AUTOEVENT_NO_EVENTS_LISTED)
        return None
    logger.debug(f'`guild.scheduled_events`: {guild.scheduled_events}')
    _epochs = {}
    for event in guild.scheduled_events:
        _event = guild.get_scheduled_event(event.id)
        logger.debug(f'`_event`: {_event}')
        _dt = _event.start_time.astimezone()
        _dt_pend = get_dt(format='datetimetextday', dt=_dt)
        epoch = int(_event.start_time.astimezone().timestamp())
        if epoch not in _epochs:
            _epochs[epoch] = 1
        elif epoch in _epochs:
            _epochs[epoch] += 1
        epoch_id = '{}-{}'.format(epoch, _epochs[epoch])
        logger.debug(f'`epoch_id`: {epoch_id}')
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
    logger.debug(f'`events_in`: {events_in}')
    if len(events_in) == 0:
        return None
    try:
        event_dict = dict(sorted(events_in.items()))
        logger.debug(f'`event_dict` is sorted: {event_dict}')
    except Exception as e:
        # events_in/get_scheduled_events() already describes the error
        logger.error(str(e))
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
    hide_empties = eval(hide_empties)
    filter_bots = eval(filter_bots)
    logger.debug(f'hide_empties: {hide_empties} {type(hide_empties)}')
    logger.debug(f'filter_bots: {filter_bots} {type(filter_bots)}')
    logger.debug(f'hide_roles: {hide_roles} {type(hide_roles)}')
    # Get all roles and their IDs
    roles_dict = {}
    for role in get_guild().roles:
        if hide_empties is True and len(role.members) <= 0:
            continue
        if filter_bots and role.is_bot_managed():
            continue
        if hide_roles and str(role.id) in hide_roles:
            continue
        roles_dict[role.name.lower()] = {
            'name': role.name,
            'id': role.id,
            'members': len(role.members),
            'premium': role.is_premium_subscriber(),
            'is_default': role.is_default(),
            'bot_managed': role.is_bot_managed()
        }
    logger.debug(
        'Got these roles: {}'.format(
            ', '.join(name for name in roles_dict)
        )
    )
    return roles_dict


async def post_to_channel(
    channel_id: int, content_in=None,
    embed_in=None
) -> discord.message.Message:
    '''
    Post `content_in` in plain text or `embed_in` to channel
    `channel_id`
    '''
    if embed_in and isinstance(embed_in, dict):
        embed_in = discord.Embed.from_dict(embed_in)
    channel_out = config.bot.get_channel(int(channel_id))
    try:
        msg_out = await channel_out.send(
            content=content_in,
            embed=embed_in
        )
        return msg_out
    except discord.errors.HTTPException as e:
        logger.error(
            f'{e} - this is the offending message:\n'
            f'`content`: {content_in}\n`embed`: {embed_in}'
        )
    return None


async def replace_post(replace_content, replace_with, channel_in):
    '''
    Look through the bot's messages for `replace_content` in channel
    `channel_in` and replace it with `replace_with.`
    #autodoc skip#
    '''
    _guild = get_guild()
    channel_out = _guild.get_channel(int(channel_in))
    async for msg in channel_out.history(limit=30):
        if str(msg.author.id) == config.BOT_ID:
            if isinstance(replace_content, str):
                if replace_content in msg.content:
                    await msg.edit(content=replace_with)
                    return
            elif isinstance(replace_content, list):
                if any(_cont in msg.content for _cont in replace_content):
                    await msg.edit(content=replace_with)
                    return
    return


async def remove_stats_post(stats_channel):
    '''
    Remove stats-post
    #autodoc skip#
    '''
    server_channels = get_text_channel_list()
    if stats_channel in server_channels:
        logger.debug(f'Found stats channel {stats_channel}')
        channel_out = config.bot.get_channel(server_channels[stats_channel])
        found_stats_msg = False
        async for msg in channel_out.history(limit=10):
            logger.debug(f'Got msg: ({msg.author.id}) {msg.content[0:50]}...')
            if str(msg.author.id) == config.BOT_ID and\
                    'Serverstats sist' in str(msg.content):
                logger.debug(
                    'Found post with `Serverstats sist`, removing...'
                )
                await msg.delete()
                found_stats_msg = True
                return
        if found_stats_msg is False:
            logger.debug('No stats post found')


async def log_to_bot_channel(content_in=None):
    'Messages you want to send directly to a specific channel'
    log_channel = config.BOT_CHANNEL
    logger.debug(f'`log_channel` er {log_channel}')
    guild = get_guild()
    channel_out = guild.get_channel(int(get_text_channel_list()[log_channel]))
    msg_out = await channel_out.send(
        content=content_in
    )
    return msg_out


if __name__ == "__main__":
    pass
