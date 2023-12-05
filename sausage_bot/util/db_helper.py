#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import aiosqlite

from sausage_bot.util import envs, file_io
from sausage_bot.util.log import log


async def prep_table(table_temp):
    log.verbose(f'Got `table_temp`: {table_temp}')
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
    try:
        async with aiosqlite.connect(
            envs.DB_DIR / table_temp['db_file']
        ) as db:
            await db.execute(_cmd)
            log.db(
                'Changed {} rows'.format(
                    db.total_changes
                )
            )
    except aiosqlite.OperationalError as e:
        log.db(f'Error: {e}')
        return None


async def insert_many_all(
        template_info,
        inserts: tuple = None
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
    log.verbose(f'Got `db_file`: {db_file}')
    log.verbose(f'Got `table_name`: {table_name}')
    log.verbose(f'Got `inserts`: {inserts}')
    _cmd = f'INSERT INTO {table_name} VALUES('
    _cmd += ', '.join('?'*len(inserts[0]))
    _cmd += ')'
    log.db(f'Using this query: {_cmd}')
    try:
        async with aiosqlite.connect(db_file) as db:
            await db.executemany(_cmd, inserts)
            await db.commit()
            log.db(
                'Changed {} rows'.format(
                    db.total_changes
                )
            )
        log.db(f'Done and commited!')
    except aiosqlite.OperationalError as e:
        log.db(f'Error: {e}')
        return None


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
    log.verbose(f'Got `db_file`: {db_file}')
    log.verbose(f'Got `table_name`: {table_name}')
    log.verbose(f'Got `rows`: {rows} {type(rows)} {len(rows)}')
    log.verbose(f'Got `inserts`: {inserts} {type(inserts)} {len(inserts)}')
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
    try:
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
    except aiosqlite.OperationalError as e:
        log.db(f'Error: {e}')
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
        return last_row
        log.db(f'Done and commited!')
    except aiosqlite.OperationalError as e:
        log.db(f'Error: {e}')
        return None

async def update_fields(template_info, where=None, updates: list = None):
    '''
    Update a table with listed tuples in `updates` where you can
    find the specific `where`

    Equals to this SQl command:
        UPDATE `template_info[table_name]`
        SET `updates[0]` = `updates[1]`,
            `updates[0]` = `updates[1]`,
            `updates[0]` = `updates[1]`
        WHERE
            `where[0]` = `where[1]`
    Parameters
    ------------
    template_info: dict
        dict info about the table from envs file
    where: tuple/list of tuples
        Single or multiple things to look for to identify correct rows
    updates: list(tuples)
        A list of tuples with a field, value combination
    '''
    db_file = envs.DB_DIR / template_info['db_file']
    table_name = template_info['name']
    if table_name is None:
        log.log('Missing table_name')
        return
    if where is None:
        log.log('Missing where')
        return
    if updates is None:
        log.log('Missing updates')
        return
    _cmd = f'UPDATE {table_name} SET '
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
    try:
        async with aiosqlite.connect(db_file) as db:
            await db.execute(_cmd)
            await db.commit()
        log.db(f'Done and commited!')
    except aiosqlite.OperationalError as e:
        log.db(f'Error: {e}')
        return None


async def get_output(
    template_info, where: tuple = None, select: tuple = None,
    order_by: list = None, get_row_ids: bool = False, single: bool = None
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
    select: tuple
        What fields to get from the db file
    order_by: list(tuples)
        What fields to order by and if ordered by ASC or DESC
    get_row_ids: bool
        Also get rowid
    '''
    db_file = envs.DB_DIR / template_info['db_file']
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
    if isinstance(where, tuple):
        log.verbose(f'`where` is tuple: {where}')
        _cmd += f" WHERE {where[0]} = '{where[1]}'"
    elif isinstance(where, list) and isinstance(where[0], tuple):
        log.verbose(f'`where` is tuple inside a list: {where}')
        _cmd += " WHERE "
        for id in where:
            _cmd += f"{id[0]} = '{id[1]}'"
            if id != where[-1]:
                _cmd += ' AND '
    if order_by is not None:
        _cmd += ' ORDER BY '
        _cmd += ', ' .join(f'{order[0]} {order[1]}' for order in order_by)
    log.db(f'Using this query: {_cmd}')
    try:
        async with aiosqlite.connect(db_file) as db:
            out = await db.execute(_cmd)
            if single:
                out = await out.fetchone()
            else:
                out = await out.fetchall()
            return out
    except aiosqlite.OperationalError as e:
        log.db(f'Error: {e}')
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
    db_file = envs.DB_DIR / template_info_1['db_file']
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
    db_file = envs.DB_DIR / template_info_1['db_file']
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
    db_file = envs.DB_DIR / template_info['db_file']
    table_name = template_info['name']
    _cmd = f'DELETE FROM {table_name};'
    log.db(f'Using this query: {_cmd}')
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
        log.db(f'Error: {e}')
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


async def del_row_id(template_info, numbers):
    db_file = envs.DB_DIR / template_info['db_file']
    table_name = template_info['name']
    _cmd = f'DELETE FROM {table_name} WHERE rowid '
    if isinstance(numbers, list):
        _cmd += f'IN ('
        _cmd += ', '.join(str(number) for number in numbers)
        _cmd += ')'
    elif isinstance(numbers, int):
        _cmd += f'= {numbers}'
    log.db(f'Using this query: {_cmd}')
    try:
        async with aiosqlite.connect(db_file) as db:
            await db.execute(_cmd)
            await db.commit()
    except aiosqlite.OperationalError:
        return None


async def del_row_ids(template_info, numbers=None):
    db_file = envs.DB_DIR / template_info['db_file']
    table_name = template_info['name']
    _cmd = f'DELETE FROM {table_name} WHERE rowid IN ('
    _cmd += ', '.join(str(number) for number in numbers)
    _cmd += ')'
    log.db(f'Using this query: {_cmd}')
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
    db_file = envs.DB_DIR / template_info['db_file']
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
    try:
        async with aiosqlite.connect(db_file) as db:
            await db.execute(_cmd)
            await db.commit()
    except aiosqlite.OperationalError:
        return None


async def del_row_by_AND_filter(
        template_info, where: list = None
):
    '''
    Delete using the following query:

        DELETE FROM `template_info[table_name]`
        WHERE `where[0]` = `where[1]`

    Additional WHEREs uses AND
    '''
    db_file = envs.DB_DIR / template_info['db_file']
    table_name = template_info['name']
    _cmd = f'DELETE FROM {table_name}'
    if isinstance(where, tuple):
        _cmd += f" WHERE {where[0]} = '{where[1]}'"
    elif isinstance(where, list):
        _cmd += " WHERE "
        for id in where:
            log.debug(
                # TODO Teste output
                f'`id` is {type(id)}: {id}'
            )
            _cmd += f"{id[0]} = '{id[1]}'"
            if id != where[-1]:
                _cmd += ' AND '
    log.db(f'Using this query: {_cmd}')
    try:
        async with aiosqlite.connect(db_file) as db:
            await db.execute(_cmd)
            await db.commit()
        log.db(f'Done and commited!')
    except aiosqlite.OperationalError as e:
        log.db(f'Error: {e}')
        return None
