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


def log_function(log_in, color=None):
    '''
    Include the name of the function in logging.

    If no `color` is specified, it will highlight in green.
    '''
    from .. import datetime_handling
    get_dt = datetime_handling.get_dt
    log_out = '[{}] '.format(get_dt(format='datetimefull'))
    if color is None:
        color = Fore.GREEN
    else:
        color = eval('Fore.{}'.format(color.upper()))
    function_name = log_func_name()
    if args.log_highlight is not None:
        if str(args.log_highlight) in function_name:
            color = Fore.RED
    if args.log_print:
        log_out += '{color}{style}[ {function_name} ]{reset} '.format(
            color = color,
            style = Style.BRIGHT,
            reset = Style.RESET_ALL,
            function_name = function_name)
    else:
        log_out += '[ {} ] '.format(log_func_name())
    log_out += log_in
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


def debug(log_in):
    '''Log the input `log_in` as debug messages.'''
    if args.debug:
        log_function(log_in, 'yellow')
    if args.log_slow:
        sleep(3)


def log_func_name():
    'Get the function name that the `log`-function is used within'
    frame_file = sys._getframe(2)
    frame_func = sys._getframe(3)
    func_name = frame_func.f_code.co_name
    func_file = frame_file.f_back.f_code.co_filename
    func_file = Path(func_file).stem
    if func_name == '<module>':
        return func_file
    else:
        return '{}.{}'.format(func_file, func_name)


async def log_to_bot_channel(text_in):
    'Messages you want to send directly to a specific channel'
    await config.bot.get_channel(
        discord_commands.get_text_channel_list()[config.BOT_CHANNEL]
    ).send(text_in)
