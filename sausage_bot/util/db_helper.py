#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'db_helper: Helper functions for database handling'
import aiosqlite
from uuid import uuid4
import re
from pathlib import Path
from discord.utils import get
from pprint import pformat

from sausage_bot.util import envs, config, file_io, discord_commands
from sausage_bot.util.args import args
from .datetime_handling import get_dt

logger = config.logger


def db_exist(db_file_in):
    file_io.ensure_folder(envs.DB_DIR)
    db_path = str(db_file_in['db_file'])
    try:
        file_io.file_exist(db_path)
        return True
    except Exception as e:
        logger.error(f'Could not find database {db_path}: {e}')
        return False


async def table_exist(template_info):
    db_file = template_info['db_file']
    logger.info(f'Opening `{db_file}`')
    table_name = template_info['name']
    async with aiosqlite.connect(db_file) as db:
        out = await db.execute(f'PRAGMA table_info({table_name})')
        out = await out.fetchall()
    return len(out) > 0


async def prep_table(
    table_in, inserts: list = None
):
    logger.debug(f'Got `table_in`: {table_in}')
    db_file = table_in['db_file']
    file_io.ensure_folder(Path(db_file).parent)
    table_name = table_in['name']
    item_list = table_in['items']
    _cmd = '''CREATE TABLE IF NOT EXISTS {} ('''.format(table_name)
    try:
        _cmd += ', '.join(
            '{} {}'.format(
                item[0], item[1]
            ) for item in item_list
        )
    except IndexError as e:
        logger.error(
            f'Error when creating table `{table_name}` in {db_file}: {e}'
        )
        return None
    if 'primary' in table_in and\
            table_in['primary'] is not None:
        _cmd += ', PRIMARY KEY({}'.format(
            table_in['primary']
        )
        if 'autoincrement' in table_in and\
                table_in['autoincrement'] is True:
            _cmd += ' AUTOINCREMENT'
        _cmd += ')'
    _cmd += ');'
    logger.debug(f'Using this query: {_cmd}')
    if args.not_write_database:
        logger.debug('`not_write_database` activated')
    elif not args.not_write_database:
        try:
            async with aiosqlite.connect(db_file) as db:
                await db.execute(_cmd)
                logger.debug(f'Changed {db.total_changes} rows')
        except aiosqlite.OperationalError as e:
            logger.error(f'Error: {e}')
            return None
    delete_json_ok = False
    if inserts:
        await add_missing_db_setup(
            table_in
        )
    return delete_json_ok


async def add_missing_db_setup(
        template_info, dict_in: dict = None
):
    logger.debug(f'Received `template_info`:\n{pformat(template_info)}')
    db_file = template_info['db_file']
    table_name = template_info['name']
    inserts = template_info['inserts'] if 'inserts' in template_info else None
    logger.debug(f'Checking `{table_name}` in `{db_file}`: {dict_in}')
    if not dict_in:
        dict_in = {}
    if table_name not in dict_in:
        dict_in[table_name] = []
        await prep_table(template_info)
    logger.debug(f'dict_in is: {dict_in}')
    wanted_cols = template_info['items']
    table_info = f'PRAGMA table_info({table_name})'
    async with aiosqlite.connect(db_file) as db:
        db_out = await db.execute(table_info)
        existing_cols = await db_out.fetchall()
        _existing_cols = [col[1] for col in existing_cols]
        logger.debug(f'_existing_cols: {_existing_cols}')
    async with aiosqlite.connect(db_file) as db:
        row_ids = await db.execute(
            f'SELECT rowid FROM {table_name}'
        )
        row_ids = await row_ids.fetchall()
    _existing_cols = [col[1] for col in existing_cols]
    if len(_existing_cols) > 0:
        # Add wanted cols if they don't exist
        for col_in in wanted_cols:
            if col_in[0] not in _existing_cols:
                logger.debug(f'Adding {col_in[0]}')
                dict_in[table_name].append(col_in)
        async with aiosqlite.connect(db_file) as db:
            for col in dict_in[table_name]:
                _cmd = f'ALTER TABLE {table_name} ADD COLUMN {col[0]};'
                logger.debug(f'Using this query: {_cmd}')
                await db.execute(_cmd)
        # Remove cols if they are not wanted anymore
        del_cols = [
            x for x in _existing_cols if x not in [x[0] for x in wanted_cols]
        ]
        async with aiosqlite.connect(db_file) as db:
            for col in del_cols:
                _cmd = f'ALTER TABLE {table_name} DROP COLUMN {col};'
                logger.debug(f'Using this query: {_cmd}')
                await db.execute(_cmd)
    # Add existing inserts in columns where they don't exist yet
    temp_inserts = []
    if inserts is not None and len(inserts) > 0:
        logger.debug('`inserts` has length')
        db_out = await get_output(
            template_info=template_info,
            select=('setting', 'value')
        )
        db_out_cols = [col['setting'] for col in db_out]
        logger.debug(f'Got `inserts`: {inserts}')
        logger.debug(f'Got `db_out`: {db_out}')
        for insert in inserts:
            add_to_temp = None
            if (insert[0] not in db_out_cols) or insert[0] in db_out and\
                    db_out[db_out_cols.index(insert[0])] is None:
                add_to_temp = True
            if add_to_temp:
                temp_inserts.append(tuple(insert))
        logger.debug(f'temp_inserts: {temp_inserts}')
    if len(temp_inserts) > 0:
        await insert_many_some(
            template_info=template_info,
            rows=tuple(item[0] for item in template_info['items']),
            inserts=temp_inserts
        )
    return dict_in


async def find_cols(
        template_info, cols_find: list = None
):
    db_file = template_info['db_file']
    table_name = template_info['name']
    logger.debug(f'Got `db_file`: {db_file}')
    logger.debug(f'Got `table_name`: {table_name}')
    table_info = f'PRAGMA table_info({table_name})'
    async with aiosqlite.connect(db_file) as db:
        db_out = await db.execute(table_info)
        search_out = await db_out.fetchall()
    _cols = [col[1] for col in search_out]
    found_cols = []
    for col_in in cols_find:
        if col_in in _cols:
            found_cols.append(col_in)
    return found_cols


