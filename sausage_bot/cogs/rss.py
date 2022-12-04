#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands, tasks
from sausage_bot.funcs import _config, _vars, feeds_core, file_io
from sausage_bot.funcs import discord_commands
from sausage_bot.log import log


env_template = {
    'rss_loop': 5
}
_config.add_cog_envs_to_env_file('rss', env_template)

config = _config.config()['rss']


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
    @rss.group(name='add', invoke_without_command=True)
    async def add(self, ctx, feed_name=None, feed_link=None, channel=None):
        '''
        Add an RSS feed to a specific channel

        `feed_name`:    The custom name for the feed

        `feed_link`:    The link to the RSS-/XML-feed

        `channel`:      The channel to post from the feed
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
            if feeds_core.check_feed_validity(feed_link):
                URL_OK = True
            else:
                URL_OK = False
            log.log_more(f'URL_OK is {URL_OK}')
            log.log_more(_vars.GOT_CHANNEL_LIST.format(
                discord_commands.get_text_channel_list()))
            if discord_commands.channel_exist(channel):
                CHANNEL_OK = True
            if URL_OK and CHANNEL_OK:
                feeds_core.add_to_feed_file(
                    str(feed_name), str(feed_link), channel, AUTHOR,
                    _vars.rss_feeds_file
                )
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
    @rss.group(name='edit', invoke_without_command=True)
    async def rss_edit(self, ctx):
        '''
        Edit a feed listing. You can edit `channel`, `name` and `url`
        '''
        pass

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss_edit.group(name='channel')
    async def rss_edit_channel(self, ctx, feed_name=None, channel=None):
        f'''
        Edit a feed's channel: {_config.PREFIX}rss edit channel [feed_name] [channel_in]

        `feed_name`:    The feed to change channel
        `channel_in`:   New channel
        '''
        if feed_name is None:
            await ctx.send(
                _vars.TOO_FEW_ARGUMENTS
            )
            return
        elif channel is None:
            await ctx.send(
                _vars.TOO_FEW_ARGUMENTS
            )
            return
        if discord_commands.channel_exist(channel):
            feeds_core.update_feed_status(
                feed_name, _vars.rss_feeds_file, channel_in=channel
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss_edit.group(name='name')
    async def rss_edit_name(self, ctx, feed_name=None, new_feed_name=None):
        f'''
        Edit the name of a feed: `{_config.PREFIX}rss edit name [feed_name] [new_feed_name]`

        `feed_name`:        The name of the RSS-/XML-feed

        `new_feed_name`:    The new name of the feed
        '''
        if feed_name is None:
            await ctx.send(
                _vars.TOO_FEW_ARGUMENTS
            )
            return
        elif new_feed_name is None:
            await ctx.send(
                _vars.TOO_FEW_ARGUMENTS
            )
            return
        feeds_core.update_feed_status(
            feed_name, _vars.rss_feeds_file, new_feed_name=new_feed_name
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss_edit.group(name='url')
    async def rss_edit_url(self, ctx, feed_name=None, url=None):
        'Edit the url for a feed'
        if feed_name is None:
            await ctx.send(
                _vars.TOO_FEW_ARGUMENTS
            )
            return
        elif url is None:
            await ctx.send(
                _vars.TOO_FEW_ARGUMENTS
            )
            return
        feeds_core.update_feed_status(
            feed_name, _vars.rss_feeds_file, url_in=url
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss.group(name='filter')
    async def rss_filter(
        self, ctx, feed_name=None, add_remove=None, allow_deny=None, filter_in=None
    ):
        f'''
        Add/remove filter for feed (deny/allow): `{_config.PREFIX}rss filter [feed_name] [add_remove] [allow_deny] [filter_in]`

        `feed_name`:    Name of feed

        `add_remove`:   Add or remove a filter

        `allow_deny`:   Specify if the filter is to `allow` or `deny` content

        `filter_in`:    Content to filter
        '''
        # Check for empty arguments
        log.debug(f'Local arguments: {locals()}')
        if feed_name is None or add_remove is None or allow_deny is None\
                or filter_in is None:
            log.debug('Too few arguments')
            await ctx.send(
                _vars.TOO_FEW_ARGUMENTS
            )
            return
        # Check for necessary arguments
        if add_remove not in ['add', 'remove']:
            if allow_deny not in ['allow', 'deny']:
                log.debug('Wrong arguments')
                await ctx.send(
                    _vars.TOO_FEW_ARGUMENTS
                )
                return
        feeds = file_io.read_json(_vars.rss_feeds_file)
        if add_remove == 'remove':
            # Check if in list, then remove
            if filter_in in feeds[feed_name]['filter'][allow_deny]:
                feeds[feed_name]['filter'][allow_deny].remove(filter_in)
        elif add_remove == 'add':
            # Check if not in list, then add
            if filter_in not in feeds[feed_name]['filter'][allow_deny]:
                feeds[feed_name]['filter'][allow_deny].append(filter_in)
        log.debug(
            f'Writing the following to the feed name:\n{feeds[feed_name]}')
        file_io.write_json(_vars.rss_feeds_file, feeds)
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss.group(name='remove')
    async def remove(self, ctx, feed_name):
        '''Remove a feed based on `feed_name`'''
        AUTHOR = ctx.message.author.name
        removal = feeds_core.remove_feed_from_file(
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

    @rss.group(name='list')
    async def list_rss(self, ctx, long=None):
        'List all active rss feeds on the discord server'
        if long is None:
            list_format = feeds_core.get_feed_list(_vars.rss_feeds_file)
        elif long == 'long':
            list_format = feeds_core.get_feed_list(
                _vars.rss_feeds_file, long=True)
        await ctx.send(list_format)
        return

    # Tasks
    @tasks.loop(minutes=config['rss_loop'])
    async def rss_parse():
        log.debug('Starting `rss_parse`')
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
        # Make sure that the feed links aren't stale / 404
        feeds_core.review_feeds_status(_vars.rss_feeds_file)
        log.log_more('Got these feeds:')
        for feed in feeds:
            log.log_more('- {}'.format(feed))
        # Start processing per feed settings
        for feed in feeds:
            CHANNEL = feeds[feed]['channel']
            # Make a check to see if the channel exist
            if not discord_commands.channel_exist(CHANNEL):
                feeds_core.update_feed_status(
                    feed, _vars.rss_feeds_file, channel_status='unlisted')
                msg_out = _vars.POST_TO_NON_EXISTING_CHANNEL.format(
                    CHANNEL
                )
                log.log(msg_out)
                await log.log_to_bot_channel(msg_out)
                return
            URL = feeds[feed]['url']
            FILTERS = feeds[feed]['filter']
            log.log('Checking {} ({})'.format(feed, CHANNEL))
            log.debug(f'`URL`: `{URL}`')
            log.debug(f'`FILTERS`: `{FILTERS}`')
            FEED_POSTS = feeds_core.get_feed_links(URL, FILTERS)
            log.debug(f'Got this for `FEED_POSTS`: {FEED_POSTS}')
            if FEED_POSTS is None:
                log.log(_vars.RSS_FEED_POSTS_IS_NONE.format(feed))
                return
            await feeds_core.process_links_for_posting_or_editing(
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
