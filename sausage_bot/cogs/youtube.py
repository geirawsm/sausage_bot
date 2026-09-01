#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"youtube: Autopost new videos from given Youtube channels"

import discord
from discord.ext import commands, tasks
from discord.app_commands import locale_str, describe
import typing
from time import sleep

# from yt_dlp import YoutubeDL
import re
from googleapiclient.discovery import build

from sausage_bot.util import config, envs, feeds_core, net_io
from sausage_bot.util import db_helper, discord_commands
from sausage_bot.util.datetime_handling import get_dt
from sausage_bot.util.i18n import I18N

logger = config.logger

# The `typing.Literal` choices for `/youtube list` are evaluated once, at
# import time, and discord hands the picked *value* back untranslated -
# only the name shown in the client is localized. Compare against the same
# constants the Literal was built from, and not a fresh `I18N.t()` call in
# whatever locale the guild happens to use, or nothing ever matches.
LIST_TYPE_NORMAL = I18N.t("youtube.commands.list.literal_list_type.normal")
LIST_TYPE_ADDED = I18N.t("youtube.commands.list.literal_list_type.added")
LIST_TYPE_FILTER = I18N.t("youtube.commands.list.literal_list_type.filter")
LINK_TYPE_CHANNEL = I18N.t("youtube.commands.list.literal_link_type.channel")
LINK_TYPE_PLAYLIST = I18N.t("youtube.commands.list.literal_link_type.playlist")

# Activate the Youtube API
youtube = build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)


class YouTubeAPI:
    "Manage the Youtube API"

    def __init__(self):
        super().__init__()

    def extract_yt_channel_info(url: str) -> dict | None:
        def get_channel_id_from_handle(handle: str) -> str | None:
            """handle uten @ foran, f.eks. 'MrBeast'"""
            request = youtube.channels().list(part="id", forHandle=handle)
            response = request.execute()

            if response["items"]:
                return response["items"][0]["id"]
            return None

        def get_channel_id_from_username(username: str) -> str | None:
            request = youtube.channels().list(part="id", forUsername=username)
            response = request.execute()

            if response["items"]:
                return response["items"][0]["id"]
            return None

        def get_channel_id_from_search(query: str) -> str | None:
            request = youtube.search().list(
                part="snippet", q=query, type="channel", maxResults=1
            )
            response = request.execute()

            if response["items"]:
                return response["items"][0]["snippet"]["channelId"]
            return None

        def get_uploads_playlist_id(channel_id: str) -> str:
            # TODO: Oversett til engelsk
            """Finner kanalens 'uploads'-spilleliste, som alltid inneholder alle videoene i publiseringsrekkefølge."""
            request = youtube.channels().list(part="contentDetails", id=channel_id)
            response = request.execute()

            if not response["items"]:
                raise ValueError(f"Fant ingen kanal med ID {channel_id}")

            return response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

        channel_id = ""
        if match := re.search(r"youtube\.com/channel/([\w-]+)", url):
            channel_id = match.group(1)
        if match := re.search(r"youtube\.com/@([\w.-]+)", url):
            channel_id = get_channel_id_from_handle(match.group(1))
        if match := re.search(r"youtube\.com/user/([\w-]+)", url):
            channel_id = get_channel_id_from_username(match.group(1))
        if match := re.search(r"youtube\.com/c/([\w-]+)", url):
            channel_id = get_channel_id_from_search(match.group(1))
        playlist_id = get_uploads_playlist_id(channel_id)
        if channel_id:
            return {"channel_id": channel_id, "playlist_id": playlist_id}
        else:
            return None

    def get_channel_info(channel_id: str) -> dict:
        request = youtube.channels().list(part="snippet", id=channel_id)
        response = request.execute()

        if not response["items"]:
            # TODO: i18n
            raise ValueError(f"Fant ingen kanal med ID {channel_id}")

        resp = response["items"][0]

        return {
            "title": resp["snippet"]["title"],
            "description": resp["snippet"]["description"],
            "id": resp["id"],
        }

    def get_playlist_info(playlist_id_or_url: str) -> dict:
        if "&list=" in playlist_id_or_url:
            playlist_id_or_url = playlist_id_or_url.split("&list=")[1]
        request = youtube.playlists().list(
            part="contentDetails,snippet", id=playlist_id_or_url, maxResults=1
        )
        response = request.execute()

        if not response["items"]:
            # TODO: i18n
            raise ValueError(f"Fant ingenting i spilleliste {playlist_id_or_url}")
        resp = response["items"][0]
        return {"channel_id": resp["snippet"]["channelId"], "playlist_id": resp["id"]}

    def get_playlist_items(playlist_id: str) -> dict:
        request = youtube.playlistItems().list(
            part="contentDetails,snippet", playlistId=playlist_id, maxResults=10
        )
        response = request.execute()

        if not response["items"]:
            # TODO: i18n
            raise ValueError(f"Fant ingenting i spilleliste {playlist_id}")
        resp = response["items"]
        video_ids = []
        for item in resp:
            video_ids.append(item["contentDetails"]["videoId"])
        return video_ids

    def get_latest_video_ids(playlist_id: str, max_results: int = 5) -> list[str]:
        """Henter de N siste video-ID-ene for ÉN spilleliste."""
        request = youtube.playlistItems().list(
            part="contentDetails", playlistId=playlist_id, maxResults=max_results
        )
        response = request.execute()

        return [item["contentDetails"]["videoId"] for item in response["items"]]

    def get_video_info(video_ids: dict[list[dict]]) -> list[dict]:
        """Henter tittel, kanalnavn, publiseringsdato og lenke (maks 50 ID-er per kall)."""
        results = []

        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]

            request = youtube.videos().list(part="snippet", id=",".join(batch))
            response = request.execute()

            for item in response["items"]:
                results.append(
                    {
                        "channel": item["snippet"]["channelTitle"],
                        "title": item["snippet"]["title"],
                        "description": item["snippet"]["description"],
                        "published": item["snippet"]["publishedAt"],
                        "id": item["id"],
                        "url": f"https://www.youtube.com/watch?v={item['id']}",
                    }
                )

        return results


