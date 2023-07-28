#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands, tasks
import re
from time import sleep
from yt_dlp import YoutubeDL

from sausage_bot.util import config, envs, feeds_core, file_io
from sausage_bot.util import discord_commands
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
    async def add(
        self, ctx, feed_name: str = commands.param(
            default=None,
            description="Name of feed"
        ),
        yt_link: str = commands.param(
            default=None,
            description="The link for the youtube-channel"
        ),
        channel: str = commands.param(
            default=None,
            description="The Discord channel to post from the feed")
    ):
        'Add a Youtube feed to a specific channel: `!youtube add '\
            '[feed_name] [yt_link] [channel]`'
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
                # Remove trailing slash from url
                try:
                    slash_filter = re.match(r'(.*)/$', yt_link).group(1)
                    if slash_filter:
                        yt_link = slash_filter
                except:
                    pass
                # Get yt-id
                yt_info = await Youtube.get_yt_info(yt_link)
                if yt_info is None:
                    await ctx.send(
                        envs.YOUTUBE_EMPTY_LINK.format(yt_link)
                    )
                    return
                await feeds_core.add_to_feed_file(
                    name=str(feed_name), feed_link=str(yt_link),
                    channel=channel, user_add=AUTHOR,
                    feeds_filename=envs.yt_feeds_file,
                    yt_id=yt_info['channel_id']
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
    @youtube.group(name='remove', aliases=['delete', 'del'])
    async def remove(
        self, ctx, feed_name: str = commands.param(
            default=None,
            description="Name of feed"
        )
    ):
        'Remove a Youtube feed: `!youtube remove [feed_name]`'
        AUTHOR = ctx.message.author.name
        removal = feeds_core.remove_feed_from_file(
            feed_name, envs.yt_feeds_file
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
    async def list_youtube(
            self, ctx, list_type: str = commands.param(
                default=None,
                description="`added` or `filter`"
            )):
        'List all active Youtube feeds: !youtube list ([list_type])'
        if list_type == 'added':
            list_format = await feeds_core.get_feed_list(
                envs.yt_feeds_file, envs.YOUTUBE_VARS, list_type='added'
            )
        elif list_type == 'filter':
            list_format = await feeds_core.get_feed_list(
                envs.yt_feeds_file, envs.YOUTUBE_VARS, list_type='filter'
            )
        else:
            list_format = await feeds_core.get_feed_list(
                envs.yt_feeds_file, envs.YOUTUBE_VARS
            )
        if list_format is not None:
            for page in list_format:
                log.debug(f'Sending page ({len(page)} / {len(list_format)})')
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

    async def process_links_for_posting_or_editing(
        name, videos, feed_info, feed_log_file
    ):
        log.debug(f'Got `videos`: {videos}')
        log.debug(f'Got `feed_info`: {feed_info}')
        CHANNEL = feed_info['channel']
        FEED_LOG = file_io.read_json(feed_log_file)
        try:
            FEED_LOG[name]
        except (KeyError):
            FEED_LOG[name] = []
        for feed_link in videos[0:2]:
            log.debug(f'Got feed_link `{feed_link}`')
            # Check if the link is in the log
            if not feeds_core.link_is_in_log(feed_link, name, FEED_LOG):
                feed_link_similar = feeds_core.link_similar_to_logged_post(
                    feed_link, FEED_LOG[name])
                if not feed_link_similar:
                    # Consider this a whole new post and post link to channel
                    log.log_more(f'Posting link `{feed_link}`')
                    await discord_commands.post_to_channel(CHANNEL, feed_link)
                    # Add link to log
                    FEED_LOG[name].append(feed_link)
                elif feed_link_similar:
                    # Consider this a similar post that needs to
                    # be edited in the channel
                    await discord_commands.replace_post(
                        feed_link_similar, feed_link, CHANNEL
                    )
                    FEED_LOG[name].remove(feed_link_similar)
                    FEED_LOG[name].append(feed_link)
            elif feeds_core.link_is_in_log(feed_link, name, FEED_LOG):
                log.log_more(f'Link `{feed_link}` already logged. Skipping.')
            # Write to the logs-file at the end
            file_io.write_json(feed_log_file, FEED_LOG)

    # Tasks
    @tasks.loop(
            minutes=config.env.int('YT_LOOP', default=5),
            reconnect=True
    )
    async def post_videos():
        log.log('Starting `post_videos`')
        # Update the feeds
        feeds = file_io.read_json(envs.yt_feeds_file)
        try:
            if len(feeds) == 0:
                log.log(envs.YOUTUBE_NO_FEEDS_FOUND)
                return
        except Exception as e:
            log.log(f'Got error when getting RSS feeds: {e}')
            if feeds is None:
                log.log(envs.YOUTUBE_NO_FEEDS_FOUND)
                return
        for feed in feeds:
            log.log(f'Checking {feed}', sameline=True)
            FEED_POSTS = await feeds_core.get_feed_links(
                feed, envs.YOUTUBE_RSS_LINK.format(feeds[feed]['yt_id']),
                feeds[feed]['filter_allow'],
                feeds[feed]['filter_deny'], 'youtube',
                include_shorts=config.env.bool(
                    'YT_INCLUDE_SHORTS', default=True
                )
            )
            CHANNEL = feeds[feed]['channel']
            log.debug(f'Got this for `FEED_POSTS`: {FEED_POSTS}')
            if FEED_POSTS is None:
                log.log(envs.YOUTUBE_FEED_POSTS_IS_NONE.format(feed))
            else:
                await feeds_core.process_links_for_posting_or_editing(
                    feed, FEED_POSTS, envs.yt_feeds_logs_file, CHANNEL
                )
        log.log('Done with posting')

        return

    @post_videos.before_loop
    async def before_post_new_videos():
        '#autodoc skip#'
        log.log_more('`post_videos` waiting for bot to be ready...')
        await config.bot.wait_until_ready()

    post_videos.start()


async def setup(bot):
    log.log(envs.COG_STARTING.format('youtube'))
    # Create necessary files before starting
    log.log_more(envs.CREATING_FILES)
    check_and_create_files = [
        (envs.yt_feeds_file, {}),
        envs.yt_feeds_logs_file
    ]
    file_io.create_necessary_files(check_and_create_files)
    # Starting the cog
    await bot.add_cog(Youtube(bot))


if __name__ == "__main__":
    pass
