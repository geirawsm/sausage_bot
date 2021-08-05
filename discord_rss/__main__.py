#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import discord
from discord.ext import commands, tasks
import re
from random import randrange
from dotenv import dotenv_values
from discord_rss import rss, _vars, file_io, log
from discord_rss._args import args
from discord_rss.lists.quotes import quotes
import sys

config = dotenv_values(_vars.env_file)
TOKEN = config['discord_token']
GUILD = config['discord_guild']
PREFIX = config['bot_prefix']
ADMINS = file_io.read_list(_vars.admins_file)

bot = commands.Bot(command_prefix=PREFIX)

# Create necessary files before starting
check_and_create_files = [_vars.admins_file, _vars.feed_file,
                          _vars.feed_log_file]
for file in check_and_create_files:
    file_io.ensure_file(file)

@bot.event
async def on_ready():
    for guild in bot.guilds:
        if guild.name == GUILD:
            break
    log.log('{} has connected to `{}`'.format(bot.user, guild.name))
    season = randrange(1, 6)
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='Tangerudbakken s0{}'.format(season)))


# Commands
@bot.command(name='hjelp')
async def hjelp(ctx):
    global PREFIX
    await ctx.send(_vars.RSS_HELP_TEXT.format(PREFIX))


@bot.command(name='pølse')
async def polse(ctx):
    await ctx.send('https://www.youtube.com/watch?v=geJZ3kJUqoY')


@bot.command(name='sitat')
async def sitat(ctx):
    _rand = randrange(0, len(quotes))
    _quote = '```{}```'.format(quotes[_rand])
    await ctx.send(_quote)


@bot.command(name='admins')
async def admins(ctx):
    if ADMINS is None:
        await ctx.send('Har ingen admins akkurat nå')
    else:
        text_out = 'Registrerte bot-admins:'
        for admin in ADMINS:
            text_out += '\n- {}'.format(admin)
        await ctx.send(text_out)


@bot.command(name='rss')
async def _rss(ctx, action, *args):
    channel_dict = {}
    for guild in bot.guilds:
        if guild.name == GUILD:
            # Get all channels and their IDs
            for channel in guild.text_channels:
                channel_dict[channel.name] = channel.id
    AUTHOR = ctx.message.author.name
    # Add RSS-feed
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
                if rss.check_feed(URL):
                    URL_OK = True
                else:
                    URL_OK = False
            if CHANNEL in channel_dict:
                CHANNEL_OK = True
            if URL_OK and CHANNEL_OK:
                rss.add_feed(NAME, URL, CHANNEL, AUTHOR)
                await ctx.send('{} la til feeden {} ({})'.format(AUTHOR, NAME, URL))
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
            removal = rss.remove_feed(NAME)
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
        list = rss.get_feed_list()
        await ctx.send(_vars.RSS_TOO_MANY_ARGUMENTS)


#Tasks
@tasks.loop(minutes = 1)
async def rss_parse():
    channel_dict = {}
    for guild in bot.guilds:
        if guild.name == GUILD:
            # Get all channels and their IDs
            for channel in guild.text_channels:
                channel_dict[channel.name] = channel.id
            # Update the feeds
            feeds = file_io.read_json(_vars.feed_file)
            for feed in feeds:
                log.log('Checking {}'.format(feed))
                URL = feeds[feed]['url']
                CHANNEL = feeds[feed]['channel']
                feed_links = rss.get_feed_links(URL)
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
                            channel_out = bot.get_channel(channel_dict[CHANNEL])
                            await channel_out.send(link)
                            # Legg til link i logg
                            feed_log[feed].append(link)
                            file_io.write_json(_vars.feed_log_file, feed_log)
                    else:
                        log.log_more('Link {} already logged. Skipping.'.format(link))
    return

if not args.no_rss:
    rss_parse.start()

bot.run(TOKEN)