async def remove_cols(
        template_info, cols_remove: list = None
):
    db_file = template_info['db_file']
    table_name = template_info['name']
    logger.debug(f'Got `db_file`: {db_file}')
    logger.debug(f'Got `table_name`: {table_name}')
    if args.not_write_database:
        logger.debug('`not_write_database` activated')
    else:
        _cmd = 'ALTER TABLE {} DROP COLUMN {};'
        try:
            async with aiosqlite.connect(db_file) as db:
                for col_in in cols_remove:
                    __cmd = _cmd.format(table_name, col_in)
                    logger.debug(f'Using this query: {__cmd}')
                    await db.execute(__cmd)
                await db.commit()
        except aiosqlite.OperationalError as e:
            logger.error(f'Error: {e}')
            return
    return


async def db_fix_old_hide_roles_status():
    old_hide_roles = await get_output(
        template_info=envs.stats_db_settings_schema,
        get_row_ids=True,
        where=('setting', 'hide_roles')
    )
    if len(old_hide_roles) > 0:
        logger.info('Moving hide_roles from settings tale to hide_roles')
        await prep_table(
            table_in=envs.stats_db_hide_roles_schema
        )
        old_hide_roles = await get_output(
            template_info=envs.stats_db_settings_schema,
            get_row_ids=True,
            where=('setting', 'hide_roles'),
            select=('value')
        )
        row_ids = [rowid['rowid'] for rowid in old_hide_roles]
        values = [[rowid['value']] for rowid in old_hide_roles]
        await insert_many_all(
            template_info=envs.stats_db_hide_roles_schema,
            inserts=values
        )
        await del_row_ids(
            template_info=envs.stats_db_settings_schema,
            numbers=row_ids
        )


async def db_fix_old_stats_msg_name_status():
    old_stats_msg_name_status = await get_output(
        template_info=envs.stats_db_settings_schema,
        where=('setting', 'stats_msg')
    )
    if len(old_stats_msg_name_status) > 0:
        logger.debug('Renaming stats_msg to stats_msg_id')
        await update_fields(
            template_info=envs.stats_db_settings_schema,
            where=('setting', 'stats_msg'),
            updates=('setting', 'stats_msg_id')
        )


async def db_fix_old_value_check_or_help():
    old_value_check_or_help = await find_cols(
        template_info=envs.stats_db_settings_schema,
        cols_find=('value_check', 'value_help')
    )
    if len(old_value_check_or_help) > 0:
        logger.debug('Removing columns: {}'.format(
            ', '.join(old_value_check_or_help)
        ))
        await remove_cols(
            template_info=envs.stats_db_settings_schema,
            cols_remove=old_value_check_or_help
        )


async def db_replace_numeral_bool_with_bool(template_info):
    old_value_numeral_instead_of_bool = await get_output(template_info)
    logger.debug(
        'old_value_numeral_instead_of_bool: '
        f'{old_value_numeral_instead_of_bool}'
    )
    # Make a copy of the db-dict to use as a checklist for converting
    # numerals to bools if need be
    db_new_bool_status = old_value_numeral_instead_of_bool.copy()
    if 'type_checking' not in template_info:
        return
    db_type_checking = template_info['type_checking']
    for setting in old_value_numeral_instead_of_bool:
        logger.debug(f'Checking {setting}')
        setting_in = list(setting.values())
        remove_status = False
        if setting_in[0] in db_type_checking:
            # Remove item from copied list if it's ok
            if db_type_checking[setting_in[0]] == 'str':
                remove_status = True
            else:
                if db_type_checking[setting_in[0]] == 'bool':
                    if type(eval(str(setting_in[1]).capitalize())) is not\
                            eval(db_type_checking[setting_in[0]]):
                        remove_status = False
                    else:
                        remove_status = True
                else:
                    remove_status = True
            if remove_status:
                db_new_bool_status.pop(db_new_bool_status.index(setting))
    logger.debug(
        f'`db_new_bool_status` after checking:\n{pformat(db_new_bool_status)}',
    )
    for setting in db_new_bool_status:
        setting_in = list(setting.values())
        if str(setting_in[1]).lower() in ['true', 'false']:
            setting_in[1] = setting_in[1].capitalize()
        if type(eval(setting_in[1])) is int:
            if setting_in[1] == 0:
                setting_in[1] = False
            elif setting_in[1] == 1:
                setting_in[1] = True
        else:
            db_new_bool_status.pop(db_new_bool_status.index(setting))
    if len(db_new_bool_status) > 0:
        logger.debug(
            'Length of `db_new_bool_status` is more than 0. Converting old '
            'value numeral to bool'
        )
        for setting in db_new_bool_status:
            setting_in = list(setting.values())
            if setting_in[1] == '0':
                new_setting_in = False
            elif setting_in[1] == '1':
                new_setting_in = True
            await update_fields(
                template_info=template_info,
                where=('setting', setting_in[0]),
                updates=('value', new_setting_in)
            )


async def db_update_to_correct_feed_types(template_info):
    update_to_correct_feed_types = await get_output(template_info)
    logger.debug('Running db_update_to_correct_feed_types')
    # Make a copy of the db-dict to use as a checklist for converting
    # feed types if need be
    db_new_feed_types = update_to_correct_feed_types.copy()
    for feed in update_to_correct_feed_types:
        if str(feed['feed_type']).lower() != 'spotify':
            # Remove item from copied list if it's ok
            remove_status = True
        else:
            remove_status = False
        if remove_status:
            db_new_feed_types.pop(db_new_feed_types.index(feed))
    if len(db_new_feed_types) > 0:
        logger.debug(
            f'`db_new_feed_types` after checking:\n{pformat(db_new_feed_types)}',
        )
        for feed_type in db_new_feed_types:
            await update_fields(
                template_info=template_info,
                where=('feed_type', 'spotify'),
                updates=('feed_type', 'podcast')
            )


