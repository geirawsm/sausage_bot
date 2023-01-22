#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pendulum
import re
from . import envs
from .log import log

# Set correct timezone and locale
tz = pendulum.timezone("Europe/Oslo")
locale = pendulum.set_locale('nb')
pendulum.week_starts_at(pendulum.MONDAY)
pendulum.week_ends_at(pendulum.SUNDAY)


def make_dt(date_in):
    '''
    Make a datetime-object from string input

    Handles the following input:
    - 17.05.22
    - 17.05.20 22
    - 17.05.2022 1122
    - 17.05.2022, 11.22
    - 17.05.2022, 1122
    - 17.05.20 22, 11.22
    - 2022-05-17T11:22:00Z
    '''
    if 'T' in str(date_in):
        return pendulum.parse(date_in)
    else:
        # Remove all special characters from input
        date_in = re.sub(r'\s+|\s*,\s*| |\.+|:+|-+', ' ', str(date_in).strip())
        # Count the number of datetime-units in input
        d_split = re.split(' ', date_in)
        d_len = len(d_split)
        # Decide how to interpret the input
        try:
            log.log_more('`date_in` is {}'.format(date_in))
            log.log_more(f'Got `d_len` {d_len}')
            log.log_more(f'd_split: {d_split}')
            if d_len == 3:
                # Expecting `DD MM YYYY`, `YYY MM DD` or `DD MM YY`
                if len(d_split[2]) == 4:
                    return pendulum.from_format(date_in, 'DD MM YYYY', tz=tz)
                elif len(d_split[0]) == 4:
                    return pendulum.from_format(date_in, 'YYYY MM DD', tz=tz)
                elif all(len(timeunit) == 2 for timeunit in d_split):
                    # We have to assume that this is DD MM YY
                    return pendulum.from_format(date_in, 'DD MM YY', tz=tz)
            elif d_len == 4:
                # Expecting a wrong space or separator somewhere
                # If all units have 2 in len, then it could be a split in YYYY,
                if all(len(timeunit) == 2 for timeunit in d_split):
                    d = d_split
                    date_in = f'{d[0]} {d[1]} {d[2]}{d[3]}'
                    return pendulum.from_format(
                        date_in, 'DD MM YYYY', tz=tz
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
                    log.log_more('date_in: {}'.format(date_in))
                    return pendulum.from_format(
                        date_in, 'DD MM YYYY HH mm', tz=tz
                    )
            elif d_len == 5:
                if len(d_split[2]) == 4:
                    return pendulum.from_format(date_in, 'DD MM YYYY HH mm', tz=tz)
                elif len(d_split[0]) == 4:
                    return pendulum.from_format(date_in, 'YYYY MM DD HH mm', tz=tz)
                elif len(d_split[2]) == 2:
                    return pendulum.from_format(date_in, 'DD MM YY HH mm', tz=tz)
                elif len(d_split[0]) == 2:
                    return pendulum.from_format(date_in, 'YY MM DD HH mm', tz=tz)
            elif d_len == 6:
                # A split of 6 is most likely a split in YYYY
                if all(len(timeunit) == 2 for timeunit in d_split):
                    d = d_split
                    date_in = f'{d[0]} {d[1]} {d[2]}{d[3]} {d[4]} {d[5]}'
                    return pendulum.from_format(
                        date_in, 'DD MM YYYY HH mm', tz=tz
                    )
                pass
            else:
                return None
            log.log_more('-'*10)
        except(ValueError):
            log.log_more('-'*10)
            return None


def get_dt(format='epoch', sep='.', dt=False):
    '''
    Get a datetime object in preferred dateformat.
    - If the datetime-input `dt` is not specified, it will use
        `pendulum.now()`.
    - If `sep` (separator) isn't specified, it will use dots.
    - If `format` is not specified, it will return in epoch/linux time-format
    ```
    Formats:
    (Example date: May 17th 2014; time: 14:23:39; timezone: GMT)
    `date`:             17.05.2014
    `datetext`:         17 May 2014
    `datetextfull`:     17 May 2014, 14.23
    `revdate`:          2014.05.17
    `datetime`:         17.05.2014 14.23
    `datetimefull`:     17.05.2014 14.23.39
    `revdatetimefull`:  2014.05.17 14.23.39
    `time`:             14.23
    `timefull`:         14.23.39
    `week`:             20
    `year`:             2014
    `month`:            05
    `day`:              17
    `epoch`:            1400336619
    ```
    '''
    if type(dt) == str:
        dt = make_dt(dt)
        if dt is None:
            print('Can\'t process date `{}`. Aborting.'.format(dt))
            return None
    elif not dt:
        dt = pendulum.now(tz)
    if format == 'date':
        return dt.format(f'DD{sep}MM{sep}YYYY')
    elif format == 'datetext':
        return dt.format(f'DD{sep} MMMM YYYY', locale=locale)
    elif format == 'datetextfull':
        return dt.format(f'DD{sep} MMMM YYYY, HH{sep}mm', locale=locale)
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
        return dt.format(f'YYYY')
    elif format == 'month':
        return dt.format(f'MM')
    elif format == 'day':
        return dt.format(f'DD')
    elif format == 'epoch':
       return dt.int_timestamp
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
        log.log(envs.TOO_FEW_ARGUMENTS)
        return None
    accepted_units=['years', 'months', 'days', 'hours', 'minutes', 'seconds']
    if unit not in accepted_units:
        log.log(f'Unit `{unit}` is not accepted')
        return None
    if not isinstance(count, (int, float)):
        log.log(f'Count `{count}` is not a number')
        return None
    p = pendulum_object_in
    if change == 'add':
        return eval(f'p.add({unit}={count})')
    elif change == 'remove':
        return eval(f'p.subtract({unit}={count})')


if __name__ == "__main__":
    pass
