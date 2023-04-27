#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands, tasks
import re
from time import sleep
from yt_dlp import YoutubeDL
import asyncio

from sausage_bot.util import config, envs, feeds_core, file_io
from sausage_bot.util import discord_commands
from sausage_bot.util.log import log
from sausage_bot.docs.autodoc import dump_output

env_template = {
    'youtube_loop': 5,
    'filter_priority': ''   # 'allow' or 'deny'
}
config.add_cog_envs_to_env_file('youtube', env_template)

env = config.config()['youtube']


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
        'Add a Youtube feed to a specific channel: `!youtube add [feed_name] [yt_link] [channel]`'
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
                # Test if the link can get videos
                yt_info = await Youtube.get_yt_info(yt_link)
                if yt_info is None:
                    await ctx.send(
                        envs.YOUTUBE_EMPTY_LINK.format(yt_link)
                    )
                    return
                await feeds_core.add_to_feed_file(
                    str(feed_name), str(yt_link), channel, AUTHOR,
                    envs.yt_feeds_file
                )
                await log.log_to_bot_channel(
                    envs.YOUTUBE_ADDED_BOT.format(
                        AUTHOR, feed_name, yt_link, channel
                    )
                )
                await ctx.send(
                    envs.YOUTUBE_ADDED.format(feed_name, channel)
                )
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

    @youtube.group(name='list')
    async def list_youtube(
            self, ctx, list_type: str = commands.param(
                default=None,
                description="`long` will give a longer list of the feed"
            )):
        'List all active Youtube feeds'
        if list_type == 'long':
            list_format = await feeds_core.get_feed_list(
                envs.yt_feeds_file, long=True
            )
        elif list_type == 'filters':
            list_format = await feeds_core.get_feed_list(
                envs.yt_feeds_file, filters=True
            )
        else:
            list_format = await feeds_core.get_feed_list(
                envs.yt_feeds_file
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
        info = None
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
        except:
            log.debug('Could not extract youtube info')
            return None

    async def get_videos_from_yt_link(name, feed) -> dict:
        'Get video links from channel'
        log.debug(f'Getting videos from `{name}` ({feed["url"]})')
        FEED_POSTS =[]
        info = await Youtube.get_yt_info(feed['url'])
        if not info:
            return FEED_POSTS
        if 'entries' in info:
            for item in info['entries']:
                # If the item is a playlist/channel, it also has an
                # 'entries' that needs to be parsed
                try:
                    if 'entries' in item:
                        for _video in item['entries']:
                            if _video is not None:
                                log.debug(f"Got video `{_video['title']}`")
                                FEED_POSTS.append(_video['original_url'])
                    # The channel does not consist of playlists, only videos
                    else:
                        log.debug(f"Got video `{item['title']}`")
                        FEED_POSTS.append(item['original_url'])
                        await asyncio.sleep(1)
                except:
                    log.debug(f"Could not find `entries` or `title` in `item`. This has been logged.")
                    dump_output(item['entries'], name='get_videos_from_yt_link')
        return FEED_POSTS

    async def post_queue_of_youtube_videos(feed_name, feed_info, videos):
        log.debug(f'Processing: {feed_name}')
        #await feeds_core.process_links_for_posting_or_editing(
        await Youtube.process_links_for_posting_or_editing(
            feed_name, videos, feed_info, envs.yt_feeds_logs_file
        )
        await asyncio.sleep(1)

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
            if not feeds_core.link_is_in_log(feed_link, FEED_LOG[name]):
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
            elif feeds_core.link_is_in_log(feed_link, FEED_LOG[name]):
                log.log_more(f'Link `{feed_link}` already logged. Skipping.')
            # Write to the logs-file at the end
            file_io.write_json(feed_log_file, FEED_LOG)


    # Tasks
    @tasks.loop(minutes=env['youtube_loop'])
    async def youtube_parse():
        log.log('Starting `youtube_parse`')
        # Update the feeds
        feeds = file_io.read_json(envs.yt_feeds_file)
        try:
            if len(feeds) == 0:
                log.log(envs.RSS_NO_FEEDS_FOUND)
                return
        except Exception as e:
            log.log(f'Got error when getting RSS feeds: {e}')
            if feeds is None:
                log.log(envs.RSS_NO_FEEDS_FOUND)
                return
        else:
            for feed in feeds:
                videos_from_feed = await Youtube.get_videos_from_yt_link(
                    feed, feeds[feed]
                )
                await Youtube.post_queue_of_youtube_videos(
                    feed, feeds[feed], videos_from_feed
                )
        return

    @youtube_parse.before_loop
    async def before_youtube_parse():
        log.log_more('`youtube_parse` waiting for bot to be ready...')
        await config.bot.wait_until_ready()

    youtube_parse.start()


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
