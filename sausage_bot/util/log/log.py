#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'Custom logging for the module'
import sys
from colorama import init, Fore, Style
from pathlib import Path
import discord
from .. import config, envs
from ..args import args
from time import sleep
import os
import json
import asyncio

# colorama specific reset routine
init(autoreset=True)


def log_function(
        log_in: str, color: str = None, extra_info: str = None,
        extra_color: str = None, pretty: bool = False,
        sameline: bool = False
):
    '''
    Include the name of the function in logging.

    log_in          The text/input to log
    color           Specify the color for highlighting the function name:
                    black, red, green, yellow, blue, magenta, cyan, white.
                    If `color` is not specified, it will highlight in green.
    extra_info      Used to specify extra information in the logging (default: None)
    extra_color     Color for the `extra_info` (default: green)
    pretty          Prettify the output. Works on dict and list
    '''
    from .. import datetime_handling
    get_dt = datetime_handling.get_dt
    log_out = '[{}] '.format(get_dt(format = 'datetimefull'))
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
            color=color, style=Style.BRIGHT,
            function_name=function_name
        )
        if extra_info:
            log_out += '{color}{style}[ {extra_info} ]'.format(
                color=extra_color, style=Style.BRIGHT,
                extra_info=extra_info
            )
        log_out += '{reset} '.format(reset=Style.RESET_ALL)
    else:
        log_out += '[ {} ] '.format(log_func_name())
        if extra_info:
            log_out += '[ {} ] '.format(extra_info)
        log_out += str(log_in)
    if args.log_print:
        if pretty:
            log_out += 'Prettifying...'
            if isinstance(log_in, (dict, list)):
                print(
                    json.dumps(
                        log_in, indent=4, ensure_ascii=False
                    )
                )
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
                    log_out, ' ' * rem_len
                ), end='\r')
            else:
                print(log_out)
    else:
        log_out += '\n'
        _logfilename = envs.LOG_DIR / \
            '{}.log'.format(get_dt('revdate', sep='-'))
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
        log_function(log_in, color=color, pretty=pretty, sameline=sameline)
    if args.log_slow:
        sleep(3)


def log_more(
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
    if args.log_more:
        log_function(log_in, color=color, pretty=pretty, sameline=sameline)
    if args.log_slow:
        sleep(3)


def debug(
        log_in: str, color: str = None, extra_info: str = False,
        extra_color: str = None, pretty: bool = False,
        sameline: bool = False
):
    '''
    Log the input `log_in` as debug messages

    color           Specify the color for highlighting the function name:
                    black, red, green, yellow, blue, magenta, cyan, white.
                    If `color` is not specified, it will highlight in gre
    extra_info      Used to specify extra information in the logging
    extra_color     Color for the `extra_info`
    pretty          Prettify the output. Works on dict and list
    '''
    if args.debug:
        if extra_info is not None:
            log_function(
                log_in, color=color, extra_info=extra_info,
                extra_color=extra_color, pretty=pretty, sameline=sameline
            )
        else:
            log_function(
                log_in, color='yellow', pretty=pretty, sameline=sameline
            )
    if args.log_slow:
        sleep(3)


def db(
        log_in: str, color: str = 'magenta', extra_info: str = False,
        extra_color: str = None
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
        if extra_info is not None:
            log_function(
                log_in, color=color, extra_info=extra_info,
                extra_color=extra_color
            )
        else:
            log_function(
                log_in, color='magenta'
            )
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


async def log_to_bot_channel(content_in=None, content_embed_in=None):
    'Messages you want to send directly to a specific channel'
    log_channel = config.BOT_CHANNEL
    server_channels = {}

    for guild in config.bot.guilds:
        if str(guild.name).lower() == config.env('DISCORD_GUILD').lower():
            log.debug(f'Got guild {guild} ({type(guild)})')
        else:
            log.log(envs.GUILD_NOT_FOUND)
            guild = None

    # Get all channels and their IDs
    for channel in guild.text_channels:
        server_channels[channel.name] = channel.id
    log.debug(f'Got these channels: {server_channels}')
    if log_channel in server_channels:
        channel_out = config.bot.get_channel(server_channels[log_channel])
        msg_out = await channel_out.send(
            content=content_in,
            embed=discord.Embed.from_dict(content_embed_in) or None
        )
        return msg_out
    else:
        log.log(
            envs.POST_TO_NON_EXISTING_CHANNEL.format(
                log_channel
            )
        )
        return None
