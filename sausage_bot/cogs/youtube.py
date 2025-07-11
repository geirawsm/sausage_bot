#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'youtube: Autopost new videos from given Youtube channels'
import discord
from discord.ext import commands, tasks
from discord.app_commands import locale_str, describe
import typing
from time import sleep
from yt_dlp import YoutubeDL

from sausage_bot.util import config, envs, feeds_core, file_io
from sausage_bot.util import db_helper, discord_commands
from sausage_bot.util.i18n import I18N

logger = config.logger


async def feed_name_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    feed_names = [
        name['feed_name'] for name in await db_helper.get_output(
            template_info=envs.youtube_db_schema,
            select=('feed_name')
        )
    ]
    return [
        discord.app_commands.Choice(name=feed_name, value=feed_name)
        for feed_name in feed_names if current.lower() in feed_name.lower()
    ][:25]


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
        filters.append(
            (filter['feed_name'], filter['allow_or_deny'], filter['filter'])
        )
    logger.debug(f'filters: {filters}')
    return [
        discord.app_commands.Choice(
            name='{} - {} - {}'.format(
                filter['feed_name'], filter['allow_or_deny'], filter['filter']
            ),
            value=str(filter['filter'])
        )
        for filter in filters if current.lower() in filter['filter'].lower()
    ][:25]