async def feed_name_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    feed_names = [
        name["feed_name"]
        for name in await db_helper.get_output(
            template_info=envs.youtube_db_schema,
            select=("feed_name"),
            guild_id=interaction.guild.id,
        )
    ]
    return [
        discord.app_commands.Choice(name=feed_name, value=feed_name)
        for feed_name in feed_names
        if current.lower() in feed_name.lower()
    ][:25]


async def broken_feed_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    "Only the feeds that url errors have taken out of rotation"
    feed_names = [
        feed["feed_name"]
        for feed in await db_helper.get_output(
            template_info=envs.youtube_db_schema,
            select=("feed_name", "status_url"),
            guild_id=interaction.guild.id,
        )
        if feed["status_url"] != envs.FEEDS_URL_SUCCESS
    ]
    return [
        discord.app_commands.Choice(name=feed_name, value=feed_name)
        for feed_name in feed_names
        if current.lower() in feed_name.lower()
    ][:25]


async def youtube_filter_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[discord.app_commands.Choice[str]]:
    db_filters = await db_helper.get_combined_output(
        template_info_1=envs.youtube_db_schema,
        template_info_2=envs.youtube_db_filter_schema,
        key="uuid",
        select=["feed_name", "allow_or_deny", "filter"],
        order_by=[("allow_or_deny", "ASC"), ("filter", "ASC")],
        guild_id=interaction.guild.id,
    )
    logger.debug(f"filters: {db_filters}")
    return [
        discord.app_commands.Choice(
            name="{} - {} - {}".format(
                filter["feed_name"], filter["allow_or_deny"], filter["filter"]
            ),
            value=str(filter["filter"]),
        )
        for filter in db_filters
        if current.lower() in str(filter["filter"]).lower()
    ][:25]


