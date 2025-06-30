#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'''
rss: Administer RSS-feeds that will autopost to a given channel
when published
'''
import discord
from discord.ext import commands, tasks
from discord.app_commands import locale_str, describe
from discord.utils import get
import typing
from time import sleep
import re
from pprint import pformat

from sausage_bot.util import config, envs, feeds_core, file_io, net_io
from sausage_bot.util import db_helper, discord_commands
from sausage_bot.util.i18n import I18N

logger = config.logger


async def rss_feed_name_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[discord.app_commands.Choice[str]]:
    db_feeds = await db_helper.get_output(
        template_info=envs.rss_db_schema,
        select=('uuid', 'feed_name', 'url', 'channel'),
        where=(('feed_type', 'rss')),
        order_by=[
            ('feed_name', 'ASC')
        ]
    )
    logger.debug(f'db_feeds:\n{pformat(db_feeds)}')
    feeds = db_feeds.copy()
    for feed in feeds:
        _counter = 87
        _counter -= len(str(feed['feed_name']))
        _counter -= len(str(feed['channel']))
        feed['length_counter'] = _counter
    return [
        discord.app_commands.Choice(
            name='{feed_name}: #{channel} ({url})'.format(
                feed_name=feed['feed_name'], channel=feed['channel'],
                url=str(feed['url'])
            )[0:feed['length_counter']], value=str(feed['feed_name'])
        )
        for feed in feeds if current.lower() in '{}-{}-{}-{}'.format(
            feed['uuid'], feed['feed_name'], feed['url'], feed['channel']
        ).lower()
    ][:25]


async def podcast_name_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[discord.app_commands.Choice[str]]:
    db_feeds = await db_helper.get_output(
        template_info=envs.rss_db_schema,
        select=('uuid', 'feed_name', 'url', 'channel'),
        where=(('feed_type', 'podcast')),
        order_by=[
            ('feed_name', 'ASC')
        ]
    )
    logger.debug(f'db_feeds:\n{pformat(db_feeds)}')
    feeds = db_feeds.copy()
    for feed in feeds:
        _counter = 87
        _counter -= len(str(feed['feed_name']))
        _counter -= len(str(feed['channel']))
        feed['length_counter'] = _counter
    return [
        discord.app_commands.Choice(
            name='{feed_name}: #{channel} ({url})'.format(
                feed_name=feed['feed_name'], channel=feed['channel'],
                url=str(feed['url'])
            )[0:feed['length_counter']], value=str(feed['feed_name'])
        )
        for feed in feeds if current.lower() in '{}-{}-{}-{}'.format(
            feed['uuid'], feed['feed_name'], feed['url'], feed['channel']
        ).lower()
    ][:25]


async def feed_uuid_autocomplete(
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
    logger.debug(f'db_feeds:\n{pformat(db_feeds)}')
    feeds = db_feeds.copy()
    for feed in feeds:
        _counter = 87
        _counter -= len(str(feed['feed_name']))
        _counter -= len(str(feed['channel']))
        feed['length_counter'] = _counter
    return [
        discord.app_commands.Choice(
            name='{feed_name}: #{channel} ({url})'.format(
                feed_name=feed['feed_name'], channel=feed['channel'],
                url=str(feed['url'])
            )[0:feed['length_counter']], value=str(feed['uuid'])
        )
        for feed in feeds if current.lower() in '{}-{}-{}-{}'.format(
            feed['uuid'], feed['feed_name'], feed['url'], feed['channel']
        ).lower()
    ][:25]


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
        filters.append(
            (filter['uuid'], filter['allow_or_deny'], filter['filter'])
        )
    logger.debug(f'filters: {filters}')
    return [
        discord.app_commands.Choice(
            name='{} - {} - {}'.format(
                filter['uuid'], filter['allow_or_deny'], filter['filter']
            ),
            value=str(filter['filter'])
        )
        for filter in filters if current.lower() in filter['filter'].lower()
    ][:25]


async def rss_settings_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[discord.app_commands.Choice[str]]:
    settings_in_db = await db_helper.get_output(
        template_info=envs.rss_db_settings_schema,
        select=('setting', 'value')
    )
    logger.debug(f'settings_in_db: {settings_in_db}')
    return [
        discord.app_commands.Choice(
            name='{}: {}'.format(
                setting['setting'], setting['value']
            ),
            value=str(setting['setting'])
        )
        for setting in settings_in_db
        if current.lower() in setting['setting'].lower()
    ][:25]


async def control_posting(feed_type, action):
    feed_type_in = []
    failed_list = []
    feed_statuses = []
    feed_types = ''
    actions = {
        'start': {'status_update': 'started'},
        'stop': {'status_update': 'stopped'},
        'restart': {'status_update': 'restarted'}

    }
    if feed_type == 'ALL':
        feed_type_in.append('feeds')
        feed_type_in.append('podcasts')
    else:
        feed_type_in.append(feed_type)
    for feed_type in feed_type_in:
        if action in actions:
            try:
                eval('RSSfeed.task_post_{}.{}()'.format(
                    feed_type, action
                ))
                feed_statuses.append(
                    {
                        'feed_type': feed_type,
                        'status': actions[action]['status_update']
                    }
                )
            except RuntimeError as e:
                logger.error('Error when {}ing feed `{}`: {}'.format(
                    actions[action]['status_update'], feed_type, e
                ))
                failed_list.append(feed_type)
    # Update status in db
    if len(feed_statuses) > 0:
        for feed_type in feed_statuses:
            if feed_type['status'] in ['started', 'stopped']:
                await db_helper.update_fields(
                    template_info=envs.tasks_db_schema,
                    where=[
                        ('cog', 'rss'),
                        ('task', 'post_{}'.format(
                            feed_type['feed_type']
                        ))
                    ],
                    updates=('status', feed_type['status']),
                )
                logger.info('Task {}: {}'.format(
                    feed_type['feed_type'],
                    feed_type['status']
                ))
            else:
                logger.debug('Restarting service, no need to update db')
        feed_types = ', '.join(
            feed_type['feed_type'] for feed_type in feed_statuses
        )
    if len(failed_list) > 0:
        failed_list_text = ', '.join(failed_list)
    _msg = ''
    if len(feed_types) > 0:
        _msg += I18N.t(
            f'rss.commands.{action}.msg_confirm_ok',
            feed_type=feed_types
        )
    if len(failed_list) > 0:
        _msg += I18N.t(
            f'rss.commands.{action}.msg_confirm_fail_suffix',
            feed_type=failed_list_text
        )
    if len(feed_types) == 0 and len(failed_list) > 0:
        _msg = I18N.t(
            f'rss.commands.{action}.msg_confirm_fail',
            feed_type=failed_list
        )
    return _msg


class RSSfeed(commands.Cog):
    '''
    Administer RSS-feeds that will autopost to a given channel when published
    '''

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    config.bot.add_dynamic_items(feeds_core.DynamicRatingSelect)

    rss_group = discord.app_commands.Group(
        name="rss", description=locale_str(I18N.t('rss.groups.rss'))
    )
    podcast_group = discord.app_commands.Group(
        name="podcast", description=locale_str(
            I18N.t('rss.groups.podcast')
        )
    )
    rss_filter_group = discord.app_commands.Group(
        name="filter", description=locale_str(I18N.t('rss.groups.filter')),
        parent=rss_group
    )
    rss_posting_group = discord.app_commands.Group(
        name="posting", description=locale_str(I18N.t('rss.groups.posting')),
        parent=rss_group
    )
    rss_settings_group = discord.app_commands.Group(
        name="settings", description=locale_str(I18N.t('rss.groups.settings')),
        parent=rss_group
    )

    @rss_posting_group.command(
        name='start', description=locale_str(I18N.t('rss.commands.start.cmd'))
    )
    async def feeds_posting_start(
        self, interaction: discord.Interaction, feed_type: typing.Literal[
            'feeds', 'podcasts', 'ALL'
        ]
    ):
        await interaction.response.defer(ephemeral=True)
        msg = await control_posting(feed_type, 'start')
        await interaction.followup.send(msg)

    @rss_posting_group.command(
        name='stop', description=locale_str(I18N.t('rss.commands.stop.cmd'))
    )
    async def feeds_posting_stop(
        self, interaction: discord.Interaction, feed_type: typing.Literal[
            'feeds', 'podcasts', 'ALL'
        ]
    ):
        await interaction.response.defer(ephemeral=True)
        msg = await control_posting(feed_type, 'stop')
        await interaction.followup.send(msg)

    @rss_posting_group.command(
        name='restart', description=locale_str(I18N.t(
            'rss.commands.restart.cmd'
        ))
    )
    async def feeds_posting_restart(
        self, interaction: discord.Interaction, feed_type: typing.Literal[
            'feeds', 'podcasts', 'ALL'
        ]
    ):
        await interaction.response.defer(ephemeral=True)
        msg = await control_posting(feed_type, 'restart')
        await interaction.followup.send(msg)

    @commands.is_owner()
    @discord.app_commands.autocomplete(feed_name=rss_feed_name_autocomplete)
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
        valid_feed = await feeds_core.check_feed_validity(feed_link)
        if not valid_feed:
            await interaction.followup.send(
                I18N.t('rss.commands.add.msg_feed_failed'),
                ephemeral=True
            )
            return
        logger.debug('Adding feed to db')
        await feeds_core.add_to_feed_db(
            'rss', str(feed_name), str(feed_link), channel.id, AUTHOR
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

    @commands.is_owner()
    @discord.app_commands.autocomplete(feed_name=rss_feed_name_autocomplete)
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

    @commands.is_owner()
    @discord.app_commands.autocomplete(feed_name=rss_feed_name_autocomplete)
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
        logger.debug(f'`feed_info` is {feed_info}')
        changes_out = I18N.t(
            'rss.commands.edit.changes_out.msg',
            feed_name=feed_name
        )
        updates_in = []
        if new_feed_name:
            updates_in.append(('feed_name', new_feed_name))
            changes_out += '\n- {}: `{}` -> `{}`'.format(
                I18N.t('rss.commands.edit.changes_out.feed_name'),
                feed_info[0]['feed_name'],
                new_feed_name
            )
        if channel:
            updates_in.append(('channel', channel))
            changes_out += '\n- {}: `{}` -> `{}`'.format(
                I18N.t('rss.commands.edit.changes_out.channel'),
                feed_info[0]['channel'],
                channel
            )
        if url:
            updates_in.append(('url', url))
            changes_out += '\n- {}: `{}` -> `{}`'.format(
                I18N.t('rss.commands.edit.changes_out.url'),
                feed_info[0]['url'],
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

    @commands.is_owner()
    @discord.app_commands.autocomplete(feed_name=rss_feed_name_autocomplete)
    @rss_filter_group.command(
        name='add', description=locale_str(
            I18N.t('rss.commands.filter_add.cmd')
        )
    )
    @describe(
        feed_name=I18N.t('rss.commands.filter_add.desc.feed_name'),
        allow_deny=I18N.t('rss.commands.filter_add.desc.allow_deny'),
        filters_in=I18N.t('rss.commands.filter_add.desc.filters')
    )
    async def rss_filter_add(
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

    @commands.is_owner()
    @discord.app_commands.autocomplete(feed_name=rss_feed_name_autocomplete)
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

    @commands.is_owner()
    @discord.app_commands.autocomplete(
        name_of_setting=rss_settings_autocomplete
    )
    @rss_settings_group.command(
        name='change', description=locale_str(I18N.t(
            'rss.commands.setting.cmd'
        ))
    )
    @describe(
        name_of_setting=I18N.t(
            'rss.commands.setting.desc.name_of_setting'
        ),
        value_in=I18N.t('rss.commands.setting.desc.value_in')
    )
    async def rss_settings_change(
        self, interaction: discord.Interaction, name_of_setting: str,
        value_in: str
    ):
        '''
        Change a setting for this cog
        '''
        await interaction.response.defer(ephemeral=True)
        settings_in_db = await db_helper.get_output(
            template_info=envs.rss_db_settings_schema,
            select=('setting', 'value', 'value_check')
        )
        for setting in settings_in_db:
            if setting['setting'] == name_of_setting:
                if setting['value_check'] == 'bool':
                    try:
                        value_in = eval(str(value_in).capitalize())
                    except NameError as _error:
                        logger.error(f'Invalid input for `value_in`: {_error}')
                        await interaction.followup.send(
                            I18N.t(
                                'rss.commands.setting.value_in_input_invalid',
                                error=_error
                            )
                        )
                        return
                logger.debug(
                    '`value_in` is {value_in} ({type_value_in})'.format(
                        value_in=value_in,
                        type_value_in=type(value_in)
                    )
                )
                logger.debug(
                    '`setting[\'value_check\']` is {value_check} '
                    '({type_value_check})'.format(
                        value_check=setting['value_check'],
                        type_value_check=type(setting['value_check'])
                    )
                )
                if type(value_in) is eval(setting['value_check']):
                    await db_helper.update_fields(
                        template_info=envs.rss_db_settings_schema,
                        where=[('setting', name_of_setting)],
                        updates=[('value', value_in)]
                    )
                await interaction.followup.send(
                    I18N.t('rss.commands.setting.msg_confirm'),
                    ephemeral=True
                )
                RSSfeed.task_post_feeds.restart()
                break
        return

    @commands.is_owner()
    @rss_group.command(
        name='list', description=locale_str(I18N.t('rss.commands.list.cmd'))
    )
    @describe(
        list_type=I18N.t('rss.commands.list.desc.list_type')
    )
    async def rss_list(
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
                logger.debug(
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

    @commands.is_owner()
    @discord.app_commands.autocomplete(feed_name=feed_uuid_autocomplete)
    @rss_group.command(
        name='test_feed', description=locale_str(
            I18N.t('rss.commands.test.cmd')
        )
    )
    @describe(
        feed_name=I18N.t('rss.commands.test.desc.feed_name'),
    )
    async def rss_test_feed(
        self, interaction: discord.Interaction, feed_name: str,
        public: typing.Literal[
            I18N.t('common.literal_yes_no.yes'),
            I18N.t('common.literal_yes_no.no')
        ] = None
    ):
        '''
        Test an added feed manually. Creates a report that is posted
        after the test is done.
        '''
        def enclose_status_out(status_out):
            return '```{}```'.format(status_out)

        if public == I18N.t('common.literal_yes_no.yes'):
            _ephemeral = False
        else:
            _ephemeral = True
        status_out = ''
        await interaction.response.defer(ephemeral=_ephemeral)
        feed = await db_helper.get_output(
            template_info=envs.rss_db_schema,
            order_by=[
                ('feed_name', 'DESC')
            ],
            where=[
                ('uuid', feed_name)
            ],
            not_like=[
                ('feed_type', 'podcast')
            ],
            single=True
        )
        status_out += '💭 Checking URL: {}'.format(feed['url'])
        status_msg = await interaction.followup.send(
            enclose_status_out(status_out), ephemeral=_ephemeral
        )
        # Reading url, what code?
        req = await net_io.get_link(feed['url'], status_out=True)
        logger.debug('Got this response from url:\n{pformat(req)}')
        if req['status'] != 200:
            status_out += '\n❌ Got http status {}'.format(req['status'])
            if req['content']:
                status_out += ':\n\t{}'.format(req['content'])
            status_msg = await interaction.followup.edit_message(
                message_id=status_msg.id,
                content=enclose_status_out(status_out)
            )
            return
        else:
            status_out += '\n✅ Got HTTP status {}'.format(req['status'])
            status_msg = await interaction.followup.edit_message(
                message_id=status_msg.id,
                content=enclose_status_out(status_out)
            )
        rss_items = await feeds_core.get_items_from_rss(
            req=req['content'],
            url=feed['url'],
        )
        if rss_items is None or len(rss_items) <= 0:
            status_out += '\n❌ Unable to get feed items'
            status_msg = await interaction.followup.edit_message(
                message_id=status_msg.id,
                content=enclose_status_out(status_out)
            )
            return
        else:
            rss_items[0].pop('type')
            status_out += '\n✅ Got {} feed items:'.format(len(rss_items))
            for item in rss_items[0]:
                status_out += '\n\t- {}: {}'.format(
                    item, rss_items[0][item]
                )
            status_msg = await interaction.followup.edit_message(
                message_id=status_msg.id,
                content=enclose_status_out(status_out)
            )
        # Get link hash
        _hash = await net_io.get_page_hash(rss_items[0]['link'])
        if _hash is None:
            status_out += f'\n❌ Could not make hash, got "{_hash}"'
            status_msg = await interaction.followup.edit_message(
                message_id=status_msg.id,
                content=enclose_status_out(status_out)
            )
            return
        # Get log
        _FEED_DB = await db_helper.get_output(
            template_info=envs.rss_db_log_schema,
            select=('url', 'hash')
        )
        FEED_HASH = [item['hash'] for item in _FEED_DB]
        if _hash in FEED_HASH:
            status_out += f'\n✅ Found hash in log ({_hash})'
        else:
            status_out += f'\n❌ Did not find hash in log ({_hash})'
        status_msg = await interaction.followup.edit_message(
            message_id=status_msg.id, content=enclose_status_out(status_out)
        )
        FEED_LOG = [item['url'] for item in _FEED_DB]
        if feed['url'] in FEED_LOG:
            status_out += '\n✅ Found link in log'
        else:
            status_out += '\n❌ Did not find link in log'
        status_msg = await interaction.followup.edit_message(
            message_id=status_msg.id, content=enclose_status_out(status_out)
        )
        return

    @commands.is_owner()
    @discord.app_commands.autocomplete(podcast_name=podcast_name_autocomplete)
    @podcast_group.command(
        name='add', description=locale_str(I18N.t('rss.commands.add.cmd'))
    )
    @describe(
        podcast_name=I18N.t('rss.commands.add.desc.feed_name'),
        feed_link=I18N.t('rss.commands.add.desc.feed_link'),
        channel=I18N.t('rss.commands.add.desc.channel')
    )
    async def podcast_add(
        self, interaction: discord.Interaction, podcast_name: str,
        feed_link: str, channel: discord.TextChannel
    ):
        '''Add a Podcast'''
        await interaction.response.defer(ephemeral=True)
        AUTHOR = interaction.user.name
        # Verify that the url is a proper feed
        valid_feed = await feeds_core.check_feed_validity(feed_link)
        if not valid_feed:
            await interaction.followup.send(
                I18N.t('rss.commands.add.msg_feed_failed'),
                ephemeral=True
            )
            return
        logger.debug('Adding feed to db')
        feed_type = 'podcast'
        if 'acast.com' in feed_link and 'feeds.acast.com' not in feed_link:
            logger.debug('Found Acast, but not the rss feed. Changing url')
            base_feed_url = 'https://feeds.acast.com/public/shows/{}'
            feed_link = re.sub(r'/episodes.*', '', feed_link)
            pod_url_name = re.search(r'.*/(.*)', feed_link).group(1)
            feed_link = base_feed_url.format(pod_url_name)
        await feeds_core.add_to_feed_db(
            feed_type, str(podcast_name), str(feed_link), channel.id, AUTHOR
        )
        await discord_commands.log_to_bot_channel(
            I18N.t(
                'rss.commands.add.log_feed_confirm',
                user_name=AUTHOR, feed_name=podcast_name,
                channel_name=channel.name
            )
        )
        await interaction.followup.send(
            I18N.t(
                'rss.commands.add.msg_feed_confirm',
                feed_name=podcast_name, channel_name=channel.name
            ),
            ephemeral=True
        )
        return

    @commands.is_owner()
    @discord.app_commands.autocomplete(podcast_name=podcast_name_autocomplete)
    @podcast_group.command(
        name='remove', description=locale_str(I18N.t(
            'rss.commands.remove.cmd'
        ))
    )
    @describe(
        podcast_name=I18N.t('rss.commands.remove.desc.feed_name')
    )
    async def podcast_remove(
        self, interaction: discord.Interaction, podcast_name: str
    ):
        '''Remove a podcast'''
        await interaction.response.defer()
        AUTHOR = interaction.user.name
        removal = await feeds_core.remove_feed_from_db(
            feed_type='podcast', podcast_name=podcast_name
        )
        if removal:
            await discord_commands.log_to_bot_channel(
                I18N.t(
                    'rss.commands.remove.log_feed_removed',
                    feed_name=podcast_name, user_name=AUTHOR
                )
            )
            await interaction.followup.send(
                I18N.t(
                    'rss.commands.remove.msg_feed_removed',
                    feed_name=podcast_name
                )
            )
        elif removal is False:
            # Couldn't remove the feed
            await interaction.followup.send(
                I18N.t(
                    'rss.commands.remove.msg_feed_remove_failed',
                    feed_name=podcast_name
                )
            )
            # Also log and send error to bot-channel
            await discord_commands.log_to_bot_channel(
                I18N.t(
                    'rss.commands.remove.log_feed_remove_failed',
                    user_name=AUTHOR, feed_name=podcast_name
                )
            )
        return

    @commands.is_owner()
    @discord.app_commands.autocomplete(podcast_name=podcast_name_autocomplete)
    @podcast_group.command(
        name='edit', description=locale_str(I18N.t('rss.commands.edit.cmd'))
    )
    @describe(
        podcast_name=I18N.t('rss.commands.edit.desc.feed_name'),
        new_podcast_name=I18N.t('rss.commands.edit.desc.new_feed_name'),
        channel=I18N.t('rss.commands.edit.desc.channel'),
        url=I18N.t('rss.commands.edit.desc.url')
    )
    async def pocast_edit(
            self, interaction: discord.Interaction,
            podcast_name: str, new_podcast_name: str = None,
            channel: discord.TextChannel = None, url: str = None
    ):
        await interaction.response.defer()
        feed_info = await db_helper.get_output(
            template_info=envs.rss_db_schema,
            select=('feed_name', 'channel', 'url'),
            where=(('feed_name', podcast_name))
        )
        logger.debug(f'`feed_info` is {feed_info}')
        changes_out = I18N.t(
            'rss.commands.edit.changes_out.msg',
            feed_name=podcast_name
        )
        updates_in = []
        if new_podcast_name:
            updates_in.append(('feed_name', new_podcast_name))
            changes_out += '\n- {}: `{}` -> `{}`'.format(
                I18N.t('rss.commands.edit.changes_out.feed_name'),
                feed_info[0]['feed_name'],
                new_podcast_name
            )
        if channel:
            updates_in.append(('channel', channel))
            changes_out += '\n- {}: `{}` -> `{}`'.format(
                I18N.t('rss.commands.edit.changes_out.channel'),
                feed_info[0]['channel'],
                channel
            )
        if url:
            updates_in.append(('url', url))
            changes_out += '\n- {}: `{}` -> `{}`'.format(
                I18N.t('rss.commands.edit.changes_out.url'),
                feed_info[0]['url'],
                url
            )
        await db_helper.update_fields(
            template_info=envs.rss_db_schema,
            where=('feed_name', podcast_name),
            updates=updates_in
        )
        await interaction.followup.send(
            changes_out, ephemeral=True
        )
        return
###

    # Tasks
    @tasks.loop(
        minutes=config.env.int('RSS_LOOP', default=5),
        reconnect=True
    )
    async def task_post_feeds():
        logger.info('Starting `post_feeds`')
        # Start processing feeds
        feeds = await db_helper.get_output(
            template_info=envs.rss_db_schema,
            order_by=[
                ('feed_name', 'DESC')
            ],
            where=[
                ('status_url', envs.FEEDS_URL_SUCCESS),
                ('status_channel', envs.CHANNEL_STATUS_SUCCESS)
            ],
            not_like=[
                ('feed_type', 'podcast')
            ]
        )
        if len(feeds) == 0:
            logger.info('No feeds found')
            return
        logger.debug('Got these feeds:')
        for feed in feeds:
            logger.debug('- {}'.format(feed['feed_name']))
        # Start processing per feed settings
        for feed in feeds:
            UUID = feed['uuid']
            FEED_NAME = feed['feed_name']
            CHANNEL = feed['channel']
            _guild = discord_commands.get_guild()
            channel_obj = _guild.get_channel(int(CHANNEL))
            logger.debug(
                f'Found channel `{channel_obj.name}` in `{FEED_NAME}`'
            )
            FEED_POSTS = await feeds_core.get_feed_links(
                feed_type='rss', feed_info=feed
            )
            if FEED_POSTS is None or isinstance(FEED_POSTS, int):
                logger.info(f'Feed {FEED_NAME} returned {FEED_POSTS}')
                await db_helper.update_fields(
                    template_info=envs.rss_db_schema,
                    where=('uuid', UUID),
                    updates=('status_url', envs.CHANNEL_STATUS_ERROR)
                )
                await discord_commands.log_to_bot_channel(
                    I18N.t(
                        'rss.tasks.feed_posts_is_none',
                        feed_name=FEED_NAME, return_value=FEED_POSTS
                    )
                )
            else:
                logger.debug(
                    f'Got {len(FEED_POSTS)} items for `FEED_POSTS`: '
                    '{}'.format(
                        ', '.join(
                            [pod_ep['title'] for pod_ep in FEED_POSTS]
                        )
                    )
                )
                await feeds_core.process_links_for_posting_or_editing(
                    'rss', UUID, FEED_POSTS, CHANNEL
                )
        logger.info('Done with posting')
        return

    @task_post_feeds.before_loop
    async def before_post_new_feeds():
        '#autodoc skip#'
        logger.debug('`post_feeds` waiting for bot to be ready...')
        await config.bot.wait_until_ready()

    @tasks.loop(
        minutes=config.env.int('RSS_LOOP', default=5)
    )
    async def task_post_podcasts():
        logger.info('Starting `post_podcasts`')
        # Check for new episodes of Spotify podcasts
        spotify_check = await net_io.check_for_new_spotify_podcast_episodes()
        logger.debug('spotify_check is {}'.format(spotify_check))
        # Get feeds of other podcasts
        pod_check = await net_io.check_other_podcast_episodes()
        logger.debug('pod_check is {}'.format(pod_check))
        logger.debug('Got these feeds:')
        for feed in spotify_check:
            logger.debug('  Spotify:')
            logger.debug('- {}'.format(spotify_check[feed]['name']))
        for feed in pod_check:
            logger.debug('  Other podcasts:')
            logger.debug('- {}'.format(pod_check[feed]['name']))
        # Start processing per feed settings
        # Spotify links first
        for feed in spotify_check:
            POD_ID = feed
            UUID = spotify_check[feed]['uuid']
            FEED_NAME = spotify_check[feed]['name']
            CHANNEL = spotify_check[feed]['channel']
            NUM_EPISODES = spotify_check[feed]['num_episodes_new']
            channel_obj = get(
                discord_commands.get_guild().channels,
                id=int(CHANNEL)
            )
            logger.debug(
                f'Found channel `{channel_obj.name}` in `{FEED_NAME}`'
            )
            FEED_POSTS = await net_io.get_spotify_podcast_links(
                feed_id=POD_ID,
                uuid=UUID,
                num_items=3
            )
            logger.debug(
                'Got {} items for `FEED_POSTS`: '
                '{}'.format(
                    len(FEED_POSTS) if FEED_POSTS else 0,
                    [
                        pod_ep['title'] for pod_ep in FEED_POSTS
                    ] if FEED_POSTS else None
                )
            )
            if FEED_POSTS is None:
                logger.info(f'Feed {FEED_NAME} returned NoneType')
                await discord_commands.log_to_bot_channel(
                    I18N.t('rss.tasks.feed_posts_is_none', feed_name=FEED_NAME)
                )
            else:
                await feeds_core.process_links_for_posting_or_editing(
                    feed_type='podcast', uuid=UUID,
                    FEED_POSTS=FEED_POSTS, CHANNEL=CHANNEL
                )
                await db_helper.update_fields(
                    template_info=envs.rss_db_schema,
                    where=('uuid', UUID),
                    updates=('num_episodes', NUM_EPISODES)
                )
        # ...then other podcasts
        for feed in pod_check:
            UUID = pod_check[feed]['uuid']
            FEED_NAME = pod_check[feed]['name']
            CHANNEL = pod_check[feed]['channel']
            URL = pod_check[feed]['url']
            logger.debug(
                'Found channel `{} ({})` in `{}`'.format(
                    get(
                        discord_commands.get_guild().channels,
                        id=int(CHANNEL)
                    ).name, CHANNEL, FEED_NAME
                )
            )
            req = await net_io.get_link(URL)
            FEED_POSTS = await net_io.get_other_podcast_links(
                req=req, url=URL, uuid=UUID, num_items=3
            )
            logger.debug(
                'Got {} items for `FEED_POSTS`: '
                '{}'.format(
                    len(FEED_POSTS) if FEED_POSTS else 0,
                    [
                        pod_ep['title'] for pod_ep in FEED_POSTS
                    ] if FEED_POSTS else None
                )
            )
            if FEED_POSTS is None:
                logger.info(f'Feed {FEED_NAME} returned NoneType')
                await discord_commands.log_to_bot_channel(
                    I18N.t('rss.tasks.feed_posts_is_none', feed_name=FEED_NAME)
                )
            else:
                await feeds_core.process_links_for_posting_or_editing(
                    feed_type='podcast', uuid=UUID,
                    FEED_POSTS=FEED_POSTS, CHANNEL=CHANNEL
                )
        logger.info('Done with posting')

    @task_post_podcasts.before_loop
    async def before_post_new_podcasts():
        '#autodoc skip#'
        logger.debug('`task_post_podcasts` waiting for bot to be ready...')
        await config.bot.wait_until_ready()


async def setup(bot):
    # Create necessary databases before starting
    cog_name = 'rss'
    logger.info(envs.COG_STARTING.format(cog_name))
    logger.debug('Checking db')
    # Convert json to sqlite db-files if exists

    # Define inserts
    rss_inserts = None
    rss_prep_is_ok = None
    rss_settings_prep_is_ok = None
    rss_log_prep_is_ok = None
    # Populate the inserts if json file exist
    if file_io.file_exist(envs.rss_feeds_file) or\
            file_io.file_exist(envs.rss_feeds_logs_file):
        logger.debug('Found old json files')
        rss_inserts = await db_helper.json_to_db_inserts(cog_name)
    logger.debug(f'Got these inserts:\n{rss_inserts}')

    # Prep of DBs with json inserts should only be done if the
    # db files does not exist
    missing_tbl_cols = {}
    logger.debug('RSS db does not exist')
    rss_prep_is_ok = await db_helper.prep_table(
        table_in=envs.rss_db_schema,
        inserts=rss_inserts['feeds'] if rss_inserts is not None
        else rss_inserts
    )
    rss_filter_prep_is_ok = await db_helper.prep_table(
        table_in=envs.rss_db_filter_schema,
        inserts=rss_inserts['filter'] if rss_inserts is not None
        else rss_inserts
    )
    rss_settings_prep_is_ok = await db_helper.prep_table(
        table_in=envs.rss_db_settings_schema,
        inserts=envs.rss_db_settings_schema['inserts']
    )
    await db_helper.prep_table(
        table_in=envs.rss_db_ratings_schema
    )
    logger.debug(f'`rss_prep_is_ok` is {rss_prep_is_ok}')
    logger.debug(f'`rss_filter_prep_is_ok` is {rss_filter_prep_is_ok}')
    logger.debug(f'`rss_settings_prep_is_ok` is {rss_settings_prep_is_ok}')

    logger.debug('Checking columns in db')
    await db_helper.add_missing_db_setup(
        envs.rss_db_schema, missing_tbl_cols
    )
    await db_helper.add_missing_db_setup(
        envs.rss_db_settings_schema, missing_tbl_cols
    )
    await db_helper.add_missing_db_setup(
        envs.rss_db_log_schema, missing_tbl_cols
    )
    await db_helper.add_missing_db_setup(
        envs.rss_db_ratings_schema, missing_tbl_cols
    )
    logger.debug(f'rss db: `missing_tbl_cols` is {missing_tbl_cols}')
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
    await db_helper.db_channel_name_to_id(
        template_info=envs.rss_db_schema,
        id_col='uuid', channel_col='channel'
    )
    rss_log_prep_is_ok = await db_helper.prep_table(
        table_in=envs.rss_db_log_schema,
        inserts=rss_inserts['logs'] if rss_inserts is not None
        else rss_inserts
    )
    logger.debug(f'`rss_log_prep_is_ok` is {rss_log_prep_is_ok}')
    logger.debug('checking columns')
    missing_tbl_cols = await db_helper.add_missing_db_setup(
        envs.rss_db_log_schema, missing_tbl_cols
    )
    logger.debug(f'rss log: `missing_tbl_cols` is {missing_tbl_cols}')
    if any(len(missing_tbl_cols[table]) > 0 for table in missing_tbl_cols):
        missing_tbl_cols_text = ''
        for _tbl in missing_tbl_cols:
            missing_tbl_cols_text += '{}:\n'.format(
                _tbl
            )
            missing_tbl_cols_text += '\n- '.join(missing_tbl_cols[_tbl])
        await discord_commands.log_to_bot_channel(
            'Missing columns in rss db: {}\n'
            'Make sure to populate missing information'.format(
                missing_tbl_cols_text
            )
        )

    # Delete old json files if they are not necessary anymore
    if rss_prep_is_ok:
        file_io.remove_file(envs.rss_feeds_file)
    if rss_log_prep_is_ok:
        file_io.remove_file(envs.rss_feeds_logs_file)
    logger.debug('Registering cog to bot')
    await bot.add_cog(RSSfeed(bot))

    task_list = await db_helper.get_output(
        template_info=envs.tasks_db_schema,
        select=('task', 'status'),
        where=('cog', 'rss')
    )
    _inserts = envs.tasks_db_schema['inserts']
    task_check = [task['task'] for task in task_list]
    if len(task_list) < len(_inserts):
        for _ins in _inserts:
            if _ins[1] in task_check:
                _inserts.remove(_ins)
        await db_helper.insert_many_all(
            template_info=envs.tasks_db_schema,
            inserts=(
                _inserts
            )
        )
    for task in task_list:
        logger.debug(f'Checking task: {task}')
        if task['task'] == 'post_feeds':
            if task['status'] == 'started':
                logger.debug(
                    '`{task}` is set as `{status}`, starting...'.format(
                        task=task['task'], status=task['status']
                    )
                )
                RSSfeed.task_post_feeds.start()
            elif task['status'] == 'stopped':
                logger.debug(
                    '`{task}` is set as `{status}`'.format(
                        task=task['task'], status=task['status']
                    )
                )
                RSSfeed.task_post_feeds.cancel()
        if task['task'] == 'post_podcasts':
            if task['status'] == 'started':
                logger.debug(
                    '`{task}` is set as `{status}`, starting...'.format(
                        task=task['task'], status=task['status']
                    )
                )
                RSSfeed.task_post_podcasts.start()
            elif task['status'] == 'stopped':
                logger.debug(
                    '`{task}` is set as `{status}`'.format(
                        task=task['task'], status=task['status']
                    )
                )
                RSSfeed.task_post_podcasts.cancel()


async def teardown(bot):
    RSSfeed.task_post_feeds.cancel()
