#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'''
This cog can take links to soccer games on predefined sites, and make them
into an event for the server.
'''
import discord
from discord.ext import commands
from discord.app_commands import locale_str
import os
import re
import typing
import asyncio

from sausage_bot.util import envs, config, datetime_handling, net_io
from sausage_bot.util import discord_commands
from sausage_bot.util.i18n import I18N
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


async def event_names_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    _guild = discord_commands.get_guild()
    log.debug(f'_guild: {_guild}')
    events = []
    for event in _guild.scheduled_events:
        events.append((event.name, event.id))
    log.debug(f'events: {events}')
    return [
        discord.app_commands.Choice(name=str(event[0]), value=str(event[1]))
        for event in events if current.lower() in event[0].lower()
    ]


class AutoEvent(commands.Cog):
    '#autodoc skip#'

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    group = discord.app_commands.Group(
        name="autoevent", description=locale_str(
            I18N.t('autoevent.commands.autoevent.cmd')
        )
    )

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_events=True)
    )
    @group.command(
        name="add", description=locale_str(
            I18N.t('autoevent.commands.add.cmd')
        )
    )
    async def event_add(
        self, interaction: discord.Interaction, url: str,
        channel: discord.VoiceChannel, text: str = None,
        event_image: discord.Attachment = None
    ):
        '''
        Add a scheduled event

        Parameters
        ------------
        url: str
            URL to match page from nifs, vglive or tv2.no/livesport
        channel: discord.VoiceChannel
            Voice channel to run event on
        text: str
            Additional text to the event's description (default: None)
        event_image
            Image for event (800 x 320)
        '''
        await interaction.response.defer(ephemeral=True)
        if url is None:
            # Delete command message
            await interaction.followup.send(
                I18N.t('common.too_few_arguments')
            )
            return
        else:
            scraped_info = await net_io.parse(url)
            if scraped_info is None:
                log.debug('scrape is NOT ok')
            else:
                log.debug('scrape is ok, this is the output:\n{}'.format(
                    scraped_info
                ))
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
                desc_tournament = I18N.t(
                    'autoevent.commands.add.description.tournament')
                desc_when = I18N.t('autoevent.commands.add.description.when')
                desc_where = I18N.t('autoevent.commands.add.description.where')
                desc_reminder = I18N.t(
                    'autoevent.commands.add.description.reminder')
                description = f'{desc_tournament}: {tournament}\n'\
                    f'{desc_when}: {start_text} ({rel_start})'
                if stadium is not None:
                    description += f'\n{desc_where}: {stadium}'
                description += f'\n\n{desc_reminder}'
                if text:
                    description += f'\n\n{text}'
                if event_image:
                    image_in = await event_image.read()
                else:
                    autoevent_img = envs.STATIC_DIR / config.env.str(
                        'AUTOEVENT_EVENT_IMAGE', default=None
                    )
                    with open(autoevent_img, 'rb') as f:
                        image_in = f.read()
                guild = discord_commands.get_guild()
                try:
                    created_event = await guild.create_scheduled_event(
                        name=f'{home} - {away}',
                        description=description,
                        channel=channel,
                        entity_type=discord.EntityType.voice,
                        image=image_in,
                        start_time=start_event,
                        end_time=end_dt,
                        privacy_level=discord.PrivacyLevel(2),
                        reason=I18N.t('autoevent.commands.add.log_confirm')
                    )
                    await interaction.followup.send(
                        I18N.t('autoevent.commands.add.msg_confirm',
                               home=home,
                               away=away,
                               id=created_event.id
                               ),
                        ephemeral=True
                    )
                except (discord.HTTPException) as e:
                    log.error('Got an error when posting event: {}'.format(
                        e.text)
                    )
                    await interaction.followup.send(
                        I18N.t(
                            'autoevent.commands.add.msg_failed',
                            error_in=e.text
                        ),
                        ephemeral=True
                    )
                    return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_events=True)
    )
    @discord.app_commands.autocomplete(event=event_names_autocomplete)
    @group.command(
        name="remove", description=locale_str(
            I18N.t('autoevent.commands.remove.cmd')
        )
    )
    async def event_remove(
        self, interaction: discord.Interaction,
        remove_all: typing.Literal[
            I18N.t('common.literal_yes_no.yes'),
            I18N.t('common.literal_yes_no.no')
        ] = None, event: str = None
    ):
        '''
        Removes a scheduled event that has not started yet

        Parameters
        ------------
        event:
            The  event to remove (default: None)
        remove_all:
            Use if you want to remove all events
        '''
        await interaction.response.defer(ephemeral=True)
        event_dict = discord_commands.get_scheduled_events()
        log.debug(f'Got `event_dict`: {event_dict}')
        # Delete all events
        _guild = discord_commands.get_guild()
        if remove_all == I18N.t('common.literal_yes_no.yes'):
            for event in event_dict:
                _id = event_dict[event]['id']
                # Delete event
                _event = _guild.get_scheduled_event(int(_id))
                await _event.delete()
            # TODO var msg
            await interaction.followup.send(
                I18N.t('autoevent.commands.remove.msg_all_confirm')
            )
        elif remove_all == I18N.t('common.literal_yes_no.no'):
            if event is not None:
                # Delete event
                _event = _guild.get_scheduled_event(int(event))
                await _event.delete()
                # TODO var msg
                await interaction.followup.send(
                    I18N.t('autoevent.commands.remove.msg_one_confirm')
                )
            else:
                log.error('No event given')
                await interaction.followup.send(
                    I18N.t('autoevent.commands.remove.msg_no_event')
                )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_events=True)
    )
    @group.command(
        name="list", description=locale_str(
            I18N.t('autoevent.commands.list.cmd')
        )
    )
    async def list_events(self, interaction: discord.Interaction):
        '''
        Lists all the planned events: `!autoevent list`
        '''
        await interaction.response.defer(ephemeral=True)
        events = discord_commands.get_sorted_scheduled_events()
        if events is None:
            msg_out = I18N.t('autoevent.commands.list.msg_no_events')
        else:
            msg_out = events
        await interaction.followup.send(
            msg_out
        )

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_events=True)
    )
    @group.command(
        name="sync", description=locale_str(
            I18N.t('autoevent.commands.sync.cmd')
        )
    )
    async def event_sync(
        self, interaction: discord.Interaction, start_time: str,
        countdown: int
    ):
        '''
        Create a timer in the active channel to make it easier for
        people attending an event to sync something that they're
        watching

        Parameters
        ------------
        start_time: str
            A start time for the timer or a command for deleting
            the timer
        countdown: int
            How many seconds should it count down before hitting the
            `start_time`

        Examples
        ------------
        >>> /autoevent sync 02:00 10
        Countdown to 02:00 with 10 seconds to go
        '''
        await interaction.response.defer(ephemeral=True)
        # Check that `start_time` is a decent time
        re_check = re.match(r'^(\d{1,2})[-:.,;_]+(\d{1,2})', str(start_time))
        if re_check:
            timer_epoch = datetime_handling.get_dt() + int(countdown)
            rel_start = f'<t:{timer_epoch}:R>'
            timer_msg = await interaction.followup.send(
                I18N.t('autoevent.commands.sync.msg_confirm',
                       time1=re_check.group(1),
                       time2=re_check.group(2),
                       rel_start=rel_start
                       )
            )
            await asyncio.sleep(int(countdown))
            await timer_msg.delete()
        else:
            await interaction.followup.send(
                I18N.t('autoevent.commands.sync.not_correct_format'),
                ephemeral=True
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_events=True)
    )
    @discord.app_commands.autocomplete(event=event_names_autocomplete)
    @group.command(
        name="announce", description=locale_str(
            I18N.t('autoevent.commands.announce.cmd')
        )
    )
    async def event_announce(
        self, interaction: discord.Interaction, event: str,
        channel: discord.TextChannel
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
        await interaction.response.defer(ephemeral=True)
        # Get event
        _guild = discord_commands.get_guild()
        _event = _guild.get_scheduled_event(int(event))
        rel_start = '<t:{}:R>'.format(
            datetime_handling.get_dt(
                format='epoch',
                dt=_event.start_time.astimezone()
            )
        )
        announce_text = I18N.t(
            'autoevent.commands.announce.annouce_text',
            rel_start=rel_start
        )
        try:
            # Announce to channel
            async with channel.typing():
                await asyncio.sleep(3)
            await channel.send(announce_text)
            await channel.send(_event.url)
            await interaction.followup.send(
                I18N.t(
                    'autoevent.commands.announce.msg_confirm',
                    channel=channel.name
                    ),
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                I18N.t(
                    'autoevent.commands.announce.msg_forbidden',
                    channel=channel.name
                    ),
                ephemeral=True
            )
        except Exception as _error:
            log.error(
                'An error occurred when announcing event: {}'.format(
                    _error
                )
            )
            await interaction.followup.send(
                I18N.t(
                    'commands.announce.msg_error',
                    error=_error
                ),
                ephemeral=True
            )
        return


async def setup(bot):
    log.log(envs.COG_STARTING.format('autoevent'))
    # Starting the cog
    await bot.add_cog(AutoEvent(bot))
