#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands, tasks
import discord
import typing
import re
from time import sleep
from yt_dlp import YoutubeDL

from sausage_bot.util import config, envs, feeds_core, file_io
from sausage_bot.util import db_helper, discord_commands
from sausage_bot.util.log import log


async def feed_name_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    feed_names = [name[0] for name in await db_helper.get_output(
            template_info=envs.youtube_db_schema,
            select=('feed_name')
        )
    ]
    return [
        discord.app_commands.Choice(name=feed_name, value=feed_name)
        for feed_name in feed_names if current.lower() in feed_name.lower()
    ]


async def youtube_filter_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[discord.app_commands.Choice[str]]:
    db_filters = await db_helper.get_combined_output(
        template_info_1=envs.youtube_db_schema,
        template_info_2=envs.youtube_db_filter_schema,
        key='uuid',
        select=['feed_name', 'allow_or_deny', 'filter'],
        order_by=[
            ('allow_or_deny', 'ASC'),
            ('filter', 'ASC')
        ]
    )
    filters = []
    for filter in db_filters:
        filters.append((filter[0], filter[1], filter[2]))
    log.debug(f'filters: {filters}')
    return [
        discord.app_commands.Choice(
            name=f'{filter[0]} - {filter[1]} - {filter[2]}',
            value=str(filter[2])
        )
        for filter in filters if current.lower() in filter[2].lower()
    ]


