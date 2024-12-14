#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import aiosqlite
from uuid import uuid4
import re
from pathlib import Path

from sausage_bot.util import envs, file_io, discord_commands
from sausage_bot.util.args import args
from sausage_bot.util.log import log
from .datetime_handling import get_dt


def db_exist(db_file_in):
    file_io.ensure_folder(envs.DB_DIR)
    db_path = str(db_file_in['db_file'])
    try:
        file_io.file_exist(db_path)
        return True
    except Exception as e:
        log.error(f'Could not find database {db_path}: {e}')
        return False


async def table_exist(template_info):
    db_file = template_info['db_file']
    log.log(f'Opening `{db_file}`')
    table_name = template_info['name']
    async with aiosqlite.connect(db_file) as db:
        out = await db.execute(f'PRAGMA table_info({table_name})')
        out = await out.fetchall()
    if len(out) > 0:
        return True
    else:
        return False


async def prep_table(
            table_in, inserts: list = None
        ):
    log.verbose(f'Got `table_in`: {table_in}')
    db_file = table_in['db_file']
    file_io.ensure_folder(Path(db_file).parent)
    table_name = table_in['name']
    item_list = table_in['items']
    _cmd = '''CREATE TABLE IF NOT EXISTS {} ('''.format(table_name)
    _cmd += ', '.join(item for item in item_list)
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
    log.db(f'Using this query: {_cmd}')
    if args.not_write_database:
        log.verbose('`not_write_database` activated')
    elif not args.not_write_database:
        try:
            async with aiosqlite.connect(db_file) as db:
                await db.execute(_cmd)
                log.db(f'Changed {db.total_changes} rows')
        except aiosqlite.OperationalError as e:
            log.error(f'Error: {e}')
            return None
    delete_json_ok = False
    if inserts:
        db_len = len(await get_row_ids(table_in))
        if db_len <= 0:
            log.verbose(f'Inserting old info into db file ({table_name})')
            # Make the returned status from `insert_many_all` decide
            # whether the json file can be deleted or not
            delete_json_ok = await insert_many_all(
                template_info=table_in,
                inserts=inserts
            )
        elif db_len == len(inserts):
            log.log(
                'Length of table and inserts are the same '
                '({} vs {}), will not import to {}'.format(
                    db_len, len(inserts), table_name
                )
            )
            delete_json_ok = True
        else:
            log.verbose(
                'Inserts given, but db file already has input. '
                'This should be looked into, so messaging the bot-dump'
            )
            await discord_commands.log_to_bot_channel(
                content_in='Want to insert info from old json into '
                f'{table_name}, but something is wrong'
                '({} vs {})'.format(
                    db_len, len(inserts)
                )
            )
            delete_json_ok = False
    return delete_json_ok


async def add_missing_db_setup(
        template_info, dict_in
):
    log.verbose(f'Received `template_info`', pretty=template_info)
    db_file = template_info['db_file']
    table_name = template_info['name']
    log.debug(f'Checking `{table_name}` in `{db_file}`')
    if 'inserts' in template_info:
        log.debug('Got `inserts`')
        inserts = template_info['inserts']
    else:
        log.debug('No `inserts` received')
        inserts = []
    await prep_table(
        table_in=template_info, inserts=inserts
    )
    if table_name not in dict_in:
        dict_in[table_name] = []
    wanted_cols = template_info['items']
    table_info = f'PRAGMA table_info({table_name})'
    async with aiosqlite.connect(db_file) as db:
        db_out = await db.execute(table_info)
        existing_cols = await db_out.fetchall()
        row_ids = await db.execute(
            f'SELECT rowid FROM {table_name}'
        )
        row_ids = await row_ids.fetchall()
    _existing_cols = [col[1] for col in existing_cols]
    log.debug(f'_existing_cols: {_existing_cols}')
    for col_in in wanted_cols:
        item = col_in.split(' ')
        log.debug(f'Checking {item}')
        if item[0] not in _existing_cols:
            log.debug(f'Adding {item[0]}')
            dict_in[table_name].append(col_in)
    async with aiosqlite.connect(db_file) as db:
        for col in dict_in[table_name]:
            item = col.split(' ')
            log.debug(f'item: {item}')
            _cmd = f'ALTER TABLE {table_name} ADD COLUMN {item[0]};'
            log.db(f'Using this query: {_cmd}')
            await db.execute(_cmd)
    # Add existing inserts in columns where they don't exist yet
    temp_inserts = []
    if len(inserts) > 0:
        log.debug('`inserts` has length')
        db_out = await get_output(
            template_info=template_info,
            select=('setting', 'value')
        )
        log.verbose(f'Got `db_out`: {db_out}')
        db_out = dict(db_out)
        log.verbose(f'Got `dict(db_out)`: {db_out}')
        for insert in inserts:
            if insert[0] not in db_out:
                temp_inserts.append(insert)
            elif insert[0] in db_out and db_out[insert[0]] is None:
                temp_inserts.append(insert)
        log.debug(f'temp_inserts: {temp_inserts}')
    if len(temp_inserts) > 0:
        await insert_many_all(template_info, temp_inserts)
    return dict_in


