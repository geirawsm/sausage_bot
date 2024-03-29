#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'''
This cog can take links to soccer games on predefined sites, and make them
into an event for the server.
'''
from discord.ext import commands
import discord
import os
import re

from sausage_bot.util import envs, config, datetime_handling, net_io
from sausage_bot.util import discord_commands
from sausage_bot.util.log import log


# Create necessary folders before starting
check_and_create_folders = [
    envs.STATIC_DIR
]
for folder in check_and_create_folders:
    try:
        os.makedirs(folder)
    except (FileExistsError):
        pass


class AutoEvent(commands.Cog):
    '#autodoc skip#'
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='autoevent', aliases=['e', 'event'])
    async def autoevent(self, ctx):
        '''
        Administer match events on the discord server based on a url from a
        supported website.
        '''
        pass

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_events=True)
    )
    @autoevent.group(name='add', aliases=['a'])
    async def event_add(
        self, ctx, url: str = None, channel: str = None, text: str = None,
    ):
        '''
        Add a scheduled event: `!autoevent add [url] [channel] [text]`

        Parameters
        ------------
        url: str
            URL to match page from nifs, vglive or tv2.no/livesport
            (default: None)
        channel: str
            Voice channel to run event on (default: None)
        text: str
            Additional text to the event's description (default: None)
        '''
        autoevent_img = envs.STATIC_DIR / config.env.str(
            'AUTOEVENT_EVENT_IMAGE', default=None
        )
        SCRAPE_OK = False
        CHANNEL_OK = False
        if url is None or\
                channel is None:
            # Delete command message
            await ctx.reply(envs.TOO_FEW_ARGUMENTS, delete_after=5)
            await ctx.message.delete()
            return
        else:
            scraped_info = await net_io.parse(url)
            if scraped_info is None:
                SCRAPE_OK = False
                log.debug('scrape is NOT ok')
            else:
                SCRAPE_OK = True
                log.debug('scrape is ok, this is the output:\n{}'.format(
                    scraped_info
                ))
            voice_channels = discord_commands.get_voice_channel_list()
            log.verbose(envs.GOT_CHANNEL_LIST.format(voice_channels))
            if channel in voice_channels:
                CHANNEL_OK = True
                log.debug('channel is ok')
                channel_id = voice_channels[channel]
                log.verbose(
                    envs.GOT_SPECIFIC_CHANNEL.format(
                        channel, channel_id
                    )
                )
            else:
                CHANNEL_OK = False
                log.debug('channel is NOT ok')
                # Delete command message
                await ctx.send(envs.CHANNEL_NOT_FOUND, delete_after=5)
                return
            if SCRAPE_OK and CHANNEL_OK:
                log.debug('Both scrape and channel is ok')
                scr = scraped_info
                # Start creating the event
                _t = scr['teams']
                home = _t['home']
                away = _t['away']
                tournament = scr['tournament']
                stadium = scr['stadium']
                _dt = scr['datetime']
                start_text = _dt['start_dt'].format(
                    'd. MMMM, HH:mm', locale=datetime_handling.locale
                )
                rel_start = _dt['rel_start']
                start_event = _dt['start_event']
                end_dt = _dt['end_dt']
                description = f'Turnering: {tournament}\n'\
                    f'Når: {start_text} ({rel_start})'
                if stadium is not None:
                    description += f'\nHvor: {stadium}'
                description += '\n\nHusk at eventet er åpent en halvtime '\
                    'før kampstart'
                if text:
                    description += f'\n\n{text}'
                with open(autoevent_img, 'rb') as f:
                    image_in = f.read()
                guild = discord_commands.get_guild()
                try:
                    created_event = await guild.create_scheduled_event(
                        name=f'{home} - {away}',
                        description=description,
                        channel=config.bot.get_channel(channel_id),
                        entity_type=discord.EntityType.voice,
                        image=image_in,
                        start_time=start_event,
                        end_time=end_dt,
                        privacy_level=discord.PrivacyLevel(2),
                        reason='autogenerated event'
                    )
                    await ctx.reply(
                        f'Opprettet event for {home} - {away} (id: '
                        f'{created_event.id})'
                    )
                except (discord.HTTPException) as e:
                    log.log(envs.AUTOEVENT_HTTP_EXCEPTION_ERROR.format(e.text))
                    if 'Cannot schedule event in the past' in str(e):
                        log.log(envs.AUTOEVENT_EVENT_START_IN_PAST)
                        # Delete command message
                        await ctx.reply(
                            envs.AUTOEVENT_EVENT_START_IN_PAST,
                            delete_after=5
                        )
                        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_events=True)
    )
    @autoevent.group(name='remove', aliases=['r', 'delete', 'del'])
    async def event_remove(self, ctx, event_id_in=None):
        '''
        Removes a scheduled event that has not started yet:
        `!autoevent remove [event_id_in]`

        Parameters
        ------------
        event_id_in:
            ID for the event to remove (default: None)
            Get ID's from `!autoevent list`
            Also accept 'all' to remove all events
        '''

        event_dict = discord_commands.get_scheduled_events()
        log.debug(f'Got `event_dict`: {event_dict}')
        # Delete all events
        if event_id_in == 'all':
            _guild = discord_commands.get_guild()
            for event in event_dict:
                _id = event_dict[event]['id']
                # Delete event
                _event = _guild.get_scheduled_event(int(_id))
                await _event.delete()
            # TODO var msg
            await ctx.reply('All events removed')
            return
        # Delete selected event
        else:
            for event in event_dict:
                _id = event_dict[event]['id']
                log.verbose(
                    envs.COMPARING_IDS.format(
                        event_id_in, type(event_id_in),
                        _id, type(_id)
                    )
                )
                event_id_in = str(event_id_in).strip()
                if event_id_in == str(event_dict[event]['id']):
                    log.log(
                        envs.AUTOEVENT_EVENT_FOUND.format(
                            event_dict[event]['name']
                        )
                    )
                    # Delete event
                    guild = discord_commands.get_guild()
                    _event = guild.get_scheduled_event(int(event_id_in))
                    await _event.delete()
                    # TODO var msg
                    await ctx.reply('Event removed')
                    return
            await ctx.reply('Did not find the event')
            log.log(envs.AUTOEVENT_EVENT_NOT_FOUND)
            return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_events=True)
    )
    @autoevent.group(name='list', aliases=['l'])
    async def list_events(self, ctx):
        '''
        Lists all the planned events: `!autoevent list`
        '''
        events = discord_commands.get_sorted_scheduled_events()
        if events is None:
            msg_out = envs.AUTOEVENT_NO_EVENTS_LISTED
        else:
            msg_out = events
        await ctx.reply(
            msg_out
        )

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_events=True)
    )
    @autoevent.group(name='sync', aliases=['s'])
    async def event_sync(
        self, ctx, start_time: str = None, countdown: int = None
    ):
        '''
        Create a timer in the active channel to make it easier for
        people attending an event to sync something that they're
        watching: `!autoevent timesync [start_time] [countdown]`

        Parameters
        ------------
        start_time: str
            A start time for the timer or a command for deleting
            the timer (default: None)
        countdown: int
            How many seconds should it count down before hitting the
            `start_time`

        Examples
        ------------
        >>> !autoevent timesync 02:00 10
        Sync til 02:00 [om 10 sekunder]
        '''
        # Check that `start_time` is a decent time
        if re.match(r'^\d{1,2}[-:.,;_]+\d{1,2}', str(start_time)):
            timer_epoch = datetime_handling.get_dt() + int(countdown)
            rel_start = f'<t:{timer_epoch}:R>'
            await ctx.message.delete()
            await ctx.send(
                f'Sync til {start_time} {rel_start}',
                delete_after=int(countdown)-1
            )
        else:
            await ctx.send(
                envs.AUTOEVENT_START_TIME_NOT_CORRECT_FORMAT,
                delete_after=3
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_events=True)
    )
    @autoevent.group(name='announce', aliases=['ann'])
    async def event_announce(
        self, ctx, event_id: str = None, channel: str = None
    ):
        '''
        Announce an event in a specific channel

        Parameters
        ------------
        event_id: str
            The ID for the event (default: None)
        channel: str
            The channel to announce in (default: None)
        '''
        # Get events
        _guild = discord_commands.get_guild()
        for event in _guild.scheduled_events:
            if int(event_id) == event.id:
                rel_start = '<t:{}:R>'.format(
                    datetime_handling.get_dt(
                        format='epoch',
                        dt=event.start_time.astimezone()
                    )
                )
                announce_text = 'Minner om eventen som '\
                    'begynner {}, 30 min før kampstart'.format(
                        rel_start
                    )
                break

        # Announce to channel
        await discord_commands.post_to_channel(
            channel_in=channel,
            content_in=event.url
        )
        await discord_commands.post_to_channel(
            channel_in=channel,
            content_in=announce_text
        )
        return


async def setup(bot):
    log.log(envs.COG_STARTING.format('autoevent'))
    # Starting the cog
    await bot.add_cog(AutoEvent(bot))
