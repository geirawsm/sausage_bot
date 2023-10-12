#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import aiosqlite

from sausage_bot.util import envs, file_io
from sausage_bot.util.log import log


async def prep_table(table_temp):
    log.log_more(f'Got `table_temp``: {table_temp}')
    table_name = table_temp['name']
    item_list = table_temp['items']
    _cmd = '''CREATE TABLE IF NOT EXISTS {} ('''.format(table_name)
    _cmd += ', '.join(item for item in item_list)
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


async def db_insert_many_all(
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
    log.log_more(f'Got `db_file``: {db_file}')
    log.log_more(f'Got `table_name``: {table_name}')
    log.log_more(f'Got `inserts``: {inserts}')
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


async def db_insert_many_some(
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
    log.log_more(f'Got `db_file``: {db_file}')
    log.log_more(f'Got `table_name``: {table_name}')
    log.log_more(f'Got `rows``: {rows} {type(rows)} {len(rows)}')
    log.log_more(f'Got `inserts``: {inserts} {type(inserts)} {len(inserts)}')
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
    log.db(f'Using this query: {_cmd}')
    async with aiosqlite.connect(db_file) as db:
        await db.executemany(_cmd, inserts)
        await db.commit()
        log.debug(
            'Changed {} rows'.format(
                db.total_changes
            )
        )


async def db_update_fields(template_info, ids=None, updates: list = None):
    '''
    Update a table with listed tuples in `updates` where you can
    find the specific `ids`

    Equals to this SQl command:
        UPDATE employees
        SET city = 'Toronto',
            state = 'ON',
            postalcode = 'M5P 2N7'
        WHERE
            employeeid = 4
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
        order_by: list = None
):
    '''
    Get output from a SELECT query from a specified `table_name`, with
    WHERE-filtering the `ids` and ORDER BY `order_by` (if given).

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

    Returns
    ------------
    int or float
        Expected results.
    '''
    db_file = envs.DB_DIR / template_info['db_file']
    table_name = template_info['name']
    _cmd = 'SELECT '
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
