#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'Custom logging for the module'
import sys
from colorama import init, Fore, Style
import pendulum
from pathlib import Path
from .. import config, envs
from ..args import args
from time import sleep
import os
import json

# colorama specific reset routine
init(autoreset=True)


# Checking if log_all is activated
if args.log_all:
    args.log = True
    args.log_verbose = True
    args.log_print = True
    args.log_file = True
    args.log_db = True
    args.debug = True
    args.log_error = True


def log_function(
        log_in: str, color: str = None, extra_info: str = None,
        extra_color: str = None, pretty: dict | list | tuple = None,
        sameline: bool = False
):
    '''
    Include the name of the function in logging.

    log_in          The text/input to log
    color           Specify the color for highlighting the function name:
                    black, red, green, yellow, blue, magenta, cyan, white.
                    If `color` is not specified, it will highlight in green.
    extra_info      Used to specify extra information in the logging
                    (default: None)
    extra_color     Color for the `extra_info` (default: green)
    pretty          Prettify specific output. Works on dict, list and tuple
    sameline        Reuse line for next output
    '''
    if args.log_print:
        if color is None:
            color = Fore.GREEN
        else:
            color = eval('Fore.{}'.format(color.upper()))
        if extra_color is None:
            extra_color = Fore.GREEN
        else:
            extra_color = eval('Fore.{}'.format(extra_color.upper()))
    function_name = log_func_name()
    if args.log_print:
        if args.log_highlight is not None:
            if str(args.log_highlight) in function_name['name'] or\
                    str(args.log_highlight) in log_in:
                color = eval('Fore.{}'.format(
                    args.log_highlight_color.upper()
                ))
    dt = pendulum.now(config.TIMEZONE)
    dt_full = dt.format('DD.MM.YYYY HH.mm.ss')
    log_out = '[ {dt} ]{extra_info} [ {func_name} ({func_line}) '\
        '] {log_in}'.format(
            dt=dt_full,
            extra_info=f' [ {extra_info} ]' if extra_info else '',
            func_name=function_name['name'],
            func_line=function_name['line'],
            log_in=str(log_in)
        )
    log_out_print = '{color}{style}[ {dt} ]{extra_info}{color}{style}'\
        ' [ {func_name} ({func_line}) ]{reset} {log_in}'.format(
            color=color if args.log_print else '',
            style=Style.BRIGHT if args.log_print else '',
            dt=dt_full,
            extra_info=f' [ {extra_info} ]' if extra_info else '',
            func_name=function_name['name'],
            func_line=function_name['line'],
            reset=Style.RESET_ALL if args.log_print else '',
            log_in=str(log_in)
        )
    # Get remaining terminal width for spacing
    if sameline and args.log_print:
        try:
            max_cols, max_rows = os.get_terminal_size(0)
        except (OSError):
            max_cols = 0
        msg_len = len(str(log_out))
        rem_len = max_cols - msg_len - 2
        log_out_print += ' ' * rem_len
    if pretty and isinstance(pretty, (dict, list, tuple)):
        pretty_log = json.dumps(
                pretty, indent=4, ensure_ascii=False
            )
    else:
        pretty_log = None
    if args.log_print:
        if sameline:
            print(log_out_print, end='\r')
        else:
            print(log_out_print)
        if pretty_log:
            print(pretty_log)
            print('-'*20)
    if args.log_file:
        log_out += '\n'
        if pretty_log:
            log_out += '\n'
            log_out += pretty_log
        dt = pendulum.now(config.TIMEZONE)
        _dt_rev = dt.format('YYYY-MM-DD')
        _logfilename = envs.LOG_DIR / f'{_dt_rev}.log'
        write_log = open(_logfilename, 'a+', encoding="utf-8")
        write_log.write(log_out)
        write_log.close()