async def find_cols(
        template_info, cols_find: list = None
):
    db_file = template_info['db_file']
    table_name = template_info['name']
    log.verbose(f'Got `db_file`: {db_file}')
    log.verbose(f'Got `table_name`: {table_name}')
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
    log.verbose(f'Got `db_file`: {db_file}')
    log.verbose(f'Got `table_name`: {table_name}')
    if args.not_write_database:
        log.verbose('`not_write_database` activated')
    else:
        _cmd = 'ALTER TABLE {} DROP COLUMN {};'
        try:
            async with aiosqlite.connect(db_file) as db:
                for col_in in cols_remove:
                    __cmd = _cmd.format(table_name, col_in)
                    log.db(f'Using this query: {__cmd}')
                    await db.execute(__cmd)
                await db.commit()
        except aiosqlite.OperationalError as e:
            log.error(f'Error: {e}')
            return
    return


async def db_fix_old_hide_roles_status():
    old_hide_roles = await get_output(
        template_info=envs.stats_db_settings_schema,
        get_row_ids=True,
        where=('setting', 'hide_roles')
    )
    if len(old_hide_roles) > 0:
        log.verbose('Moving hide_roles from settings tale to hide_roles')
        old_hide_roles = await get_output(
            template_info=envs.stats_db_settings_schema,
            get_row_ids=True,
            where=('setting', 'hide_roles'),
            select=('value')
        )
        row_ids = [rowid[0] for rowid in old_hide_roles]
        values = [[rowid[1]] for rowid in old_hide_roles]
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
        log.verbose('Renaming stats_msg to stats_msg_id')
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
        log.verbose('Removing columns: {}'.format(
            ', '.join(old_value_check_or_help)
        ))
        await remove_cols(
            template_info=envs.stats_db_settings_schema,
            cols_remove=old_value_check_or_help
        )


async def db_replace_numeral_bool_with_bool():
    old_value_numeral_instead_of_bool = await get_output(
        template_info=envs.stats_db_settings_schema
    )
    new_bool_status = old_value_numeral_instead_of_bool.copy()
    log.verbose(new_bool_status)
    type_checking = envs.stats_db_settings_schema['type_checking']
    for setting in new_bool_status:
        log.verbose(f'Checking type of {setting}')
        if type_checking[setting['setting']] == 'bool':
            pass
        if type(eval(setting['value'])) is \
            type(eval(type_checking[setting['setting']])):
            log.verbose('Removing...')
            new_bool_status.pop(new_bool_status.index(setting))
    log.verbose('`new_bool_status` after checking is ', pretty=new_bool_status)
    for setting in new_bool_status:
        print(
            'Checking {}: {}'.format(
                setting['setting'],
                type(eval(setting['value']))
            )
        )
        if type(eval(setting['value'])) is int:
            if setting['value'] == 0:
                setting['value'] = False
            elif setting['value'] == 1:
                setting['value'] = True
            else:
                setting['value'] = \
                    dict(envs.stats_db_settings_schema['inserts'])[setting['setting']]
        else:
            new_bool_status.pop(new_bool_status.index(setting))
    if len(new_bool_status) > 0:
        log.verbose(new_bool_status)
        log.verbose(
            'Length of `new_bool_status` is more than 0. Converting old '
            'value numeral to bool'
        )
        log.verbose(new_bool_status)
        for setting in new_bool_status:
            # TODO Denne fungerer ikke
            await update_fields(
                template_info=envs.stats_db_settings_schema,
                where=('setting', setting),
                updates=('value', new_bool_status)[setting]
            )


