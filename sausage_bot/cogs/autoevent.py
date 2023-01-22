#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from nis import match
from discord.ext import commands
import discord
from sausage_bot.util import envs, config, datetime_handling, net_io
from sausage_bot.util import discord_commands
from sausage_bot.util.log import log
import re


class AutoEvent(commands.Cog):
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
    async def add(
        self, ctx, url: str = commands.param(
            default=None,
            description="URL to match page from nifs.no"
        ),
        channel: str = commands.param(
            default=None,
            description="Voice channel to run event on"
        ),
        text: str = commands.param(
            default=None,
            description="Additional text to the event's description"
        )
    ):
        'Add a scheduled event: `!autoevent add [url] [channel] [text]`'
        # React to the command message
        await ctx.message.add_reaction('✅')
        kampchat_img = envs.STATIC_DIR / 'kampchat.png'
        SCRAPE_OK = False
        CHANNEL_OK = False
        if url is None or\
                channel is None:
            # Delete command message
            await ctx.message.delete()
            await ctx.send(envs.TOO_FEW_ARGUMENTS, delete_after=3)
            return
        else:
            scraped_info = net_io.parse(url)
            if scraped_info is None:
                SCRAPE_OK = False
            else:
                SCRAPE_OK = True
            voice_channels = discord_commands.get_voice_channel_list()
            log.log_more(envs.GOT_CHANNEL_LIST.format(voice_channels))
            if channel in voice_channels:
                CHANNEL_OK = True
                channel_id = voice_channels[channel]
                log.log_more(
                    envs.GOT_SPECIFIC_CHANNEL.format(
                        channel, channel_id
                    )
                )
            else:
                CHANNEL_OK = False
                # Delete command message
                await ctx.message.delete()
                await ctx.send(envs.CHANNEL_NOT_FOUND, delete_after=3)
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
                try:
                    await guild.create_scheduled_event(
                        name=f'{home} - {away}',
                        description=description,
                        channel=config.bot.get_channel(channel_id),
                        entity_type=discord.EntityType.voice,
                        image=image_in,
                        start_time=start_dt,
                        end_time=end_dt,
                        reason='autogenerated event'
                    )
                except (discord.HTTPException) as e:
                    # TODO vars msg
                    log.log(f'Got an error when posting event: {e.text}')
                    if 'Cannot schedule event in the past' in str(e):
                        # Delete command message
                        await ctx.message.delete()
                        # TODO vars msg
                        await ctx.send(
                            'Kan ikke lage en event med starttid i '
                            'fortida', delete_after=3
                        )
                        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_events=True)
    )
    @autoevent.group(name='remove', aliases=['r'])
    async def remove(
        self, ctx, event_id_in: int = commands.param(
            default=None,
            description="ID for the event to remove. Get ID's from `!autoevent list`"
        )
    ):
        'Removes a scheduled event that has not started yet: `!autoevent remove [event_id_in]`'
        event_dict = discord_commands.get_scheduled_events()
        for event in event_dict:
            _id = event_dict[event]['id']
            log.log_more(
                envs.COMPARING_IDS.format(
                    event_id_in, _id
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
                return
        log.log(envs.AUTOEVENT_EVENT_NOT_FOUND)
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_events=True)
    )
    @autoevent.group(name='list', aliases=['l'])
    async def list_events(self, ctx):
        f'''
        Lists all the planned events: `{config.PREFIX}autoevent list`
        '''
        events = discord_commands.get_sorted_scheduled_events()
        if events is None:
            msg_out = envs.AUTOEVENT_NO_EVENTS_LISTED
        else:
            msg_out = events
        await ctx.send(
            msg_out
        )

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_events=True)
    )
    @autoevent.group(name='sync', aliases=['s'])
    async def sync(
            self, ctx, start_time: str = commands.param(
                description="A start time for the timer or a command for deleting the timer"
            ),
            countdown: int = commands.param(
                description="How many seconds should it count down before hitting the `start_time`"
            )):
        'Create a timer in the active channel to make it easier for '\
            'people attending an event to sync something that they\'re '\
            'watching: `!autoevent timesync [start_time] [countdown]`'
        # Check that `start_time` is a decent time
        if re.match(r'^\d{1,2}[-:.,;_]+\d{1,2}', str(start_time)):
            timer_epoch = datetime_handling.get_dt() + int(countdown)
            rel_start = f'<t:{timer_epoch}:R>'
            await ctx.send(
                f'Sync til {start_time} {rel_start}', delete_after=int(countdown)
            )
        else:
            await ctx.send(
                envs.AUTOEVENT_START_TIME_NOT_CORRECT_FORMAT,
                delete_after=3
            )
        await ctx.message.delete()
        return


async def setup(bot):
    log.log(envs.COG_STARTING.format('autoevent'))
    # Starting the cog
    await bot.add_cog(AutoEvent(bot))
