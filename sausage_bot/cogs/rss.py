#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import discord
from discord.ext import commands, tasks
from discord.app_commands import locale_str, describe
import typing
from time import sleep
import re

from sausage_bot.util import config, envs, feeds_core, file_io, net_io
from sausage_bot.util import db_helper, discord_commands
from sausage_bot.util.i18n import I18N
from sausage_bot.util.log import log
from sausage_bot.util.args import args


async def feed_name_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[discord.app_commands.Choice[str]]:
    db_feeds = await db_helper.get_output(
        template_info=envs.rss_db_schema,
        select=('uuid', 'feed_name', 'url', 'channel'),
        order_by=[
            ('feed_name', 'ASC')
        ]
    )
    feeds = []
    for feed in db_feeds:
        feeds.append((feed[0], feed[1], feed[2], feed[3]))
    log.debug(f'feeds: {feeds}')
    length_counter = 90
    length_counter -= len(str(feed[1]))
    length_counter -= len(str(feed[3]))
    return [
        discord.app_commands.Choice(
            name='{feed_name}: #{channel} ({url})'.format(
                feed_name=feed[1], channel=feed[3],
                url='{}...'.format(
                    str(feed[2])[0:length_counter]
                ) if len(feed[2]) > length_counter else str(feed[2]),
            ), value=str(feed[1])
        )
        for feed in feeds if current.lower() in feed[0].lower()
    ]


