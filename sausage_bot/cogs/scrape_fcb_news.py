#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from bs4 import BeautifulSoup
import requests
from discord.ext import commands, tasks
from sausage_bot.util import config, envs, feeds_core
from sausage_bot.util.log import log

team_channel_defaults = {
    'FIRSTTEAM': 'first-team',
    'FEMENI': 'femení',
    'ATLETIC': 'atlètic',
    'JUVENIL': 'juvenil',
    'CLUB': 'club'
}


class scrape_and_post(commands.Cog):
    '''
    A hardcoded cog - get newsposts from https://www.fcbarcelona.com and post
    them to specific team channels
    '''

    def __init__(self, bot):
        self.bot = bot

    # Tasks
    @tasks.loop(minutes=config.env('FCB_LOOP', default=5))
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
            root_url = 'https://www.fcbarcelona.com/en/football/'
            wanted_links = {
                'firstteam': [f'{root_url}first-team/news'],
                'femeni': [f'{root_url}womens-football/news'],
                'atletic': [f'{root_url}barca-atletic/news'],
                'juvenil': [
                    f'{root_url}fc-barcelona-u19a/news',
                    f'{root_url}barca-youth/news'
                ],
                'club': ['https://www.fcbarcelona.com/en/club/news']
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
                                except Exception as e:
                                    log.log(f'Kom over en feil: {e}')
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
                CHANNEL = config.env(
                    'FCB_{}'.format(team.upper()),
                    default=team_channel_defaults[team.upper()])
                try:
                    await feeds_core.process_links_for_posting_or_editing(
                        feed, FEED_POSTS[team], envs.scrape_logs_file,
                        CHANNEL
                    )
                except AttributeError as e:
                    log.log(str(e))
        return

    @post_fcb_news.before_loop
    async def before_post_fcb_news():
        '#autodoc skip#'
        log.verbose('`post_fcb_news` waiting for bot to be ready...')
        await config.bot.wait_until_ready()

    post_fcb_news.start()

    def cog_unload():
        'Cancel task if unloaded'
        log.log('Unloaded, cancelling tasks...')
        scrape_and_post.post_fcb_news.cancel()


async def setup(bot):
    log.log(envs.COG_STARTING.format('scrape_fcb_news'))
    await bot.add_cog(scrape_and_post(bot))
