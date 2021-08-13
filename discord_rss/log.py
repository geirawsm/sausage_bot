#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import os
import sys
from colorama import init, Fore, Style
from pathlib import Path
from discord.ext import commands
from discord_rss import _vars, discord_commands, _config
from discord_rss._args import args
from discord_rss.datetime_funcs import get_dt as get_dt

# colorama specific reset routine
init(autoreset=True)


def log_function(log_in):
    log_out = '[{}] '.format(get_dt(format='datetimefull'))
    if args.log_print:
        log_out += '{color}{style}[ {func_name} ]{reset} '.format(
            color = Fore.GREEN,
            style = Style.BRIGHT,
            reset = Style.RESET_ALL,
            func_name = log_func_name())
    else:
        log_out += '[ {} ] '.format(log_func_name())
    log_out += log_in
    if args.log_print:
        print(log_out)
    else:
        log_out += '\n'
        
        _logfilename = _vars.LOG_DIR / '{}.log'.format(get_dt('revdate', sep='-'))
        write_log = open(_logfilename, 'a+', encoding="utf-8")
        write_log.write(log_out)
        write_log.close()


def log(log_in):
    '''Log the input `log_in`'''
    if args.log:
        log_function(log_in)


def log_more(log_in):
    '''Log the input `log_in`. Used as more verbose than `log`'''
    if args.log_more:
        log_function(log_in)


def log_func_name():
    'Get the function name that the `log`-function is used within'
    frame_file = sys._getframe(2)
    frame_func = sys._getframe(3)
    func_name = frame_func.f_code.co_name
    func_file = frame_file.f_back.f_code.co_filename
    func_file = Path(func_file).stem
    return '{}.{}'.format(func_file, func_name)


async def log_to_bot_channel(text_in):
    'Messages you want to send directly to a specific channel'
    await _config.bot.get_channel(
        discord_commands.get_channel_list()[_config.BOT_CHANNEL]
    ).send(text_in)
