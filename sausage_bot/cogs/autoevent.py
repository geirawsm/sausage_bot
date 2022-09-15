#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands
import discord
from sausage_bot.funcs import _vars, _config
from sausage_bot.funcs import discord_commands, net_io
from sausage_bot.log import log


class AutoEvent(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='autoevent', aliases=['e', 'event'])
    async def autoevent(self, ctx):
        '''
        Administer match events on the discord server based on a url from a
        supported website.
        Add, remove or list events.
        '''
        pass

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_events=True)
    )
    @autoevent.group(name='add', aliases=['a'])
    async def add(self, ctx, url=None, channel=None, text=None):
        '''
        Add a scheduled event: `!autoevent add [url] [channel] [text]`

        `channel` should be a voice channel for the event.

        `url` should be a link to a specific match from an accepted site.
        As of now only match links from nifs.no is parsed.

        `text` is additional text that should be added to the description
        of the event.
        '''
        kampchat_img = _vars.STATIC_DIR / 'kampchat.png'
        SCRAPE_OK = False
        CHANNEL_OK = False
        if url is None or\
                channel is None:
            await ctx.send(_vars.TOO_FEW_ARGUMENTS)
            return
        else:
            scraped_info = net_io.parse(url)
            if scraped_info is None:
                SCRAPE_OK = False
            else:
                SCRAPE_OK = True
            voice_channels = discord_commands.get_voice_channel_list()
            log.log_more(_vars.GOT_CHANNEL_LIST.format(voice_channels))
            if channel in voice_channels:
                CHANNEL_OK = True
                channel_id = voice_channels[channel]
                log.log_more(
                    _vars.GOT_SPECIFIC_CHANNEL.format(
                        channel, channel_id
                    )
                )
            else:
                CHANNEL_OK = False
                await ctx.send(_vars.CHANNEL_NOT_FOUND)
                return
            if SCRAPE_OK and CHANNEL_OK:
                scr = scraped_info
                # Start creating the event
                _t = scr['teams']
                home = _t['home']
                away = _t['away']
                tournament = scr['tournament']
                stadium = scr['stadium']
                _dt = scr['datetime']
                start_text = _dt['start_dt'].strftime('%-d. %B, kl. %H:%M')
                rel_start = _dt['rel_start']
                start_dt = _dt['start_dt']
                end_dt = _dt['end_dt']
                description = f'Turnering: {tournament}\n'\
                    f'Når: {start_text} ({rel_start})\n'\
                    f'Hvor: {stadium}'
                if text:
                    description += f'\n\n{text}'
                with open(kampchat_img, 'rb') as f:
                    image_in = f.read()
                guild = discord_commands.get_guild()
                await guild.create_scheduled_event(
                    name = f'{home} - {away}',
                    description = description,
                    channel = _config.bot.get_channel(channel_id),
                    entity_type = discord.EntityType.voice,
                    image = image_in,
                    start_time = start_dt,
                    end_time = end_dt,
                    reason = 'autogenerated event'
                )

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_events=True)
    )
    @autoevent.group(name='remove', aliases=['r'])
    async def remove(self, ctx, event_id_in):
        '''
        Removes a scheduled event that has not started yet: `!autoevent remove [event_id_in]`

        You can get `event_id_in` by getting list of all events
        '''
        event_dict = discord_commands.get_scheduled_events()
        for event in event_dict:
            _id = event_dict[event]['id']
            log.log_more(
                _vars.COMPARING_IDS.format(
                    event_id_in, _id
                )
            )
            event_id_in = str(event_id_in).strip()
            if event_id_in == str(event_dict[event]['id']):
                log.log(
                    _vars.AUTOEVENT_EVENT_FOUND.format(
                        event_dict[event]['name']
                    )
                )
                # Delete event
                guild = discord_commands.get_guild()
                _event = guild.get_scheduled_event(int(event_id_in))
                await _event.delete()
                return
        log.log(_vars.AUTOEVENT_EVENT_NOT_FOUND)
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
            msg_out = _vars.AUTOEVENT_NO_EVENTS_LISTED
        else:
            msg_out = events
        await ctx.send(
            msg_out
        )


async def setup(bot):
    log.log('Starting cog: `autoevent`')
    # Starting the cog
    await bot.add_cog(AutoEvent(bot))