class Youtube(commands.Cog):
    'Autopost new videos from given Youtube channels'

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    youtube_group = discord.app_commands.Group(
        name="youtube", description=locale_str(
            I18N.t('youtube.groups.youtube')
        )
    )

    youtube_filter_group = discord.app_commands.Group(
        name="filter", description=locale_str(
            I18N.t('youtube.groups.filter')
        ),
        parent=youtube_group
    )

    youtube_posting_group = discord.app_commands.Group(
        name="posting", description=locale_str(
            I18N.t('youtube.groups.posting')
        ),
        parent=youtube_group
    )

    @youtube_posting_group.command(
        name='start', description=locale_str(
            I18N.t('youtube.commands.start.cmd')
        )
    )
    async def youtube_posting_start(
        self, interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)
        logger.info('Task started')
        Youtube.task_post_videos.start()
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[
                ('cog', 'youtube'),
                ('task', 'post_videos')
            ],
            updates=('status', 'started')
        )
        await interaction.followup.send(
            I18N.t('youtube.commands.start.msg_confirm')
        )

    @youtube_posting_group.command(
        name='stop', description=locale_str(
            I18N.t('youtube.commands.stop.cmd')
        )
    )
    async def youtube_posting_stop(
        self, interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)
        logger.info('Task stopped')
        Youtube.task_post_videos.cancel()
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[
                ('task', 'post_videos'),
                ('cog', 'youtube'),
            ],
            updates=('status', 'stopped')
        )
        await interaction.followup.send(
            I18N.t('youtube.commands.stop.msg_confirm')
        )

    @youtube_posting_group.command(
        name='restart', description=locale_str(
            I18N.t('youtube.commands.restart.cmd')
        )
    )
    async def youtube_posting_restart(
        self, interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)
        logger.info('Task restarted')
        Youtube.task_post_videos.restart()
        await interaction.followup.send(
            I18N.t('youtube.commands.restart.msg_confirm')
        )

    @commands.is_owner()
    @discord.app_commands.autocomplete(feed_name=feed_name_autocomplete)
    @youtube_group.command(
        name='add', description=locale_str(
            I18N.t('youtube.commands.add.cmd')
        )
    )
    @describe(
        feed_name=I18N.t('youtube.commands.add.desc.feed_name'),
        youtube_link=I18N.t('youtube.commands.add.desc.youtube_link'),
        channel=I18N.t('youtube.commands.add.desc.channel')
    )
    async def youtube_add(
        self, interaction: discord.Interaction, feed_name: str,
        youtube_link: str, channel: discord.TextChannel
    ):
        '''
        Add a Youtube feed or playlist
        '''
        await interaction.response.defer()
        AUTHOR = interaction.user.name
        # Get yt-id
        youtube_info = await Youtube.get_youtube_info(youtube_link)
        if youtube_info is None:
            await interaction.followup.send(
                I18N.t(
                    'youtube.commands.add.msg_empty_link',
                    link=youtube_link
                ),
            )
            return
        if '&list=' in youtube_link:
            await feeds_core.add_to_feed_db(
                'youtube', str(feed_name), str(youtube_link), channel.id,
                AUTHOR, youtube_info['channel_id'],
                youtube_info['id']
            )
        else:
            await feeds_core.add_to_feed_db(
                'youtube', str(feed_name), str(youtube_link), channel.id,
                AUTHOR, youtube_info['channel_id'],
                None
            )
        await discord_commands.log_to_bot_channel(
            I18N.t(
                'youtube.commands.add.log_feed_confirm',
                user=AUTHOR, feed_name=feed_name,
                yt_link=youtube_link, channel=channel.name
            )
        )
        await interaction.followup.send(
            I18N.t(
                'youtube.commands.add.msg_added',
                feed_name=feed_name, channel_name=channel.name
            )
        )
        return

    @commands.is_owner()
    @discord.app_commands.autocomplete(feed_name=feed_name_autocomplete)
    @youtube_group.command(
        name='remove', description=locale_str(
            I18N.t('youtube.commands.remove.cmd')
        )
    )
    @describe(
        feed_name=I18N.t('youtube.commands.remove.desc.feed_name')
    )
    async def youtube_remove(
        self, interaction: discord.Interaction, feed_name: str
    ):
        '''
        Remove a Youtube feed
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
            logger.debug(f'The feed `{feed_name}` does not exist')
            await interaction.followup.send(
                I18N.t(
                    'youtube.commands.remove.msg_remove_non_existing_feed',
                    feed_name=feed_name
                )
            )
            return
        removal = await feeds_core.remove_feed_from_db(
            feed_type='youtube', feed_name=feed_name
        )
        if removal:
            await discord_commands.log_to_bot_channel(
                I18N.t(
                    'youtube.commands.remove.log_feed_removed',
                    feed_name=feed_name, user_name=AUTHOR
                )
            )
            await interaction.followup.send(
                I18N.t(
                    'youtube.commands.remove.msg_feed_removed',
                    feed_name=feed_name
                )
            )
        elif removal is False:
            # Couldn't remove the feed
            await interaction.followup.send(
                I18N.t(
                    'youtube.commands.remove.msg_feed_remove_failed',
                    feed_name=feed_name
                )
            )
            # Also log and send error to either a bot-channel or admin
            await discord_commands.log_to_bot_channel(
                I18N.t(
                    'youtube.commands.remove.log_feed_remove_failed',
                    user_name=AUTHOR, feed_name=feed_name
                )
            )
        return

    @commands.is_owner()
    @discord.app_commands.autocomplete(feed_name=feed_name_autocomplete)
    @youtube_filter_group.command(
        name='add', description=locale_str(
            I18N.t('youtube.commands.filter_add.cmd')
        )
    )
    @describe(
        feed_name=I18N.t('youtube.commands.filter_add.desc.feed_name'),
        allow_deny=I18N.t('youtube.commands.filter_add.desc.allow_deny'),
        filters_in=I18N.t('youtube.commands.filter_add.desc.filters_in')
    )
    async def youtube_filter_add(
        self, interaction: discord.Interaction, feed_name: str,
        allow_deny: typing.Literal[
            I18N.t('common.literal_allow_deny.allow'),
            I18N.t('common.literal_allow_deny.deny')
        ], filters_in: str
    ):
        '''
        Add filter for feed (deny/allow)
        '''
        await interaction.response.defer(ephemeral=True)
        # Make sure that the filter input can be split
        _uuid = await db_helper.get_output(
            template_info=envs.youtube_db_schema,
            select=('uuid'),
            where=(('feed_name', feed_name)),
            single=True
        )
        _inserts = [(_uuid, allow_deny, filter)]
        adding_filter = await db_helper.insert_many_all(
            template_info=envs.youtube_db_filter_schema,
            inserts=_inserts
        )
        if adding_filter:
            await interaction.followup.send(
                I18N.t(
                    'youtube.commands.filter_add.msg_filter_added',
                    allow_deny=allow_deny, filter_in=filter
                ),
                ephemeral=True)
        else:
            await interaction.followup.send(
                I18N.t(
                    'youtube.commands.filter_add.msg_filter_failed'
                ),
                ephemeral=True
            )
        return

    @commands.is_owner()
    @discord.app_commands.autocomplete(feed_name=feed_name_autocomplete)
    @discord.app_commands.autocomplete(filter_in=youtube_filter_autocomplete)
    @youtube_filter_group.command(
        name='remove', description=locale_str(
            I18N.t('youtube.commands.filter_remove.cmd')
        )
    )
    @describe(
        feed_name=I18N.t('youtube.commands.filter_remove.desc.feed_name'),
        filter_in=I18N.t('youtube.commands.filter_remove.desc.filter_in')
    )
    async def youtube_filter_remove(
        self, interaction: discord.Interaction, feed_name: str, filter_in: str
    ):
        '''
        Remove filter for feed
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
                I18N.t(
                    'youtube.commands.filter_remove.msg_confirm',
                    filter_in=filter_in
                ),
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                I18N.t(
                    'youtube.commands.filter_remove.msg_error',
                    filter_in=filter_in
                ),
                ephemeral=True
            )
        return

    @youtube_group.command(
        name='list', description=locale_str(
            I18N.t('youtube.commands.list.cmd')
        )
    )
    @describe(
        list_type=I18N.t('youtube.commands.list.desc.list_type'),
        link_type=I18N.t('youtube.commands.list.desc.link_type')
    )
    async def youtube_list(
        self, interaction: discord.Interaction,
        list_type: typing.Literal[
            I18N.t('youtube.commands.list.literal_list_type.normal'),
            I18N.t('youtube.commands.list.literal_list_type.added'),
            I18N.t('youtube.commands.list.literal_list_type.filter')
        ],
        link_type: typing.Literal[
            I18N.t('youtube.commands.list.literal_link_type.channel'),
            I18N.t('youtube.commands.list.literal_link_type.playlist'),
        ] = None
    ):
        '''
        List all active Youtube feeds
        '''
        await interaction.response.defer()
        if list_type == I18N.t(
            'youtube.commands.list.literal_list_type.added'
        ):
            formatted_list = await feeds_core.get_feed_list(
                db_in=envs.youtube_db_schema,
                list_type=list_type.lower(),
                link_type=link_type
            )
        elif list_type == I18N.t(
            'youtube.commands.list.literal_list_type.filter'
        ):
            formatted_list = await feeds_core.get_feed_list(
                db_in=envs.youtube_db_schema,
                db_filter_in=envs.youtube_db_filter_schema,
                list_type=list_type.lower(),
                link_type=link_type
            )
        else:
            formatted_list = await feeds_core.get_feed_list(
                envs.youtube_db_schema,
                link_type=link_type
            )
        if formatted_list is not None:
            page_counter = 0
            for page in formatted_list:
                page_counter += 1
                logger.debug(
                    f'Sending page ({page_counter} / {len(formatted_list)})')
                await interaction.followup.send(
                    f"```{page}```"
                )
                sleep(1)
        else:
            await interaction.followup.send(
                I18N.t('youtube.commands.list.msg_error')
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
            logger.error(f'Could not extract youtube info: {_error}')
            return None

    # Tasks
    @tasks.loop(minutes=config.YT_LOOP,reconnect=True)
    async def task_post_videos():
        logger.info('Starting `post_videos`')
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
        if len(feeds) == 0 or feeds is None:
            logger.info('Couldn\'t find any Youtube feeds')
            return
        logger.debug('Got these feeds:')
        for feed in feeds:
            logger.debug('- {}'.format(feed['feed_name']))
        # Start processing per feed settings
        for feed in feeds:
            UUID = feed['uuid']
            FEED_NAME = feed['feed_name']
            CHANNEL = feed['channel']
            logger.info(f'Checking {FEED_NAME}')
            logger.debug(
                f'Found channel `{CHANNEL}` in `{FEED_NAME}`'
            )
            FEED_POSTS = await feeds_core.get_feed_links(
                feed_type='youtube', feed_info=feed
            )
            if FEED_POSTS is not None:
                logger.debug(
                    'Got {} items for `FEED_POSTS`: '
                    '{}'.format(
                        len(FEED_POSTS),
                        ', '.join(
                            [pod_ep['title'] for pod_ep in FEED_POSTS[0:3]]
                        )
                    )
                )
            if FEED_POSTS is None:
                logger.info(f'{feed}: this feed returned NoneType.')
                await discord_commands.log_to_bot_channel(
                    I18N.t('youtube.tasks.log_error', feed_name=FEED_NAME)
                )
            else:
                await feeds_core.process_links_for_posting_or_editing(
                    'youtube', UUID, FEED_POSTS, CHANNEL
                )
        logger.info('Done with posting')
        return

    @task_post_videos.before_loop
    async def before_post_new_videos():
        '#autodoc skip#'
        logger.debug('`post_videos` waiting for bot to be ready...')
        await config.bot.wait_until_ready()


async def setup(bot):
    # Create necessary databases before starting
    cog_name = 'youtube'
    logger.info(envs.COG_STARTING.format(cog_name))
    logger.debug('Checking db')
    # Convert json to sqlite db-files if exists

    # Define inserts
    youtube_inserts = None
    youtube_prep_is_ok = None
    youtube_log_prep_is_ok = None
    # Populate the inserts if feed and logs json files exist
    if file_io.file_exist(envs.youtube_feeds_file) and \
            file_io.file_exist(envs.youtube_feeds_logs_file):
        logger.debug('Found old json file - feeds')
        youtube_inserts = await db_helper.json_to_db_inserts(cog_name)
    logger.debug(f'Got these inserts:\n{youtube_inserts}')

    logger.debug('Youtube db does not exist')
    youtube_prep_is_ok = await db_helper.prep_table(
        table_in=envs.youtube_db_schema,
        inserts=youtube_inserts['feeds'] if youtube_inserts is not None
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
    logger.debug(f'`youtube_prep_is_ok` is {youtube_prep_is_ok}')
    logger.debug(
        f'`youtube_filter_prep_is_ok` is {youtube_filter_prep_is_ok}'
    )
    logger.debug(f'`youtube_log_prep_is_ok` is {youtube_log_prep_is_ok}')
    missing_tbl_cols = {}
    missing_tbl_cols = await db_helper.add_missing_db_setup(
        envs.youtube_db_schema, missing_tbl_cols
    )
    missing_tbl_cols = await db_helper.add_missing_db_setup(
        envs.youtube_db_filter_schema, missing_tbl_cols
    )
    missing_tbl_cols = await db_helper.add_missing_db_setup(
        envs.youtube_db_log_schema, missing_tbl_cols
    )
    logger.debug(f'`missing_tbl_cols` is {missing_tbl_cols}')
    if any(len(missing_tbl_cols[table]) > 0 for table in missing_tbl_cols):
        missing_tbl_cols_text = ''
        for _tbl in missing_tbl_cols:
            missing_tbl_cols_text += '{}:'.format(_tbl)
            for col in missing_tbl_cols[_tbl]:
                missing_tbl_cols_text += '\n{}'.format(' - '.join(col))
            if _tbl != list(missing_tbl_cols.keys())[-1]:
                missing_tbl_cols_text += '\n\n'
        await discord_commands.log_to_bot_channel(
            'Missing columns in rss db: {}\n'
            'Make sure to populate missing information'.format(
                missing_tbl_cols_text
            )
        )
    # Change channel name to id
    await db_helper.db_channel_names_to_ids(
        template_info=envs.youtube_db_schema,
        id_col='uuid', channel_col='channel'
    )
    # Delete old json files if they are not necessary anymore
    if youtube_prep_is_ok:
        file_io.remove_file(envs.youtube_feeds_file)
    if youtube_log_prep_is_ok:
        file_io.remove_file(envs.youtube_feeds_logs_file)
    logger.debug('Registering cog to bot')
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
        if task['task'] == 'post_videos':
            if task['status'] == 'started':
                logger.debug(
                    '`{}` is set as `{}`, starting...'.format(
                        task['task'], task['status']
                    ))
                Youtube.task_post_videos.start()
            elif task['status'] == 'stopped':
                logger.debug(
                    '`{}` is set as `{}`'.format(
                        task['task'], task['status']
                    ))
                Youtube.task_post_videos.cancel()


async def teardown(bot):
    Youtube.task_post_videos.cancel()
