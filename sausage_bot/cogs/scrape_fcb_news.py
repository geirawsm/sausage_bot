#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from bs4 import BeautifulSoup
import requests
from time import sleep as sleep
from discord.ext import commands, tasks
from sausage_bot.funcs._args import args
from sausage_bot.funcs import _config, _vars, datetimefuncs, file_io, rss_core, discord_commands
from sausage_bot.log import log


class scrape_and_post(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    #Tasks
    @tasks.loop(minutes = 5)
    async def post_fcb_news():
        def scrape_fcb_page(url):
            scrape = requests.get(url)
            soup = BeautifulSoup(scrape.content, features='html5lib')
            return soup

        def scrape_fcb_news_links():
            wanted_links = {
                'firstteam': [
                    'https://www.fcbarcelona.com/en/football/first-team/news'
                ],
                'femeni': [
                    'https://www.fcbarcelona.com/en/football/womens-football/news'
                ],
                'atletic': [
                    'https://www.fcbarcelona.com/en/football/barca-atletic/news'
                ],
                'juvenil': [
                    'https://www.fcbarcelona.com/en/football/fc-barcelona-u19a/news',
                    'https://www.fcbarcelona.com/en/football/barca-youth/news'
                ]
            }
            links = {}
            root_url = 'https://www.fcbarcelona.com'
            for team in wanted_links:
                for wanted_link in wanted_links[team]:
                    main_dev = scrape_fcb_page(wanted_link).find('div', attrs={'class': 'widget__content-wrapper'})
                    news_dev = main_dev.find_all('div', attrs={'class': 'feed__items'})
                    max_items = 2
                    index_items = 0
                    for row in news_dev:
                        if index_items < max_items:
                            for news_item in row.find_all('a'):
                                link = news_item['href']
                                if link[0:4] == '/en/':
                                    link = f'{root_url}{link}'
                                try:
                                    links[team].append(link)
                                except:
                                    links[team] = []
                                    links[team].append(link)
                                index_items += 1
                        elif index_items >= max_items:
                            break
            return links
        
        feed = 'FCB news'
        FEED_POSTS = scrape_fcb_news_links()
        if len(FEED_POSTS) < 1:
            log.log(f'{feed}: this feed is empty')
            return
        else:
            log.log(
                f'{feed}: `FEED_POSTS` are good:\n'
                f'### {FEED_POSTS} ###'
                )
            for team in FEED_POSTS:
                CHANNEL = team.upper()
                sleep(2)
                await rss_core.process_links_for_posting_or_editing(
                    feed, FEED_POSTS[team], _vars.scrape_logs_file,
                    eval(f'_config.{CHANNEL}')
                )
        return

    @post_fcb_news.before_loop
    async def before_post_fcb_news():
        log.log_more('`post_fcb_news` waiting for bot to be ready...')
        await _config.bot.wait_until_ready()

    if args.no_scrape:
        log.log_more('Module loaded but tasks are disabled for this session')
    elif not args.no_scrape:
        post_fcb_news.start()


def setup(bot):
    bot.add_cog(scrape_and_post(bot))