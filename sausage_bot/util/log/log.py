#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'Custom logging for the module'
import sys
from colorama import init, Fore, Style
from pathlib import Path
from .. import config, envs, discord_commands
from ..args import args
from time import sleep

# colorama specific reset routine
init(autoreset=True)


def log_function(
    log_in: str, extra_info: str = None, color: str = None, extra_color: str = None):
    '''
    Include the name of the function in logging.

    color           If no `color` is specified, it will highlight in green.
    extra_info      Used to specify extra information in the logging (default: None)
    extra_color     Color for the `extra_info` (default: green)
    '''
    from .. import datetime_handling
    get_dt = datetime_handling.get_dt
    log_out = '[{}] '.format(get_dt(format='datetimefull'))
    if color is None:
        color = Fore.GREEN
    else:
        color = eval('Fore.{}'.format(color.upper()))
    if extra_color is None:
        extra_color = Fore.GREEN
    else:
        extra_color = eval('Fore.{}'.format(extra_color.upper()))
    function_name = log_func_name()
    if args.log_highlight is not None and str(args.log_highlight)\
            in function_name:
        color = Fore.RED
    if args.log_print:
        log_out += '{color}{style}[ {function_name} ]'.format(
            color=color,
            style=Style.BRIGHT,
            function_name=function_name)
        if extra_info:
            log_out += '{color}{style}[ {extra_info} ]'.format(
                color=extra_color,
                style=Style.BRIGHT,
                extra_info=extra_info
            )
        log_out += '{reset} '.format(reset=Style.RESET_ALL)

    else:
        log_out += '[ {} ] '.format(log_func_name())
        if extra_info:
            log_out += '[ {} ] '.format(extra_info)
    log_out += str(log_in)
    if args.log_print:
        print(log_out)
    else:
        log_out += '\n'
        _logfilename = envs.LOG_DIR / \
            '{}.log'.format(get_dt('revdate', sep='-'))
        write_log = open(_logfilename, 'a+', encoding="utf-8")
        write_log.write(log_out)
        write_log.close()


def log(log_in, color=None):
    '''
    Log the input `log_in`

    Optional: Specify the color for highlighting the function name.

    Available colors: black, red, green, yellow, blue, magenta, cyan, white.
    '''
    if args.log:
        log_function(log_in, color)
    if args.log_slow:
        sleep(3)


def log_more(log_in, color=None):
    '''Log the input `log_in`. Used as more verbose than `log`'''
    if args.log_more:
        log_function(log_in, color)
    if args.log_slow:
        sleep(3)


def debug(log_in, extra_info=None, extra_color=None):
    '''
    Log the input `log_in` as debug messages
    
    extra_info      Used to specify extra information in the logging
    extra_color     Color for the `extra_info`
    '''
    if args.debug:
        if extra_info:
            log_function(log_in, extra_info=extra_info, color=extra_color)
        else:
            log_function(log_in, color='yellow')
    if args.log_slow:
        sleep(3)


def log_func_name() -> str:
    'Get the function name that the `log`-function is used within'
    frame_file = sys._getframe(2)
    frame_func = sys._getframe(3)
    func_name = frame_func.f_code.co_name
    func_file = frame_file.f_back.f_code.co_filename
    func_file = Path(func_file).stem
    if func_name == '<module>':
        return str(func_file)
    else:
        return '{}.{}'.format(func_file, func_name)


async def log_to_bot_channel(text_in):
    'Messages you want to send directly to a specific channel'
    await config.bot.get_channel(
        discord_commands.get_text_channel_list()[config.BOT_CHANNEL]
    ).send(text_in)
