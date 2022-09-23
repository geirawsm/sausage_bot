#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands, tasks
from sausage_bot.funcs import _config, datetimefuncs, _vars, file_io
from sausage_bot.funcs import rss_core, discord_commands
from sausage_bot.log import log
import pyyoutube


class Youtube(commands.Cog):
    'Autopost new videos from given Youtube channels'
    def __init__(self, bot):
        self.bot = bot


    def add_feed_to_file(self, name, feed_link, channel, user_add):
        '''Add a new Youtube feed'''
        date_now = datetimefuncs.get_dt(format='datetime')
        feeds_file = file_io.read_json(_vars.yt_feeds_file)
        feeds_file[name] = {'url': feed_link,
                        'channel': channel,
                        'added': date_now,
                        'added by': user_add}
        file_io.write_json(_vars.yt_feeds_file, feeds_file)


    def remove_feed_from_file(name):
        '''Remove a Youtube feed from the feeds file'''
        name = str(name)
        feeds_file = file_io.read_json(_vars.yt_feeds_file)
        try:
            feeds_file.pop(name)
            file_io.write_json(_vars.yt_feeds_file, feeds_file)
            return True
        except(KeyError):
            return False


    def get_videos_from_yt_link(url):
        'Get the 6 last videos from channel'
        id_in = url.split('/')[-1]
        api = pyyoutube.Api(api_key=_config.YOUTUBE_API_KEY)
        channel_info = None
        channel_by_username = api.get_channel_info(for_username=id_in)
        channel_by_id = api.get_channel_info(channel_id=id_in)
        if channel_by_username.items is not None:
            channel_info = channel_by_username
        elif channel_by_id.items is not None:
            channel_info = channel_by_id
        else:
            log.log_more(f'Nothing found')
            return None
        playlist_id = channel_info.items[0].contentDetails.relatedPlaylists.uploads
        uploads_playlist_items = api.get_playlist_items(
            playlist_id=playlist_id, count=10, limit=6
        )
        videos = []
        for item in uploads_playlist_items.items:
            video_id = item.contentDetails.videoId
            videos.append(video_id)
        return videos


    @commands.group(name='youtube', aliases=['yt'])
    async def youtube(self, ctx):
        '''Uses `add` and `remove` to administer what Youtube channels to post
to any given channels on the Discord server.

`list` returns a list over the feeds that are active as of now.

Examples:
```
!youtube add [name of youtube feed] [youtube channel's url] [youtube feed posting channel]

!youtube remove [name of youtube feed]

!youtube list

!youtube list long
```'''
        pass

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @youtube.group(name='add')
    async def add(self, ctx, feed_name=None, yt_link=None, channel=None):
        '''
        Add a Youtube feed to a specific channel: `!youtube add [feed_name] [yt_link] [channel]`

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
                self.add_feed_to_file(str(feed_name), str(yt_link), channel, AUTHOR)
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
        removal = rss_core.remove_feed_from_file(
            feed_name, _vars.yt_feeds_file
        )
        if removal:
            log.log_to_bot_channel(
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
            list_format = rss_core.get_feed_list(_vars.yt_feeds_file)
        elif long == 'long':
            list_format = rss_core.get_feed_list(_vars.yt_feeds_file, long=True)
        await ctx.send(list_format)
        return


    async def process_links_for_posting_or_editing(
        feed, FEED_POSTS, feed_log_file, CHANNEL
    ):
        'Check new links against the log and post them if they are brand new'
        FEED_LOG = file_io.read_json(feed_log_file)
        try:
            FEED_LOG[feed]
        except(KeyError):
            FEED_LOG[feed] = []
        for video_id in FEED_POSTS[0:2]:
            log.log_more(f'Got video_id `{video_id}`')
            # Check if the link is in the log
            if not rss_core.link_is_in_log(video_id, FEED_LOG[feed]):
                # Consider this a whole new post and post link to channel
                video_link = f'https://www.youtube.com/watch?v={video_id}'
                log.log_more(f'Posting link `{video_link}`')
                await discord_commands.post_to_channel(video_link, CHANNEL)
                # Add link to log
                FEED_LOG[feed].append(video_id)
            elif rss_core.link_is_in_log(video_id, FEED_LOG[feed]):
                log.log_more(f'Link `{video_id}` already logged. Skipping.')
            # Write to the logs-file at the end
            file_io.write_json(feed_log_file, FEED_LOG)


    #Tasks
    @tasks.loop(minutes = 1)
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
