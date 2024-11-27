#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'Custom logging for the module'
import sys
from colorama import init, Fore, Style
import pendulum
from pathlib import Path
from time import sleep
import os
import json
import stat

from .. import config, envs
from ..args import args


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
    args.log_i18n = True


class internal_cmd():
    def __init__():
        pass

    @staticmethod
    def file_size(filename):
        '''
        Checks the file size of a file. If it can't find the file it will
        return False
        '''
        try:
            _stats = os.stat(filename, follow_symlinks=True)
            return _stats[stat.ST_SIZE]
        except FileNotFoundError:
            return False

    @staticmethod
    def ensure_folder(folder_path: str):
        '''
        Create folders in `folder_path` if it doesn't exist
        '''
        folder_path = str(folder_path)
        # Make the folders if necessary
        if not os.path.exists(folder_path):
            _dirs = str(folder_path).split(os.sep)
            _path = ''
            for _dir in _dirs:
                _path += '{}/'.format(_dir)
            Path(_path).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def ensure_file(file_path_in: str, file_template=False):
        '''
        Create file `file_path_in` if it doesn't exist and include the
        `file_template` if provided.
        '''
        full_file_path = str(file_path_in).split(os.sep)
        folder_path = '/'.join(full_file_path[0:-1])
        folder_path += '/'
        # Make the folders if necessary
        if not os.path.exists(file_path_in):
            internal_cmd.ensure_folder(folder_path)
        # Don't overwrite the file unless it's empty
        # Create the file if it doesn't exist
        if not internal_cmd.file_size(file_path_in):
            with open(file_path_in, 'w+') as fout:
                if file_template:
                    fout.write(file_template)
                else:
                    fout.write('')


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
        internal_cmd.ensure_file(_logfilename)
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
        log_in: str, color: str = None,
        extra_info: str = envs.log_extra_info('database'),
        extra_color: str = None, pretty: dict | list | tuple = None,
        sameline: bool = False
):
    '''
    Log the input `log_in` as debug messages

    color           Specify the color for highlighting the function name:
                    black, red, green, yellow, blue, magenta, cyan, white.
                    If `color` is not specified, it will highlight in green
    extra_info      Used to specify extra information in the logging
    extra_color     Color for the `extra_info`
    pretty          Prettify specific output. Works on dict, list and tuple
    sameline        When printing log, reuse the same line
    '''
    if args.debug:
        log_function(
            log_in, color=color, extra_color=extra_color,
            extra_info=extra_info,
            sameline=sameline, pretty=pretty if pretty else None
        )
    if args.log_slow:
        sleep(3)


def db(
    log_in: str, color: str = 'magenta',
    extra_info: str = envs.log_extra_info('database'),
    extra_color: str = None, pretty: dict | list | tuple = None,
    sameline: bool = False
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
            extra_info=extra_info,
            sameline=sameline, pretty=pretty if pretty else None
        )
    if args.log_slow:
        sleep(3)


def error(
    log_in: str, color: str = 'red',
    extra_info: str = envs.log_extra_info('error'),
    extra_color: str = None, pretty: dict | list | tuple = None,
    sameline: bool = False
):
    '''
    Log the input `log_in`. Used as more verbose than `log`

    log_in          The text/input to log
    color           Specify the color for highlighting the function name:
                    black, red, green, yellow, blue, magenta, cyan, white.
                    If `color` is not specified, it will highlight in red.
    extra_info      Used to specify extra information in the logging
    extra_color     Color for the `extra_info`
    pretty          Prettify specific output. Works on dict, list and tuple
    sameline        When printing log, reuse the same line
    '''
    if args.log_error:
        log_function(
            log_in, color=color, extra_color=extra_color,
            extra_info=extra_info, sameline=sameline,
            pretty=pretty if pretty else None
        )
    if args.log_slow:
        sleep(3)


def i18n(log_in: str):
    '''
    Log the input from errors in i18n with `log_in`.
    '''
    if args.log_i18n:
        dt = pendulum.now(config.TIMEZONE)
        dt_full = dt.format('DD.MM.YYYY HH.mm.ss')
        log_out = '[ {dt} ] {log_in}\n'.format(dt=dt_full, log_in=str(log_in))
        dt = pendulum.now(config.TIMEZONE)
        _logfilename = envs.LOG_DIR / 'i18n.log'
        file_io.ensure_file(_logfilename)
        write_log = open(_logfilename, 'a+', encoding="utf-8")
        write_log.write(log_out)
        write_log.close()


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
