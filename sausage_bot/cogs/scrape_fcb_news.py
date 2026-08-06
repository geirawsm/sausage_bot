#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
scrape_fcb_news: A hardcoded cog - get newsposts from
https://www.fcbarcelona.com and post them to specific team channels
"""

from bs4 import BeautifulSoup
import requests
from discord.ext import commands, tasks
import discord
from sausage_bot.util import config, envs, feeds_core, db_helper
from sausage_bot.util import discord_commands

logger = config.logger

team_channel_defaults = {
    "FIRSTTEAM": "first-team",
    "FEMENI": "femení",
    "ATLETIC": "atlètic",
    "JUVENIL": "juvenil",
    "CLUB": "club",
}


class scrape_and_post(commands.Cog):
    """
    A hardcoded cog - get newsposts from https://www.fcbarcelona.com and post
    them to specific team channels
    """

    def __init__(self, bot):
        self.bot = bot

    fcb_group = discord.app_commands.Group(
        name="barca", description="Administer Barcelona-scraping"
    )

    @discord_commands.is_owner_or_manage_guild()
    @fcb_group.command(name="start", description="Start posting")
    async def barca_posting_start(self, interaction: discord.Interaction):
        "Enable Barca posting for this guild."
        await interaction.response.defer(ephemeral=True)
        logger.info(f"Enabling barca posting for `{interaction.guild.name}`")
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[("cog", "barca_news"), ("task", "post_news")],
            updates=("status", "started"),
            guild_id=interaction.guild.id,
        )
        await interaction.followup.send("Barca posting started")

    @discord_commands.is_owner_or_manage_guild()
    @fcb_group.command(name="stop", description="Stop posting")
    async def barca_posting_stop(self, interaction: discord.Interaction):
        "Disable Barca posting for this guild."
        await interaction.response.defer(ephemeral=True)
        logger.info(f"Disabling barca posting for `{interaction.guild.name}`")
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[
                ("cog", "barca_news"),
                ("task", "post_news"),
            ],
            updates=("status", "stopped"),
            guild_id=interaction.guild.id,
        )
        await interaction.followup.send("Barca posting stopped")

    # Tasks
    @tasks.loop(minutes=config.FCB_LOOP, reconnect=True)
    async def post_fcb_news():
        """
        Post news from https://www.fcbarcelona.com to specific team channels
        """

        def scrape_fcb_page(url):
            "Scrape https://www.fcbarcelona.com"
            scrape = requests.get(url)
            soup = BeautifulSoup(scrape.content, features="html5lib")
            return soup

        def barca_news_links():
            "Find links for specific team news and return it as a dict"
            root_url = "https://www.fcbarcelona.com/en/football/"
            wanted_links = {
                "firstteam": [f"{root_url}first-team/news"],
                "femeni": [f"{root_url}womens-football/news"],
                "atletic": [f"{root_url}barca-atletic/news"],
                "juvenil": [
                    f"{root_url}fc-barcelona-u19a/news",
                    f"{root_url}barca-youth/news",
                ],
                "club": ["https://www.fcbarcelona.com/en/club/news"],
            }
            links = {}
            root_url = "https://www.fcbarcelona.com"
            for team in wanted_links:
                for wanted_link in wanted_links[team]:
                    try:
                        main_dev = scrape_fcb_page(wanted_link).find(
                            "div", attrs={"class": "widget__content-wrapper"}
                        )
                        news_dev = main_dev.find_all(
                            "div", attrs={"class": "feed__items"}
                        )
                    except AttributeError as e:
                        logger.error(f"Error when fetching articles: {e}")
                        return None
                    max_items = 2
                    index_items = 0
                    for row in news_dev:
                        if index_items < max_items:
                            for news_item in row.find_all("a"):
                                link = news_item["href"]
                                if link[0:4] == "/en/":
                                    link = f"{root_url}{link}"
                                if team not in links:
                                    links[team] = []
                                links[team].append(link)
                                index_items += 1
                        elif index_items >= max_items:
                            break
            return links

        feed = "FCB news"
        FEED_POSTS = barca_news_links()
        if FEED_POSTS is None:
            return
        if len(FEED_POSTS) < 1:
            logger.info(f"{feed}: this feed is empty")
            return
        logger.info(f"{feed}: `FEED_POSTS` are good:\n### {FEED_POSTS} ###")
        approved_guilds = await db_helper.get_output(
            envs.guilds_db_schema, where=("status", "approved")
        )
        for guild_row in approved_guilds:
            guild = config.bot.get_guild(int(guild_row["guild_id"]))
            if guild is None:
                continue
            task_status = await db_helper.get_output(
                template_info=envs.tasks_db_schema,
                where=[("cog", "barca_news"), ("task", "post_news")],
                select=("status"),
                single=True,
                guild_id=guild.id,
            )
            if task_status.get("status") != "started":
                logger.debug(
                    f"`post_news` is not enabled for `{guild.name}`, skipping"
                )
                continue
            guild_channels = discord_commands.get_text_channel_list(guild)
            for team in FEED_POSTS:
                channel_name = team_channel_defaults[team.upper()]
                if channel_name not in guild_channels:
                    error_msg = f"Could not find channel `{channel_name}` in guild"
                    logger.error(error_msg)
                    # TODO: i18n
                    await discord_commands.log_to_bot_channel(guild, error_msg)
                    continue
                CHANNEL = guild.get_channel(guild_channels[channel_name]).id
                try:
                    await feeds_core.process_links_for_posting_or_editing(
                        feed_name=f"{feed} - {team}",
                        feed_type="rss",
                        uuid=f"barca_{team}",
                        FEED_POSTS=FEED_POSTS[team],
                        CHANNEL=CHANNEL,
                        guild=guild,
                    )
                except AttributeError as e:
                    logger.error(str(e))
        return

    @post_fcb_news.before_loop
    async def before_post_fcb_news():
        "#autodoc skip#"
        logger.debug("`post_fcb_news` waiting for bot to be ready...")
        await config.bot.wait_until_ready()


async def setup(bot):
    logger.info(envs.COG_STARTING.format("barca_news"))

    approved_guilds = await db_helper.get_output(
        envs.guilds_db_schema, where=("status", "approved")
    )
    for guild_row in approved_guilds:
        guild = config.bot.get_guild(int(guild_row["guild_id"]))
        if guild is None:
            continue
        await db_helper.ensure_guild_tasks_rows(guild.id)

    await bot.add_cog(scrape_and_post(bot))
    logger.info(envs.COG_STARTED.format("barca_news"))

    # Shared, always-running loop - each tick checks every guild's own
    # tasks_db_schema row to decide whether to process that guild.
    scrape_and_post.post_fcb_news.start()


def teardown(bot):
    scrape_and_post.post_fcb_news.cancel()
