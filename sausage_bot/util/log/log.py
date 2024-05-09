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
    args.log_db = True
    args.debug = True


def log_function(
        log_in: str, color: str = None, extra_info: str = None,
        extra_color: str = None, pretty: bool = False,
        sameline: bool = False, pre: str = None
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
    _dt_full = dt.format('DD.MM.YYYY HH.mm.ss')
    if args.log_print:
        log_out = '{color}{style}[ {dt} ] '.format(
            color=color,
            style=Style.BRIGHT,
            dt=_dt_full
        )
    if args.log_print:
        if extra_info:
            log_out += '[ {extra_info} ]'.format(
                extra_info=extra_info
            )
        log_out += '{color}{style}[ {func_name} ({func_line}) ]'.format(
            color=color, style=Style.BRIGHT,
            func_line=function_name['line'],
            func_name=function_name['name']
        )
        log_out += '{reset} '.format(reset=Style.RESET_ALL)
        if pretty:
            print(log_out)
            if isinstance(pretty, (dict)):
                log_out += f'{log_in} (prettifying...):'
                print(
                    json.dumps(
                        pretty, indent=4, ensure_ascii=False
                    )
                )
            else:
                print('input is not dict, list nor tuple')
        else:
            log_out += str(log_in)
            if sameline:
                try:
                    max_cols, max_rows = os.get_terminal_size(0)
                except (OSError):
                    max_cols = 0
                msg_len = len(str(log_out))
                rem_len = max_cols - msg_len - 2
                print('{}{}'.format(
                    log_out, ' '*rem_len
                ), end='\r')
            else:
                print(log_out)
        if extra_info:
            log_out = '[ {} ] '.format(extra_info)
        log_out += '[ {} ] '.format(function_name['line'])
        log_out += '[ {} ] '.format(function_name['name'])
        log_out += str(log_in)
    else:
        dt = pendulum.now(config.TIMEZONE)
        _dt_rev = dt.format('YYYY-MM-DD HH.mm.ss')
        _logfilename = envs.LOG_DIR / f'{_dt_rev}.log'
        write_log = open(_logfilename, 'a+', encoding="utf-8")
        write_log.write(log_out)
        write_log.close()


def log(
    log_in: str, color: str = None, pretty: bool = False,
    sameline: bool = False
):
    '''
    Log the input `log_in`

    log_in          The text/input to log
    color           Specify the color for highlighting the function name:
                    black, red, green, yellow, blue, magenta, cyan, white.
                    If `color` is not specified, it will highlight in green.
    pretty          Prettify the output. Works on dict and list
    '''
    if args.log:
        log_function(
            log_in, color=color, pretty=pretty, sameline=sameline,
            extra_info=envs.log_extra_info('log')
        )
    if args.log_slow:
        sleep(3)


def verbose(
        log_in: str, color: str = None, pretty: bool = False,
        sameline: bool = False
):
    '''
    Log the input `log_in`. Used as more verbose than `log`

    log_in          The text/input to log
    color           Specify the color for highlighting the function name:
                    black, red, green, yellow, blue, magenta, cyan, white.
                    If `color` is not specified, it will highlight in green.
    pretty          Prettify the output. Works on dict and list
    '''
    if args.log_verbose:
        log_function(
            log_in, color=color, pretty=pretty, sameline=sameline,
            extra_info=envs.log_extra_info('verbose')
        )
    if args.log_slow:
        sleep(3)


def error(
        log_in: str, color: str = 'red', pretty: bool = False,
        sameline: bool = False
):
    '''
    Log the input `log_in`. Used as more verbose than `log`

    log_in          The text/input to log
    color           Specify the color for highlighting the function name:
                    black, red, green, yellow, blue, magenta, cyan, white.
                    If `color` is not specified, it will highlight in red.
    pretty          Prettify the output. Works on dict and list
    '''
    if args.log_error:
        log_function(
            log_in, color=color, pretty=pretty, sameline=sameline,
            extra_info=envs.log_extra_info('error')
        )
    if args.log_slow:
        sleep(3)


def debug(
        log_in: str, color: str = None, pretty: bool = False,
        sameline: bool = False
):
    '''
    Log the input `log_in` as debug messages

    color           Specify the color for highlighting the function name:
                    black, red, green, yellow, blue, magenta, cyan, white.
                    If `color` is not specified, it will highlight in gre
    pretty          Prettify the output. Works on dict and list
    '''
    if args.debug:
        log_function(
            log_in, color=color, extra_info=envs.log_extra_info('debug'),
            pretty=pretty, sameline=sameline
        )
    if args.log_slow:
        sleep(3)


def db(
        log_in: str, color: str = 'magenta', extra_color: str = None
):
    '''
    Log database input specifically

    color           Specify the color for highlighting the function name:
                    black, red, green, yellow, blue, magenta, cyan, white.
                    If `color` is not specified, it will highlight in magenta.
    extra_info      Used to specify extra information in the logging
    extra_color     Color for the `extra_info`
    pretty          Prettify the output. Works on dict and list
    '''
    if args.log_db:
        log_function(
            log_in, color=color, extra_color=extra_color,

            extra_info=envs.log_extra_info('database')
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


async def log_to_bot_channel(content_in=None, content_embed_in=None):
    'Messages you want to send directly to a specific channel'
    log_channel = config.BOT_CHANNEL
    server_channels = {}

    for guild in config.bot.guilds:
        if str(guild.name).lower() == config.env('DISCORD_GUILD').lower():
            debug(f'Got guild {guild} ({type(guild)})')
        else:
            log(envs.GUILD_NOT_FOUND)
            guild = None

    # Get all channels and their IDs
    for channel in guild.text_channels:
        server_channels[channel.name] = channel.id
    debug(f'Got these channels: {server_channels}')
    if log_channel in server_channels:
        channel_out = config.bot.get_channel(server_channels[log_channel])
    else:
        channel_out = await guild.create_text_channel(
            name=str(config.BOT_CHANNEL),
            topic=f'Incoming log messages from {config.bot.user.name}',
        )
    msg_out = await channel_out.send(
        content=content_in
    )
    return msg_out
