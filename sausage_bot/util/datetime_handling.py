#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'datetime_handling: Handle datetimes'
import pendulum
import re
import datetime
import asyncio
import aiosqlite

from sausage_bot.util import config, envs, file_io
from sausage_bot.util.i18n import I18N

logger = config.logger

# Set correct timezone and locale
tz = config.timezone
locale = config.locale


async def make_dt(date_in):
    '''
    Make a datetime-object from string input

    Handles the following input:
    - 17.05.22
    - 17.05.22 20
    - 17.05.2022 1122
    - 17.05.2022, 11.22
    - 17.05.2022, 1122
    - 17.05.20 22, 11.22
    - 2022-05-17T11:22:00Z
    - 2022-05-17T11:22:00+02:00
    - 1122
    - 11.22
    - 2022-05-17 11:22:00.987
    - 1652779320
    '''
    db_in = None
    try:
        async with aiosqlite.connect(envs.locale_db_schema['db_file']) as db:
            db.row_factory = aiosqlite.Row
            out = await db.execute(
                "SELECT setting, value FROM {};".format(
                    envs.locale_db_schema['name']
                )
            )
            db_in = [dict(row) for row in await out.fetchall()]
        locale_db = file_io.make_db_output_to_json(
            ['setting', 'value'],
            db_in
        )
        tz = locale_db.get('timezone', 'UTC')
        locale = locale_db.get('language', 'en')
    except aiosqlite.OperationalError as e:
        logger.error(f'Error: {e}')
        tz = 'UTC'
        locale = 'en'
    logger.debug(f'tz is {tz}')
    logger.debug(f'language/locale is {locale}')
    if any(marker in str(date_in) for marker in ['Z', 'T', '+']):
        logger.debug('Found a Z/T/+ in `date_in`')
        return pendulum.parse(str(date_in)).in_timezone(tz)
    elif re.match(r'\d{10}|\d{13}', str(date_in)):
        return pendulum.from_timestamp(int(date_in))
    else:
        # Remove all special characters from input
        date_in = re.sub(r'\s+|\s*,\s*| |\.+|:+|-+', ' ', str(date_in).strip())
        # Count the number of datetime-units in input
        d_split = re.split(' ', date_in)
        d_len = len(d_split)
        # Decide how to interpret the input
        try:
            logger.debug('`date_in` is {}'.format(date_in))
            logger.debug(f'Got `d_len` {d_len}')
            logger.debug(f'd_split: {d_split}')
            if d_len <= 2:
                # Expecting `HHmm` or `HH( |:|-|_|.)mm`
                date_in = date_in.replace(' ', '')
                return pendulum.from_format(
                    date_in, 'HHmm'
                )
            elif d_len == 3:
                # Expecting `DD MM YYYY`, `YYY MM DD` or `DD MM YY`
                if len(d_split[2]) == 4:
                    return pendulum.from_format(
                        date_in, 'DD MM YYYY'
                    )
                elif len(d_split[0]) == 4:
                    return pendulum.from_format(
                        date_in, 'YYYY MM DD'
                    )
                elif all(len(timeunit) == 2 for timeunit in d_split):
                    # We have to assume that this is DD MM YY
                    return pendulum.from_format(
                        date_in, 'DD MM YY'
                    )
            elif d_len == 4:
                # Expecting a wrong space or separator somewhere
                # If all units have 2 in len, then it could be a split in YYYY,
                if all(len(timeunit) == 2 for timeunit in d_split):
                    d = d_split
                    date_in = f'{d[0]} {d[1]} {d[2]}{d[3]}'
                    return pendulum.from_format(
                        date_in, 'DD MM YYYY'
                    )
                # If the fourth and last unit has a len of 4, it probably
                # is the time with a missing separator
                elif all(len(timeunit) == 2 for timeunit in d_split[0:2])\
                        and len(d_split[3]) == 4:
                    d_split[3] = '{} {}'.format(
                        d_split[3][0:2],
                        d_split[3][2:4]
                    )
                    if len(d_split[2]) == 2:
                        d_split[2] = '20{}'.format(
                            d_split[2]
                        )
                    d = d_split
                    date_in = f'{d[0]} {d[1]} {d[2]} {d[3]}'
                    date_in = date_in.strip()
                    logger.debug('date_in: {}'.format(date_in))
                    return pendulum.from_format(
                        date_in, 'DD MM YYYY HH mm'
                    )
            elif d_len == 5:
                if len(d_split[2]) == 4:
                    return pendulum.from_format(
                        date_in, 'DD MM YYYY HH mm'
                    )
                elif len(d_split[0]) == 4:
                    return pendulum.from_format(
                        date_in, 'YYYY MM DD HH mm'
                    )
                elif len(d_split[2]) == 2:
                    return pendulum.from_format(
                        date_in, 'DD MM YY HH mm'
                    )
                elif len(d_split[0]) == 2:
                    return pendulum.from_format(
                        date_in, 'YY MM DD HH mm'
                    )
            elif d_len == 6:
                if all(len(timeunit) == 2 for timeunit in d_split):
                    d = d_split
                    date_in = f'{d[0]} {d[1]} {d[2]}{d[3]} {d[4]} {d[5]}'
                    return pendulum.from_format(
                        date_in, 'DD MM YYYY HH mm'
                    )
                pass
            elif d_len == 7:
                if len(d_split[0]) == 4 and len(d_split[1]) == 2 and\
                        len(d_split[2]) == 2 and len(d_split[3]) == 2 and\
                        len(d_split[4]) == 2 and len(d_split[5]) == 2 and\
                        len(d_split[6]) == 3:
                    d = d_split
                    date_in = f'{d[0]} {d[1]} {d[2]} {d[3]} {d[4]} '\
                        f'{d[5]} {d[6]}'
                    return pendulum.from_format(
                        date_in, 'YYYY MM DD HH mm ss SSS'
                    )
            else:
                return None
        except ValueError:
            logger.error('ValueError: {}'.format(ValueError))
            return None