async def rss_filter_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[discord.app_commands.Choice[str]]:
    db_filters = await db_helper.get_combined_output(
        template_info_1=envs.rss_db_schema,
        template_info_2=envs.rss_db_filter_schema,
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


class RSSfeed(commands.Cog):
    '''
    Administer RSS-feeds that will autopost to a given channel when published
    '''

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    rss_group = discord.app_commands.Group(
        name="rss", description=locale_str(I18N.t('rss.groups.rss'))
    )
    rss_filter_group = discord.app_commands.Group(
        name="filter", description=locale_str(I18N.t('rss.groups.filter')),
        parent=rss_group
    )
    rss_posting_group = discord.app_commands.Group(
        name="posting", description=locale_str(I18N.t('rss.groups.posting')),
        parent=rss_group
    )

    @rss_posting_group.command(
        name='start', description=locale_str(I18N.t('rss.commands.start.cmd'))
    )
    async def rss_posting_start(
        self, interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)
        log.log('Task started')
        RSSfeed.post_feeds.start()
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[
                ('cog', 'rss'),
                ('task', 'post_feeds')
            ],
            updates=('status', 'started')
        )
        await interaction.followup.send(
            I18N.t('rss.commands.start.msg_confirm')
        )

    @rss_posting_group.command(
        name='stop', description=locale_str(I18N.t('rss.commands.stop.cmd'))
    )
    async def rss_posting_stop(
        self, interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)
        log.log('Task stopped')
        RSSfeed.post_feeds.cancel()
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[
                ('task', 'post_feeds'),
                ('cog', 'rss'),
            ],
            updates=('status', 'stopped')
        )
        await interaction.followup.send(
            I18N.t('rss.commands.stop.msg_confirm')
        )

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @discord.app_commands.autocomplete(feed_name=feed_name_autocomplete)
    @rss_group.command(
        name='add', description=locale_str(I18N.t('rss.commands.add.cmd'))
    )
    @describe(
        feed_name=I18N.t('rss.commands.add.desc.feed_name'),
        feed_link=I18N.t('rss.commands.add.desc.feed_link'),
        channel=I18N.t('rss.commands.add.desc.channel')
    )
    async def rss_add(
        self, interaction: discord.Interaction, feed_name: str,
        feed_link: str, channel: discord.TextChannel
    ):
        '''Add a RSS feed'''
        await interaction.response.defer(ephemeral=True)
        AUTHOR = interaction.user.name
        # Verify that the url is a proper feed
        if "open.spotify.com/show/" not in feed_link:
            valid_feed = await feeds_core.check_feed_validity(feed_link)
            if not valid_feed:
                # TODO var msg
                await interaction.followup.send(
                    I18N.t('rss.commands.add.msg_feed_failed'),
                    ephemeral=True
                )
                return
        log.verbose('Adding feed to db')
        await feeds_core.add_to_feed_db(
            'spotify', str(feed_name), str(feed_link), channel.name, AUTHOR
        )
        await discord_commands.log_to_bot_channel(
            I18N.t(
                'rss.commands.add.log_feed_confirm',
                user_name=AUTHOR, feed_name=feed_name,
                channel_name=channel.name
            )
        )
        await interaction.followup.send(
            I18N.t(
                'rss.commands.add.msg_feed_confirm',
                feed_name=feed_name, channel_name=channel.name
            ),
            ephemeral=True
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @discord.app_commands.autocomplete(feed_name=feed_name_autocomplete)
    @rss_group.command(
        name='remove', description=locale_str(I18N.t(
            'rss.commands.remove.cmd'
        ))
    )
    @describe(
        feed_name=I18N.t('rss.commands.remove.desc.feed_name')
    )
    async def rss_remove(
        self, interaction: discord.Interaction, feed_name: str
    ):
        '''Remove a RSS feed'''
        await interaction.response.defer()
        AUTHOR = interaction.user.name
        removal = await feeds_core.remove_feed_from_db(
            feed_type='rss', feed_name=feed_name
        )
        if removal:
            await discord_commands.log_to_bot_channel(
                I18N.t(
                    'rss.commands.remove.log_feed_removed',
                    feed_name=feed_name, user_name=AUTHOR
                )
            )
            await interaction.followup.send(
                I18N.t(
                    'rss.commands.remove.msg_feed_removed',
                    feed_name=feed_name
                )
            )
        elif removal is False:
            # Couldn't remove the feed
            await interaction.followup.send(
                I18N.t(
                    'rss.commands.remove.msg_feed_remove_failed',
                    feed_name=feed_name
                )
            )
            # Also log and send error to bot-channel
            await discord_commands.log_to_bot_channel(
                I18N.t(
                    'rss.commands.remove.log_feed_remove_failed',
                    user_name=AUTHOR, feed_name=feed_name
                )
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @discord.app_commands.autocomplete(feed_name=feed_name_autocomplete)
    @rss_group.command(
        name='edit', description=locale_str(I18N.t(
            'rss.commands.edit.cmd'
        ))
    )
    @describe(
        feed_name=I18N.t('rss.commands.edit.desc.feed_name'),
        new_feed_name=I18N.t('rss.commands.edit.desc.new_feed_name'),
        channel=I18N.t('rss.commands.edit.desc.channel'),
        url=I18N.t('rss.commands.edit.desc.url')
    )
    async def rss_edit(
            self, interaction: discord.Interaction,
            feed_name: str, new_feed_name: str = None,
            channel: discord.TextChannel = None, url: str = None
    ):
        await interaction.response.defer()
        feed_info = await db_helper.get_output(
            template_info=envs.rss_db_schema,
            select=('feed_name', 'channel', 'url'),
            where=(('feed_name', feed_name))
        )
        log.debug(f'`feed_info` is {feed_info}')
        changes_out = I18N.t(
            'rss.commands.edit.changes_out.msg',
            feed_name=feed_name
        )
        updates_in = []
        if new_feed_name:
            updates_in.append(('feed_name', new_feed_name))
            changes_out += '\n- {}: `{}` -> `{}`'.format(
                    I18N.t('rss.commands.edit.changes_out.feed_name'),
                    feed_info[0][0],
                    new_feed_name
                )
        if channel:
            updates_in.append(('channel', channel))
            changes_out += '\n- {}: `{}` -> `{}`'.format(
                I18N.t('rss.commands.edit.changes_out.channel'),
                feed_info[0][1],
                channel
            )
        if url:
            updates_in.append(('url', url))
            changes_out += '\n- {}: `{}` -> `{}`'.format(
                I18N.t('rss.commands.edit.changes_out.url'),
                feed_info[0][2],
                url
            )
        await db_helper.update_fields(
            template_info=envs.rss_db_schema,
            where=('feed_name', feed_name),
            updates=updates_in
        )
        await interaction.followup.send(
            changes_out, ephemeral=True
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @discord.app_commands.autocomplete(feed_name=feed_name_autocomplete)
    @rss_filter_group.command(
        name='add', description=locale_str(I18N.t('rss.commands.filter_add.cmd'))
    )
    @describe(
        feed_name=I18N.t('rss.commands.filter_add.desc.feed_name'),
        allow_deny=I18N.t('rss.commands.filter_add.desc.allow_deny'),
        filters_in=I18N.t('rss.commands.filter_add.desc.filters_in')
    )
    async def rss_filter_add(
        self, interaction: discord.Interaction, feed_name: str,
        allow_deny: typing.Literal[
            I18N.t('rss.commands.filter_add.desc.allow_deny.allow'),
            I18N.t('rss.commands.filter_add.desc.allow_deny.deny')
        ], filters_in: str
    ):
        '''
        Add filter for feed (deny/allow)
        '''
        await interaction.response.defer(ephemeral=True)
        # Make sure that the filter input can be split
        _filters_in = re.split(
            envs.input_split_regex, filters_in
        )
        _uuid = await db_helper.get_output(
            template_info=envs.rss_db_schema,
            select=('uuid'),
            where=(('feed_name', feed_name)),
            single=True
        )
        temp_inserts = []
        for _index, filter in enumerate(_filters_in):
            temp_inserts.append((_uuid, allow_deny, filter))
        adding_filter = await db_helper.insert_many_all(
            template_info=envs.rss_db_filter_schema,
            inserts=temp_inserts
        )
        if adding_filter:
            msg_out = I18N.t(
                'rss.commands.filter_add.msg_confirm',
                allow_deny=allow_deny
            )
            for filter in _filters_in:
                msg_out += f'\n- {filter}'
            await interaction.followup.send(msg_out, ephemeral=True)
        else:
            await interaction.followup.send(
                I18N.t('rss.commands.filter_add.msg_error'),
                ephemeral=True
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @discord.app_commands.autocomplete(feed_name=feed_name_autocomplete)
    @discord.app_commands.autocomplete(filter_in=rss_filter_autocomplete)
    @rss_filter_group.command(
        name='remove', description=locale_str(I18N.t(
            'rss.commands.filter_remove.cmd'
        ))
    )
    @describe(
        feed_name=I18N.t('rss.commands.filter_remove.desc.feed_name'),
        filter_in=I18N.t('rss.commands.filter_remove.desc.filter')
    )
    async def rss_filter_remove(
        self, interaction: discord.Interaction, feed_name: str, filter_in: str
    ):
        '''
        Remove filter for feed
        '''
        await interaction.response.defer(ephemeral=True)
        _uuid = await db_helper.get_output(
            template_info=envs.rss_db_schema,
            select=('uuid'),
            where=(('feed_name', feed_name)),
            single=True
        )
        removing_filter = await db_helper.del_row_by_AND_filter(
            template_info=envs.rss_db_filter_schema,
            where=(
                ('uuid', _uuid),
                ('filter', filter_in)
            )
        )
        if removing_filter:
            await interaction.followup.send(
                I18N.t(
                    'rss.commands.filter_remove.msg_confirm',
                    filter=filter_in
                ),
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                I18N.t(
                    'rss.commands.filter_remove.msg_error',
                    filter=filter_in
                ),
                ephemeral=True
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @rss_group.command(
        name='list', description=locale_str(I18N.t('rss.commands.list.cmd'))
    )
    @describe(
        list_type=I18N.t('rss.commands.list.desc.list_type')
    )
    async def list_rss(
        self, interaction: discord.Interaction,
        list_type: typing.Literal[
            I18N.t('rss.commands.list.literal_type.normal'),
            I18N.t('rss.commands.list.literal_type.added'),
            I18N.t('rss.commands.list.literal_type.filter')
        ]
    ):
        '''
        List all active rss feeds
        '''
        await interaction.response.defer()
        if list_type.lower() == 'added':
            formatted_list = await feeds_core.get_feed_list(
                db_in=envs.rss_db_schema,
                list_type=list_type.lower()
            )
        elif list_type.lower() == 'filter':
            formatted_list = await feeds_core.get_feed_list(
                db_in=envs.rss_db_schema,
                db_filter_in=envs.rss_db_filter_schema,
                list_type=list_type.lower()
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
                await interaction.followup.send(
                    f"```{page}```"
                )
                sleep(1)
        else:
            await interaction.followup.send(
                I18N.t('rss.commands.list.msg_error'),
                ephemeral=True
            )
        return

    # Tasks
    @tasks.loop(
        minutes=config.env.int('RSS_LOOP', default=5)
    )
    async def post_feeds():
        log.log('Starting `rss_parse`')
        # Make sure that the feed links aren't stale / 404
        review_feeds = await feeds_core.review_feeds_status('rss')
        if review_feeds in [None, False]:
            log.log('No feeds to post')
            return
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
            URL = feed[2]
            CHANNEL = feed[3]
            log.debug(
                f'Found channel `{CHANNEL}` in `{FEED_NAME}`'
            )
            if "open.spotify.com/show/" in URL:
                log.debug('Is a spotify-link')
                FEED_POSTS = await net_io.get_spotify_podcast_links(feed)
                log.debug(
                    f'Got {len(FEED_POSTS)} items for `FEED_POSTS`: '
                    f'{FEED_POSTS}'
                )
                await feeds_core.process_links_for_posting_or_editing(
                    'spotify', UUID, FEED_POSTS, CHANNEL
                )
                log.log('Done with posting')
                continue
            else:
                FEED_POSTS = await feeds_core.get_feed_links(
                    feed_type='rss', feed_info=feed
                )
            log.debug(f'Got this for `FEED_POSTS`: {FEED_POSTS}')
            if FEED_POSTS is None:
                log.log(envs.RSS_FEED_POSTS_IS_NONE.format(FEED_NAME))
                await discord_commands.log_to_bot_channel(
                    envs.RSS_FEED_POSTS_IS_NONE.format(FEED_NAME)
                )
            else:
                await feeds_core.process_links_for_posting_or_editing(
                    'rss', UUID, FEED_POSTS, CHANNEL
                )
        log.log('Done with posting')
        return

    @post_feeds.before_loop
    async def before_post_new_feeds():
        '#autodoc skip#'
        log.verbose('`post_feeds` waiting for bot to be ready...')
        await config.bot.wait_until_ready()


async def setup(bot):
    # Create necessary databases before starting
    cog_name = 'rss'
    log.log(envs.COG_STARTING.format(cog_name))
    log.verbose('Checking db')
    # Convert json to sqlite db-files if exists

    # Define inserts
    rss_inserts = None
    rss_prep_is_ok = None
    rss_log_prep_is_ok = None
    # Populate the inserts if json file exist
    if file_io.file_exist(envs.rss_feeds_file) or\
            file_io.file_exist(envs.rss_feeds_logs_file):
        log.verbose('Found old json files')
        rss_inserts = await db_helper.json_to_db_inserts(cog_name)
    log.debug(f'Got these inserts:\n{rss_inserts}')

    # Prep of DBs should only be done if the db files does not exist
    if not file_io.file_exist(envs.rss_db_schema['db_file']):
        log.verbose('RSS db does not exist')
        rss_prep_is_ok = await db_helper.prep_table(
            table_in=envs.rss_db_schema,
            old_inserts=rss_inserts['feeds'] if rss_inserts is not None
            else rss_inserts
        )
        rss_filter_prep_is_ok = await db_helper.prep_table(
            envs.rss_db_filter_schema,
            rss_inserts['filter'] if rss_inserts is not None else rss_inserts
        )
        rss_log_prep_is_ok = await db_helper.prep_table(
            envs.rss_db_log_schema,
            rss_inserts['logs'] if rss_inserts is not None else rss_inserts
        )
        log.verbose(f'`rss_prep_is_ok` is {rss_prep_is_ok}')
        log.verbose(f'`rss_filter_prep_is_ok` is {rss_filter_prep_is_ok}')
        log.verbose(f'`rss_log_prep_is_ok` is {rss_log_prep_is_ok}')
    else:
        log.verbose('rss db exist!')
    # Delete old json files if they are not necessary anymore
    if rss_prep_is_ok:
        file_io.remove_file(envs.rss_feeds_file)
    if rss_log_prep_is_ok:
        file_io.remove_file(envs.rss_feeds_logs_file)
    log.verbose('Registering cog to bot')
    await bot.add_cog(RSSfeed(bot))

    task_list = await db_helper.get_output(
        template_info=envs.tasks_db_schema,
        select=('task', 'status'),
        where=('cog', 'rss')
    )
    if len(task_list) == 0:
        await db_helper.insert_many_all(
            template_info=envs.tasks_db_schema,
            inserts=(
                ('rss', 'post_feeds', 'stopped')
            )
        )
    for task in task_list:
        if task[0] == 'post_feeds':
            if task[1] == 'started':
                log.debug(f'`{task[0]}` is set as `{task[1]}`, starting...')
                RSSfeed.post_feeds.start()
            elif task[1] == 'stopped':
                log.debug(f'`{task[0]}` is set as `{task[1]}`')
                RSSfeed.post_feeds.cancel()


async def teardown(bot):
    RSSfeed.post_feeds.cancel()
