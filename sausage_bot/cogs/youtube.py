#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands, tasks
from sausage_bot.funcs import _config, _vars, feeds_core, file_io, net_io
from sausage_bot.funcs import discord_commands
from sausage_bot.log import log
import re


class Youtube(commands.Cog):
    'Autopost new videos from given Youtube channels'

    def __init__(self, bot):
        self.bot = bot

    def get_videos_from_yt_link(url):
        'Get the 6 last videos from channel'
        log.debug(f'Got `url`: {url}')
        id_in = url.split('/')[-1]
        log.debug(f'`id_in` is `{id_in}`')
        channel_by_username = f'https://www.youtube.com/feeds/videos.xml?user={id_in}'
        log.debug(f'Got `channel_by_username`: `{channel_by_username}`')
        channel_by_id = f'https://www.youtube.com/feeds/videos.xml?channel_id={id_in}'
        log.debug(f'Got `channel_by_id.items`: `{channel_by_id}`')
        videos = None
        # Try to get videos based on username
        if videos is None:
            try:
                videos = feeds_core.get_feed_links(channel_by_username)
            except:
                pass
        # Try to get videos based on ID
        if videos is None:
            try:
                videos = feeds_core.get_feed_links(channel_by_id)
            except:
                pass
        if videos is None:
            return None
        video_log = []
        for video in videos:
            video_log.append(video)
        return video_log

    def test_link_for_yt_compatibility(url):
        'Test a Youtube-link to make sure it can get videos'
        log.debug(f'Got `url`: {url}')
        id_in = url.split('/')[-1]
        log.debug(f'`id_in` is `{id_in}`')
        channel_by_username = f'https://www.youtube.com/feeds/videos.xml?user={id_in}'
        log.debug(f'Got `channel_by_username`: `{channel_by_username}`')
        channel_by_id = f'https://www.youtube.com/feeds/videos.xml?channel_id={id_in}'
        log.debug(f'Got `channel_by_id.items`: `{channel_by_id}`')
        test_ok = None
        # Try to get videos based on username
        if test_ok is None:
            try:
                test_ok = feeds_core.get_feed_links(channel_by_username)
            except:
                pass
        # Try to get videos based on ID
        if test_ok is None:
            try:
                test_ok = feeds_core.get_feed_links(channel_by_id)
            except:
                pass
        if test_ok is not None:
            return True
        else:
            return False

    @commands.group(name='youtube', aliases=['yt'])
    async def youtube(self, ctx):
        f'''Uses `add` and `remove` to administer what Youtube channels to post
to any given channels on the Discord server.

`list` returns a list over the feeds that are active as of now.

Examples:
```
{_config.PREFIX}youtube add [name of youtube feed] [youtube channel's url] [youtube feed posting channel]

{_config.PREFIX}youtube remove [name of youtube feed]

{_config.PREFIX}youtube list

{_config.PREFIX}youtube list long
```'''
        pass

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @youtube.group(name='add')
    async def add(self, ctx, feed_name=None, yt_link=None, channel=None):
        f'''
        Add a Youtube feed to a specific channel: `{_config.PREFIX}youtube add [feed_name] [yt_link] [channel]`

        `feed_name`:    The custom name for the feed

        `yt_link`:      The link for the youtube-channel

        `channel`:      The Discord channel to post from the feed
        '''
        AUTHOR = ctx.message.author.name
        CHANNEL_OK = False
        if feed_name is None:
            await ctx.send(
                _vars.TOO_FEW_ARGUMENTS
            )
            return
        elif yt_link is None:
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
                        _vars.YOUTUBE_EMPTY_LINK.format(yt_link)
                    )
                    return
                feeds_core.add_feed_to_file(
                    str(feed_name), str(yt_link), channel, AUTHOR,
                    _vars.yt_feeds_file
                )
                await log.log_to_bot_channel(
                    _vars.YOUTUBE_ADDED_BOT.format(
                        AUTHOR, feed_name, yt_link, channel
                    )
                )
                await ctx.send(
                    _vars.YOUTUBE_ADDED.format(feed_name, channel)
                )
                return
            elif not CHANNEL_OK:
                await ctx.send(_vars.CHANNEL_NOT_FOUND)
                return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @youtube.group(name='remove')
    async def remove(self, ctx, feed_name):
        '''Remove a Youtube feed based on `feed_name`'''
        AUTHOR = ctx.message.author.name
        removal = feeds_core.remove_feed_from_file(
            feed_name, _vars.yt_feeds_file
        )
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

    @youtube.group(name='list')
    async def list_youtube(self, ctx, long=None):
        'List all active Youtube feeds'
        if long is None:
            list_format = feeds_core.get_feed_list(_vars.yt_feeds_file)
        elif long == 'long':
            list_format = feeds_core.get_feed_list(
                _vars.yt_feeds_file, long=True)
        await ctx.send(list_format)
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

    @tasks.loop(minutes=1)
    async def youtube_parse():
        log.log('Starting `youtube_parse`')
        # Update the feeds
        feeds = file_io.read_json(_vars.yt_feeds_file)
        try:
            if len(feeds) == 0:
                log.log(_vars.RSS_NO_FEEDS_FOUND)
                return
        except Exception as e:
            log.log(f'Got error when getting RSS feeds: {e}')
            if feeds is None:
                log.log(_vars.RSS_NO_FEEDS_FOUND)
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
                    feed, FEED_POSTS, _vars.yt_feeds_logs_file, CHANNEL
                )
        return

    @youtube_parse.before_loop
    async def before_youtube_parse():
        log.log_more('`youtube_parse` waiting for bot to be ready...')
        await _config.bot.wait_until_ready()

    youtube_parse.start()


async def setup(bot):
    log.log(_vars.COG_STARTING.format('youtube'))
    # Create necessary files before starting
    log.log_more(_vars.CREATING_FILES)
    check_and_create_files = [
        (_vars.yt_feeds_file, '{}'),
        _vars.yt_feeds_logs_file
    ]
    file_io.create_necessary_files(check_and_create_files)
    # Starting the cog
    await bot.add_cog(Youtube(bot))
