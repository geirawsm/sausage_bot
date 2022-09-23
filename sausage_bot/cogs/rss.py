#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands, tasks
from sausage_bot.funcs import _config, _vars, file_io
from sausage_bot.funcs import rss_core, discord_commands
from sausage_bot.log import log


class RSSfeed(commands.Cog):
    '''
    Administer RSS-feeds that will autopost to a given channel when published
    '''
    def __init__(self, bot):
        self.bot = bot


    @commands.group(name='rss')
    async def rss(self, ctx):
        '''Uses `add` and `remove` to administer RSS-feeds.

`list` returns a list over the feeds that are active as of now.

Examples:
```
!rss add [name for rss] [rss url] [rss posting channel]

!rss remove [name for rss]

!rss list

!rss list long
```'''
        pass

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss.group(name='add')
    async def add(self, ctx, feed_name=None, feed_link=None, channel=None):
        '''
        Add an RSS feed to a specific channel
        
        `feed_name`: The custom name for the feed

        `feed_link`: The link to the RSS-/XML-feed

        `channel`:   The channel to post from the feed
        '''
        AUTHOR = ctx.message.author.name
        URL_OK = False
        CHANNEL_OK = False
        if feed_name is None:
            await ctx.send(
                _vars.TOO_FEW_ARGUMENTS
                )
            return
        elif feed_link is None:
            await ctx.send(
                _vars.TOO_FEW_ARGUMENTS
                )
            return
        elif channel is None:
            await ctx.send(
                _vars.TOO_FEW_ARGUMENTS
                )
            return
        else:
            # Check rss validity
            if rss_core.check_feed_validity(feed_link):
                URL_OK = True
            else:
                URL_OK = False
            log.log_more(f'URL_OK is {URL_OK}')
            log.log_more(_vars.GOT_CHANNEL_LIST.format(discord_commands.get_text_channel_list()))
            if channel in discord_commands.get_text_channel_list():
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
                await ctx.send(_vars.CHANNEL_NOT_FOUND)
                return


    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss.group(name='remove')
    async def remove(self, ctx, feed_name):
        '''Remove a feed based on `feed_name`'''
        AUTHOR = ctx.message.author.name
        removal = rss_core.remove_feed_from_file(
            feed_name, _vars.rss_feeds_file)
        if removal:
            await log.log_to_bot_channel(
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


    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss.group(name='channel')
    async def channel(self, ctx, feed_name, channel_in):
        '''
        Edit a feed's channel: !rss channel [feed_name] [channel_in]

        `feed_name`:    The feed to change channel
        `channel_in`:   New channel
        '''
        AUTHOR = ctx.message.author.name
        rss_core.update_feed_status(feed_name, channel_in=channel_in)
        await ctx.send(
            _vars.RSS_CHANGED_CHANNEL.format(
                feed_name, channel_in)
            )
        await log.log_to_bot_channel(
            _vars.RSS_FEED_CHANNEL_CHANGE.format(AUTHOR, feed_name, channel_in)
        )
        return


    @rss.group(name='list')
    async def list_rss(self, ctx, long=None):
        'List all active rss feeds on the discord server'
        if long is None:
            list_format = rss_core.get_feed_list(_vars.rss_feeds_file)
        elif long == 'long':
            list_format = rss_core.get_feed_list(_vars.rss_feeds_file, long=True)
        await ctx.send(list_format)
        return


    #Tasks
    @tasks.loop(minutes = 5)
    async def rss_parse():
        log.log('Starting `rss_parse`')
        # Update the feeds
        feeds = file_io.read_json(_vars.rss_feeds_file)
        try:
            if len(feeds) == 0:
                log.log(_vars.RSS_NO_FEEDS_FOUND)
                return
        except Exception as e:
            log.log(f'Got error when getting RSS feeds: {e}')
            if feeds is None:
                log.log(_vars.RSS_NO_FEEDS_FOUND)
                return
        log.log_more('Got these feeds:')
        for feed in feeds:
            log.log_more('- {}'.format(feed))
        # Make sure that the feed links aren't stale / 404
        rss_core.review_feeds_status(feeds)
        # Start processing per feed settings
        for feed in feeds:
            CHANNEL = feeds[feed]['channel']
            # Make a check to see if the channel exist
            if not discord_commands.channel_exist(CHANNEL):
                rss_core.update_feed_status(feed, channel_status='unlisted')
                msg_out = _vars.POST_TO_NON_EXISTING_CHANNEL.format(
                    CHANNEL
                )
                log.log(msg_out)
                await log.log_to_bot_channel(msg_out)
                return
            URL = feeds[feed]['url']
            log.log('Checking {} ({})'.format(feed, CHANNEL))
            FEED_POSTS = rss_core.get_feed_links(URL)
            if FEED_POSTS is None:
                log.log_vars.RSS_FEED_POSTS_IS_NONE.format(feed))
                return
            await rss_core.process_links_for_posting_or_editing(
                feed, FEED_POSTS, _vars.rss_feeds_logs_file, CHANNEL
            )
        return


    @rss_parse.before_loop
    async def before_rss_parse():
        log.log_more('`rss_parse` waiting for bot to be ready...')
        await _config.bot.wait_until_ready()

    rss_parse.start()


async def setup(bot):
    # Create necessary files before starting
    log.log(_vars.COG_STARTING.format('rss'))
    log.log_more(_vars.CREATING_FILES)
    check_and_create_files = [
        (_vars.rss_feeds_file, '{}'),
        _vars.rss_feeds_logs_file
    ]
    file_io.create_necessary_files(check_and_create_files)
    # Starting the cog
    await bot.add_cog(RSSfeed(bot))
