#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from bs4 import BeautifulSoup
import requests
from time import sleep as sleep
from discord.ext import commands, tasks
from sausage_bot.util.args import args
from sausage_bot.util import config, envs, feeds_core
from sausage_bot.util.log import log

env_template = {
    'firstteam': 'first-team',
    'femeni': 'femení',
    'atletic': 'atlètic',
    'juvenil': 'juvenil',
    'club': 'club'
}
config.add_cog_envs_to_env_file('scrape_fcb_news', env_template)

env = config.config()['scrape_fcb_news']


class scrape_and_post(commands.Cog):
    '''
    A hardcoded cog - get newsposts from https://www.fcbarcelona.com and post
    them to specific team channels
    '''

    def __init__(self, bot):
        self.bot = bot

    # Tasks
    @tasks.loop(minutes=5)
    async def post_fcb_news():
        '''
        Post news from https://www.fcbarcelona.com to specific team channels
        '''
        def scrape_fcb_page(url):
            'Scrape https://www.fcbarcelona.com'
            scrape = requests.get(url)
            soup = BeautifulSoup(scrape.content, features='html5lib')
            return soup

        def scrape_fcb_news_links():
            'Find links for specific team news and return it as a dict'
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
                ],
                'club': [
                    'https://www.fcbarcelona.com/en/club/news'
                ]
            }
            links = {}
            root_url = 'https://www.fcbarcelona.com'
            for team in wanted_links:
                for wanted_link in wanted_links[team]:
                    try:
                        main_dev = scrape_fcb_page(wanted_link).find(
                            'div', attrs={'class': 'widget__content-wrapper'})
                        news_dev = main_dev.find_all(
                            'div', attrs={'class': 'feed__items'})
                    except (AttributeError) as e:
                        log.log(f'Fikk feil ved henting av nyhetssaker: {e}')
                        return None
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
        if FEED_POSTS is None:
            return
        if len(FEED_POSTS) < 1:
            log.log(f'{feed}: this feed is empty')
            return
        else:
            log.log(
                f'{feed}: `FEED_POSTS` are good:\n'
                f'### {FEED_POSTS} ###'
            )
            for team in FEED_POSTS:
                CHANNEL = team.lower()
                try:
                    await feeds_core.process_links_for_posting_or_editing(
                        feed, FEED_POSTS[team], envs.scrape_logs_file,
                        env[CHANNEL]
                    )
                except AttributeError as e:
                    log.log(str(e))
        return

    @post_fcb_news.before_loop
    async def before_post_fcb_news():
        '#autodoc skip#'
        log.log_more('`post_fcb_news` waiting for bot to be ready...')
        await config.bot.wait_until_ready()

    post_fcb_news.start()


async def setup(bot):
    log.log(envs.COG_STARTING.format('scrape_fcb_news'))
    await bot.add_cog(scrape_and_post(bot))