class Youtube(commands.Cog):
    "Autopost new videos from given Youtube channels"

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    youtube_group = discord.app_commands.Group(
        name="youtube", description=locale_str(I18N.t("youtube.groups.youtube"))
    )

    youtube_filter_group = discord.app_commands.Group(
        name="filter",
        description=locale_str(I18N.t("youtube.groups.filter")),
        parent=youtube_group,
    )

    youtube_posting_group = discord.app_commands.Group(
        name="posting",
        description=locale_str(I18N.t("youtube.groups.posting")),
        parent=youtube_group,
    )

    @discord_commands.is_owner_or_manage_guild()
    @youtube_posting_group.command(
        name="start", description=locale_str(I18N.t("youtube.commands.start.cmd"))
    )
    async def youtube_posting_start(self, interaction: discord.Interaction):
        """
        Enable video posting for this guild. The background loop itself
        is shared, always-running infrastructure - this just flips this
        guild's own `tasks_db_schema` row.
        """
        await interaction.response.defer(ephemeral=True)
        logger.info(f"Enabling video posting for `{interaction.guild.name}`")
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[("cog", "youtube"), ("task", "post_videos")],
            updates=("status", "started"),
            guild_id=interaction.guild.id,
        )
        await interaction.followup.send(I18N.t("youtube.commands.start.msg_confirm"))

    @discord_commands.is_owner_or_manage_guild()
    @youtube_posting_group.command(
        name="stop", description=locale_str(I18N.t("youtube.commands.stop.cmd"))
    )
    async def youtube_posting_stop(self, interaction: discord.Interaction):
        "Disable video posting for this guild."
        await interaction.response.defer(ephemeral=True)
        logger.info(f"Disabling video posting for `{interaction.guild.name}`")
        await db_helper.update_fields(
            template_info=envs.tasks_db_schema,
            where=[
                ("task", "post_videos"),
                ("cog", "youtube"),
            ],
            updates=("status", "stopped"),
            guild_id=interaction.guild.id,
        )
        await interaction.followup.send(I18N.t("youtube.commands.stop.msg_confirm"))

    @discord_commands.is_owner()
    @youtube_posting_group.command(
        name="restart", description=locale_str(I18N.t("youtube.commands.restart.cmd"))
    )
    async def youtube_posting_restart(self, interaction: discord.Interaction):
        """
        Restart the shared background video-posting loop (all guilds).
        Useful for troubleshooting - not guild-scoped, since the loop
        itself is shared infrastructure.
        """
        await interaction.response.defer(ephemeral=True)
        logger.info("Video posting loop restarted")
        Youtube.task_post_videos.restart()
        await interaction.followup.send(I18N.t("youtube.commands.restart.msg_confirm"))

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(feed_name=feed_name_autocomplete)
    @youtube_group.command(
        name="add", description=locale_str(I18N.t("youtube.commands.add.cmd"))
    )
    @describe(
        feed_name=I18N.t("youtube.commands.add.desc.feed_name"),
        youtube_link=I18N.t("youtube.commands.add.desc.youtube_link"),
        channel=I18N.t("youtube.commands.add.desc.channel"),
    )
    async def youtube_add(
        self,
        interaction: discord.Interaction,
        feed_name: str,
        youtube_link: str,
        channel: discord.TextChannel,
    ):
        """
        Add a Youtube feed or playlist
        """
        await interaction.response.defer()
        AUTHOR = interaction.user.name
        # Get yt-id
        if "&list=" in youtube_link:
            youtube_info = YouTubeAPI.get_playlist_info(str(youtube_link))
        else:
            youtube_info = YouTubeAPI.extract_yt_channel_info(str(youtube_link))
            if youtube_info is None:
                # TODO: i18n
                print("Fant ikke kanal hos Youtube, riktig link?")
                return
        if youtube_info is None:
            await interaction.followup.send(
                I18N.t("youtube.commands.add.msg_empty_link", link=youtube_link),
            )
            return
        await feeds_core.add_to_feed_db(
            "youtube",
            str(feed_name),
            str(youtube_link),
            channel.id,
            AUTHOR,
            youtube_info["channel_id"],
            youtube_info["playlist_id"],
            guild_id=interaction.guild.id,
        )
        await discord_commands.log_to_bot_channel(
            interaction.guild,
            I18N.t(
                "youtube.commands.add.log_feed_confirm",
                user=AUTHOR,
                feed_name=feed_name,
                yt_link=youtube_link,
                channel=channel.name,
            ),
        )
        await interaction.followup.send(
            I18N.t(
                "youtube.commands.add.msg_added",
                feed_name=feed_name,
                channel_name=channel.name,
            )
        )
        return

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(feed_name=feed_name_autocomplete)
    @youtube_group.command(
        name="remove", description=locale_str(I18N.t("youtube.commands.remove.cmd"))
    )
    @describe(feed_name=I18N.t("youtube.commands.remove.desc.feed_name"))
    async def youtube_remove(self, interaction: discord.Interaction, feed_name: str):
        """
        Remove a Youtube feed
        """
        await interaction.response.defer()
        AUTHOR = interaction.user.name
        _uuid = await db_helper.get_output(
            template_info=envs.youtube_db_schema,
            select=("uuid"),
            where=(("feed_name", feed_name)),
            single=True,
            guild_id=interaction.guild.id,
        )
        if _uuid is None:
            logger.debug(f"The feed `{feed_name}` does not exist")
            await interaction.followup.send(
                I18N.t(
                    "youtube.commands.remove.msg_remove_non_existing_feed",
                    feed_name=feed_name,
                )
            )
            return
        removal = await feeds_core.remove_feed_from_db(
            feed_type="youtube", feed_name=feed_name, guild_id=interaction.guild.id
        )
        if removal:
            await discord_commands.log_to_bot_channel(
                interaction.guild,
                I18N.t(
                    "youtube.commands.remove.log_feed_removed",
                    feed_name=feed_name,
                    user_name=AUTHOR,
                ),
            )
            await interaction.followup.send(
                I18N.t("youtube.commands.remove.msg_feed_removed", feed_name=feed_name)
            )
        elif removal is False:
            # Couldn't remove the feed
            await interaction.followup.send(
                I18N.t(
                    "youtube.commands.remove.msg_feed_remove_failed",
                    feed_name=feed_name,
                )
            )
            # Also log and send error to either a bot-channel or admin
            await discord_commands.log_to_bot_channel(
                interaction.guild,
                I18N.t(
                    "youtube.commands.remove.log_feed_remove_failed",
                    user_name=AUTHOR,
                    feed_name=feed_name,
                ),
            )
        return

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(feed_name=feed_name_autocomplete)
    @youtube_filter_group.command(
        name="add", description=locale_str(I18N.t("youtube.commands.filter_add.cmd"))
    )
    @describe(
        feed_name=I18N.t("youtube.commands.filter_add.desc.feed_name"),
        allow_deny=I18N.t("youtube.commands.filter_add.desc.allow_deny"),
        filters_in=I18N.t("youtube.commands.filter_add.desc.filters_in"),
    )
    async def youtube_filter_add(
        self,
        interaction: discord.Interaction,
        feed_name: str,
        allow_deny: typing.Literal[
            I18N.t("common.literal_allow_deny.allow"),
            I18N.t("common.literal_allow_deny.deny"),
        ],
        filters_in: str,
    ):
        """
        Add filter for feed (deny/allow)
        """
        await interaction.response.defer(ephemeral=True)
        _uuid = await db_helper.get_output(
            template_info=envs.youtube_db_schema,
            select=("uuid"),
            where=(("feed_name", feed_name)),
            single=True,
            guild_id=interaction.guild.id,
        )
        # One filter per command, stored whole - unlike rss, which splits
        # its input on `envs.input_split_regex`. That keeps phrases like
        # `let's play` usable as a single filter here.
        _inserts = [(_uuid["uuid"], allow_deny, filters_in)]
        adding_filter = await db_helper.insert_many_all(
            template_info=envs.youtube_db_filter_schema,
            inserts=_inserts,
            guild_id=interaction.guild.id,
        )
        if adding_filter:
            await interaction.followup.send(
                I18N.t(
                    "youtube.commands.filter_add.msg_filter_added",
                    allow_deny=allow_deny,
                    filter_in=filters_in,
                ),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                I18N.t("youtube.commands.filter_add.msg_filter_failed"), ephemeral=True
            )
        return

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(feed_name=feed_name_autocomplete)
    @discord.app_commands.autocomplete(filter_in=youtube_filter_autocomplete)
    @youtube_filter_group.command(
        name="remove",
        description=locale_str(I18N.t("youtube.commands.filter_remove.cmd")),
    )
    @describe(
        feed_name=I18N.t("youtube.commands.filter_remove.desc.feed_name"),
        filter_in=I18N.t("youtube.commands.filter_remove.desc.filter_in"),
    )
    async def youtube_filter_remove(
        self, interaction: discord.Interaction, feed_name: str, filter_in: str
    ):
        """
        Remove filter for feed
        """
        await interaction.response.defer(ephemeral=True)
        _uuid = await db_helper.get_output(
            template_info=envs.youtube_db_schema,
            select=("uuid"),
            where=(("feed_name", feed_name)),
            single=True,
            guild_id=interaction.guild.id,
        )
        removing_filter = await db_helper.del_row_by_AND_filter(
            template_info=envs.youtube_db_filter_schema,
            where=(("uuid", _uuid["uuid"]), ("filter", filter_in)),
            guild_id=interaction.guild.id,
        )
        if removing_filter:
            await interaction.followup.send(
                I18N.t(
                    "youtube.commands.filter_remove.msg_confirm", filter_in=filter_in
                ),
                ephemeral=True,
            )
            logger.info(f"Youtube filter '{filter_in}' removed from feed '{feed_name}'")
        else:
            await interaction.followup.send(
                I18N.t("youtube.commands.filter_remove.msg_error", filter_in=filter_in),
                ephemeral=True,
            )
        return

    @youtube_group.command(
        name="list", description=locale_str(I18N.t("youtube.commands.list.cmd"))
    )
    @describe(
        list_type=I18N.t("youtube.commands.list.desc.list_type"),
        link_type=I18N.t("youtube.commands.list.desc.link_type"),
    )
    async def youtube_list(
        self,
        interaction: discord.Interaction,
        list_type: typing.Literal[
            LIST_TYPE_NORMAL,
            LIST_TYPE_ADDED,
            LIST_TYPE_FILTER,
        ],
        link_type: typing.Literal[
            LINK_TYPE_CHANNEL,
            LINK_TYPE_PLAYLIST,
        ] = None,
    ):
        """
        List all active Youtube feeds
        """
        await interaction.response.defer()
        # `get_feed_list` takes untranslated types, so don't pass the
        # literals along as they are
        if link_type == LINK_TYPE_CHANNEL:
            link_type_in = "channel"
        elif link_type == LINK_TYPE_PLAYLIST:
            link_type_in = "playlist"
        else:
            link_type_in = None
        if list_type == LIST_TYPE_ADDED:
            formatted_list = await feeds_core.get_feed_list(
                guild=interaction.guild,
                db_in=envs.youtube_db_schema,
                list_type="added",
                link_type=link_type_in,
            )
        elif list_type == LIST_TYPE_FILTER:
            formatted_list = await feeds_core.get_feed_list(
                guild=interaction.guild,
                db_in=envs.youtube_db_schema,
                db_filter_in=envs.youtube_db_filter_schema,
                list_type="filter",
                link_type=link_type_in,
            )
        else:
            formatted_list = await feeds_core.get_feed_list(
                guild=interaction.guild,
                db_in=envs.youtube_db_schema,
                link_type=link_type_in,
            )
        if formatted_list is not None:
            page_counter = 0
            for page in formatted_list:
                page_counter += 1
                logger.debug(f"Sending page ({page_counter} / {len(formatted_list)})")
                await interaction.followup.send(f"```{page}```")
                sleep(1)
        else:
            await interaction.followup.send(I18N.t("youtube.commands.list.msg_error"))
        return

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(feed_name=broken_feed_autocomplete)
    @youtube_group.command(
        name="reset_url_errors",
        description=locale_str(I18N.t("youtube.commands.reset_url_errors.cmd")),
    )
    @describe(feed_name=I18N.t("youtube.commands.reset_url_errors.desc.feed_name"))
    async def youtube_reset_url_errors(
        self, interaction: discord.Interaction, feed_name: str = None
    ):
        """
        Put feeds that url errors took out of rotation back to work
        """
        await interaction.response.defer()
        reset = await feeds_core.reset_url_errors(
            envs.youtube_db_schema, interaction.guild, feed_name
        )
        if not reset:
            await interaction.followup.send(
                I18N.t("youtube.commands.reset_url_errors.msg_nothing_to_reset")
            )
            return
        await interaction.followup.send(
            I18N.t(
                "youtube.commands.reset_url_errors.msg_confirm",
                feeds="\n- ".join(reset),
            )
        )
        await discord_commands.log_to_bot_channel(
            interaction.guild,
            I18N.t(
                "youtube.commands.reset_url_errors.log_reset",
                feeds="\n- ".join(reset),
                user_name=interaction.user.name,
            ),
        )
        return

    # async def get_youtube_info(url):
    #     "Use yt-dlp to get info about a channel"
    #     # Get more yt-dlp opts here:
    #     # https://github.com/ytdl-org/youtube-dl/blob/3e4cedf9e8cd3157df2457df7274d0c842421945/youtube_dl/YoutubeDL.py#L137-L312
    #     ydl_opts = {
    #         "simulate": True,
    #         "download": False,
    #         "playlistend": 2,
    #         "ignoreerrors": True,
    #         "quiet": True,
    #     }
    #     try:
    #         with YoutubeDL(ydl_opts) as ydl:
    #             return ydl.extract_info(url)
    #     except Exception as _error:
    #         logger.error(f"Could not extract youtube info: {_error}")
    #         return None

    # Tasks
    @tasks.loop(minutes=config.YT_LOOP, reconnect=True)
    async def task_post_videos():
        logger.info("Starting `post_videos`")
        approved_guilds = await db_helper.get_output(
            envs.guilds_db_schema, where=("status", "approved")
        )
        for guild_row in approved_guilds:
            guild = config.bot.get_guild(int(guild_row["guild_id"]))
            if guild is None:
                logger.debug(f"Guild `{guild_row['guild_id']}` not in cache, skipping")
                continue
            task_status = await db_helper.get_output(
                template_info=envs.tasks_db_schema,
                where=[("cog", "youtube"), ("task", "post_videos")],
                select=("status"),
                single=True,
                guild_id=guild.id,
            )
            if task_status.get("status") != "started":
                logger.debug(
                    f"`post_videos` is not enabled for `{guild.name}`, skipping"
                )
                continue
            async with db_helper.guild_locale_context(guild.id):
                # Start processing feeds
                feeds = await db_helper.get_output(
                    template_info=envs.youtube_db_schema,
                    order_by=[("feed_name", "DESC")],
                    where=[
                        ("status_url", envs.FEEDS_URL_SUCCESS),
                        ("status_channel", envs.CHANNEL_STATUS_SUCCESS),
                    ],
                    guild_id=guild.id,
                )
                if len(feeds) == 0 or feeds is None:
                    logger.debug(f"Couldn't find any Youtube feeds for `{guild.name}`")
                    continue
                logger.debug(f"Got these feeds for `{guild.name}`:")
                for feed in feeds:
                    logger.debug("- {}".format(feed["feed_name"]))
                video_queue = []
                video_channels = {}
                video_uuids = {}
                # Get videos from each feed and add to a queue
                for feed in feeds:
                    UUID = feed["uuid"]
                    FEED_NAME = feed["feed_name"]
                    CHANNEL = feed["channel"]
                    logger.info(f"Checking {FEED_NAME}")
                    logger.debug(f"Found channel `{CHANNEL}` in `{FEED_NAME}`")
                    # Hente de siste videoene til kanalen
                    last_videos = YouTubeAPI.get_latest_video_ids(feed["playlist_id"])
                    for video in last_videos:
                        video_channels[video] = CHANNEL
                        video_uuids[video] = UUID
                    video_queue += last_videos
                video_infos = YouTubeAPI.get_video_info(video_queue)
                log_db = await db_helper.get_output(
                    template_info=envs.youtube_db_log_schema,
                    guild_id=guild.id,
                    select=("url"),
                    single_col_results=True,
                )
                unlogged_videos = []
                for video in video_infos:
                    if video["url"] not in log_db:
                        logger.info(
                            "Video '{} - {}' not found in logs, posting".format(
                                video["channel"], video["title"]
                            )
                        )
                        unlogged_videos.append(video)
                    else:
                        logger.info(
                            "Video '{} - {}' found in logs, will not post!".format(
                                video["channel"], video["title"]
                            )
                        )
                # A filter row belongs to one feed, so every video is
                # judged against its own feed's filters only - a deny on
                # `feed a` must not silence `feed b`. `filter_the_links`
                # is the same allow/deny handling the rss feeds get, so
                # `FEED_FILTER_PRIORITY` means the same thing everywhere.
                filtered_videos = []
                for feed in feeds:
                    UUID = feed["uuid"]
                    feed_videos = [
                        video
                        for video in unlogged_videos
                        if video_uuids.get(video["id"]) == UUID
                    ]
                    if len(feed_videos) == 0:
                        continue
                    filters_db = await db_helper.get_output(
                        template_info=envs.youtube_db_filter_schema,
                        select=("allow_or_deny", "filter"),
                        where=[("uuid", UUID)],
                        guild_id=guild.id,
                    )
                    # [{'allow_or_deny': 'Deny', 'filter': 'omarchy'}]
                    filtered_videos += net_io.FilterLinks(
                        {"items": feed_videos, "filters": filters_db}
                    ).filter_the_links()
                for video in filtered_videos[::-1]:
                    if video["id"] in video_channels:
                        await discord_commands.post_to_channel(
                            channel_id=video_channels[video["id"]],
                            content_in=str(video["url"]),
                        )
                        await db_helper.insert_many_all(
                            template_info=envs.youtube_db_log_schema,
                            inserts=(
                                (
                                    video_uuids[video["id"]],
                                    video["url"],
                                    str(
                                        await get_dt(
                                            format="datetimeobject", no_timezone=True
                                        )
                                    ),
                                )
                            ),
                            guild_id=guild.id,
                        )
        logger.info("Done with posting")

    @task_post_videos.before_loop
    async def before_post_new_videos():
        "#autodoc skip#"
        logger.debug("`post_videos` waiting for bot to be ready...")
        await config.bot.wait_until_ready()

    # Slower than `post_videos` on purpose: a feed only lands here after
    # 3 failures in a row, and hammering a source that just throttled us
    # is what got every feed deactivated in the first place.
    @tasks.loop(hours=6, reconnect=True)
    async def task_retry_failed():
        logger.info("Starting `retry_failed`")
        approved_guilds = await db_helper.get_output(
            envs.guilds_db_schema, where=("status", "approved")
        )
        for guild_row in approved_guilds:
            guild = config.bot.get_guild(int(guild_row["guild_id"]))
            if guild is None:
                logger.debug(f"Guild `{guild_row['guild_id']}` not in cache, skipping")
                continue
            # Gated on `post_videos`: retrying feeds nobody is posting
            # would only be noise in the bot channel
            task_status = await db_helper.get_output(
                template_info=envs.tasks_db_schema,
                where=[("cog", "youtube"), ("task", "post_videos")],
                select=("status"),
                single=True,
                guild_id=guild.id,
            )
            if task_status.get("status") != "started":
                logger.debug(
                    f"`post_videos` is not enabled for `{guild.name}`, skipping"
                )
                continue
            async with db_helper.guild_locale_context(guild.id):
                await feeds_core.retry_failed("youtube", envs.youtube_db_schema, guild)
        logger.info("Done with retrying")
        return

    @task_retry_failed.before_loop
    async def before_retry_failed():
        "#autodoc skip#"
        logger.debug("`retry_failed` waiting for bot to be ready...")
        await config.bot.wait_until_ready()


