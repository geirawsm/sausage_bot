#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands, tasks
import re
from time import sleep
from yt_dlp import YoutubeDL
from concurrent.futures import ThreadPoolExecutor, as_completed

from sausage_bot.util import config, envs, feeds_core, file_io
from sausage_bot.util import discord_commands
from sausage_bot.util.log import log

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

    def get_yt_info(url):
        'Use yt-dlp to get info about a channel'
        # Get more yt-dlp opts here:
        # https://github.com/ytdl-org/youtube-dl/blob/3e4cedf9e8cd3157df2457df7274d0c842421945/youtube_dl/YoutubeDL.py#L137-L312
        ydl_opts = {
            'simulate': True,
            'download': False,
            'playlistend': 5,
            'ignoreerrors': True,
            'quiet': True
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url)
                return info
        except:
            return None

    def get_videos_from_yt_link(feed, feeds):
        'Get video links from channel'
        log.debug(f'Getting videos from `{feed}`')
        FEED_POSTS = {
            'name': feed,
            'channel': feeds[feed]['channel'],
            'posts': []
        }
        info = Youtube.get_yt_info(feeds[feed]['url'])
        if info is None:
            log.debug(f'`info` in `{feed}` is None')
        elif info['entries'] is not None:
            for item in info['entries']:
                # If the item is a playlist/channel, it also has an
                # 'entries' that needs to be parsed
                if 'entries' in item:
                    for _video in item['entries']:
                        log.debug(f"Got video `{_video['title']}`")
                        FEED_POSTS['posts'].append(_video['original_url'])
                # The channel does not consist of playlists, only videos
                else:
                    log.debug(f"Got video `{item['title']}`")
                    FEED_POSTS['posts'].append(item['original_url'])
        return FEED_POSTS

    def get_all_youtube_videos(feeds):
        vids_out = []
        with ThreadPoolExecutor(
                max_workers=6, thread_name_prefix='Get_YT_vids'
        ) as executor:
            futures = [executor.submit(
                Youtube.get_videos_from_yt_link, feed, feeds) for feed in feeds]
            for future in as_completed(futures):
###     Keeping this here for now
                try:
                    vids_out.append(future.result())
                except Exception:
                    log.debug('Unable to get the result')
###
###     This was replaced by the block above
#                vids_out.append(future.result())
###
        executor.shutdown()
        return vids_out

    async def post_queue_of_youtube_videos(feed_posts):
        for feed_post in feed_posts:
            log.debug(f'Processing: {feed_post}')
            await feeds_core.process_links_for_posting_or_editing(
                feed_post['name'], feed_post['posts'], envs.yt_feeds_logs_file,
                feed_post['channel']
            )

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
                if Youtube.get_yt_info(yt_link) is None:
                    await ctx.send(
                        envs.YOUTUBE_EMPTY_LINK.format(yt_link)
                    )
                    return
                feeds_core.add_to_feed_file(
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
            list_format = feeds_core.get_feed_list(
                envs.yt_feeds_file, long=True
            )
        elif list_type == 'filters':
            list_format = feeds_core.get_feed_list(
                envs.yt_feeds_file, filters=True
            )
        else:
            list_format = feeds_core.get_feed_list(
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
            log.log_more('Got these feeds:')
            for feed in feeds:
                log.log_more('- {}'.format(feed))
            # Start processing per feed settings
            videos = Youtube.get_all_youtube_videos(feeds)
            await Youtube.post_queue_of_youtube_videos(videos)
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
