#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import aiosqlite

from sausage_bot.util import envs, file_io
from sausage_bot.util.log import log


async def prep_table(table_temp):
    log.log_more(f'Got `table_temp`: {table_temp}')
    table_name = table_temp['name']
    item_list = table_temp['items']
    _cmd = '''CREATE TABLE IF NOT EXISTS {} ('''.format(table_name)
    _cmd += ', '.join(item for item in item_list)
    if 'primary' in table_temp and\
            table_temp['primary'] is not None:
        _cmd += ', PRIMARY KEY({}'.format(
            table_temp['primary']
        )
        if 'autoincrement' in table_temp and\
                table_temp['autoincrement'] is True:
            _cmd += ' AUTOINCREMENT'
        _cmd += ')'
    _cmd += ');'
    log.db(f'Using this query: {_cmd}')
    file_io.ensure_folder(envs.DB_DIR)
    async with aiosqlite.connect(
        envs.DB_DIR / table_temp['db_file']
    ) as db:
        await db.execute(_cmd)
        log.db(
            'Changed {} rows'.format(
                db.total_changes
            )
        )


async def insert_many_all(
        template_info,
        inserts=None
):
    '''
    Insert info to all columns in a sqlite row

    Parameters
    ------------
    template_info: dict
        dict info about the table from envs file
    inserts: list(tuple)
        A list with tuples for reach row
    '''
    db_file = envs.DB_DIR / template_info['db_file']
    table_name = template_info['name']
    log.log_more(f'Got `db_file`: {db_file}')
    log.log_more(f'Got `table_name`: {table_name}')
    log.log_more(f'Got `inserts`: {inserts}')
    _cmd = f'INSERT INTO {table_name} VALUES('
    _cmd += ', '.join('?'*len(inserts[0]))
    _cmd += ')'
    log.db(f'Using this query: {_cmd}')
    async with aiosqlite.connect(db_file) as db:
        await db.executemany(_cmd, inserts)
        await db.commit()
        log.db(
            'Changed {} rows'.format(
                db.total_changes
            )
        )


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
    db_file = envs.DB_DIR / template_info['db_file']
    table_name = template_info['name']
    if db_file is None:
        log.log('`db_file` is None')
        return None
    if table_name is None:
        log.log('`table_name` is None')
        return None
    log.log_more(f'Got `db_file`: {db_file}')
    log.log_more(f'Got `table_name`: {table_name}')
    log.log_more(f'Got `rows`: {rows} {type(rows)} {len(rows)}')
    log.log_more(f'Got `inserts`: {inserts} {type(inserts)} {len(inserts)}')
    input_singles = False
    input_multiples = False
    if isinstance(rows, str) and len(inserts) == 1:
        log.log(
            f'Only one rows and inserts, which is OK'
        )
        input_singles = True
    else:
        if len(rows) != len(inserts[0]):
            log.log(
                f'Length of rows and inserts does not match ({len(rows)} vs '
                f'{len(inserts[0])})'
            )
            return None
        else:
            input_multiples = True
    _cmd = f'INSERT INTO {table_name} ('
    if input_singles:
        _cmd += rows
    elif input_multiples:
        _cmd += ', '.join(row for row in rows)
    _cmd += ') VALUES ('
    if input_singles:
        _cmd += '?'
    elif input_multiples:
        _cmd += ', '.join('?'*len(inserts[0]))
    _cmd += ')'
    log.db(f'Using this query: {_cmd} {inserts}')
    async with aiosqlite.connect(db_file) as db:
        if len(inserts) >= 1:
            await db.executemany(_cmd, inserts)
            db_last_row = None
        else:
            await db.execute(_cmd, inserts)
            db_last_row = None
        await db.commit()
        log.debug(
            'Changed {} rows'.format(
                db.total_changes
            )
        )
    return db_last_row


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
    db_file = envs.DB_DIR / template_info['db_file']
    table_name = template_info['name']
    if db_file is None:
        log.log('`db_file` is None')
        return None
    if table_name is None:
        log.log('`table_name` is None')
        return None
    _cmd = f'''INSERT INTO {table_name} ({field_name})
              VALUES(?)'''
    log.db(f'Using this query: {_cmd}')
    async with aiosqlite.connect(db_file) as db:
        await db.execute(_cmd, insert)
        await db.commit()
        log.debug(
            'Changed {} rows'.format(
                db.total_changes
            )
        )
        last_row = db.lastinsertrow
    return last_row