# The Youtube data used to be split over two files: `youtube_feeds.sqlite`
# held the feeds (in a table named after the file) plus the filters, and
# `youtube_log.sqlite` held the post log. All three are tables in a single
# `youtube.sqlite` now - see `envs.youtube_db_schema` and friends.
LEGACY_FEEDS_DB_FILE = "youtube_feeds.sqlite"
LEGACY_FEEDS_TABLE = "youtube_feeds"
LEGACY_FILTER_TABLE = "filter"
LEGACY_LOG_DB_FILE = "youtube_log.sqlite"
LEGACY_LOG_TABLE = "log"


async def migrate_legacy_youtube_tables(guild):
    """
    Move a guild's Youtube data out of the old `youtube_feeds.sqlite` and
    `youtube_log.sqlite` and into `youtube.sqlite`.

    Without this the new, empty tables simply hide the old rows: the
    guild's feeds disappear from `/youtube list`, and - worse - an empty
    post log makes `task_post_videos` treat every video it finds as
    unposted and repost the lot.

    The legacy files are left on disk untouched. Safe to call repeatedly
    (idempotent): `db_copy_table_between_files()` skips any table that
    already holds rows. #autodoc skip#
    """
    db_dir = envs.guild_db_dir(guild.id)
    legacy_feeds_db = db_dir / LEGACY_FEEDS_DB_FILE
    legacy_log_db = db_dir / LEGACY_LOG_DB_FILE
    if not legacy_feeds_db.is_file() and not legacy_log_db.is_file():
        logger.debug(f"No legacy youtube databases for `{guild.name}`")
        return
    logger.info(f"Found legacy youtube database(s) for `{guild.name}`, migrating")
    copied = {
        "feeds": await db_helper.db_copy_table_between_files(
            source_db_file=legacy_feeds_db,
            source_table=LEGACY_FEEDS_TABLE,
            template_info=envs.youtube_db_schema,
            guild_id=guild.id,
        ),
        "filters": await db_helper.db_copy_table_between_files(
            source_db_file=legacy_feeds_db,
            source_table=LEGACY_FILTER_TABLE,
            template_info=envs.youtube_db_filter_schema,
            guild_id=guild.id,
        ),
        # The old log also had a `hash` column, used back when videos
        # were deduplicated on their description. It is not in the
        # schema anymore, so it is simply not carried over.
        "log entries": await db_helper.db_copy_table_between_files(
            source_db_file=legacy_log_db,
            source_table=LEGACY_LOG_TABLE,
            template_info=envs.youtube_db_log_schema,
            guild_id=guild.id,
        ),
    }
    if sum(copied.values()) == 0:
        logger.info(f"Nothing left to migrate for `{guild.name}`")
        return
    _msg = (
        "Migrated youtube data to `{}`: {}. The old `{}` and `{}` are no "
        "longer in use, but were left in `{}`.".format(
            envs.youtube_db_schema["db_file"],
            ", ".join(f"{count} {name}" for name, count in copied.items()),
            LEGACY_FEEDS_DB_FILE,
            LEGACY_LOG_DB_FILE,
            db_dir,
        )
    )
    logger.info(_msg)
    await discord_commands.log_to_bot_channel(guild, _msg)


