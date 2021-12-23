#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands, tasks
import typing
import random
import re
from discord_rss import rss_core, file_io, _vars, log, _config, discord_commands
from discord_rss.datetime_funcs import get_dt
from discord_rss._args import args






class RSSfeed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.group(name='rss')
    async def rss(self, ctx):
        '''Bruker actions `add` og `remove` for å legge til og fjerne RSS-feeder.
Du kan også få en liste over aktiverte RSS-feeds ved å bruke `list`.

Eksempler:
`!rss add [navn på rss] [rss url] [kanal som rss skal publiseres til]`
`!rss remove [navn på rss]`
`!rss list`
`!rss list long`'''
        pass

    @rss.group(name='add')
    async def add(self, ctx, feed_name, feed_link, channel):
        '''Legg til RSS-feeder'''
        AUTHOR = ctx.message.author.name
        URL_OK = False
        CHANNEL_OK = False
        if re.match(r'(www|http:|https:)+[^\s]+[\w]', feed_link):
            # Check rss validity
            if rss_core.check_feed_validity(feed_link):
                URL_OK = True
            else:
                URL_OK = False
            if channel in discord_commands.get_channel_list():
                CHANNEL_OK = True
            if URL_OK and CHANNEL_OK:
                rss_core.add_feed_to_file(str(feed_name), str(feed_link), channel, AUTHOR)
                log_text = '{} la til feeden {} ({}) til kanalen {}'.format(
                    AUTHOR, feed_name, feed_link, channel
                )
                await log.log_to_bot_channel(log_text)
                return
            elif not URL_OK:
                await ctx.send(_vars.RSS_URL_NOT_OK)
                return
            elif not CHANNEL_OK:
                await ctx.send(_vars.RSS_CHANNEL_NOT_OK)
                return


    @rss.group(name='remove')
    async def remove(self, ctx, feed_name):
        '''***'''
        removal = rss_core.remove_feed_from_file(feed_name)
        if removal:
            await ctx.send(_vars.RSS_REMOVED.format(feed_name))
        elif removal is False:
            # Couldn't remove the feed
            await ctx.send(_vars.RSS_COULD_NOT_REMOVE.format(feed_name))
            # Also log and send error to either a bot-channel or admin
        return


    @rss.group(name='list')
    async def list_rss(self, ctx):
        if ctx.invoked_subcommand == 'long':
            list_format = rss_core.get_feed_list(long=True)
        else:
            list_format = rss_core.get_feed_list()
        await ctx.send(list_format)
        return


#Tasks
@tasks.loop(minutes = 1)
async def rss_parse():
    log.log('Starting `rss_parse`')
    channel_dict = {}
    for guild in _config.bot.guilds:
        if guild.name == _config.GUILD:
            # Get all channels and their IDs
            for channel in guild.text_channels:
                channel_dict[channel.name] = channel.id
            # Update the feeds
            feeds = file_io.read_json(_vars.feed_file)
            log.log_more('Got these feeds:')
            for feed in feeds:
                log.log_more('- {}'.format(feed))
            for feed in feeds:
                log.log('{}: {}'.format(feed, feeds[feed]['status']))
                CHANNEL = feeds[feed]['channel']
                URL = feeds[feed]['url']
                URL_STATUS = feeds[feed]['status']
                if URL_STATUS == 'stale':
                    log.log('Feed {} is stale, checking it...'.format(feed))
                    if rss_core.get_feed_links(URL) is not None:
                        log.log('Feed {} is ok, reactivating!'.format(feed))
                        rss_core.update_feed_status(feed, 'ok')
                    elif rss_core.get_feed_links(URL) is None:
                        log.log('Feed {} is still stale, skipping'.format(feed))
                        break
                log.log('Checking {} ({})'.format(feed, CHANNEL))
                feed_links = rss_core.get_feed_links(URL)
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



def setup(bot):
    bot.add_cog(RSSfeed(bot))