async def db_channel_names_to_ids(template_info, id_col, channel_col: str):
    row_items = await get_output(
        template_info=template_info,
        select=(id_col, channel_col)
    )
    # Replace channel names with channel id in list
    row_items_copy = row_items.copy()
    for row_item in row_items:
        if not re.match(r'(\d+)', row_item['channel']):
            # Try to search for channel ID
            logger.debug('channel is not an id, searching for name...')
            try:
                channel_id = get(
                    discord_commands.get_guild().text_channels,
                    name=row_item['channel']
                ).id
                logger.debug(f'Found channel id: {channel_id}')
                row_item['channel_new'] = channel_id
            except AttributeError as e:
                # TODO i18n
                error_msg = 'Could not find channel `{}` in `{}` (`{}`)'\
                    ': {}'.format(
                        row_item['channel'],
                        template_info['name'],
                        template_info['db_file'],
                        e
                    )
                logger.error(error_msg)
                await discord_commands.log_to_bot_channel(
                    f'`db_channel_name_to_id`: {error_msg}'
                )
                row_items_copy.pop(row_items_copy.index(row_item))
        elif re.match(r'(\d+)', row_item['channel']):
            logger.debug(
                'Channel `{}` is an id and is ok'.format(
                    row_item['channel']
                )
            )
            row_items_copy.pop(row_items_copy.index(row_item))
        else:
            logger.error('Unexpected error')
            row_items_copy.pop(row_items_copy.index(row_item))
    changes = {channel_col: []}
    logger.debug('Channel updates: {}'.format(row_items_copy))
    for copy in row_items_copy:
        changes[channel_col].append(
            (
                channel_col,
                copy['channel'],
                copy['channel_new']
            )
        )
    logger.debug('Changes: {}'.format(changes))
    if len(changes[channel_col]) > 0:
        # Replace channel names with channel id in db
        await update_fields(
            template_info=template_info,
            updates=changes
        )
    return


async def db_single_channel_name_to_id(
        template_info, channel_row: str, channel_col: str
):
    channel_in_db = await get_output(
        template_info=template_info,
        where=(channel_row, 'channel'),
        select=(channel_col)
    )
    # Replace channel names with channel id in list
    if len(channel_in_db) <= 0:
        logger.debug('No channel found in database')
        return None
    channel_in = channel_in_db[0]['value']
    if not re.match(r'(\d+)', channel_in):
        # Try to search for channel ID
        logger.debug('channel is not an id, searching for name...')
        try:
            channel_id = get(
                discord_commands.get_guild().text_channels,
                name=channel_in
            ).id
            logger.debug(f'Found channel id: {channel_id}')
            # Replace channel names with channel id in db
            await update_fields(
                template_info=template_info,
                where=(channel_row, 'channel'),
                updates=(channel_col, channel_id)
            )
        except AttributeError as e:
            # TODO i18n
            error_msg = 'Could not find channel `{}` in `{}` (`{}`)'\
                ': {}'.format(
                    channel_in,
                    template_info['name'],
                    template_info['db_file'],
                    e
                )
            logger.error(error_msg)
            await discord_commands.log_to_bot_channel(
                f'`db_single_channel_name_to_id`: {error_msg}'
            )
    elif re.match(r'(\d+)', channel_in):
        logger.debug(
            'Channel `{}` is an id and is ok'.format(
                channel_in
            )
        )
    else:
        logger.error('Unexpected error')
        return None
    return


async def db_remove_old_cols(template_info):
    '''
    Sjekke hvilke kolonner som ikke finnes i ny envs
    Fjern disse
    '''
    async def list_cols(template_info):
        db_file = template_info['db_file']
        table_name = template_info['name']
        logger.debug(f'Got `db_file`: {db_file}')
        logger.debug(f'Got `table_name`: {table_name}')
        table_info = f'PRAGMA table_info({table_name})'
        async with aiosqlite.connect(db_file) as db:
            db_out = await db.execute(table_info)
            list_out = await db_out.fetchall()
        return [col[1] for col in list_out] if list_out is not None else None

    logger.debug(f'Received `template_info`:\n{pformat(template_info)}')
    cols = template_info['items']
    cols_to_remove = []
    # Check existing columns in db
    cols_in_db = await list_cols(template_info)
    for db_col in cols_in_db:
        if db_col not in [col[0] for col in cols]:
            cols_to_remove.append(db_col)
    await remove_cols(template_info, cols_to_remove)


