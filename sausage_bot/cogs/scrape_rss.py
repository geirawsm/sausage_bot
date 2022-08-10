#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from bs4 import BeautifulSoup
import requests
from discord.ext import commands, tasks
from sausage_bot.funcs._args import args
from sausage_bot.funcs import _config, _vars, datetimefuncs, file_io, rss_core, discord_commands
from sausage_bot.log import log


class RSSscrape_and_post(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    #Tasks
    #@tasks.loop(minutes = 10)
    @tasks.loop(minutes = 1)
    async def post_fcb_news():
        def scrape_fcb():
            scrape = requests.get('https://www.fcbarcelona.com/en/football/first-team/news')
            soup = BeautifulSoup(scrape.content, features='html5lib')
            return soup

        def scrape_fcb_agreement_links():
            links = []
            root_url = 'https://www.fcbarcelona.com'
            main_dev = scrape_fcb().find('div', attrs={'class': 'widget__content-wrapper'})
            news_dev = main_dev.find_all('div', attrs={'class': 'feed__items'})
            max_items = 2
            index_items = 0
            for row in news_dev:
                if index_items < max_items:
                    for news_item in row.find_all('a'):
                        tag = news_item.find('div', attrs={'class': 'content-tag'}).text
                        news_text = news_item.find ('div', attrs={'class': 'thumbnail__text'}).text
                        if 'agreement' in news_text.lower():
                            link = news_item['href']
                            if link[0:4] == '/en/':
                                link = f'{root_url}{link}'
                            links.append(link)
                            index_items += 1
                elif index_items >= max_items:
                    break
            return links
        
        feed = 'fcb'
        CHANNEL = _config.RSS_SCRAPE_FCB_AGREEMENT_CHANNEL
        log.log('Checking {} ({})'.format(feed, CHANNEL))
        FEED_POSTS = scrape_fcb_agreement_links()
        if FEED_POSTS is None:
            log.log(f'{feed}: this feed returned NoneType.')
            return
        else:
            log.log(
                f'{feed}: `FEED_POSTS` are good:\n'
                f'### {FEED_POSTS} ###'
                )
        await rss_core.process_links_for_posting_or_editing(
            feed, FEED_POSTS, _vars.scrape_logs_file, CHANNEL
        )
        return

    @post_fcb_news.before_loop
    async def before_post_fcb_news():
        log.log_more('`post_fcb_news` waiting for bot to be ready...')
        await _config.bot.wait_until_ready()

    post_fcb_news.start()


def setup(bot):
    bot.add_cog(RSSscrape_and_post(bot))