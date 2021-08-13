#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import discord
from discord.ext import commands, tasks
import re
import os
from random import randrange
from discord_rss import rss, _vars, file_io, log, _config, discord_commands
from discord_rss._args import args
import sys


# Create necessary folders before starting
check_and_create_folders = [_vars.LOG_DIR]
for folder in check_and_create_folders:
    try:
        os.makedirs(folder)
    except(FileExistsError):
        pass


# Create necessary files before starting
check_and_create_files = [_vars.feed_file, _vars.feed_log_file]
for file in check_and_create_files:
    file_io.ensure_file(file)


@_config.bot.event
async def on_ready():
    for guild in _config.bot.guilds:
        if guild.name == _config.GUILD:
            break
    log.log('{} has connected to `{}`'.format(_config.bot.user, guild.name))
    if args.maintenance_mode:
        await _config.bot.change_presence(
            status=discord.Status.dnd)
    else:
        season = randrange(1, 6)
        await _config.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name='Tangerudbakken s0{}'.format(season)
            )
        )

# Load cogs
for filename in os.listdir(_vars.COGS_DIR):
    if filename.endswith('.py'):
        _config.bot.load_extension('{}.{}'.format(
            _vars.COGS_REL_DIR, filename[:-3]
        ))


# Commands
@_config.bot.command(name='pølse')
async def polse(ctx):
    'Poster det famøse "Pølse-gate"-klippet fra Tangerudbakken'
    await ctx.send('https://www.youtube.com/watch?v=geJZ3kJUqoY')


@_config.bot.command(name='rss')
#@commands.has_permissions(administrator=True)
async def _rss(ctx, action, *args):
    '''TODO Gjør om denne til en  egen cog
Bruker actions `add` og `remove` for å legge til og fjerne RSS-feeder.
Du kan også få en liste over aktiverte RSS-feeds ved å bruke `list`.

Eksempler:
`!rss add [navn på rss] [rss url] [kanal som rss skal publiseres til]`
`!rss remove [navn på rss]`
`!rss list`
`!rss list long`
    '''
    AUTHOR = ctx.message.author.name
    # Add RSS-feeds
    if action == 'add':
        log.log_more('Run `rss add`')
        URL_OK = False
        CHANNEL_OK = False
        log.log_more('Received {} arguments'.format(len(args)))
        if len(args) == 3:
            NAME = args[0]
            URL = args[1]
            CHANNEL = args[2]
            if re.match(r'(www|http:|https:)+[^\s]+[\w]', URL):
                # Check rss validity
                if rss.check_feed_validity(URL):
                    URL_OK = True
                else:
                    URL_OK = False
            if CHANNEL in discord_commands.get_channel_list():
                CHANNEL_OK = True
            if URL_OK and CHANNEL_OK:
                rss.add_feed_to_file(NAME, URL, CHANNEL, AUTHOR)
                log_text = '{} la til feeden {} ({}) til kanalen {}'.format(
                    AUTHOR, NAME, URL, CHANNEL
                )
                log.log_to_bot_channel(log_text)
                return
            elif not URL_OK:
                await ctx.send(_vars.RSS_URL_NOT_OK)
                return
            elif not CHANNEL_OK:
                await ctx.send(_vars.RSS_CHANNEL_NOT_OK)
                return
        else:
            await ctx.send(_vars.RSS_URL_AND_CHANNEL_NOT_OK)
    elif action == 'remove':
        if len(args) == 1:
            NAME = args[0]
            removal = rss.remove_feed_from_file(NAME)
            if removal:
                await ctx.send(_vars.RSS_REMOVED.format(NAME))
            elif removal is False:
                # Couldn't remove the feed
                await ctx.send(_vars.RSS_COULD_NOT_REMOVE.format(NAME))
                # Also log and send error to either a bot-channel or admin
            return
        else:
            await ctx.send(_vars.RSS_TOO_MANY_ARGUMENTS)
    elif action == 'list':
        print(len(args))
        if len(args) == 1:
            arg = args[0]
            if arg == 'long':
                list = rss.get_feed_list(long=True)
            else:
                await ctx.send(_vars.RSS_LIST_ARG_WRONG.format(arg))
                return
        else:
            list = rss.get_feed_list()
        await ctx.send(list)
        return


#Tasks
@tasks.loop(minutes = 1)
async def rss_parse():
    channel_dict = {}
    for guild in _config.bot.guilds:
        if guild.name == _config.GUILD:
            # Get all channels and their IDs
            for channel in guild.text_channels:
                channel_dict[channel.name] = channel.id
            # Update the feeds
            feeds = file_io.read_json(_vars.feed_file)
            for feed in feeds:
                URL = feeds[feed]['url']
                CHANNEL = feeds[feed]['channel']
                log.log('Checking {} ({})'.format(feed, CHANNEL))
                feed_links = rss.get_feed_links(URL)
                if feed_links is None:
                    log.log('Klarte ikke å behandle feed: {}'.format(URL))
                    continue
                feed_log = file_io.read_json(_vars.feed_log_file)
                for link in feed_links:
                    try:
                        feed_log[feed]
                    except(KeyError):
                        feed_log[feed] = []
                    if link not in feed_log[feed]:
                        log.log('Got fresh link from {}. Posting...'.format(feed))
                        # Post link to channel
                        if CHANNEL in channel_dict:
                            channel_out = _config.bot.get_channel(channel_dict[CHANNEL])
                            await channel_out.send(link)
                            # Legg til link i logg
                            feed_log[feed].append(link)
                            file_io.write_json(_vars.feed_log_file, feed_log)
                    else:
                        log.log_more('Link {} already logged. Skipping.'.format(link))
    return


if not args.no_rss:
    rss_parse.start()

_config.bot.run(_config.TOKEN)