async def json_to_db_inserts(cog_name):
    '''
    This is a cleanup function to be used for converting from old json
    files to sqlite files
    #autodoc skip#
    '''
    logger.info('Converting json to db')
    logger.info(f'Processing `{cog_name}`')
    if cog_name == 'roles':
        settings_file = file_io.read_json(envs.roles_settings_file)
        settings_inserts = []
        msg_inserts = []
        reactions_inserts = []
        if len(settings_file) > 0:
            if 'unique_role' in settings_file:
                logger.debug('Found unique role-settings')
                if settings_file['unique_role']['role'] is not None:
                    settings_inserts.append(
                        ('unique', str(settings_file['unique_role']['role']))
                    )
                no_total = settings_file['unique_role']['not_include_in_total']
                if len(no_total) > 0:
                    for list_item in no_total:
                        settings_inserts.append(
                            ('not_include_in_total', str(no_total[list_item]))
                        )
                logger.debug(
                    f'Got this for `settings_inserts`:\n{settings_inserts}'
                )
            for _msg in settings_file['reaction_messages']:
                __msg = settings_file['reaction_messages'][_msg]
                msg_inserts.append(
                    (
                        str(__msg['id']), __msg['channel'], str(_msg),
                        __msg['content'], __msg['description'],
                        int(__msg['order'])
                    )
                )
                reacts = __msg['reactions']
                for react in reacts:
                    reactions_inserts.append(
                        (
                            str(__msg['id']), react[0], react[1]
                        )
                    )
        return {
            'settings_inserts': settings_inserts,
            'msg_inserts': msg_inserts,
            'reactions_inserts': reactions_inserts
        }
    elif cog_name == 'dilemmas':
        dilemmas_file = file_io.read_json(envs.dilemmas_file)
        dilemmas_inserts = []
        for dilemma in dilemmas_file:
            dilemmas_inserts.append(
                (str(uuid4()), dilemmas_file[dilemma])
            )
        logger.debug(f'Got this for `dilemmas_inserts`:\n{dilemmas_inserts}')
        return dilemmas_inserts
    elif cog_name == 'quote':
        quote_file = file_io.read_json(envs.quote_file)
        quotes_inserts = []
        for quote in quote_file:
            quotes_inserts.append(
                (
                    str(uuid4()), quote_file[quote]['quote'],
                    await get_dt(
                        format="ISO8601", dt=re.sub(
                            r'[\(\)]+', '',
                            quote_file[quote]['datetime']
                        )
                    )
                )
            )
        logger.debug(f'Got this for `quotes_inserts`:\n{quotes_inserts}')
        return quotes_inserts
    elif cog_name == 'stats':
        # Check stats file
        stats_inserts = []
        if file_io.file_exist(envs.stats_file):
            stats_file = file_io.read_json(envs.stats_file)
            stats_settings_inserts = envs.stats_db_settings_schema['inserts']
            for insert in stats_settings_inserts:
                if insert[0] in stats_file:
                    under_inserts = stats_file[insert[0]]
                    if isinstance(under_inserts, list):
                        for under_insert in under_inserts:
                            stats_inserts.append(
                                (insert[0], under_insert, insert[2], insert[3])
                            )
                    else:
                        stats_inserts.append(
                            (
                                insert[0], stats_file[insert[0]], insert[2],
                                insert[3]
                            )
                        )
                else:
                    stats_inserts.append(
                        (
                            insert[0], insert[1], insert[2],
                            insert[3]
                        )
                    )
            logger.debug(f'Got this for `stats_inserts`:\n{stats_inserts}')
        stats_hide_roles_inserts = envs.stats_db_hide_roles_schema['inserts']
        # Check stats log file
        stats_logs_inserts = []
        if file_io.file_exist(envs.stats_logs_file):
            stats_logs_file = file_io.read_json(envs.stats_logs_file)
            for _y in stats_logs_file:
                for _m in stats_logs_file[_y]:
                    for _d in stats_logs_file[_y][_m]:
                        _stats_in = stats_logs_file[_y][_m][_d]
                        if 'files_in_codebase' in _stats_in:
                            files_in = _stats_in.get(['files_in_codebase'], 0)
                        if 'lines_in_codebase' in _stats_in:
                            lines_in = _stats_in.get(['lines_in_codebase'], 0)
                        if 'members' in _stats_in:
                            members_in = _stats_in['members']['total']
                        else:
                            members_in = 0
                        stats_logs_inserts.append(
                            (
                                f'{_y}-{_m}-{_d} 00:00:00.000',
                                files_in,
                                lines_in,
                                members_in
                            )
                        )
        return {
            'stats_inserts': stats_inserts,
            'stats_logs_inserts': stats_logs_inserts,
            'stats_hide_roles_inserts': stats_hide_roles_inserts
        }
    elif cog_name == 'rss':
        rss_file = file_io.read_json(envs.rss_feeds_file)
        logger.debug('Got `rss_file`: {}'.format(str(rss_file)[0:100]))
        rss_logs_file = file_io.read_json(envs.rss_feeds_logs_file)
        logger.debug(
            'Got `rss_logs_file`: {}'.format(str(rss_logs_file)[0:100])
        )
        rss_inserts = []
        rss_filter_inserts = []
        rss_logs_inserts = []
        rss_logs_index = {}
        for feed in rss_file:
            _uuid = str(uuid4())
            rss_logs_index[feed] = _uuid
            rss_inserts.append(
                (
                    _uuid,
                    feed,
                    rss_file[feed]['url'],
                    rss_file[feed]['channel'],
                    rss_file[feed]['added'],
                    rss_file[feed]['added by'],
                    str(rss_file[feed]['status_url']).upper(),
                    rss_file[feed]['status_url_counter'],
                    str(rss_file[feed]['status_channel']).upper(),
                )
            )
            filter_allow = rss_file[feed]['filter_allow']
            filter_deny = rss_file[feed]['filter_deny']
            if (len(filter_allow) + len(filter_deny)) > 0:
                if len(filter_allow) > 0:
                    for line in filter_allow:
                        rss_filter_inserts.append(
                            (
                                _uuid, 'allow', filter_allow[line]
                            )
                        )
                if len(filter_deny) > 0:
                    for line in filter_deny:
                        rss_filter_inserts.append(
                            (
                                _uuid, 'deny', line
                            )
                        )
        if rss_logs_file is not None:
            for feed in rss_logs_file:
                if feed in rss_logs_index:
                    for link in rss_logs_file[feed]:
                        rss_logs_inserts.append(
                            (
                                rss_logs_index[feed], link,
                                str(await get_dt(format='ISO8601'))
                            )
                        )
        return {
            'feeds': rss_inserts,
            'filter': rss_filter_inserts,
            'logs': rss_logs_inserts
        }
    elif cog_name == 'youtube':
        yt_file = file_io.read_json(envs.youtube_feeds_file)
        yt_logs_file = file_io.read_json(envs.youtube_feeds_logs_file)
        yt_inserts = []
        yt_filter_inserts = []
        yt_logs_inserts = []
        yt_logs_index = {}
        for feed in yt_file:
            _uuid = str(uuid4())
            yt_logs_index[feed] = _uuid
            yt_inserts.append(
                (
                    _uuid, feed, yt_file[feed]['url'],
                    yt_file[feed]['channel'],
                    yt_file[feed]['added'],
                    yt_file[feed]['added by'],
                    yt_file[feed]['status_url'],
                    yt_file[feed]['status_url_counter'],
                    yt_file[feed]['status_channel'],
                    yt_file[feed]['yt_id']
                )
            )
            filter_allow = yt_file[feed]['filter_allow']
            filter_deny = yt_file[feed]['filter_deny']
            if (len(filter_allow) + len(filter_deny)) > 0:
                if len(filter_allow) > 0:
                    for line in filter_allow:
                        yt_filter_inserts.append(
                            (
                                _uuid, 'allow', filter_allow[line]
                            )
                        )
                if len(filter_deny) > 0:
                    for line in filter_deny:
                        yt_filter_inserts.append(
                            (
                                _uuid, 'deny', line
                            )
                        )
        for feed in yt_logs_file:
            if feed in yt_logs_index:
                for link in yt_logs_file[feed]:
                    yt_logs_inserts.append(
                        (
                            yt_logs_index[feed], link,
                            str(await get_dt(format='ISO8601'))
                        )
                    )
        return {
            'feeds': yt_inserts,
            'filter': yt_filter_inserts,
            'logs': yt_logs_inserts
        }
    logger.info('Converting done!')


