#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands, tasks
from time import sleep
from sausage_bot.util import config, envs, feeds_core, file_io
from sausage_bot.util import discord_commands, db_helper
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
    async def rss_add(
        self, ctx, feed_name: str = None, feed_link: str = None,
        channel: str = None,
    ):
        '''Add RSS feed to a specific channel:
        `!rss add [feed_name] [feed_link] [channel]`

        Parameters
        ------------
        feed_name: str
            The name of the feed to change (default: None)
        feed_link: str
            Link to the RSS-/XML-feed (default: None)
        channel: str
            The channel to post from the feed
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
            log.verbose(f'URL_OK is {URL_OK}')
            log.verbose(envs.GOT_CHANNEL_LIST.format(
                discord_commands.get_text_channel_list()))
            if discord_commands.channel_exist(channel):
                CHANNEL_OK = True
            if URL_OK and CHANNEL_OK:
                await feeds_core.add_to_feed_db(
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
                    log.debug('Restarted the `rss_parse` task')
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
            self, ctx, feed_name: str = None, channel: str = None
    ):
        '''
        Edit a feed's channel:
        `!rss edit channel [feed_name] [channel]`
        Parameters
        ------------
        feed_name: str
            The name of the feed to change (default: None)
        channel: str
            New channel for updating in database (default: None)
        '''

        if feed_name is None or channel is None:
            await ctx.send(
                envs.TOO_FEW_ARGUMENTS
            )
            return
        feed_check = await feeds_core.check_if_feed_name_exist(feed_name)
        if not feed_check:
            await ctx.reply('Feeden finnes ikke')
            return
        if discord_commands.channel_exist(channel):
            await db_helper.update_fields(
                template_info=envs.rss_db_schema,
                where=('feed_name', feed_name),
                updates=(('channel', channel))
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss_edit.group(name='name')
    async def rss_edit_name(
        self, ctx, feed_name: str = None,
        new_feed_name: str = None,
    ):
        '''
        Edit the name of a feed:
        `!rss edit name [feed_name] [new_feed_name]`

        Parameters
        ------------
        feed_name: str
            The name of the feed to change (default: None)
        new_feed_name: str
            New name of the feed (default: None)
        '''

        if feed_name is None or new_feed_name is None:
            await ctx.send(
                envs.TOO_FEW_ARGUMENTS
            )
            return
        feed_check = await feeds_core.check_if_feed_name_exist(feed_name)
        if not feed_check:
            await ctx.reply('Feeden finnes ikke')
            return
        await db_helper.update_fields(
            template_info=envs.rss_db_schema,
            where=('feed_name', feed_name),
            updates=(('feed_name', new_feed_name))
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss_edit.group(name='url')
    async def rss_edit_url(
        self, ctx, feed_name: str = None, url: str = None
    ):
        '''
        Edit the url for a feed:
        `!rss edit url [feed_name] [url]`

        Parameters
        ------------
        feed_name: str
            The name of the feed to change (default: None)
        url: str
            The new url for the feed (default: None)
        '''

        if feed_name is None or url is None:
            await ctx.send(
                envs.TOO_FEW_ARGUMENTS
            )
            return
        feed_check = await feeds_core.check_if_feed_name_exist(feed_name)
        if not feed_check:
            await ctx.reply('Feeden finnes ikke')
            return
        # Verify that the url edited is proper
        valid_feed = await feeds_core.check_feed_validity(url)
        if not valid_feed:
            await ctx.reply('Den nye urlen er ikke en RSS/XML feed')
            return
        await db_helper.update_fields(
            template_info=envs.rss_db_schema,
            where=('feed_name', feed_name),
            updates=(('url', url))
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )

    @rss.group(name='filter', invoke_without_command=True)
    async def rss_filter(self, ctx):
        '''
        Manage filters for feeds
        '''
        await ctx.reply('Denne kommandoen trenger mer info. Sjekk `!help rss filter`')

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss_filter.group(name='add')
    async def rss_filter_add(
        self, ctx, feed_name: str = None, allow_deny: str = None,
        filter_in: str = None
    ):
        '''
        Add filter for feed (deny/allow):
        `!rss filter add [feed_name] [allow_deny] [filter_in]`

        Parameters
        ------------
        feed_name: str
            Name of feed
        allow_deny: str
            Specify if the filter should `allow` or `deny` (default: None)
        filter_in: str
            What to filter a post by (default: None)
        '''
        if feed_name is None or allow_deny is None or filter_in is None:
            log.debug('Too few arguments')
            await ctx.send(
                envs.TOO_FEW_ARGUMENTS
            )
            return
        # Check for necessary arguments
        if allow_deny not in ['allow', 'deny']:
            _error_msg = 'Wrong arguments, check `allow_deny`'
            log.debug(_error_msg)
            await ctx.reply(_error_msg)
            return
        _uuid = await db_helper.get_output(
            template_info=envs.rss_db_schema,
            select=('uuid'),
            where=(('feed_name', feed_name)),
            single=True
        )
        if _uuid is None:
            _error_msg = f'The feed `{feed_name}` does not exist'
            log.debug(_error_msg)
            await ctx.reply(_error_msg)
            return
        adding_filter = await db_helper.insert_many_all(
            template_info=envs.rss_db_filter_schema,
            inserts=((_uuid, allow_deny, filter_in))
        )
        if adding_filter:
            await ctx.message.reply(f'Added filter `{filter_in} ({allow_deny})`')
        else:
            await ctx.message.reply(
                f'Error when adding filter `{filter_in}`, check logs'
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss_filter.group(name='remove')
    async def rss_filter_remove(
        self, ctx, feed_name: str = None, allow_deny: str = None,
        filter_in: str = None
    ):
        '''
        Remove filter for feed (deny/allow):
        `!rss filter remove [feed_name] [allow_deny] [filter_in]`

        Parameters
        ------------
        feed_name:
        allow_deny: str
            Specify if the filter is an `allow` or `deny` (default: None)
        filter_in: str
            What filter to remove (default: None)
        '''
        if feed_name is None or allow_deny is None or filter_in is None:
            log.debug('Too few arguments')
            await ctx.send(
                envs.TOO_FEW_ARGUMENTS
            )
            return
        # Check for necessary arguments
        if allow_deny not in ['allow', 'deny']:
            _error_msg = 'Wrong arguments, check `allow_deny`'
            log.debug(_error_msg)
            await ctx.reply(_error_msg)
            return
        _uuid = await db_helper.get_output(
            template_info=envs.rss_db_schema,
            select=('uuid'),
            where=(('feed_name', feed_name)),
            single=True
        )
        if _uuid is None:
            _error_msg = f'The feed `{feed_name}` does not exist'
            log.debug(_error_msg)
            await ctx.reply(_error_msg)
            return
        removing_filter = await db_helper.del_row_by_AND_filter(
            template_info=envs.rss_db_filter_schema,
            where=(
                ('uuid', _uuid),
                ('allow_or_deny', allow_deny),
                ('filter', filter_in)
            )
        )
        if removing_filter:
            await ctx.message.reply(f'Removed filter `{filter_in}`')
        else:
            await ctx.message.reply(
                f'Error when removing filter `{filter_in}`, check logs'
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss.group(name='remove')
    async def rss_remove(
        self, ctx, feed_name: str = None,
    ):
        '''
        Remove a feed based on `feed_name`

        Parameters
        ------------
        feed_name: str
            The name of the feed to remove (default: None)
        '''

        AUTHOR = ctx.message.author.name
        _uuid = await db_helper.get_output(
            template_info=envs.rss_db_schema,
            select=('uuid'),
            where=(('feed_name', feed_name)),
            single=True
        )
        if _uuid is None:
            _error_msg = f'The feed `{feed_name}` does not exist'
            log.debug(_error_msg)
            await ctx.reply(_error_msg)
            return
        removal = await feeds_core.remove_feed_from_db(_uuid)
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
            # Also log and send error to bot-channel
            await log.log_to_bot_channel(
                envs.RSS_TRIED_REMOVED_BOT.format(AUTHOR, feed_name)
            )
        return

    @rss.group(name='list')
    async def list_rss(
        self, ctx, list_type: str = None
    ):
        '''
        List all active rss feeds on the discord server:
        !rss list ([list_type])

        Parameters
        ------------
        list_type: str
            List feeds by `added`, or `filter` (default: None)
        '''

        if list_type == 'added':
            formatted_list = await feeds_core.get_feed_list(
                db_in=envs.rss_db_schema,
                list_type='added'
            )
        elif list_type == 'filter':
            formatted_list = await feeds_core.get_feed_list(
                db_in=envs.rss_db_schema,
                db_filter_in=envs.rss_db_filter_schema,
                list_type='filter'
            )
        else:
            formatted_list = await feeds_core.get_feed_list(
                db_in=envs.rss_db_schema
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
        # Make sure that the feed links aren't stale / 404
        await feeds_core.review_feeds_status('rss')
        # Start processing feeds
        feeds = await db_helper.get_output(
            template_info=envs.rss_db_schema,
            order_by=[
                ('feed_name', 'DESC')
            ],
            where=[
                ('status_url', envs.FEEDS_URL_SUCCESS),
                ('status_channel', envs.CHANNEL_STATUS_SUCCESS)
            ]
        )
        if len(feeds) == 0:
            log.log(envs.RSS_NO_FEEDS_FOUND)
            return
        log.verbose('Got these feeds:')
        for feed in feeds:
            log.verbose('- {}'.format(feed[1]))
        # Start processing per feed settings
        for feed in feeds:
            UUID = feed[0]
            FEED_NAME = feed[1]
            CHANNEL = feed[3]
            log.debug(
                f'Found channel `{CHANNEL}` in `{FEED_NAME}`'
            )
            FEED_POSTS = await feeds_core.get_feed_links(feed_info=feed)
            log.debug(f'Got this for `FEED_POSTS`: {FEED_POSTS}')
            if FEED_POSTS is None:
                log.log(envs.RSS_FEED_POSTS_IS_NONE.format(FEED_NAME))
                await log.log_to_bot_channel(
                    envs.RSS_FEED_POSTS_IS_NONE.format(FEED_NAME)
                )
            else:
                await feeds_core.process_links_for_posting_or_editing(
                    UUID, feed, FEED_POSTS, CHANNEL
                )
        return

    @rss_parse.before_loop
    async def before_rss_parse():
        '#autodoc skip#'
        log.verbose('`rss_parse` waiting for bot to be ready...')
        await config.bot.wait_until_ready()

    rss_parse.start()

    def cog_unload():
        'Cancel task if unloaded'
        log.log('Unloaded, cancelling tasks...')
        RSSfeed.rss_parse.cancel()


async def setup(bot):
    # Create necessary databases before starting
    cog_name = 'rss'
    log.log(envs.COG_STARTING.format(cog_name))
    log.verbose('Checking db')
    # Convert json to sqlite db-files if exists
    rss_inserts = None
    rss_prep_is_ok = None
    rss_log_prep_is_ok = None
    if not file_io.file_size(envs.rss_db_schema['db_file']):
        if file_io.file_size(envs.rss_feeds_file):
            log.verbose('Found old json file - feeds')
            rss_inserts = db_helper.json_to_db_inserts(cog_name)
        rss_prep_is_ok = await db_helper.prep_table(
            envs.rss_db_schema,
            rss_inserts['feeds'] if rss_inserts is not None else rss_inserts
        )
        await db_helper.prep_table(
            envs.rss_db_filter_schema,
            rss_inserts['filter'] if rss_inserts is not None else rss_inserts
        )
    if not file_io.file_size(envs.rss_db_schema['db_file']):
        if file_io.file_size(envs.rss_feeds_logs_file):
            log.verbose('Found old json file - logs')
        rss_log_prep_is_ok = await db_helper.prep_table(
            envs.rss_db_log_schema,
            rss_inserts['logs'] if rss_inserts is not None else rss_inserts
        )
    # Delete old json files if they are not necessary anymore
    if rss_prep_is_ok:
        file_io.remove_file(envs.rss_feeds_file)
    if rss_log_prep_is_ok:
        file_io.remove_file(envs.rss_feeds_logs_file)
    log.verbose('Registering cog to bot')
    await bot.add_cog(RSSfeed(bot))
