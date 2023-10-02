#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import aiosqlite

from sausage_bot.util import envs, file_io
from sausage_bot.util.log import log


async def prep_table(db_file, table_temp):
    log.log_more(f'Got `db_file``: {db_file}')
    log.log_more(f'Got `table_temp``: {table_temp}')
    table_name = table_temp['name']
    item_list = table_temp['items']
    _cmd = '''CREATE TABLE IF NOT EXISTS {} ('''.format(table_name)
    _cmd += ', '.join(item for item in item_list)
    _cmd += ');'
    log.db(f'Using this query: {_cmd}')
    file_io.ensure_folder(envs.DB_DIR)
    async with aiosqlite.connect(envs.DB_DIR / db_file) as db:
        await db.execute(_cmd)
        log.db(
            'Changed {} rows'.format(
                db.total_changes
            )
        )


async def db_insert_many_all(
        db_file,
        table_name: str = None,
        inserts=None
):
    '''
    Insert info to all columns in a sqlite row

    Parameters
    ------------
    table_name: str
        The names of the table to add to (default: None)
    inserts: list(tuple)
        A list with tuples for reach row
    '''
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
        db_file: str = None,
        table_name: str = None,
        rows: tuple = None,
        inserts: list = None
):
    '''
    Insert info in specific columns in a sqlite row

    Parameters
    ------------
    db_file: str
        Name of the db file (default: None)
    table_name: str
        Name of the table to add to (default: None)
    rows: tuple
        A tuple with the row names to add each inserts tuple into
    inserts: list(tuples)
        A list with tuples for reach row
    '''
    if db_file is None:
        log.log('`db_file` is None')
        return None
    if table_name is None:
        log.log('`table_name` is None')
        return None
    log.log_more(f'Got `db_file``: {db_file}')
    log.log_more(f'Got `table_name``: {table_name}')
    log.log_more(f'Got `rows``: {rows}')
    log.log_more(f'Got `inserts``: {inserts}')
    if len(rows) != len(inserts[0]):
        log.log(
            f'Lenght of rows and inserts does not match ({len(rows)} vs '
            f'len(inserts[0]))'
        )
        return None
    _cmd = f'INSERT INTO {table_name} ('
    _cmd += ', '.join(row for row in rows)
    _cmd += ') VALUES ('
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


async def db_update_fields(
        db_file: str = None, table_name: str = None,
        ids=None, updates: list = None
):
    '''
    Update a `table_name` with listed tuples in `updates` where you can
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
    db_file: str
        Name of the db file (default: None)
    table_name: str
        Table name in sqlite (default: None)
    ids: tuple/list of tuples
        Single or multiple things to look for to identify correct rows
    updates: list(tuples)
        A list of tuples with a field, value combination
    '''
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
        db_file: str = None, table_name: str = None,
        ids: tuple = None, fields_out: tuple = None, order_by: list = None
):
    '''
    Get output from a SELECT query from a specified `table_name`, with
    WHERE-filtering the `ids` and ORDER BY `order_by` (if given).

    Parameters
    ------------
    db_file: str
        The names of the role to add (default: None)
    table_name: str
        Table name in sqlite (default: None)
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
    _cmd = 'SELECT '
    if fields_out is None:
        _cmd += '*'
    elif isinstance(fields_out, tuple):
        _cmd += ', '.join(field for field in fields_out)
    _cmd += f' FROM {table_name}'
    if ids is not None:
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
