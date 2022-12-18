#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands, tasks
from sausage_bot.util import config, mod_vars, feeds_core, file_io
from sausage_bot.util import discord_commands
from sausage_bot.util.log import log
import re
from yt_dlp import YoutubeDL


env_template = {
    'youtube_loop': 5
}
config.add_cog_envs_to_env_file('youtube', env_template)

env = config.config()['youtube']


class Youtube(commands.Cog):
    'Autopost new videos from given Youtube channels'

    def __init__(self, bot):
        self.bot = bot

    def get_yt_id(url):
        'Use yt-dlp to get the ID of a channel'
        # Get more yt-dlp opts here:
        # https://github.com/ytdl-org/youtube-dl/blob/3e4cedf9e8cd3157df2457df7274d0c842421945/youtube_dl/YoutubeDL.py#L137-L312
        ydl_opts = {
            'playlistend': 0,
            'simulate': True,
            'quiet': True
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info['uploader_id']

    def get_videos_from_yt_link(url):
        'Get the 6 last videos from channel'
        log.debug(f'Got `url`: {url}')
        id_in = Youtube.get_yt_id(url)
        channel_by_id = f'https://www.youtube.com/feeds/videos.xml?channel_id={id_in}'
        log.debug(f'Got `channel_by_id`: `{channel_by_id}`')
        videos = feeds_core.get_feed_links(channel_by_id)
        video_log = []
        for video in videos[0:6]:
            video_log.append(video)
        return video_log

    def test_link_for_yt_compatibility(url):
        'Test a Youtube-link to make sure it can get videos'
        log.debug(f'Got `url`: {url}')
        id_in = Youtube.get_yt_id(url)
        channel_by_id = f'https://www.youtube.com/feeds/videos.xml?channel_id={id_in}'
        log.debug(f'Got `channel_by_id.items`: `{channel_by_id}`')
        videos = feeds_core.get_feed_links(channel_by_id)
        return videos[0]

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
                mod_vars.TOO_FEW_ARGUMENTS
            )
            return
        elif yt_link is None:
            await ctx.send(
                mod_vars.TOO_FEW_ARGUMENTS
            )
            return
        elif channel is None:
            await ctx.send(
                mod_vars.TOO_FEW_ARGUMENTS
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
                if not Youtube.test_link_for_yt_compatibility(yt_link):
                    await ctx.send(
                        mod_vars.YOUTUBE_EMPTY_LINK.format(yt_link)
                    )
                    return
                feeds_core.add_to_feed_file(
                    str(feed_name), str(yt_link), channel, AUTHOR,
                    mod_vars.yt_feeds_file
                )
                await log.log_to_bot_channel(
                    mod_vars.YOUTUBE_ADDED_BOT.format(
                        AUTHOR, feed_name, yt_link, channel
                    )
                )
                await ctx.send(
                    mod_vars.YOUTUBE_ADDED.format(feed_name, channel)
                )
                return
            elif not CHANNEL_OK:
                await ctx.send(
                    mod_vars.CHANNEL_NOT_FOUND.format(channel)
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
            feed_name, mod_vars.yt_feeds_file
        )
        if removal:
            await log.log_to_bot_channel(
                mod_vars.RSS_REMOVED_BOT.format(feed_name, AUTHOR)
            )
            await ctx.send(
                mod_vars.RSS_REMOVED.format(feed_name)
            )
        elif removal is False:
            # Couldn't remove the feed
            await ctx.send(mod_vars.RSS_COULD_NOT_REMOVE.format(feed_name))
            # Also log and send error to either a bot-channel or admin
            await log.log_to_bot_channel(
                mod_vars.RSS_TRIED_REMOVED_BOT.format(AUTHOR, feed_name)
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
            list_format = feeds_core.get_feed_list(
                mod_vars.yt_feeds_file, long=True
            )
        elif list_type == 'filters':
            list_format = feeds_core.get_feed_list(
                mod_vars.yt_feeds_file, filters=True
            )
        else:
            list_format = feeds_core.get_feed_list(
                mod_vars.yt_feeds_file
            )
        if list_format is not None:
            await ctx.send(list_format)
        else:
            await ctx.send('No feeds added')
        return

    async def process_links_for_posting_or_editing(
        feed, FEED_POSTS, feed_log_file, CHANNEL
    ):
        'Check new links against the log and post them if they are brand new'
        FEED_LOG = file_io.read_json(feed_log_file)
        try:
            FEED_LOG[feed]
        except (KeyError):
            FEED_LOG[feed] = []
        for video in FEED_POSTS[0:2]:
            log.log_more(f'Got video `{video}`')
            # Check if the link is in the log
            if not feeds_core.link_is_in_log(video, FEED_LOG[feed]):
                # Consider this a whole new post and post link to channel
                log.log_more(f'Posting link `{video}`')
                await discord_commands.post_to_channel(video, CHANNEL)
                # Add link to log
                FEED_LOG[feed].append(video)
            elif feeds_core.link_is_in_log(video, FEED_LOG[feed]):
                log.log_more(f'Link `{video}` already logged. Skipping.')
            # Write to the logs-file at the end
            file_io.write_json(feed_log_file, FEED_LOG)

    # Tasks

    @tasks.loop(minutes=env['youtube_loop'])
    async def youtube_parse():
        log.log('Starting `youtube_parse`')
        # Update the feeds
        feeds = file_io.read_json(mod_vars.yt_feeds_file)
        try:
            if len(feeds) == 0:
                log.log(mod_vars.RSS_NO_FEEDS_FOUND)
                return
        except Exception as e:
            log.log(f'Got error when getting RSS feeds: {e}')
            if feeds is None:
                log.log(mod_vars.RSS_NO_FEEDS_FOUND)
                return
        else:
            log.log_more('Got these feeds:')
            for feed in feeds:
                log.log_more('- {}'.format(feed))
            # Start processing per feed settings
            for feed in feeds:
                CHANNEL = feeds[feed]['channel']
                URL = feeds[feed]['url']
                log.log('Checking {} ({})'.format(feed, CHANNEL))
                FEED_POSTS = Youtube.get_videos_from_yt_link(URL)
                if FEED_POSTS is None:
                    log.log(f'{feed}: this feed returned NoneType.')
                    return
                await Youtube.process_links_for_posting_or_editing(
                    feed, FEED_POSTS, mod_vars.yt_feeds_logs_file, CHANNEL
                )
        return

    @youtube_parse.before_loop
    async def before_youtube_parse():
        log.log_more('`youtube_parse` waiting for bot to be ready...')
        await config.bot.wait_until_ready()

    youtube_parse.start()


async def setup(bot):
    log.log(mod_vars.COG_STARTING.format('youtube'))
    # Create necessary files before starting
    log.log_more(mod_vars.CREATING_FILES)
    check_and_create_files = [
        (mod_vars.yt_feeds_file, '{}'),
        mod_vars.yt_feeds_logs_file
    ]
    file_io.create_necessary_files(check_and_create_files)
    # Starting the cog
    await bot.add_cog(Youtube(bot))


if __name__ == "__main__":
    print(Youtube.get_yt_id('https://www.youtube.com/@centurymedia'))