async def insert_many_all(
        template_info,
        inserts: tuple = None
):
    '''
    Insert info to all columns in a sqlite row

    Equals to this SQl command:
        INSERT INTO `template_info[table_name]`
        VALUES(?, ?, ?)

        (inserts is tuples of values)

    Parameters
    ------------
    template_info: dict
        dict info about the table from envs file
    inserts: list(tuple)
        A list with tuples for reach row
    '''
    db_file = template_info['db_file']
    table_name = template_info['name']
    logger.debug(f'Got `db_file`: {db_file}')
    logger.debug(f'Got `table_name`: {table_name}')
    logger.debug(
        'Got `inserts`: {}'.format(
            str(inserts)[0:200] + '...' if len(str(inserts)) > 200 else inserts
        )
    )
    input_singles = False
    input_multiples = False
    _cmd = f'INSERT INTO {table_name} VALUES('
    logger.debug(f'Got {len(inserts)} `inserts`')
    if isinstance(inserts[0], (list, tuple)):
        logger.debug('Got multiple inserts')
        _cmd += ', '.join('?' * len(inserts[0]))
        input_multiples = True
    else:
        logger.debug('Got single insert')
        _cmd += ', '.join('?' * len(inserts))
        input_singles = True
    _cmd += ')'
    logger.debug(f'Using this query: {_cmd}')
    if args.not_write_database:
        logger.debug('`not_write_database` activated')
    elif not args.not_write_database:
        try:
            async with aiosqlite.connect(db_file) as db:
                if input_singles:
                    await db.execute(_cmd, inserts)
                elif input_multiples:
                    await db.executemany(_cmd, inserts)
                await db.commit()
                logger.debug(
                    'Changed {} rows'.format(
                        db.total_changes
                    )
                )
            logger.debug('Done and commited!')
            return True
        except aiosqlite.OperationalError as e:
            logger.error(e)
            return False


async def insert_many_some(
        template_info,
        rows: tuple = None,
        inserts: list = None
):
    '''
    Insert info in specific columns in a sqlite row:

    Parameters
    ------------
    template_info: dict
        dict info about the table from envs file
    rows: tuple
        A tuple with the row names to add each inserts tuple into
    inserts: list(tuples)
        A list with tuples for reach row
    '''
    db_file = template_info['db_file']
    table_name = template_info['name']
    if db_file is None:
        logger.error('`db_file` is None')
        return None
    if table_name is None:
        logger.error('`table_name` is None')
        return None
    logger.debug(f'Got `db_file`: {db_file}')
    logger.debug(f'Got `table_name`: {table_name}')
    logger.debug(f'Got `rows`: {rows}')
    logger.debug(
        f'Got `inserts`: {type(inserts)} {len(inserts)}:\n{pformat(inserts)}'
    )
    input_singles = False
    input_multiples = False
    if isinstance(inserts[0], (tuple)):
        input_multiples = True
    elif isinstance(inserts[0], str):
        input_singles = True
    _cmd = f'INSERT INTO {table_name} ('
    _cmd += ', '.join(row for row in rows)
    _cmd += ') VALUES ('
    if input_singles:
        _cmd += ', '.join('?' * len(inserts))
    elif input_multiples:
        _cmd += ', '.join('?' * len(inserts[0]))
    _cmd += ')'
    logger.debug(f'Using this query: {_cmd} {inserts}')
    if args.not_write_database:
        logger.debug('`not_write_database` activated')
    elif not args.not_write_database:
        if input_singles:
            inserts = [inserts]
        try:
            async with aiosqlite.connect(db_file) as db:
                await db.executemany(_cmd, inserts)
                await db.commit()
                logger.debug(
                    'Changed {} rows'.format(
                        db.total_changes
                    )
                )
        except aiosqlite.OperationalError as e:
            logger.error(f'Error: {e}')
            return None


async def insert_single(
        template_info,
        field_name: str = None,
        insert=None
):
    '''
    Insert a single field in specific column in a sqlite row:

    Parameters
    ------------
    template_info: dict
        dict info about the table from envs file
    field_name: str
        Row name to add insert into
    insert:
        Input for the field_name
    '''
    db_file = template_info['db_file']
    table_name = template_info['name']
    if db_file is None:
        logger.error('`db_file` is None')
        return None
    if table_name is None:
        logger.error('`table_name` is None')
        return None
    _cmd = f'''INSERT INTO {table_name} ({field_name})
               VALUES(?)'''
    logger.debug(f'Using this query: {_cmd}')
    if args.not_write_database:
        logger.debug('`not_write_database` activated')
    elif not args.not_write_database:
        try:
            async with aiosqlite.connect(db_file) as db:
                await db.execute(_cmd, insert)
                await db.commit()
                logger.debug(
                    'Changed {} rows'.format(
                        db.total_changes
                    )
                )
                last_row = db.lastinsertrow
            logger.debug('Done and commited!')
            return last_row
        except aiosqlite.OperationalError as e:
            logger.error(f'Error: {e}')
            return None


