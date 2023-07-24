#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands, tasks
from time import sleep
from sausage_bot.util import config, envs, feeds_core, file_io
from sausage_bot.util import discord_commands
from sausage_bot.util.log import log


class RSSfeed(commands.Cog):
    '''
    Administer RSS-feeds that will autopost to a given channel when published
    '''

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='rss')
    async def rss(self, ctx):
        'Administer RSS-feeds'
        pass

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss.group(name='add', invoke_without_command=True)
    async def add(
        self, ctx, feed_name: str = commands.param(
            default=None,
            description="Name of feed"
        ),
        feed_link: str = commands.param(
            default=None,
            description="Link to the RSS-/XML-feed"
        ),
        channel: str = commands.param(
            default=None,
            description="The channel to post from the feed"
        )
    ):
        '''Add RSS feed to a specific channel:
        `!rss add [feed_name] [feed_link] [channel]`
        '''
        AUTHOR = ctx.message.author.name
        URL_OK = False
        CHANNEL_OK = False
        if feed_name is None:
            await ctx.send(
                envs.TOO_FEW_ARGUMENTS
            )
            return
        elif feed_link is None:
            await ctx.send(
                envs.TOO_FEW_ARGUMENTS
            )
            return
        elif channel is None:
            await ctx.send(
                envs.TOO_FEW_ARGUMENTS
            )
            return
        else:
            # Check rss validity
            if feeds_core.check_feed_validity(feed_link):
                URL_OK = True
            else:
                URL_OK = False
            log.log_more(f'URL_OK is {URL_OK}')
            log.log_more(envs.GOT_CHANNEL_LIST.format(
                discord_commands.get_text_channel_list()))
            if discord_commands.channel_exist(channel):
                CHANNEL_OK = True
            if URL_OK and CHANNEL_OK:
                await feeds_core.add_to_feed_file(
                    str(feed_name), str(feed_link), channel, AUTHOR,
                    envs.rss_feeds_file
                )
                await log.log_to_bot_channel(
                    envs.RSS_ADDED_BOT.format(
                        AUTHOR, feed_name, feed_link, channel
                    )
                )
                await ctx.send(
                    envs.RSS_ADDED.format(feed_name, channel)
                )
                # Restart task to kickstart the new RSS-feed
                if not RSSfeed.rss_parse.is_running():
                    RSSfeed.rss_parse.start()
                return
            elif not URL_OK:
                await ctx.send(envs.RSS_URL_NOT_OK)
                return
            elif not CHANNEL_OK:
                await ctx.send(
                    envs.CHANNEL_NOT_FOUND.format(channel)
                )
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
    async def rss_edit_channel(
            self, ctx, feed_name: str = commands.param(
                default=None,
                description="Name of feed"
            ),
            channel: str = commands.param(
                default=None,
                description="Name of channel"
            )):
        'Edit a feed\'s channel: `!rss edit channel [feed_name] [channel]`'
        if feed_name is None:
            await ctx.send(
                envs.TOO_FEW_ARGUMENTS
            )
            return
        elif channel is None:
            await ctx.send(
                envs.TOO_FEW_ARGUMENTS
            )
            return
        if discord_commands.channel_exist(channel):
            feeds_core.update_feed(
                feed_name, envs.rss_feeds_file, actions="edit",
                items=channel, values_in=channel
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss_edit.group(name='name')
    async def rss_edit_name(
        self, ctx,
        feed_name: str = commands.param(
            default=None,
            description="Name of feed"
        ),
        new_feed_name: str = commands.param(
            default=None,
            description="New name of feed"
        )
    ):
        'Edit the name of a feed: `!rss edit name [feed_name] [new_feed_name]`'
        if feed_name is None:
            await ctx.send(
                envs.TOO_FEW_ARGUMENTS
            )
            return
        elif new_feed_name is None:
            await ctx.send(
                envs.TOO_FEW_ARGUMENTS
            )
            return
        feeds_core.update_feed(
            feed_name, envs.rss_feeds_file, actions="edit", items="name",
            values_in=new_feed_name
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss_edit.group(name='url')
    async def rss_edit_url(
        self, ctx,
        feed_name: str = commands.param(
            default=None,
            description="Name of feed"
        ),
        url: str = commands.param(
            default=None,
            description="New url for feed"
        )
    ):
        'Edit the url for a feed: `!rss edit url [feed_name] [url]`'
        if feed_name is None:
            await ctx.send(
                envs.TOO_FEW_ARGUMENTS
            )
            return
        elif url is None:
            await ctx.send(
                envs.TOO_FEW_ARGUMENTS
            )
            return
        feeds_core.update_feed(
            feed_name, envs.rss_feeds_file, actions="edit", items='url',
            values_in=url
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss.group(name='filter')
    async def rss_filter(
        self, ctx,
        feed_name: str = commands.param(
            default=None,
            description="Name of feed"
        ),
        add_remove: str = commands.param(
            default=None,
            description="`Add` or `remove`"
        ),
        allow_deny: str = commands.param(
            default=None,
            description="Specify if the filter should `allow` or `deny`"
        ),
        filter_in: str = commands.param(
            default=None,
            description="What to filter a post by"
        )
    ):
        'Add/remove filter for feed (deny/allow): `!rss filter '\
            '[feed name] [add/remove] [allow/deny] [filter]`'
        # Check for empty arguments
        log.debug(f'Local arguments: {locals()}')
        if feed_name is None or add_remove is None or allow_deny is None\
                or filter_in is None:
            log.debug('Too few arguments')
            await ctx.send(
                envs.TOO_FEW_ARGUMENTS
            )
            return
        # Check for necessary arguments
        if add_remove not in ['add', 'remove']:
            if allow_deny not in ['allow', 'deny']:
                log.debug('Wrong arguments')
                await ctx.send(
                    envs.TOO_FEW_ARGUMENTS
                )
                return
        feeds = file_io.read_json(envs.rss_feeds_file)
        if add_remove == 'remove':
            # Check if in list, then remove
            if filter_in in feeds[feed_name][eval(f'filter{allow_deny}')]:
                feeds[feed_name][eval(f'filter{allow_deny}')].remove(filter_in)
                await ctx.message.reply(f'Removed filter `{filter_in}`')
        elif add_remove == 'add':
            # Check if not in list, then add
            if filter_in not in feeds[feed_name][eval(f'filter{allow_deny}')]:
                feeds[feed_name][eval(f'filter{allow_deny}')].append(filter_in)
                await ctx.message.reply(f'Added filter `{filter_in}`')
        log.debug(
            f'Writing the following to the feed name:\n{feeds[feed_name]}')
        file_io.write_json(envs.rss_feeds_file, feeds)
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss.group(name='remove')
    async def remove(
        self, ctx, feed_name: str = commands.param(
            default=None,
            description="Name of feed"
        )
    ):
        'Remove a feed based on `feed_name`'
        AUTHOR = ctx.message.author.name
        removal = feeds_core.remove_feed_from_file(
            feed_name, envs.rss_feeds_file)
        if removal:
            await log.log_to_bot_channel(
                envs.RSS_REMOVED_BOT.format(feed_name, AUTHOR)
            )
            await ctx.send(
                envs.RSS_REMOVED.format(feed_name)
            )
        elif removal is False:
            # Couldn't remove the feed
            await ctx.send(envs.RSS_COULD_NOT_REMOVE.format(feed_name))
            # Also log and send error to either a bot-channel or admin
            await log.log_to_bot_channel(
                envs.RSS_TRIED_REMOVED_BOT.format(AUTHOR, feed_name)
            )
        return

    @rss.group(name='list')
    async def list_rss(
        self, ctx, list_type: str = commands.param(
            default=None,
            description="`long` or `filter`"
        )
    ):
        '''
        List all active rss feeds on the discord server:
        !rss list ([list_type])
        '''
        if list_type == 'added':
            formatted_list = await feeds_core.get_feed_list(
                envs.rss_feeds_file, envs.RSS_VARS, list_type='added'
            )
        elif list_type == 'filter':
            formatted_list = await feeds_core.get_feed_list(
                envs.rss_feeds_file, envs.RSS_VARS, list_type='filter'
            )
        else:
            formatted_list = await feeds_core.get_feed_list(
                envs.rss_feeds_file, envs.RSS_VARS
            )
        if formatted_list is not None:
            page_counter = 0
            for page in formatted_list:
                page_counter += 1
                log.debug(
                    f'Sending page ({page_counter} / {len(formatted_list)})')
                await ctx.send(f"```{page}```")
                sleep(1)
        else:
            await ctx.send('No feeds added')
        return

    # Tasks
    @tasks.loop(minutes=config.env.int('RSS_LOOP', default=5))
    async def rss_parse():
        log.debug('Starting `rss_parse`')
        # Update the feeds
        feeds = file_io.read_json(envs.rss_feeds_file)
        try:
            if len(feeds) == 0:
                log.log(envs.RSS_NO_FEEDS_FOUND)
        except Exception as e:
            log.log(f'Got error when getting RSS feeds: {e}')
            if feeds is None:
                log.log(envs.RSS_NO_FEEDS_FOUND)
        # Make sure that the feed links aren't stale / 404
        await feeds_core.review_feeds_status(envs.rss_feeds_file)
        log.log_more('Got these feeds:')
        for feed in feeds:
            log.log_more('- {}'.format(feed))
        # Start processing per feed settings
        for feed in feeds:
            log.debug(
                f'Found channel `{feeds[feed]["channel"]}` in `{feeds[feed]}`')
            CHANNEL = feeds[feed]['channel']
            # Make a check to see if the channel exist
            if not discord_commands.channel_exist(CHANNEL):
                feeds_core.update_feed(
                    feed, envs.rss_feeds_file, actions='edit',
                    items='status_channel', values_in='Does not exist'
                )
                msg_out = envs.POST_TO_NON_EXISTING_CHANNEL.format(
                    CHANNEL
                )
                log.log(msg_out)
                await log.log_to_bot_channel(msg_out)
            URL = feeds[feed]['url']
            filter_allow = feeds[feed]['filter_allow']
            filter_deny = feeds[feed]['filter_deny']
            FEED_POSTS = await feeds_core.get_feed_links(
                feed, URL, filter_allow, filter_deny, 'rss',
                config.env('RSS_FILTER_PRIORITY', default='deny')
            )
            log.debug(f'Got this for `FEED_POSTS`: {FEED_POSTS}')
            if FEED_POSTS is None:
                log.log(envs.RSS_FEED_POSTS_IS_NONE.format(feed))
            else:
                await feeds_core.process_links_for_posting_or_editing(
                    feed, FEED_POSTS, envs.rss_feeds_logs_file, CHANNEL
                )
        return

    @rss_parse.before_loop
    async def before_rss_parse():
        '#autodoc skip#'
        log.log_more('`rss_parse` waiting for bot to be ready...')
        await config.bot.wait_until_ready()

    rss_parse.start()


async def setup(bot):
    # Create necessary files before starting
    log.log(envs.COG_STARTING.format('rss'))
    log.log_more(envs.CREATING_FILES)
    check_and_create_files = [
        (envs.rss_feeds_file, {}),
        envs.rss_feeds_logs_file
    ]
    file_io.create_necessary_files(check_and_create_files)
    # Starting the cog
    await bot.add_cog(RSSfeed(bot))
