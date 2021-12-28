#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from ratelimit import limits, sleep_and_retry
import requests
from hashlib import md5
import json
from discord.ext import commands, tasks
from discord_rss import file_io, _vars, log, _config, discord_commands
from discord_rss.datetime_funcs import get_dt
from discord_rss._args import args

import sys

@sleep_and_retry
@limits(calls=500, period=3600)
def fetch_sales_info():
    log.log_more('Kjører')
    API_URL = 'https://platprices.com/api.php?key={API_KEY}'\
        '&discount=1&region=NO'.format(
        API_KEY = _config.PLATPRICE_API_KEY
    )
    r = requests.get(API_URL)
    if r.status_code != 200:
        log.log('PlatPrices API returned {}'.format(r.status_code))
        log.log('Current API usage: {usage}/{limit}'.format(
            usage = r.json()['apiUsage'],
            limit = r.json()['apiLimit']
        ))
    else:
        log.log('Current API usage: {usage}/{limit}'.format(
            usage = r.json()['apiUsage'],
            limit = r.json()['apiLimit']
        ))
        return r.json()


def write_sales_if_new(sales_in):
    try:
        file_in = json.dumps(
            file_io.read_json(
                _vars.ps_sale_file
            )['discounts'], sort_keys=True
        )
    except(KeyError):
        file_in =  {}
    json_in = json.dumps(sales_in['discounts'], sort_keys=True)
    if file_in != json_in:
        log.log_more('Writing new sales file')
        file_io.write_json(_vars.ps_sale_file, sales_in)
        return True
    else:
        return False


def prettify_games(json_in):
    def strikethrough(text):
        result = ''
        for c in text:
            result = result + c + '\u0336'
        return result

    sale_json = json_in['discounts']
    sale_json.pop('HoursLow')
    sale_json.pop('HoursHigh')
    sale_log = file_io.read_json(_vars.ps_sale_log_file)
    out = ''
    for game_in_json in sale_json:
        GAME = sale_json[game_in_json]
        if type(GAME) is dict:
            game_id = GAME['PPID']
            game_discount_until = GAME['LastDiscounted']
            ref_id = '{}_{}'.format(game_id, game_discount_until)
            if ref_id not in sale_log:
                name = GAME['Name']
                ps_type = ''
                if int(GAME['IsPS4']) == 1 and int(GAME['IsPS5']) == 1:
                    ps_type += 'PS4/PS5'
                elif int(GAME['IsPS4']) == 1:
                    ps_type += 'PS4'            
                elif int(GAME['IsPS5']) == 1:
                    ps_type += 'PS5'
                price = GAME['formattedSalePrice']
                price_old = strikethrough(GAME['formattedBasePrice'])
                out += '{name} ({ps_type}): {price} ({price_old})'.format(
                    name = name, ps_type = ps_type, price = price,
                    price_old = price_old
                )
                file_io.add_to_list(_vars.ps_sale_log_file, ref_id)
            if game_in_json is not list(sale_json)[-1]:
                out += '\n'
    return out




class ps_sale_info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


#Tasks
#@tasks.loop(minutes = 1)
@tasks.loop(seconds = 20)
async def ps_store_sale():
    log.log('Starting `ps_store_sale`')
    channel_dict = {}
    for guild in _config.bot.guilds:
        if guild.name == _config.GUILD:
            # Get all channels and their IDs
            for channel in guild.text_channels:
                channel_dict[channel.name] = channel.id
            # Update the sales info
            new_sales = bool(write_sales_if_new(fetch_sales_info()))
            if not new_sales:
                log.log('No new game sales found')
                return
            elif new_sales:
                sales_json_in = file_io.read_json(_vars.ps_sale_file)
                log.log_more(
                    'Got {} new game sales'.format(
                        len(sales_json_in)
                    )
                )
                games_out = 'Spill som akkurat har kommet på tilbud:\n'
                games_out += prettify_games(sales_json_in)
                # Post sales info to channel
                channel = _config.GAME_CHANNEL
                if channel in channel_dict:
                    channel_out = _config.bot.get_channel(channel_dict[channel])
                    await channel_out.send(games_out)
            return


ps_store_sale.start()


def setup(bot):
    bot.add_cog(ps_sale_info(bot))