def log(
    log_in: str, color: str = None, pretty: dict | list | tuple = None,
    sameline: bool = False
):
    '''
    Log the input `log_in`

    log_in          The text/input to log
    color           Specify the color for highlighting the function name:
                    black, red, green, yellow, blue, magenta, cyan, white.
                    If `color` is not specified, it will highlight in green.
    pretty          Prettify specific output. Works on dict, list and tuple
    sameline        When printing log, reuse the same line
    '''
    if args.log:
        log_function(
            log_in, color=color, sameline=sameline,
            extra_info=envs.log_extra_info('log'), pretty=pretty if pretty else None
        )
    if args.log_slow:
        sleep(3)


def verbose(
        log_in: str, color: str = None, pretty: dict | list | tuple = None,
        sameline: bool = False
):
    '''
    Log the input `log_in`. Used as more verbose than `log`

    log_in          The text/input to log
    color           Specify the color for highlighting the function name:
                    black, red, green, yellow, blue, magenta, cyan, white.
                    If `color` is not specified, it will highlight in green.
    pretty          Prettify specific output. Works on dict, list and tuple
    sameline        When printing log, reuse the same line
    '''
    if args.log_verbose:
        log_function(
            log_in, color=color, sameline=sameline,
            extra_info=envs.log_extra_info('verbose'),
            pretty=pretty if pretty else None
            
        )
    if args.log_slow:
        sleep(3)


def debug(
        log_in: str, color: str = None, pretty: dict | list | tuple = None,
        sameline: bool = False
):
    '''
    Log the input `log_in` as debug messages

    color           Specify the color for highlighting the function name:
                    black, red, green, yellow, blue, magenta, cyan, white.
                    If `color` is not specified, it will highlight in green
    pretty          Prettify specific output. Works on dict, list and tuple
    sameline        When printing log, reuse the same line
    '''
    if args.debug:
        log_function(
            log_in, color=color, extra_info=envs.log_extra_info('debug'),
            sameline=sameline, pretty=pretty if pretty else None
        )
    if args.log_slow:
        sleep(3)


def db(
        log_in: str, color: str = 'magenta', extra_color: str = None,
        pretty: dict | list | tuple = None, sameline: bool = False
):
    '''
    Log database input specifically

    color           Specify the color for highlighting the function name:
                    black, red, green, yellow, blue, magenta, cyan, white.
                    If `color` is not specified, it will highlight in magenta.
    extra_info      Used to specify extra information in the logging
    extra_color     Color for the `extra_info`
    pretty          Prettify specific output. Works on dict, list and tuple
    sameline        When printing log, reuse the same line
    '''
    if args.log_db:
        log_function(
            log_in, color=color, extra_color=extra_color,
            extra_info=envs.log_extra_info('database'),
            sameline=sameline, pretty=pretty if pretty else None
        )
    if args.log_slow:
        sleep(3)


def error(
        log_in: str, color: str = 'red', pretty: dict | list | tuple = None,
        sameline: bool = False
):
    '''
    Log the input `log_in`. Used as more verbose than `log`

    log_in          The text/input to log
    color           Specify the color for highlighting the function name:
                    black, red, green, yellow, blue, magenta, cyan, white.
                    If `color` is not specified, it will highlight in red.
    pretty          Prettify specific output. Works on dict, list and tuple
    sameline        When printing log, reuse the same line
    '''
    if args.log_error:
        log_function(
            log_in, color=color, extra_info=envs.log_extra_info('error'),
            sameline=sameline, pretty=pretty if pretty else None
        )
    if args.log_slow:
        sleep(3)


def log_func_name() -> dict:
    'Get the function name that the `log`-function is used within'
    frame_line = sys._getframe(3).f_lineno
    frame_file = sys._getframe(2)
    frame_func = sys._getframe(3)
    func_name = frame_func.f_code.co_name
    func_file = frame_file.f_back.f_code.co_filename
    func_file = Path(func_file).stem
    if func_name == '<module>':
        return {
            'name': str(func_file),
            'line': str(frame_line)
        }
    else:
        return {
            'name': f'{func_file}.{func_name}',
            'line': str(frame_line)
        }


if __name__ == "__main__":
    args.log_print = True
    args.log = True
    log('This is a log')
    args.log_verbose = True
    verbose('This is a verbose')
    args.debug = True
    debug('This is a debug')
    args.log_db = True
    db('This is a db')
    args.log_error = True
    error('This is an error')
