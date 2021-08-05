#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pendulum
import re

# Set correct timezone and locale
tz = pendulum.timezone("Europe/Oslo")
locale = pendulum.set_locale('nb')
pendulum.week_starts_at(pendulum.MONDAY)
pendulum.week_ends_at(pendulum.SUNDAY)


def make_dt(date_in):
    '''
    Make a datetime-object from string input.

    Accepts the following formats:
    - `DD MM YYYY`
    - `DD MM YYYY HH mm`
    - `DD MM YYYY HH mm ss`
    '''
    if 'T' in str(date_in):
        return pendulum.parse(date_in)
    else:
        # Remove all special characters from input
        date_in = re.sub(r'\s+| |\.+|:+|-+|T|Z', ' ', str(date_in.strip()))
        # Count the number of datetime-units in input
        date_in_split = re.split(' ', date_in)
        date_in_len = len(date_in_split)
        # Decide how to interpret the input
        try:
            if date_in_len == 3:
                if len(date_in_split[2]) == 4:
                    return pendulum.from_format(date_in, 'DD MM YYYY', tz=tz)
                elif len(date_in_split[0]) == 4:
                    return pendulum.from_format(date_in, 'YYYY MM DD', tz=tz)
            elif date_in_len == 5:
                if len(date_in_split[2]) == 4:
                    return pendulum.from_format(date_in, 'DD MM YYYY HH mm', tz=tz)
                elif len(date_in_split[0]) == 4:
                    return pendulum.from_format(date_in, 'YYY MM DD HH mm', tz=tz)
            elif date_in_len == 6:
                if len(date_in_split[2]) == 4:
                    return pendulum.from_format(
                        date_in, 'DD MM YYYY HH mm ss', tz=tz)
                elif len(date_in_split[0]) == 4:
                    return pendulum.from_format(
                        date_in, 'YYYY MM DD HH mm ss', tz=tz)
            else:
                return None
        except(ValueError):
            return None


def get_dt(format='epoch', sep='.', dt=False):
    '''
    Get a datetime object in preferred dateformat.
    - If the datetime-input `dt` is not specified, it will use
        `pendulum.now()`.
    - If `sep` (separator) isn't specified, it will use dots.
    - If `format` is not specified, it will return in epoch/linux time-format
    '''
    if type(dt) == str:
        dt = make_dt(dt)
        if dt is None:
            print('Can\'t process date `{}`. Aborting.'.format(dt))
            return None
    elif not dt:
        dt = pendulum.now(tz)
    if format == 'date':
        return dt.format('DD{sep}MM{sep}YYYY'.format(sep=sep))
    elif format == 'datetext':
        return dt.format('DD{sep} MMMM{sep} YYYY'.format(sep=sep),
                         locale=locale)
    elif format == 'revdate':
        return dt.format('YYYY{sep}MM{sep}DD'.format(sep=sep))
    elif format == 'datetime':
        return dt.format('DD{sep}MM{sep}YYYY HH{sep}mm'
                         .format(sep=sep))
    elif format == 'datetimefull':
        return dt.format('DD{sep}MM{sep}YYYY HH{sep}mm{sep}ss'
                         .format(sep=sep))
    elif format == 'revdatetimefull':
        return dt.format('YYYY{sep}MM{sep}DD HH{sep}mm{sep}ss'
                         .format(sep=sep))
    elif format == 'time':
        return dt.format('HH{sep}mm'.format(sep=sep))
    elif format == 'timefull':
        return dt.format('HH{sep}mm{sep}ss'.format(sep=sep))
    elif format == 'week':
        return dt.week_of_year
    elif format == 'year':
        return dt.year
    elif format == 'epoch':
        return dt.int_timestamp
    else:
        return None