class Youtube(commands.Cog):
    'Autopost new videos from given Youtube channels'

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    youtube_group = discord.app_commands.Group(
        name="youtube", description='Administer YouTube feeds'
    )

    youtube_filter_group = discord.app_commands.Group(
        name="filter", description='Filter YouTube feeds',
        parent=youtube_group
    )

    youtube_posting_group = discord.app_commands.Group(
        name="posting", description='Posting from YouTube feeds',
        parent=youtube_group
    )

    @youtube_posting_group.command(
        name='start', description='Start posting'
    )
    async def youtube_posting_start(
        self, interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)
        log.log('Task started')
        Youtube.post_videos.start()
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[
                ('cog', 'youtube'),
                ('task', 'post_videos')
            ],
            updates=('status', 'started')
        )
        await interaction.followup.send(
            'Youtube posting started'
        )

    @youtube_posting_group.command(
        name='stop', description='Stop posting'
    )
    async def youtube_posting_stop(
        self, interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)
        log.log('Task stopped')
        Youtube.post_videos.cancel()
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[
                ('task', 'post_videos'),
                ('cog', 'youtube'),
            ],
            updates=('status', 'stopped')
        )
        await interaction.followup.send(
            'Youtube posting stopped'
        )

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @discord.app_commands.autocomplete(feed_name=feed_name_autocomplete)
    @youtube_group.command(
        name='add', description='Add a YouTube-feed'
    )
    async def youtube_add(
        self, interaction: discord.Interaction, feed_name: str,
        youtube_link: str, channel: discord.TextChannel
    ):
        '''
        Add a Youtube feed

        Parameters
        ------------
        feed_name: str
            Name of feed to manage
        youtube_link: str
            The link for the YouTube-channel
        channel: str
            The Discord channel to post from the feed
        '''
        await interaction.response.defer()
        AUTHOR = interaction.user.name
        # Get yt-id
        youtube_info = await Youtube.get_youtube_info(youtube_link)
        if youtube_info is None:
            await interaction.followup.send(
                envs.YOUTUBE_EMPTY_LINK.format(youtube_link)
            )
            return
        await feeds_core.add_to_feed_db(
            'youtube', str(feed_name), str(youtube_link), channel.name,
            AUTHOR, youtube_info['channel_id']
        )
        await discord_commands.log_to_bot_channel(
            envs.YOUTUBE_ADDED_BOT.format(
                AUTHOR, feed_name, youtube_link, channel.name
            )
        )
        await interaction.followup.send(
            envs.YOUTUBE_ADDED.format(feed_name, channel.name)
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @discord.app_commands.autocomplete(feed_name=feed_name_autocomplete)
    @youtube_group.command(
        name='remove', description='Remove a YouTube-feed'
    )
    async def youtube_remove(
        self, interaction: discord.Interaction, feed_name: str
    ):
        '''
        Remove a Youtube feed

        Parameters
        ------------
        feed_name: str
            Name of feed to manage
        '''
        await interaction.response.defer()
        AUTHOR = interaction.user.name
        _uuid = await db_helper.get_output(
            template_info=envs.youtube_db_schema,
            select=('uuid'),
            where=(('feed_name', feed_name)),
            single=True
        )
        if _uuid is None:
            _error_msg = f'The feed `{feed_name}` does not exist'
            log.debug(_error_msg)
            await interaction.followup.send(
                _error_msg
            )
            return
        removal = await feeds_core.remove_feed_from_db(
            feed_type='youtube', feed_name=feed_name
        )
        if removal:
            await discord_commands.log_to_bot_channel(
                envs.YOUTUBE_REMOVED_BOT.format(feed_name, AUTHOR)
            )
            await interaction.followup.send(
                envs.YOUTUBE_REMOVED.format(feed_name)
            )
        elif removal is False:
            # Couldn't remove the feed
            await interaction.followup.send(
                envs.YOUTUBE_COULD_NOT_REMOVE.format(feed_name)
            )
            # Also log and send error to either a bot-channel or admin
            await discord_commands.log_to_bot_channel(
                envs.YOUTUBE_TRIED_REMOVED_BOT.format(AUTHOR, feed_name)
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @discord.app_commands.autocomplete(feed_name=feed_name_autocomplete)
    @youtube_filter_group.command(
        name='add', description='Add filters on an Youtube feed'
    )
    async def youtube_filter_add(
        self, interaction: discord.Interaction, feed_name: str,
        allow_deny: typing.Literal['Allow', 'Deny'], filters_in: str
    ):
        '''
        Add filter for feed (deny/allow)

        Parameters
        ------------
        feed_name: str
            Name of feed
        allow_deny: str
            Specify if the filter should `allow` or `deny`. Separate multiples
            with any of the following characers: " .,;-_\\/"
        filters_in: str
            What to filter a post by. Separate multiple with any of the
            following characers: " .,;-_\\/"

        '''
        await interaction.response.defer(ephemeral=True)
        # Make sure that the filter input can be split
        _filters_in = re.split(
            envs.input_split_regex, filters_in
        )
        _uuid = await db_helper.get_output(
            template_info=envs.youtube_db_schema,
            select=('uuid'),
            where=(('feed_name', feed_name)),
            single=True
        )
        temp_inserts = []
        for _index, filter in enumerate(_filters_in):
            temp_inserts.append((_uuid, allow_deny, filter))
        adding_filter = await db_helper.insert_many_all(
            template_info=envs.youtube_db_filter_schema,
            inserts=temp_inserts
        )
        if adding_filter:
            msg_out = f'Added filters as {allow_deny}:'
            for filter in _filters_in:
                msg_out += f'\n- {filter}'
            await interaction.followup.send(msg_out, ephemeral=True)
        else:
            await interaction.followup.send(
                'Error when adding filter, check logs',
                ephemeral=True
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @discord.app_commands.autocomplete(feed_name=feed_name_autocomplete)
    @discord.app_commands.autocomplete(filter_in=youtube_filter_autocomplete)
    @youtube_filter_group.command(
        name='remove', description='Remove filters on an Youtube feed'
    )
    async def youtube_filter_remove(
        self, interaction: discord.Interaction, feed_name: str, filter_in: str
    ):
        '''
        Remove filter for feed

        Parameters
        ------------
        feed_name: str
            Name of feed
        filter_in: str
            What filter to look for
        '''
        await interaction.response.defer(ephemeral=True)
        _uuid = await db_helper.get_output(
            template_info=envs.youtube_db_schema,
            select=('uuid'),
            where=(('feed_name', feed_name)),
            single=True
        )
        removing_filter = await db_helper.del_row_by_AND_filter(
            template_info=envs.youtube_db_filter_schema,
            where=(
                ('uuid', _uuid),
                ('filter', filter_in)
            )
        )
        if removing_filter:
            await interaction.followup.send(
                f'Removed filter `{filter_in}`',
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f'Error when removing filter `{filter_in}`, check logs',
                ephemeral=True
            )
        return

    @youtube_group.command(
        name='list', description='List all active YouTube feeds'
    )
    async def youtube_list(
        self, interaction: discord.Interaction,
        list_type: typing.Literal['Normal', 'Added', 'Filter']
    ):
        '''
        List all active Youtube feeds
        '''
        await interaction.response.defer()
        if list_type.lower() == 'added':
            formatted_list = await feeds_core.get_feed_list(
                db_in=envs.youtube_db_schema,
                list_type=list_type.lower()
            )
        elif list_type.lower() == 'filter':
            formatted_list = await feeds_core.get_feed_list(
                db_in=envs.youtube_db_schema,
                db_filter_in=envs.youtube_db_filter_schema,
                list_type=list_type.lower()
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
                await interaction.followup.send(
                    f"```{page}```"
                )
                sleep(1)
        else:
            await interaction.followup.send(
                'No feeds added'
            )
        return

    async def get_youtube_info(url):
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
            log.error(f'Could not extract youtube info: {_error}')
            return None

    # Tasks
    @tasks.loop(
        minutes=config.env.int('YT_LOOP', default=5)
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
                await discord_commands.log_to_bot_channel(
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

    # Define inserts
    youtube_inserts = None
    youtube_prep_is_ok = None
    youtube_log_prep_is_ok = None
    # Populate the inserts if feed and logs json files exist
    if file_io.file_exist(envs.youtube_feeds_file) and \
            file_io.file_exist(envs.youtube_feeds_logs_file):
        log.verbose('Found old json file - feeds')
        youtube_inserts = await db_helper.json_to_db_inserts(cog_name)
    log.debug(f'Got these inserts:\n{youtube_inserts}')

    # Prep of DBs should only be done if the db files does not exist
    if not file_io.file_exist(envs.youtube_db_schema['db_file']):
        log.verbose('Youtube db does not exist')
        youtube_prep_is_ok = await db_helper.prep_table(
            table_in=envs.youtube_db_schema,
            old_inserts=youtube_inserts['feeds'] if youtube_inserts is not None
            else youtube_inserts
        )
        youtube_filter_prep_is_ok = await db_helper.prep_table(
            envs.youtube_db_filter_schema,
            youtube_inserts['filter']
            if youtube_inserts is not None else youtube_inserts
        )
        youtube_log_prep_is_ok = await db_helper.prep_table(
            envs.youtube_db_log_schema,
            youtube_inserts['logs']
            if youtube_inserts is not None else youtube_inserts
        )
        log.verbose(f'`youtube_prep_is_ok` is {youtube_prep_is_ok}')
        log.verbose(
            f'`youtube_filter_prep_is_ok` is {youtube_filter_prep_is_ok}'
        )
        log.verbose(f'`youtube_log_prep_is_ok` is {youtube_log_prep_is_ok}')
    else:
        log.verbose('youtube db exist!')
    # Delete old json files if they are not necessary anymore
    if youtube_prep_is_ok:
        file_io.remove_file(envs.youtube_feeds_file)
    if youtube_log_prep_is_ok:
        file_io.remove_file(envs.youtube_feeds_logs_file)
    log.verbose('Registering cog to bot')
    await bot.add_cog(Youtube(bot))

    task_list = await db_helper.get_output(
        template_info=envs.tasks_db_schema,
        select=('task', 'status'),
        where=('cog', 'youtube')
    )
    if len(task_list) == 0:
        await db_helper.insert_many_all(
            template_info=envs.tasks_db_schema,
            inserts=(
                ('youtube', 'post_videos', 'stopped')
            )
        )
    for task in task_list:
        if task[0] == 'post_videos':
            if task[1] == 'started':
                log.debug(f'`{task[0]}` is set as `{task[1]}`, starting...')
                Youtube.post_videos.start()
            elif task[1] == 'stopped':
                log.debug(f'`{task[0]}` is set as `{task[1]}`')
                Youtube.post_videos.cancel()


async def teardown(bot):
    Youtube.post_videos.cancel()
