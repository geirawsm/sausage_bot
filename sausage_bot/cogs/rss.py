#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from ctypes.wintypes import BOOL
from discord.ext import commands, tasks
import re
from sausage_bot.funcs._args import args
from sausage_bot.funcs import _config, _vars, datetimefuncs, file_io, rss_core, discord_commands
from sausage_bot.log import log


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

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss.group(name='add')
    async def add(self, ctx, feed_name=None, feed_link=None, channel=None):
        '''
        Add an RSS feed to a specific channel
        
        `feed_name` = The custom name for the feed
        `feed_link` = The link to the RSS-/XML-feed
        `channel` = The channel to post from the feed
        '''
        AUTHOR = ctx.message.author.name
        URL_OK = False
        CHANNEL_OK = False
        if feed_name is None:
            await ctx.send(
                _vars.RSS_TOO_FEW_ARGUMENTS
                )
            return
        elif feed_link is None:
            await ctx.send(
                _vars.RSS_TOO_FEW_ARGUMENTS
                )
            return
        elif channel is None:
            await ctx.send(
                _vars.RSS_TOO_FEW_ARGUMENTS
                )
            return
        else:
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
                    await log.log_to_bot_channel(
                        _vars.RSS_ADDED_BOT.format(
                            AUTHOR, feed_name, feed_link, channel
                        )
                    )
                    await ctx.send(
                        _vars.RSS_ADDED.format(feed_name, channel)
                    )
                    return
                elif not URL_OK:
                    await ctx.send(_vars.RSS_URL_NOT_OK)
                    return
                elif not CHANNEL_OK:
                    await ctx.send(_vars.RSS_CHANNEL_NOT_OK)
                    return


    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss.group(name='remove')
    async def remove(self, ctx, feed_name):
        '''***'''
        AUTHOR = ctx.message.author.name
        removal = rss_core.remove_feed_from_file(feed_name)
        if removal:
            log_text = f'{AUTHOR} removed feed {feed_name}'
            log.log_to_bot_channel(
                _vars.RSS_REMOVED_BOT.format(feed_name, AUTHOR)
            )
            await ctx.send(
                _vars.RSS_REMOVED.format(feed_name)
                )
        elif removal is False:
            # Couldn't remove the feed
            await ctx.send(_vars.RSS_COULD_NOT_REMOVE.format(feed_name))
            # Also log and send error to either a bot-channel or admin
            await log.log_to_bot_channel(
                _vars.RSS_TRIED_REMOVED_BOT.format(AUTHOR, feed_name)
            )
        return


    @rss.group(name='list')
    async def list_rss(self, ctx, long=None):
        if long is None:
            list_format = rss_core.get_feed_list()
        elif long == 'long':
            list_format = rss_core.get_feed_list(long=True)
        await ctx.send(list_format)
        return


    #Tasks
    #@tasks.loop(minutes = 10)
    @tasks.loop(minutes = 1)
    async def rss_parse():
        def review_feeds_status(feeds):
            for feed in feeds:
                log.log('{}: {}'.format(feed, feeds[feed]['status']))
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

        def link_is_in_log(link: str, feed_log: list) -> BOOL:
            # Checks if given link is in the log given
            if link in feed_log:
                return True
            else:
                return False

        def link_similar_to_logged_post(link: str, feed_log: list):
            '''
            Checks if given link is similar to any logged link,
            then return the similar link from log.
            If no log-links are found to be similar, return None
            '''
            for log_item in feed_log:
                if rss_core.check_similarity(log_item, link):
                    return log_item

        log.log('Starting `rss_parse`')
        channel_dict = {}
        for guild in _config.bot.guilds:
            if guild.name == _config.GUILD:
                # Get all channels and their IDs
                for channel in guild.text_channels:
                    channel_dict[channel.name] = channel.id
        # Update the feeds
        feeds = file_io.read_json(_vars.feeds_file)
        if len(feeds) == 0:
            log.log('No feeds found')
            return
        else:
            log.log_more('Got these feeds:')
            for feed in feeds:
                log.log_more('- {}'.format(feed))
            # Make sure that the feed links aren't stale / 404
            review_feeds_status(feeds)
            FEED_LOG = file_io.read_json(_vars.feeds_logs_file)
            try:
                FEED_LOG[feed]
            except(KeyError):
                FEED_LOG[feed] = []
            # Start processing per feed settings
            for feed in feeds:
                CHANNEL = feeds[feed]['channel']
                URL = feeds[feed]['url']
                log.log('Checking {} ({})'.format(feed, CHANNEL))
                FEED_POSTS = rss_core.get_feed_links(URL)
                if FEED_POSTS is None:
                    log.log(f'{feed}: this feed returned NoneType.')
                    return
                else:
                    log.log(
                        f'{feed}: `FEED_POSTS` are good:\n'
                        f'### {FEED_POSTS} ###'
                        )
                for feed_link in FEED_POSTS:
                    log.log_more(f'Got feed_link `{feed_link}`')
                    # Check if the link is in the log
                    if not link_is_in_log(feed_link, FEED_LOG[feed]):
                        feed_link_similar = link_similar_to_logged_post(feed_link, FEED_LOG[feed])
                        if not feed_link_similar:
                            # Consider this a whole new post and post link to channel
                            await discord_commands.post_to_channel(feed_link, CHANNEL)
                            # Add link to log
                            FEED_LOG[feed].append(feed_link)
                        elif feed_link_similar:
                            # Consider this a similar post that needs to
                            # be edited in the channel
                            await discord_commands.edit_post(
                                feed_link_similar, feed_link, CHANNEL
                            )
                            FEED_LOG[feed].remove(feed_link_similar)
                            FEED_LOG[feed].append(feed_link)
                    elif link_is_in_log(feed_link, FEED_LOG[feed]):
                        log.log_more(f'Link `{feed_link}` already logged. Skipping.')
                    # Write to the logs-file at the end
                    file_io.write_json(_vars.feeds_logs_file, FEED_LOG)
        return


    @rss_parse.before_loop
    async def before_rss_parse():
        log.log_more('`rss_parse` waiting for bot to be ready...')
        await _config.bot.wait_until_ready()

    if args.no_rss:
        log.log_more('Module loaded but disabled for this session')
    elif not args.no_rss:
        rss_parse.start()


def setup(bot):
    bot.add_cog(RSSfeed(bot))
