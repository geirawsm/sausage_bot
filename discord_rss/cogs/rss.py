#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands
import typing
import random
from discord_rss import rss_core, file_io, _vars, log, _config, discord_commands
from discord_rss.datetime_funcs import get_dt


class RSS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.group(name='rss')
    async def rss(ctx, action, *args):
        '''Bruker actions `add` og `remove` for å legge til og fjerne RSS-feeder.
Du kan også få en liste over aktiverte RSS-feeds ved å bruke `list`.

Eksempler:
`!rss add [navn på rss] [rss url] [kanal som rss skal publiseres til]`
`!rss remove [navn på rss]`
`!rss list`
`!rss list long`'''
        pass


    @rss.group(name='add')
    async def add(self, ctx, channel, feed_link):
        '''***'''
        URL_OK = False
        CHANNEL_OK = False
        if re.match(r'(www|http:|https:)+[^\s]+[\w]', feed_link):
            # Check rss validity
            if rss_core.check_feed_validity(URL):
                URL_OK = True
            else:
                URL_OK = False
            if channel in discord_commands.get_channel_list():
                CHANNEL_OK = True
            if URL_OK and CHANNEL_OK:
                rss_core.add_feed_to_file(NAME, URL, CHANNEL, AUTHOR)
                log_text = '{} la til feeden {} ({}) til kanalen {}'.format(
                    AUTHOR, NAME, URL, CHANNEL
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
        await ctx.send(list)
        return


def setup(bot):
    bot.add_cog(RSS(bot))