async def update_fields(
    template_info, where=None, updates: list = None
):
    '''
    Update a table with listed tuples in `updates` where you can
    find the specific `where`.

    Equals to this SQl command:
        UPDATE `template_info[table_name]`
        SET `updates[0][0]` = `updates[0][1]`
            `updates[1][0]` = `updates[1][1]`,
            `updates[2][0]` = `updates[2][1]`
        WHERE
            `where[0]` = `where[1]`

    If one update has a list as a value, interpret this as using CASE.
    This cannot be combined with WHERE

        UPDATE `template_info[table_name]`
        SET `updates[0][0]` = `updates[0][1]`
            `updates[1][0]` = CASE
                WHEN `updates[1][1][0][0]` = `updates[1][1][0][1]`
                    THEN `updates[1][1][0][2]`
                WHEN `updates[1][1][1][0]` = `updates[1][1][1][1]`
                    THEN `updates[1][1][1][2]`
                ELSE `updates[1][0]`
            END,
            `updates[2][0]` = `updates[2][1]`

    Parameters
    ------------
    template_info: dict
        dict info about the table from envs file
    where: tuple/list of tuples
        Single or multiple things to look for to identify correct rows
    updates: list(tuples)
        A list of tuples with a field, value combination. If value is a
        list, it should be treated as CASE
    '''
    db_file = template_info['db_file']
    table_name = template_info['name']
    if table_name is None:
        logger.error('Missing table_name')
        return
    if updates is None:
        logger.error('Missing updates')
        return
    _cmd = f'UPDATE {table_name} SET '
    if isinstance(updates, dict):
        logger.debug('`updates` is dict')
        for update in updates:
            logger.debug(f'Got `update`: {update}')
            _cmd += "{} = CASE".format(update)
            for _item in updates[update]:
                _cmd += " WHEN {} = '{}' THEN '{}'".format(
                    _item[0], _item[1], _item[2]
                )
            _cmd += ' ELSE {} END'.format(update)
            if update != list(updates)[-1]:
                _cmd += ', '
    elif isinstance(updates, (list, tuple)):
        logger.debug('`updates` is list or tuple')
        if isinstance(updates[0], (str, int)):
            _cmd += "{} = '{}'".format(updates[0], updates[1])
        elif isinstance(updates[0], (list, tuple)):
            for update in updates:
                _cmd += "{} = '{}'".format(update[0], update[1])
                if update != updates[-1]:
                    _cmd += ', '
        if isinstance(where, tuple):
            _cmd += f" WHERE {where[0]} = '{where[1]}'"
        elif isinstance(where, list):
            _cmd += " WHERE "
            for id in where:
                _cmd += f"{id[0]} = '{id[1]}'"
                if id != where[-1]:
                    _cmd += ' AND '
    logger.debug(f'Using this query: {_cmd}')
    if args.not_write_database:
        logger.debug('`not_write_database` activated')
    elif not args.not_write_database:
        try:
            async with aiosqlite.connect(db_file) as db:
                await db.execute(_cmd)
                await db.commit()
            logger.debug('Done and commited!')
        except aiosqlite.OperationalError as e:
            logger.error(f'Error: {e}')
            return None


async def get_output(
    template_info, where: tuple = None, like: tuple = None,
    not_like: tuple = None, select: tuple = None, order_by: list = None,
    get_row_ids: bool = False, rowid_sort: bool = False,
    single: bool = None, as_settings_json: bool = False
):
    '''
    Get output from a SELECT query from a specified
    `template_info[table_name]`, with WHERE-filtering the `where` and
    ORDER BY `order_by` (if given).

    Parameters
    ------------
    template_info: dict
        dict info about the table from envs file
    where: list/tuple
        Single or multiple things to look for to identify correct rows
        Could be a single tuple or a list of tuples
        Tuple can be:
            (`col name`, `value`)
                or
            (`col name`, `operator`, `value`)
        If no operator is given, it will always use `==`
    like: tuple
        Single or multiple keywords to search for in a row
    not_like: tuple
        Single or multiple keywords to exclude
    select: tuple
        What fields to get from the db file
    order_by: list(tuples)
        What fields to order by and if ordered by ASC or DESC
    get_row_ids: bool
        Also get rowid
    rowid_sort: bool
        Sort output by rowids
    single: bool
        Only return one single result
    as_settings_json: bool
        Return output as json instead of dict
        Only works for tables with two columns
    '''
    def parse_wheres(where):
        if not isinstance(where, tuple):
            return None
        # If length of where is 3, then it contains an operator
        if len(where) == 3:
            print(where[2].lower())
            if where[2].lower() in ['none', 'null', '0', 'false']:
                cmd = f" {where[0]} {where[1]} NULL"
            else:
                cmd = f" LOWER({where[0]}) {where[1]} LOWER('{where[2]}')"
        # If length of where is 2, then it contains only col name and value
        elif len(where) == 2:
            cmd = f" LOWER({where[0]}) = LOWER('{where[1]}')"
        else:
            logger.error('Error with input, returning None')
            return None
        return cmd

    db_file = template_info['db_file']
    logger.debug(f'Opening `{db_file}`')
    table_name = template_info['name']
    _cmd = 'SELECT '
    if get_row_ids:
        _cmd += 'rowid, '
    if select is None:
        _cmd += '*'
    elif isinstance(select, tuple) and\
            len(select) > 1:
        _cmd += ', '.join(field for field in select)
    elif isinstance(select, str):
        _cmd += select
    _cmd += f' FROM {table_name}'
    logger.debug(f'where: {where}')
    logger.debug(f'like: {like}')
    logger.debug(f'not_like: {not_like}')
    if where is not None:
        if 'where' not in _cmd.lower():
            _cmd += " WHERE"
        else:
            _cmd += ' AND'
        if isinstance(where, tuple):
            logger.debug(f'`where` is tuple: {where}')
            _cmd += parse_wheres(where)
        elif isinstance(where, list) and isinstance(where[0], tuple):
            logger.debug(f'`where` is tuple inside a list: {where}')
            for _where in where:
                _cmd += parse_wheres(_where)
                if _where[0] != where[-1][0]:
                    _cmd += ' AND'
    if like is not None:
        if 'where' not in _cmd.lower():
            _cmd += " WHERE"
        else:
            _cmd += ' AND'
        if isinstance(like, tuple):
            logger.debug(f'`like` is tuple: {like}')
            _cmd += f" {like[0]} LIKE '%{like[1]}%'"
        elif isinstance(like, list) and isinstance(like[0], tuple):
            logger.debug(f'`like` is tuple inside a list: {like}')
            for id in like:
                _cmd += f" {id[0]} LIKE '%{id[1]}%'"
                if id != like[-1]:
                    _cmd += ' AND'
    if not_like is not None:
        if 'where' not in _cmd.lower():
            _cmd += " WHERE "
        else:
            _cmd += ' AND'
        if isinstance(not_like, tuple):
            logger.debug(f'`not_like` is tuple: {not_like}')
            _cmd += f" {not_like[0]} NOT LIKE '%{not_like[1]}%'"
        elif isinstance(not_like, list) and isinstance(not_like[0], tuple):
            logger.debug(f'`not_like` is tuple inside a list: {not_like}')
            for id in not_like:
                _cmd += f" {id[0]} NOT LIKE '%{id[1]}%'"
                if id != not_like[-1]:
                    _cmd += ' AND'
    if order_by is not None:
        _cmd += ' ORDER BY '
        _cmd += ', ' .join(f'{order[0]} {order[1]}' for order in order_by)
    if rowid_sort:
        if order_by is None:
            _cmd += ' ORDER BY rowid'
        if order_by is not None:
            _cmd += ', rowid'
    logger.debug(f'Using this query: {_cmd}')
    try:
        async with aiosqlite.connect(db_file) as db:
            db.row_factory = aiosqlite.Row
            out = await db.execute(_cmd)
            if single:
                out = await out.fetchone()
                if out is None:
                    return None
                else:
                    return dict(out)
            else:
                out = [dict(row) for row in await out.fetchall()]
                if as_settings_json:
                    out_dict = {}
                    for item in out:
                        out_dict[item['setting']] = item['value']
                    return out_dict
            logger.debug(f'Returning {len(out)} items from from db')
            return out
    except aiosqlite.OperationalError as e:
        logger.error(f'Error: {e}')
        return None


