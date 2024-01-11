#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands, tasks
from time import sleep
from yt_dlp import YoutubeDL

from sausage_bot.util import config, envs, feeds_core, file_io
from sausage_bot.util import discord_commands, db_helper
from sausage_bot.util.log import log


class Youtube(commands.Cog):
    'Autopost new videos from given Youtube channels'

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='youtube', aliases=['yt'])
    async def youtube(self, ctx):
        'Administer what Youtube channels to post'
        pass

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @youtube.group(name='add')
    async def youtube_add(
        self, ctx, feed_name: str = None, yt_link: str = None,
        channel: str = None
    ):
        '''
        Add a Youtube feed to a specific channel:
        `!youtube add [feed_name] [yt_link] [channel]`

        Parameters
        ------------
        feed_name: str
            Name of feed (default: None)
        yt_link: str
            The link for the youtube-channel
        channel: str
            The Discord channel to post from the feed
        '''
        AUTHOR = ctx.message.author.name
        CHANNEL_OK = False
        if feed_name is None:
            await ctx.send(
                envs.TOO_FEW_ARGUMENTS
            )
            return
        elif yt_link is None:
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
            # Make a check to see if the channel exist
            if discord_commands.channel_exist(channel):
                CHANNEL_OK = True
            if CHANNEL_OK:
                # Get yt-id
                yt_info = await Youtube.get_yt_info(yt_link)
                if yt_info is None:
                    await ctx.send(
                        envs.YOUTUBE_EMPTY_LINK.format(yt_link)
                    )
                    return
                await feeds_core.add_to_feed_db(
                    'youtube', str(feed_name), str(yt_link), channel,
                    AUTHOR, yt_info['channel_id']
                )
                await log.log_to_bot_channel(
                    envs.YOUTUBE_ADDED_BOT.format(
                        AUTHOR, feed_name, yt_link, channel
                    )
                )
                await ctx.send(
                    envs.YOUTUBE_ADDED.format(feed_name, channel)
                )
                # Restart task to kickstart the new YT-channel
                if not Youtube.post_videos.is_running():
                    log.debug('Restarted the `post_videos` task')
                    Youtube.post_videos.start()
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
    @youtube.group(name='remove', aliases=['r', 'delete', 'del'])
    async def youtube_remove(self, ctx, feed_name: str = None):
        '''
        Remove a Youtube feed: `!youtube remove [feed_name]`

        Parameters
        ------------
        feed_name: str
            Name of feed (default: None)
        yt_link: str
            The link for the youtube-channel
        channel: str
            The Discord channel to post from the feed
        '''

        AUTHOR = ctx.message.author.name
        removal = await feeds_core.remove_feed_from_db(
            feed_type='youtube', feed_name=feed_name
        )
        if removal:
            await log.log_to_bot_channel(
                envs.YOUTUBE_REMOVED_BOT.format(feed_name, AUTHOR)
            )
            await ctx.send(
                envs.YOUTUBE_REMOVED.format(feed_name)
            )
        elif removal is False:
            # Couldn't remove the feed
            await ctx.send(envs.YOUTUBE_COULD_NOT_REMOVE.format(feed_name))
            # Also log and send error to either a bot-channel or admin
            await log.log_to_bot_channel(
                envs.YOUTUBE_TRIED_REMOVED_BOT.format(AUTHOR, feed_name)
            )
        return

    @youtube.group(name='list')
    async def youtube_list(self, ctx, list_type: str = None):
        '''
        List all active Youtube feeds: !youtube list ([list_type])

        Parameters
        ------------
        list_type: str
            None, `added` or `filter` (default: None)
        '''
        if list_type == 'added':
            formatted_list = await feeds_core.get_feed_list(
                db_in=envs.youtube_db_schema,
                list_type='added'
            )
        elif list_type == 'filter':
            formatted_list = await feeds_core.get_feed_list(
                db_in=envs.youtube_db_schema,
                db_filter_in=envs.youtube_db_filter_schema,
                list_type='filter'
            )
        else:
            formatted_list = await feeds_core.get_feed_list(
                envs.youtube_db_schema
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

    async def get_yt_info(url):
        'Use yt-dlp to get info about a channel'
        # Get more yt-dlp opts here:
        # https://github.com/ytdl-org/youtube-dl/blob/3e4cedf9e8cd3157df2457df7274d0c842421945/youtube_dl/YoutubeDL.py#L137-L312
        ydl_opts = {
            'simulate': True,
            'download': False,
            'playlistend': 2,
            'ignoreerrors': True,
            'quiet': True
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url)
        except Exception as _error:
            log.debug(f'Could not extract youtube info: {_error}')
            return None

    # Tasks
    @tasks.loop(
            minutes=config.env.int('YT_LOOP', default=5),
            reconnect=True
    )
    async def post_videos():
        log.log('Starting `post_videos`')
        # Make sure that the feed links aren't stale / 404
        review_feeds = await feeds_core.review_feeds_status('youtube')
        if review_feeds in [None, False]:
            log.log('No videos to post')
            return
        # Start processing feeds
        feeds = await db_helper.get_output(
            template_info=envs.youtube_db_schema,
            order_by=[
                ('feed_name', 'DESC')
            ],
            where=[
                ('status_url', envs.FEEDS_URL_SUCCESS),
                ('status_channel', envs.CHANNEL_STATUS_SUCCESS)
            ]
        )
        if len(feeds) == 0:
            log.log(envs.YOUTUBE_NO_FEEDS_FOUND)
            return
        log.verbose('Got these feeds:')
        for feed in feeds:
            log.verbose('- {}'.format(feed[1]))
        # Start processing per feed settings
        for feed in feeds:
            log.log(f'Checking {feed[1]}', sameline=True)
            UUID = feed[0]
            FEED_NAME = feed[1]
            CHANNEL = feed[3]
            log.debug(
                f'Found channel `{CHANNEL}` in `{FEED_NAME}`'
            )
            FEED_POSTS = await feeds_core.get_feed_links(
                feed_type='youtube', feed_info=feed
            )
            log.debug(f'Got this for `FEED_POSTS`: {FEED_POSTS}')
            if FEED_POSTS is None:
                log.log(envs.YOUTUBE_FEED_POSTS_IS_NONE.format(feed))
                await log.log_to_bot_channel(
                    envs.YOUTUBE_FEED_POSTS_IS_NONE.format(FEED_NAME)
                )
            else:
                await feeds_core.process_links_for_posting_or_editing(
                    'youtube', UUID, FEED_POSTS, CHANNEL
                )
        log.log('Done with posting')
        return

    @post_videos.before_loop
    async def before_post_new_videos():
        '#autodoc skip#'
        log.verbose('`post_videos` waiting for bot to be ready...')
        await config.bot.wait_until_ready()


async def setup(bot):
    # Create necessary databases before starting
    cog_name = 'youtube'
    log.log(envs.COG_STARTING.format(cog_name))
    log.verbose('Checking db')
    # Convert json to sqlite db-files if exists
    yt_inserts = None
    yt_prep_is_ok = None
    yt_log_prep_is_ok = None
    if not file_io.file_size(envs.youtube_db_schema['db_file']):
        if file_io.file_size(envs.yt_feeds_file):
            log.verbose('Found old json file - feeds')
            yt_inserts = db_helper.json_to_db_inserts(cog_name)
        yt_prep_is_ok = await db_helper.prep_table(
            envs.youtube_db_schema,
            yt_inserts['feeds'] if yt_inserts is not None else yt_inserts
        )
        await db_helper.prep_table(
            envs.youtube_db_filter_schema,
            yt_inserts['filter'] if yt_inserts is not None else yt_inserts
        )
    if not file_io.file_size(envs.youtube_db_log_schema['db_file']):
        if file_io.file_size(envs.yt_feeds_logs_file):
            log.verbose('Found old json file - logs')
        yt_log_prep_is_ok = await db_helper.prep_table(
            envs.youtube_db_log_schema,
            yt_inserts['logs'] if yt_inserts is not None else yt_inserts
        )
    # Delete old json files if they are not necessary anymore
    if yt_prep_is_ok:
        file_io.remove_file(envs.yt_feeds_file)
    if yt_log_prep_is_ok:
        file_io.remove_file(envs.yt_feeds_logs_file)
    log.verbose('Registering cog to bot')
    await bot.add_cog(Youtube(bot))
    Youtube.post_videos.start()


async def teardown(bot):
    Youtube.post_videos.stop()
