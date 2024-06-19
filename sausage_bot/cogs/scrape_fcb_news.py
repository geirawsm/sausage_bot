#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from bs4 import BeautifulSoup
import requests
from discord.ext import commands, tasks
import discord
from sausage_bot.util import config, envs, feeds_core, db_helper
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

    fcb_group = discord.app_commands.Group(
        name="barca", description='Administer Barcelona-scraping'
    )

    @fcb_group.command(
        name='start', description='Start posting'
    )
    async def barca_posting_start(
        self, interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)
        log.log('Task started')
        scrape_and_post.post_fcb_news.start()
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[
                ('cog', 'barca_news'),
                ('task', 'post_news')
            ],
            updates=('status', 'started')
        )
        await interaction.followup.send(
            'Barca posting started'
        )

    @fcb_group.command(
        name='stop', description='Stop posting'
    )
    async def barca_posting_stop(
        self, interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)
        log.log('Task stopped')
        scrape_and_post.post_fcb_news.cancel()
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[
                ('cog', 'barca_news'),
                ('task', 'post_news'),
            ],
            updates=('status', 'stopped')
        )
        await interaction.followup.send(
            'Barca posting stopped'
        )

    # Tasks
    @tasks.loop(minutes=int(config.env('FCB_LOOP', default=5)))
    async def post_fcb_news():
        '''
        Post news from https://www.fcbarcelona.com to specific team channels
        '''
        def scrape_fcb_page(url):
            'Scrape https://www.fcbarcelona.com'
            scrape = requests.get(url)
            soup = BeautifulSoup(scrape.content, features='html5lib')
            return soup

        def barca_news_links():
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
                        log.error(f'Fikk feil ved henting av nyhetssaker: {e}')
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
                                    log.error(f'Kom over en feil: {e}')
                                    links[team] = []
                                    links[team].append(link)
                                index_items += 1
                        elif index_items >= max_items:
                            break
            return links

        feed = 'FCB news'
        FEED_POSTS = barca_news_links()
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
                        'rss', 'BARCA', FEED_POSTS[team], CHANNEL
                    )
                except AttributeError as e:
                    log.error(str(e))
        return

    @post_fcb_news.before_loop
    async def before_post_fcb_news():
        '#autodoc skip#'
        log.verbose('`post_fcb_news` waiting for bot to be ready...')
        await config.bot.wait_until_ready()


async def setup(bot):
    async def get_tasks():
        return await db_helper.get_output(
            template_info=envs.tasks_db_schema,
            select=('task', 'status'),
            where=('cog', 'barca_news')
        )

    log.log(envs.COG_STARTING.format('barca_news'))
    await bot.add_cog(scrape_and_post(bot))
    task_list = await get_tasks()
    log.debug(f'Got `task_list`: {task_list}')
    if task_list is None:
        await db_helper.insert_many_all(
            template_info=envs.tasks_db_schema,
            inserts=(
                ('barca_news', 'post_news', 'stopped')
            )
        )
        task_list = await get_tasks()
    for task in task_list:
        log.debug(f'checking task: {task}')
        if task[0] == 'post_news':
            if task[1] == 'started':
                log.debug(f'`{task[0]}` is set as `{task[1]}`, starting...')
                scrape_and_post.post_fcb_news.start()
            elif task[1] == 'stopped':
                log.debug(f'`{task[0]}` is set as `{task[1]}`')
                scrape_and_post.post_fcb_news.cancel()


async def teardown(bot):
    scrape_and_post.post_fcb_news.cancel()