async def get_random_left_exclude_output(
    template_info_1, template_info_2, key: str = None,
    select: tuple = None
):
    '''
    Get output from the following query:

        SELECT `select`
        FROM `template_info_1[table_name] A`
        LEFT JOIN `template_info_2[table_name]` B
        ON A.`key` = B.`key`
        WHERE B.`key` IS NULL
        ORDER BY RAND()
        LIMIT 1

    Note: `select` will only get values from `template_info_1`

    Returns
    ------------
    tuple
        ()
    '''
    db_file = template_info_1['db_file']
    table_name1 = template_info_1['name']
    table_name2 = template_info_2['name']
    _cmd = 'SELECT '
    if select is None:
        _cmd += '*'
    elif isinstance(select, tuple) and\
            len(select) > 1:
        _cmd += ', '.join(f'A.{field}' for field in select)
    elif isinstance(select, str):
        _cmd += select
    _cmd += f' FROM {table_name1} A'
    _cmd += f' LEFT JOIN {table_name2} B ON'
    _cmd += f' A.{key} = B.{key}'
    _cmd += f' WHERE B.{key} IS NULL'
    _cmd += ' ORDER BY RANDOM()'
    _cmd += ' LIMIT 1'
    logger.debug(f'Using this query: {_cmd}')
    try:
        async with aiosqlite.connect(db_file) as db:
            out = await db.execute(_cmd)
            out = await out.fetchall()
            return out
    except aiosqlite.OperationalError:
        return None


async def get_combined_output(
    template_info_1, template_info_2, key: str = None,
    select: list = None, where: list = None, group_by: str = None,
    order_by: list = None
):
    '''
    Get output from the following query:

        SELECT `select`
        FROM `template_info_1[table_name] A`
        INNER JOIN `template_info_2[table_name]` B
        ON A.`key` = B.`key`
        WHERE `where[0]` = `where[1]`
        GROUP BY `group_by`
        ORDER BY `order_by` (tuples in list)
    '''
    db_file = template_info_1['db_file']
    table_name1 = template_info_1['name']
    table_name2 = template_info_2['name']
    logger.debug('Getting combined info from `{}` and `{}`'.format(
        table_name1, table_name2
    ))
    _cmd = 'SELECT '
    if select is None or len(select) == 0:
        _cmd += '*'
    elif isinstance(select, list) and\
            len(select) > 1:
        _cmd += ', '.join(f'{field}' for field in select)
    elif isinstance(select, str):
        _cmd += select
    if group_by:
        _cmd += ', COUNT(*)'
    _cmd += f' FROM {table_name1} A'
    _cmd += f' INNER JOIN {table_name2} B ON'
    _cmd += f' A.{key} = B.{key}'
    if where:
        if isinstance(where, tuple):
            _cmd += f" WHERE {where[0]} = '{where[1]}'"
        elif isinstance(where, list):
            _cmd += " WHERE "
            for item in where:
                _cmd += f"{item[0]} = '{item[1]}'"
                if item != where[-1]:
                    _cmd += ' AND '
    if group_by:
        _cmd += f" GROUP BY {group_by}"
    if order_by:
        _cmd += ' ORDER BY '
        _cmd += ', ' .join(f'{order[0]} {order[1]}' for order in order_by)
    logger.debug(f'Using this query: {_cmd}')
    try:
        async with aiosqlite.connect(db_file) as db:
            db.row_factory = aiosqlite.Row
            out = await db.execute(_cmd)
            out = [dict(row) for row in await out.fetchall()]
            return out
    except aiosqlite.OperationalError:
        return None


async def empty_table(template_info):
    db_file = template_info['db_file']
    table_name = template_info['name']
    _cmd = f'DELETE FROM {table_name};'
    logger.debug(f'Using this query: {_cmd}')
    if args.not_write_database:
        logger.debug('`not_write_database` activated')
    elif not args.not_write_database:
        try:
            async with aiosqlite.connect(db_file) as db:
                out = await db.execute(_cmd)
                await db.commit()
                logger.debug(
                    'Changed {} rows'.format(
                        db.total_changes
                    )
                )
                return out
        except aiosqlite.OperationalError as e:
            logger.error(f'Error: {e}')
            return None


async def get_one_random_output(
    template_info, fields_out: tuple = None
):
    '''
    Get output from the following query:

        SELECT `fields_out`
        FROM `template_info[table_name]`
        ORDER BY RAND()
        LIMIT 1
    '''
    db_file = template_info['db_file']
    table_name1 = template_info['name']
    _cmd = 'SELECT '
    if fields_out is None:
        _cmd += '*'
    elif isinstance(fields_out, tuple) and\
            len(fields_out) > 1:
        _cmd += ', '.join(f'A.{field}' for field in fields_out)
    elif isinstance(fields_out, str):
        _cmd += fields_out
    _cmd += f' FROM {table_name1} A'
    _cmd += ' ORDER BY RANDOM()'
    _cmd += ' LIMIT 1'
    logger.debug(f'Using this query: {_cmd}')
    try:
        async with aiosqlite.connect(db_file) as db:
            out = await db.execute(_cmd)
            out = await out.fetchall()
            return out
    except aiosqlite.OperationalError:
        return None