async def get_dt(format='epoch', sep='.', dt=False):
    '''
    Get a datetime object in preferred dateformat.

    Parameters
    ------------
    format: str
        The format to return the datetime-object in (default: 'epoch')
    sep: str
        Separators to use in the output (default: '.')
    dt: str/datetime-object
        Use a specific datetime-object when making the output
        (default: 'pendulum.now()')

    Returns
    ------------
    str
        A datetime object formatted pretty in a string

    Formats
    ------------
    (Example date: May 17th 2014; time: 14:23:39; timezone: GMT)
    date                17.05.2014
    datetext            17 May 2014
    shortdate           17.05.14
    datetextfull        17 May 2014, 14.23
    datetimetextday     Monday, 17. May, 14.23
    revdate             2014.05.17
    datetime            17.05.2014 14.23
    datetimefull        17.05.2014 14.23.39
    revdatetimefull     2014.05.17 14.23.39
    time                14.23
    timefull            14.23.39
    week                20
    year                2014
    month               05
    day                 17
    epoch               1400336619
    ISO8601             YYYY-MM-DD HH:MM:SS.SSS
    datetimeobject      datetime object
    '''
    db_in = None
    try:
        async with aiosqlite.connect(envs.locale_db_schema['db_file']) as db:
            db.row_factory = aiosqlite.Row
            out = await db.execute(
                "SELECT setting, value FROM {};".format(
                    envs.locale_db_schema['name']
                )
            )
            db_in = [dict(row) for row in await out.fetchall()]
        locale_db = file_io.make_db_output_to_json(
            ['setting', 'value'],
            db_in
        )
        tz = locale_db.get('timezone', 'UTC')
        locale = locale_db.get('language', 'en')
    except aiosqlite.OperationalError as e:
        logger.error(f'Error: {e}')
        tz = 'UTC'
        locale = 'en'
    logger.debug(f'tz is {tz}')
    logger.debug(f'language/locale is {locale}')
    if isinstance(dt, datetime.datetime):
        logger.debug('Input is a datetime object')
        dt = await make_dt(str(dt))
        dt = await make_dt(str(dt))
    if isinstance(dt, str):
        logger.debug('Input is a string')
        dt = await make_dt(dt)
        dt = await make_dt(dt)
        if dt is None:
            print('Can\'t process date `{}`. Aborting.'.format(dt))
            return None
    elif not dt:
        logger.debug('No input detected, getting `now()`')
        dt = pendulum.now(tz)
    # Make sure correct timezone is used in input
    if format == 'date':
        return dt.format(f'DD{sep}MM{sep}YYYY')
    elif format == 'datetext':
        return dt.format(f'DD{sep} MMMM YYYY', locale=locale)
    elif format == 'shortdate':
        return dt.format(f'DD{sep}MM{sep}YY')
    elif format == 'datetextfull':
        return dt.format(f'DD{sep} MMMM YYYY, HH{sep}mm', locale=locale)
    elif format == 'datetimetextday':
        return dt.format(f'dddd, DD{sep} MMMM, HH{sep}mm', locale=locale)
    elif format == 'revdate':
        return dt.format(f'YYYY{sep}MM{sep}DD')
    elif format == 'datetime':
        return dt.format(f'DD{sep}MM{sep}YYYY HH{sep}mm')
    elif format == 'datetimefull':
        return dt.format(f'DD{sep}MM{sep}YYYY HH{sep}mm{sep}ss')
    elif format == 'revdatetimefull':
        return dt.format(f'YYYY{sep}MM{sep}DD HH{sep}mm{sep}ss')
    elif format == 'time':
        return dt.format(f'HH{sep}mm')
    elif format == 'timefull':
        return dt.format(f'HH{sep}mm{sep}ss')
    elif format == 'week':
        return dt.week_of_year
    elif format == 'year':
        return dt.format('YYYY')
    elif format == 'month':
        return dt.format('MM')
    elif format == 'day':
        return dt.format('DD')
    elif format == 'epoch':
        return dt.int_timestamp
    elif format == 'ISO8601':
        return dt.format('YYYY-MM-DD HH:mm:ss.SSS', locale=locale)
    elif format == 'datetimeobject':
        return dt
    else:
        return None


def change_dt(
    pendulum_object_in, change=None, count=None, unit=None
):
    '''
    Take a pendulum datetime object and change it relatively

    `pendulum_object_in`: The object to change

    `change`: Accepts `add` or `remove`

    `count`: How many `units` to change

    `unit`: Unit to change. Accepted units are `years`, `months`, `days`,
        `hours`, `minutes` and `seconds`'''
    if change is None or unit is None or count is None:
        logger.info(I18N.t('common.too_few_arguments'))
        return None
    accepted_units = [
        'years', 'months', 'days', 'hours', 'minutes', 'seconds'
    ]
    if unit not in accepted_units:
        logger.info(f'Unit `{unit}` is not accepted')
        return None
    if not isinstance(count, (int, float)):
        logger.info(f'Count `{count}` is not a number')
        return None
    p = pendulum_object_in  # noqa: F841
    if change == 'add':
        return eval(f'p.add({unit}={count})')
    elif change == 'remove':
        return eval(f'p.subtract({unit}={count})')


async def main():
    print(await make_dt('17.05.22'))

if __name__ == "__main__":
    asyncio.run(main())