async def json_to_db_inserts(cog_name):
    '''
    This is a cleanup function to be used for converting from old json
    files to sqlite files
    #autodoc skip#
    '''
    log.log('Converting json to db')
    log.log(f'Processing `{cog_name}`')
    if cog_name == 'roles':
        settings_file = file_io.read_json(envs.roles_settings_file)
        settings_inserts = []
        msg_inserts = []
        reactions_inserts = []
        if len(settings_file) > 0:
            if 'unique_role' in settings_file:
                log.verbose('Found unique role-settings')
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
                log.verbose(
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
        log.verbose(f'Got this for `dilemmas_inserts`:\n{dilemmas_inserts}')
        return dilemmas_inserts
    elif cog_name == 'quote':
        quote_file = file_io.read_json(envs.quote_file)
        quotes_inserts = []
        for quote in quote_file:
            quotes_inserts.append(
                (
                    str(uuid4()), quote_file[quote]['quote'],
                    get_dt(
                        format="ISO8601", dt=re.sub(
                            r'[\(\)]+', '',
                            quote_file[quote]['datetime']
                        )
                    )
                )
            )
        log.verbose(f'Got this for `quotes_inserts`:\n{quotes_inserts}')
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
            log.verbose(f'Got this for `stats_inserts`:\n{stats_inserts}')
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
                            files_in = _stats_in['files_in_codebase']
                        else:
                            files_in = 0
                        if 'lines_in_codebase' in _stats_in:
                            lines_in = _stats_in['lines_in_codebase']
                        else:
                            lines_in = 0
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
        log.debug('Got `rss_file`: {}'.format(str(rss_file)[0:100]))
        rss_logs_file = file_io.read_json(envs.rss_feeds_logs_file)
        log.debug('Got `rss_logs_file`: {}'.format(str(rss_logs_file)[0:100]))
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
                                str(get_dt(format='ISO8601'))
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
                            str(get_dt(format='ISO8601'))
                        )
                    )
        return {
            'feeds': yt_inserts,
            'filter': yt_filter_inserts,
            'logs': yt_logs_inserts
        }
    log.log('Converting done!')


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
    log.verbose(f'Got `db_file`: {db_file}')
    log.verbose(f'Got `table_name`: {table_name}')
    log.verbose(
        'Got `inserts`: {}'.format(
            str(inserts)[0:200]+'...' if len(str(inserts)) > 200 else inserts
        )
    )
    input_singles = False
    input_multiples = False
    _cmd = f'INSERT INTO {table_name} VALUES('
    log.debug(f'Got {len(inserts)} `inserts`')
    if isinstance(inserts[0], (list, tuple)):
        log.debug('Got multiple inserts')
        _cmd += ', '.join('?'*len(inserts[0]))
        input_multiples = True
    else:
        log.debug('Got single insert')
        _cmd += ', '.join('?'*len(inserts))
        input_singles = True
    _cmd += ')'
    log.db(f'Using this query: {_cmd}')
    if args.not_write_database:
        log.verbose('`not_write_database` activated')
    elif not args.not_write_database:
        try:
            async with aiosqlite.connect(db_file) as db:
                if input_singles:
                    await db.execute(_cmd, inserts)
                elif input_multiples:
                    await db.executemany(_cmd, inserts)
                await db.commit()
                log.db(
                    'Changed {} rows'.format(
                        db.total_changes
                    )
                )
            log.db('Done and commited!')
            return True
        except aiosqlite.OperationalError as e:
            log.error(f'Error: {e}')
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
        log.error('`db_file` is None')
        return None
    if table_name is None:
        log.error('`table_name` is None')
        return None
    log.verbose(f'Got `db_file`: {db_file}')
    log.verbose(f'Got `table_name`: {table_name}')
    log.verbose(f'Got `rows`: {rows} {type(rows)} {len(rows)}')
    log.verbose(
        f'Got `inserts`: {type(inserts)} {len(inserts)}', pretty=inserts
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
        _cmd += ', '.join('?'*len(inserts))
    elif input_multiples:
        _cmd += ', '.join('?'*len(inserts[0]))
    _cmd += ')'
    log.db(f'Using this query: {_cmd} {inserts}')
    if args.not_write_database:
        log.verbose('`not_write_database` activated')
    elif not args.not_write_database:
        if input_singles:
            inserts = [inserts]
        try:
            async with aiosqlite.connect(db_file) as db:
                await db.executemany(_cmd, inserts)
                await db.commit()
                log.debug(
                    'Changed {} rows'.format(
                        db.total_changes
                    )
                )
        except aiosqlite.OperationalError as e:
            log.error(f'Error: {e}')
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
        log.error('`db_file` is None')
        return None
    if table_name is None:
        log.error('`table_name` is None')
        return None
    _cmd = f'''INSERT INTO {table_name} ({field_name})
               VALUES(?)'''
    log.db(f'Using this query: {_cmd}')
    if args.not_write_database:
        log.verbose('`not_write_database` activated')
    elif not args.not_write_database:
        try:
            async with aiosqlite.connect(db_file) as db:
                await db.execute(_cmd, insert)
                await db.commit()
                log.debug(
                    'Changed {} rows'.format(
                        db.total_changes
                    )
                )
                last_row = db.lastinsertrow
            log.db('Done and commited!')
            return last_row
        except aiosqlite.OperationalError as e:
            log.error(f'Error: {e}')
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
        log.error('Missing table_name')
        return
    if updates is None:
        log.error('Missing updates')
        return
    _cmd = f'UPDATE {table_name} SET '
    if isinstance(updates, dict):
        for update in updates:
            log.verbose(f'Got `update`: {update}')
            _cmd += "{} = CASE".format(update)
            for _item in updates[update]:
                _cmd += " WHEN {} = '{}' THEN '{}'".format(
                    _item[0], _item[1], _item[2]
                )
            _cmd += ' ELSE {} END'.format(update)
            if update != list(updates)[-1]:
                _cmd += ', '
    elif isinstance(updates, (list, tuple)):
        if isinstance(updates[0], str):
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
    log.db(f'Using this query: {_cmd}')
    if args.not_write_database:
        log.verbose('`not_write_database` activated')
    elif not args.not_write_database:
        try:
            async with aiosqlite.connect(db_file) as db:
                await db.execute(_cmd)
                await db.commit()
            log.db('Done and commited!')
        except aiosqlite.OperationalError as e:
            log.error(f'Error: {e}')
            return None


async def get_output(
    template_info, where: tuple = None, like: tuple = None,
    not_like: tuple = None, select: tuple = None, order_by: list = None,
    get_row_ids: bool = False, rowid_sort: bool = False, single: bool = None
):
    '''
    Get output from a SELECT query from a specified
    `template_info[table_name]`, with WHERE-filtering the `where` and
    ORDER BY `order_by` (if given).

    Parameters
    ------------
    template_info: dict
        dict info about the table from envs file
    where: tuple
        Single or multiple things to look for to identify correct rows
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
    '''
    db_file = template_info['db_file']
    log.db(f'Opening `{db_file}`')
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
    log.debug(f'where: {where}')
    log.debug(f'like: {like}')
    log.debug(f'not_like: {not_like}')
    if where is not None:
        if 'where' not in _cmd.lower():
            _cmd += " WHERE"
        else:
            _cmd += ' AND'
        if isinstance(where, tuple):
            log.verbose(f'`where` is tuple: {where}')
            _cmd += f" LOWER({where[0]}) = LOWER('{where[1]}')"
        elif isinstance(where, list) and isinstance(where[0], tuple):
            log.verbose(f'`where` is tuple inside a list: {where}')
            for id in where:
                _cmd += f" LOWER({id[0]}) = LOWER('{id[1]}')"
                if id != where[-1]:
                    _cmd += ' AND'
    if like is not None:
        if 'where' not in _cmd.lower():
            _cmd += " WHERE"
        else:
            _cmd += ' AND'
        if isinstance(like, tuple):
            log.verbose(f'`like` is tuple: {like}')
            _cmd += f" {like[0]} LIKE '%{like[1]}%'"
        elif isinstance(like, list) and isinstance(like[0], tuple):
            log.verbose(f'`like` is tuple inside a list: {like}')
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
            log.verbose(f'`not_like` is tuple: {not_like}')
            _cmd += f" {not_like[0]} NOT LIKE '%{not_like[1]}%'"
        elif isinstance(not_like, list) and isinstance(not_like[0], tuple):
            log.verbose(f'`not_like` is tuple inside a list: {not_like}')
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
    log.db(f'Using this query: {_cmd}')
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
            log.verbose(f'Returning {len(out)} items from from db')
            return out
    except aiosqlite.OperationalError as e:
        log.error(f'Error: {e}')
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
    log.db(f'Using this query: {_cmd}')
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

    Note: `select` will only get values from `template_info_1`
    '''
    db_file = template_info_1['db_file']
    table_name1 = template_info_1['name']
    table_name2 = template_info_2['name']
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
    log.db(f'Using this query: {_cmd}')
    try:
        async with aiosqlite.connect(db_file) as db:
            out = await db.execute(_cmd)
            out = await out.fetchall()
            return out
    except aiosqlite.OperationalError:
        return None


async def empty_table(template_info):
    db_file = template_info['db_file']
    table_name = template_info['name']
    _cmd = f'DELETE FROM {table_name};'
    log.db(f'Using this query: {_cmd}')
    if args.not_write_database:
        log.verbose('`not_write_database` activated')
    elif not args.not_write_database:
        try:
            async with aiosqlite.connect(db_file) as db:
                out = await db.execute(_cmd)
                await db.commit()
                log.debug(
                    'Changed {} rows'.format(
                        db.total_changes
                    )
                )
                return out
        except aiosqlite.OperationalError as e:
            log.error(f'Error: {e}')
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
    log.db(f'Using this query: {_cmd}')
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
    log.db(f'Using this query: {_cmd}')
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
    log.db(f'Using this query: {_cmd}')
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
        log.error(f'Could not find rowid for {numbers}')
        return None
    log.db(f'Using this query: {_cmd}')
    if args.not_write_database:
        log.verbose('`not_write_database` activated')
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
    log.db(f'Using this query: {_cmd}')
    if args.not_write_database:
        log.verbose('`not_write_database` activated')
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
    log.db(f'Using this query: {_cmd}')
    if args.not_write_database:
        log.verbose('`not_write_database` activated')
    elif not args.not_write_database:
        try:
            async with aiosqlite.connect(db_file) as db:
                await db.execute(_cmd)
                await db.commit()
            log.db('Done and commited!')
        except aiosqlite.OperationalError as e:
            log.error(f'Error: {e}')
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
            log.debug(
                f'`id` is {type(id)}: {id}'
            )
            _cmd += f"{id[0]} = '{id[1]}'"
            if id != where[-1]:
                _cmd += ' AND '
    log.db(f'Using this query: {_cmd}')
    if args.not_write_database:
        log.verbose('`not_write_database` activated')
    elif not args.not_write_database:
        try:
            async with aiosqlite.connect(db_file) as db:
                await db.execute(_cmd)
                await db.commit()
            log.db('Done and commited!')
            return True
        except aiosqlite.OperationalError as e:
            log.error(f'Error: {e}')
            return None