async def get_output_by_rowid(
    template_info, rowid: str = None, fields_out: tuple = None
):
    '''
    Get a unique output from the following query:

        SELECT * / `fields_out`
        FROM `template_info[table_name]`
        WHERE rowid = `rowid`
    '''
    db_file = template_info['db_file']
    table_name = template_info['name']
    _cmd = 'SELECT '
    if fields_out is None:
        _cmd += 'rowid, *'
    elif isinstance(fields_out, tuple) and\
            len(fields_out) > 1:
        _cmd += ', '.join(f'A.{field}' for field in fields_out)
    elif isinstance(fields_out, str):
        _cmd += fields_out
    _cmd += f' FROM {table_name}'
    _cmd += f" WHERE rowid = {rowid}"
    _cmd += " ORDER BY rowid"
    logger.debug(f'Using this query: {_cmd}')
    try:
        async with aiosqlite.connect(db_file) as db:
            db.row_factory = aiosqlite.Row
            out = await db.execute(_cmd)
            out = [dict(row) for row in await out.fetchall()]
            return out
    except aiosqlite.OperationalError:
        return None


async def get_row_ids(template_info, sort=False):
    db_file = template_info['db_file']
    table_name = template_info['name']
    _cmd = f'SELECT rowid FROM {table_name}'
    if sort:
        _cmd += ' ORDER BY rowid'
    logger.debug(f'Using this query: {_cmd}')
    try:
        async with aiosqlite.connect(db_file) as db:
            out = await db.execute(_cmd)
            out = await out.fetchall()
            return [id[0] for id in out]
            return out
    except aiosqlite.OperationalError:
        return None


async def del_row_id(template_info, numbers):
    db_file = template_info['db_file']
    table_name = template_info['name']
    _cmd = f'DELETE FROM {table_name} WHERE rowid '
    if isinstance(numbers, list):
        _cmd += 'IN ('
        _cmd += ', '.join(str(number) for number in numbers)
        _cmd += ')'
    elif isinstance(numbers, (int, str)):
        _cmd += f'= {numbers}'
    else:
        logger.error(f'Could not find rowid for {numbers}')
        return None
    logger.debug(f'Using this query: {_cmd}')
    if args.not_write_database:
        logger.debug('`not_write_database` activated')
    elif not args.not_write_database:
        try:
            async with aiosqlite.connect(db_file) as db:
                await db.execute(_cmd)
                await db.commit()
        except aiosqlite.OperationalError:
            return None


async def del_row_ids(template_info, numbers=None):
    db_file = template_info['db_file']
    table_name = template_info['name']
    _cmd = f'DELETE FROM {table_name} WHERE rowid IN ('
    _cmd += ', '.join(str(number) for number in numbers)
    _cmd += ')'
    logger.debug(f'Using this query: {_cmd}')
    if args.not_write_database:
        logger.debug('`not_write_database` activated')
    elif not args.not_write_database:
        try:
            async with aiosqlite.connect(db_file) as db:
                await db.execute(_cmd)
                await db.commit()
        except aiosqlite.OperationalError:
            return None


async def del_row_by_OR_filters(
        template_info, where=None
):
    '''
    Delete using the following query:

        DELETE FROM `template_info[table_name]`
        WHERE `where[0]` = `where[1]`

    Additional WHEREs uses OR
    '''
    db_file = template_info['db_file']
    table_name = template_info['name']
    _cmd = f'DELETE FROM {table_name} '
    if isinstance(where, tuple):
        _cmd += f" WHERE {where[0]} = '{where[1]}'"
    elif isinstance(where, list):
        _cmd += " WHERE "
        for id in where:
            _cmd += f"{id[0]} = '{id[1]}'"
            if id != where[-1]:
                _cmd += ' OR '
    logger.debug(f'Using this query: {_cmd}')
    if args.not_write_database:
        logger.debug('`not_write_database` activated')
    elif not args.not_write_database:
        try:
            async with aiosqlite.connect(db_file) as db:
                await db.execute(_cmd)
                await db.commit()
            logger.debug('Done and commited!')
        except aiosqlite.OperationalError as e:
            logger.error(f'Error: {e}')
            return None


async def del_row_by_AND_filter(
        template_info, where: list = None
):
    '''
    Delete using the following query:

        DELETE FROM `template_info[table_name]`
        WHERE
            `where[0]` = `where[1]`

    Additional WHEREs uses AND
    '''
    db_file = template_info['db_file']
    table_name = template_info['name']
    _cmd = f'DELETE FROM {table_name}'
    if isinstance(where[0], str):
        _cmd += f" WHERE {where[0]} = '{where[1]}'"
    elif isinstance(where, (list, tuple)):
        _cmd += " WHERE "
        for id in where:
            logger.debug(
                f'`id` is {type(id)}: {id}'
            )
            _cmd += f"{id[0]} = '{id[1]}'"
            if id != where[-1]:
                _cmd += ' AND '
    logger.debug(f'Using this query: {_cmd}')
    if args.not_write_database:
        logger.debug('`not_write_database` activated')
    elif not args.not_write_database:
        try:
            async with aiosqlite.connect(db_file) as db:
                await db.execute(_cmd)
                await db.commit()
            logger.debug('Done and commited!')
            return True
        except aiosqlite.OperationalError as e:
            logger.error(f'Error: {e}')
            return None


async def calculate_average_rating_from_db(
    show_uuid, episode_uuid, template_info
):
    all_ratings = await get_output(
        template_info=template_info,
        where=[
            ('show_uuid', show_uuid),
            ('episode_uuid', episode_uuid),
        ],
        select=('rating')
    )
    if len(all_ratings) <= 0:
        logger.debug(
            f'No ratings found for show_uuid: {show_uuid}, '
            f'episode_uuid: {episode_uuid}'
        )
        return None
    ratings = [int(rating['rating']) for rating in all_ratings]
    return sum(ratings) / len(ratings)