async def update_fields(template_info, ids=None, updates: list = None):
    '''
    Update a table with listed tuples in `updates` where you can
    find the specific `ids`

    Equals to this SQl command:
        UPDATE `template_info[table_name]`
        SET `updates[0]` = `updates[1]`,
            `updates[0]` = `updates[1]`,
            `updates[0]` = `updates[1]`
        WHERE
            `id[0]` = `id[1]`
    Parameters
    ------------
    template_info: dict
        dict info about the table from envs file
    ids: tuple/list of tuples
        Single or multiple things to look for to identify correct rows
    updates: list(tuples)
        A list of tuples with a field, value combination
    '''
    db_file = envs.DB_DIR / template_info['db_file']
    table_name = template_info['name']
    if table_name is None:
        log.log('Missing table_name')
        return
    if ids is None:
        log.log('Missing ids')
        return
    if updates is None:
        log.log('Missing updates')
        return
    _cmd = f'UPDATE {table_name} SET '
    for update in updates:
        _cmd += "{} = '{}'".format(update[0], update[1])
        if update != updates[-1]:
            _cmd += ', '
    if isinstance(ids, tuple):
        _cmd += f" WHERE {ids[0]} = '{ids[1]}'"
    elif isinstance(ids, list):
        _cmd += " WHERE "
        for id in ids:
            _cmd += f"{id[0]} = '{id[1]}'"
            if id != ids[-1]:
                _cmd += ' AND '
    log.db(f'Using this query: {_cmd}')
    async with aiosqlite.connect(db_file) as db:
        await db.execute(_cmd)
        await db.commit()


async def get_output(
    template_info, ids: tuple = None, fields_out: tuple = None,
    order_by: list = None, get_row_ids: bool = False
):
    '''
    Get output from a SELECT query from a specified
    `template_info[table_name]`, with WHERE-filtering the `ids` and
    ORDER BY `order_by` (if given).

    Parameters
    ------------
    template_info: dict
        dict info about the table from envs file
    ids: tuple
        Single or multiple things to look for to identify correct rows
    fields_out: tuple
        What fields to get from the db file
    order_by: list(tuples)
        What fields to order by and if ASC or DESC
    get_row_ids: bool
        Also get rowid
    '''
    db_file = envs.DB_DIR / template_info['db_file']
    table_name = template_info['name']
    _cmd = 'SELECT '
    if get_row_ids:
        _cmd += 'rowid, '
    if fields_out is None:
        _cmd += '*'
    elif isinstance(fields_out, tuple) and\
            len(fields_out) > 1:
        _cmd += ', '.join(field for field in fields_out)
    elif isinstance(fields_out, str):
        _cmd += fields_out
    _cmd += f' FROM {table_name}'
    if ids is not None and len(ids) > 0:
        _cmd += ' WHERE '
        for id in ids:
            _cmd += f"{id[0]} = '{id[1]}'"
    if order_by is not None:
        _cmd += ' ORDER BY '
        _cmd += ', ' .join(f'{order[0]} {order[1]}' for order in order_by)
    log.db(f'Using this query: {_cmd}')
    async with aiosqlite.connect(db_file) as db:
        out = await db.execute(_cmd)
        out = await out.fetchall()
        return out


async def get_random_left_exclude_output(
    template_info_1, template_info_2, key: str = None,
    fields_out: tuple = None
):
    '''
    Get output from the following query:

        SELECT `fields_out`
        FROM `template_info_1[table_name] A`
        LEFT JOIN `template_info_2[table_name]` B
        ON A.`key` = B.`key`
        WHERE B.`key` IS NULL
        ORDER BY RAND()
        LIMIT 1

    Note: `fields_out` will only get values from `template_info_1`

    Returns
    ------------
    tuple
        ()
    '''
    db_file = envs.DB_DIR / template_info_1['db_file']
    table_name1 = template_info_1['name']
    table_name2 = template_info_2['name']
    _cmd = 'SELECT '
    if fields_out is None:
        _cmd += '*'
    elif isinstance(fields_out, tuple) and\
            len(fields_out) > 1:
        _cmd += ', '.join(f'A.{field}' for field in fields_out)
    elif isinstance(fields_out, str):
        _cmd += fields_out
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


async def empty_table(template_info):
    db_file = envs.DB_DIR / template_info['db_file']
    table_name = template_info['name']
    _cmd = f'DELETE FROM {table_name};'
    log.db(f'Using this query: {_cmd}')
    async with aiosqlite.connect(db_file) as db:
        out = await db.execute(_cmd)
        await db.commit()
        log.debug(
            'Changed {} rows'.format(
                db.total_changes
            )
        )
        return out


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
    db_file = envs.DB_DIR / template_info['db_file']
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
    db_file = envs.DB_DIR / template_info['db_file']
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
    _cmd += f" ORDER BY rowid"
    log.db(f'Using this query: {_cmd}')
    try:
        async with aiosqlite.connect(db_file) as db:
            out = await db.execute(_cmd)
            out = await out.fetchall()
            return out
    except aiosqlite.OperationalError:
        return None


async def get_row_ids(template_info):
    db_file = envs.DB_DIR / template_info['db_file']
    table_name = template_info['name']
    _cmd = f'SELECT rowid FROM {table_name}'
    log.db(f'Using this query: {_cmd}')
    try:
        async with aiosqlite.connect(db_file) as db:
            out = await db.execute(_cmd)
            out = await out.fetchall()
            return out
    except aiosqlite.OperationalError:
        return None


async def del_row_id(template_info, number):
    db_file = envs.DB_DIR / template_info['db_file']
    table_name = template_info['name']
    _cmd = f'DELETE FROM {table_name} WHERE rowid = {number}'
    log.db(f'Using this query: {_cmd}')
    try:
        async with aiosqlite.connect(db_file) as db:
            await db.execute(_cmd)
            await db.commit()
    except aiosqlite.OperationalError:
        return None