async def ensure_guild_youtube_tables(guild):
    """
    Prep this guild's Youtube tables, and fix up any legacy channel-name
    data. Safe to call repeatedly (idempotent).
    #autodoc skip#
    """
    await db_helper.prep_table(table_in=envs.youtube_db_schema, guild_id=guild.id)
    await db_helper.prep_table(
        table_in=envs.youtube_db_filter_schema, guild_id=guild.id
    )
    await db_helper.prep_table(table_in=envs.youtube_db_log_schema, guild_id=guild.id)
    missing_tbl_cols = {}
    missing_tbl_cols = await db_helper.add_missing_db_setup(
        envs.youtube_db_schema, missing_tbl_cols, guild_id=guild.id
    )
    missing_tbl_cols = await db_helper.add_missing_db_setup(
        envs.youtube_db_filter_schema, missing_tbl_cols, guild_id=guild.id
    )
    missing_tbl_cols = await db_helper.add_missing_db_setup(
        envs.youtube_db_log_schema, missing_tbl_cols, guild_id=guild.id
    )
    # Carry over data from the two databases this cog used to keep. Has
    # to happen after the tables above are up to date, and before the
    # fixups below, so the migrated rows get repaired too.
    await migrate_legacy_youtube_tables(guild)
    logger.debug(
        f"youtube db for `{guild.name}`: `missing_tbl_cols` is {missing_tbl_cols}"
    )
    if any(len(missing_tbl_cols[table]) > 0 for table in missing_tbl_cols):
        missing_tbl_cols_text = ""
        for _tbl in missing_tbl_cols:
            missing_tbl_cols_text += "{}:".format(_tbl)
            for col in missing_tbl_cols[_tbl]:
                missing_tbl_cols_text += "\n{}".format(" - ".join(col))
            if _tbl != list(missing_tbl_cols.keys())[-1]:
                missing_tbl_cols_text += "\n\n"
        await discord_commands.log_to_bot_channel(
            guild,
            "Missing columns in youtube db: {}\n"
            "Make sure to populate missing information".format(missing_tbl_cols_text),
        )
    # Put back the uuid on filter rows that got a whole db row written
    # into the column instead
    await db_helper.db_fix_dict_uuid_in_filters(
        template_info=envs.youtube_db_filter_schema, guild_id=guild.id
    )
    # Change channel name to id
    await db_helper.db_channel_names_to_ids(
        template_info=envs.youtube_db_schema,
        id_col="uuid",
        channel_col="channel",
        guild=guild,
    )


async def setup(bot):
    cog_name = "youtube"
    logger.info(envs.COG_STARTING.format(cog_name))
    logger.debug("Checking db")

    approved_guilds = await db_helper.get_output(
        envs.guilds_db_schema, where=("status", "approved")
    )
    for guild_row in approved_guilds:
        guild = config.bot.get_guild(int(guild_row["guild_id"]))
        if guild is None:
            continue
        await ensure_guild_youtube_tables(guild)
        await db_helper.ensure_guild_tasks_rows(guild.id)

    logger.debug("Registering cog to bot")
    await bot.add_cog(Youtube(bot))
    logger.info(envs.COG_STARTED.format(cog_name))

    # Shared, always-running loop - each tick checks every guild's own
    # tasks_db_schema row to decide whether to process that guild.
    Youtube.task_post_videos.start()
    Youtube.task_retry_failed.start()


async def teardown(bot):
    Youtube.task_post_videos.cancel()
    Youtube.task_retry_failed.cancel()
