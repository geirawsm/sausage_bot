#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"feeds_core: Core functions for RSS and Youtube feeds"

from bs4 import BeautifulSoup
from lxml import etree
from tabulate import tabulate
from uuid import uuid4
import discord
import re
from pprint import pformat
from time import monotonic

from sausage_bot.util import config, envs, datetime_handling
from sausage_bot.util import discord_commands, net_io, db_helper
from sausage_bot.util.args import args
from sausage_bot.util.i18n import I18N

logger = config.logger

# A dead channel affects every feed posting to it, so warn about the
# channel once and stay quiet for a while instead of sending one message
# per video. Keyed on (guild id, channel), holding a `time.monotonic()`
# reading, which is immune to the wall clock being adjusted.
DEAD_CHANNEL_ALERT_COOLDOWN = 60 * 10
dead_channel_alerts = {}


class DynamicRatingSelect(
    discord.ui.DynamicItem[discord.ui.Select],
    template=r"rating.show:(?P<show_uuid>.*):episode:(?P<episode_uuid>.*)",
):
    def __init__(self, show_uuid: str, episode_uuid: str) -> None:
        self.show_uuid: str = show_uuid
        self.episode_uuid: str = episode_uuid
        super().__init__(
            discord.ui.Select(
                custom_id=f"rating.show:{show_uuid}:episode:{episode_uuid}",
                placeholder="★ Rate this episode ★",
                min_values=1,
                max_values=1,
                options=[
                    discord.SelectOption(
                        label="★", value="1", description="1 star", default=False
                    ),
                    discord.SelectOption(
                        label="★★", value="2", description="2 stars", default=False
                    ),
                    discord.SelectOption(
                        label="★★★", value="3", description="3 stars", default=False
                    ),
                    discord.SelectOption(
                        label="★★★★", value="4", description="4 stars", default=False
                    ),
                    discord.SelectOption(
                        label="★★★★★", value="5", description="5 stars", default=False
                    ),
                ],
            )
        )
        self.show_uuid = show_uuid
        self.episode_uuid = episode_uuid

    # This method actually extracts the information from the custom ID and
    # creates the item.
    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Select,
        match: re.Match[str],
        /,
    ):
        show_uuid = str(match["show_uuid"])
        episode_uuid = str(match["episode_uuid"])
        return cls(show_uuid, episode_uuid)

    async def callback(self, interaction: discord.Interaction) -> None:
        self.rating = self.item.values[0]
        self.custom_id = "rating.show:{}:episode:{}".format(
            self.show_uuid, self.episode_uuid
        )
        uuid_checks = await db_helper.get_output(
            template_info=envs.rss_db_ratings_schema,
            where=[
                ("show_uuid", self.show_uuid),
                ("episode_uuid", self.episode_uuid),
                ("user_id", str(interaction.user.id)),
            ],
            guild_id=interaction.guild.id,
        )
        if len(uuid_checks) >= 1:
            await db_helper.update_fields(
                template_info=envs.rss_db_ratings_schema,
                where=[
                    ("show_uuid", self.show_uuid),
                    ("episode_uuid", self.episode_uuid),
                    ("user_id", str(interaction.user.id)),
                ],
                updates=[
                    ("rating", self.rating),
                    ("datetime", await datetime_handling.get_dt(format="ISO8601")),
                ],
                guild_id=interaction.guild.id,
            )
        else:
            await db_helper.insert_many_all(
                template_info=envs.rss_db_ratings_schema,
                inserts=[
                    (
                        str(interaction.user.id),
                        self.show_uuid,
                        self.episode_uuid,
                        self.rating,
                        await datetime_handling.get_dt(format="ISO8601"),
                    )
                ],
                guild_id=interaction.guild.id,
            )
        # Update average rating
        avg_rating = await db_helper.calculate_average_rating_from_db(
            show_uuid=self.show_uuid,
            episode_uuid=self.episode_uuid,
            template_info=envs.rss_db_ratings_schema,
            guild_id=interaction.guild.id,
        )
        if not avg_rating:
            await db_helper.add_avg_for_new_show(
                template_info="",
                show_uuid=self.show_uuid,
                episode_uuid=self.episode_uuid,
                message_id=interaction.id,
                episode_rating=self.rating,
            )
        stars = calculate_star_rating(float(self.rating))
        await interaction.response.edit_message(
            view=self.view, content=f"★ Average rating {stars} ({avg_rating:.1f}) ★"
        )
        await interaction.followup.send(
            ephemeral=True,
            content=I18N.t("feeds_core.podcast_rating.msg_confirm", rating=self.rating),
        )


async def check_if_feed_name_exist(feed_name, guild_id):
    feeds = await db_helper.get_output(
        template_info=envs.rss_db_schema, select="feed_name", guild_id=guild_id
    )
    feeds = [feed["feed_name"] for feed in feeds]
    logger.debug(f"`feeds`: {feeds}")
    return feed_name not in feeds


async def check_feed_validity(url_in, mock_file=None, guild=None):
    "Make sure that `url_in` is a valid link with feed items"
    if args.rss_skip_url_validation:
        logger.debug("Skipping url validation")
        return True
    sample_item = None
    logger.debug(f"Checking `url_in`: {url_in}")
    if net_io.url_hostname_matches(
        url_in, "acast.com"
    ) and not net_io.url_hostname_matches(url_in, "feeds.acast.com"):
        logger.debug("Found Acast, but not the rss feed. Changing url")
        base_feed_url = "https://feeds.acast.com/public/shows/{}"
        url_in = re.sub(r"/episodes.*", "", url_in)
        pod_url_name = re.search(r".*/(.*)", url_in).group(1)
        url_in = base_feed_url.format(pod_url_name)
    req = await net_io.get_link(url_in, mock_file=mock_file)
    logger.debug(f"req is ({type(req)})")
    if req is None:
        logger.debug("Returned None")
        return None
    elif isinstance(req, int):
        return req
    if "open.spotify.com/show/" in url_in:
        logger.debug("Discovered Spotify branded link")
        sample_item = await net_io.check_spotify_podcast(
            url=url_in, mock_file=mock_file, guild=guild
        )
    else:
        logger.debug("Discovered normal link")
        _items = await get_items_from_rss(req=req, url=url_in, num_items=1)
        if isinstance(_items, list):
            sample_item = _items[0]
    logger.debug(f"Got `sample_item`: {sample_item}")
    if sample_item is None:
        soup = BeautifulSoup(req, features="xml")
        if bool(soup.find("link", attrs={"type": "application/rss+xml"})):
            return True
        else:
            return False
    try:
        logger.debug(f"`req` is a {type(req)}")
        BeautifulSoup(req, features="xml")
        return True
    except etree.XMLSyntaxError as e:
        logger.error(f"Error: {e}")
        return False


async def get_items_from_rss(
    req, url, filters_in=None, log_in=None, num_items=None
) -> list:
    try:
        soup = BeautifulSoup(req, features="xml")
        rss_status = False
        if (
            soup.find("feed")
            or soup.find("rss")
            or soup.find("link", attrs={"type": "application/rss+xml"})
        ):
            rss_status = True
        if rss_status is False:
            logger.error(f"No rss feed found in {url}")
            return None
        else:
            logger.debug(f"Found rss feed in {url}")
    except Exception as e:
        logger.error(f"Error when reading `soup` from {url}: {e}")
        return None
    items_out = {"filters": filters_in, "items": [], "log": log_in}
    # Feed level info, so items get the same shape as the ones coming out
    # of `net_io.get_spotify_podcast_links` and
    # `net_io.get_other_podcast_links`
    feed_name, feed_description, feed_img = net_io.get_channel_info(soup)
    items_info = {
        "feed_name": feed_name,
        "feed_description": feed_description,
        "feed_img": feed_img,
        "feed_uuid": None,
        "type": "",
        "title": "",
        "description": "",
        "hash": "",
        "link": "",
        "img": "",
    }
    # Gets podcast feed
    podcast_status, _ratio, _signals = net_io.is_podcast_feed(soup)
    if podcast_status:
        logger.debug("Found podcast feed")
        if isinstance(num_items, int) and num_items > 0:
            all_items = soup.find_all("item")[0:num_items]
        else:
            all_items = soup.find_all("item")
        for item in all_items:
            temp_info = items_info.copy()
            temp_info["type"] = "podcast"
            temp_info["title"] = (
                item.find("title").text
                if hasattr(item.find("title"), "text")
                else item.find("title")
            )
            desc_in = (
                str(item.find("description").text)
                if hasattr(item.find("description"), "text")
                else str(item.find("description"))
            )
            desc_in = net_io.clean_pod_description(desc_in)
            temp_info["description"] = desc_in
            temp_info["hash"] = net_io.get_content_hash(
                temp_info["description"], temp_info["title"]
            )
            temp_info["link"] = (
                item.find("link").text
                if hasattr(item.find("link"), "text")
                else item.find("link")
            )
            item_img = item.find("itunes:image")
            if item_img and item_img.get("href"):
                temp_info["img"] = item_img["href"]
            else:
                temp_info["img"] = feed_img
            items_out["items"].append(temp_info)
    # Gets plain articles
    else:
        logger.debug("Found normal RSS feed")
        article_method = False
        if len(soup.find_all("item")) > 0:
            article_method = "item"
        elif len(soup.find_all("entry")) > 0:
            article_method = "entry"
        else:
            logger.error("Could not find any articles")
            return None
        if isinstance(num_items, int) and num_items > 0:
            all_items = soup.find_all(article_method)[0:num_items]
        else:
            all_items = soup.find_all(article_method)
        for item in all_items:
            temp_info = items_info.copy()
            temp_info["type"] = "rss"
            temp_info["title"] = item.find("title").text
            if item.find("description"):
                temp_info["description"] = str(item.find("description").text)
            elif item.find("media:keywords"):
                temp_info["description"] = str(item.find("media:keywords"))
            elif item.find("content"):
                temp_info["description"] = str(item.find("content").text)
            else:
                temp_info["description"] = None
            temp_info["hash"] = net_io.get_content_hash(
                temp_info["description"], temp_info["title"]
            )
            if article_method == "item":
                temp_info["link"] = item.find("link").text
            elif article_method == "entry":
                temp_info["link"] = item.find("link")["href"]
            logger.debug(f"Got `temp_info`: {temp_info}")
            items_out["items"].append(temp_info)
    links_out = net_io.FilterLinks(items_out).filter_the_links()
    return links_out


async def add_to_feed_db(
    feed_type,
    name,
    feed_link=None,
    channel=None,
    user_add=None,
    yt_id=None,
    playlist_id=None,
    guild_id=None,
):
    """
    Add a an item to the feeds table in db

    `feed_type`:
    `name`:         The identifiable name of the added feed
    `feed_link`:    The link for the feed
    `channel`:      The discord channel to post the feed to
    `user_add`:     The user who added the feed
    `yt_id`:        yt-id
    ``playlist_id`: id of playlist
    `guild_id`:     Guild the feed belongs to
    """

    if feed_type not in ["rss", "youtube", "podcast"]:
        logger.error("Function requires `feed_type`")
        return None
    # Test the link first
    test_link = await net_io.get_link(feed_link)
    if not args.rss_skip_url_validation:
        if test_link is None:
            logger.debug("`test_link` is None")
            return None
        elif isinstance(test_link, int):
            logger.debug(f"`test_link` returns code {test_link}")
            return test_link
    else:
        logger.debug("Skipping url validation")
    date_now = await datetime_handling.get_dt(format="datetime")
    if feed_type in ["rss"]:
        await db_helper.insert_many_some(
            envs.rss_db_schema,
            rows=(
                "uuid",
                "feed_name",
                "url",
                "channel",
                "added",
                "added_by",
                "feed_type",
                "status_url",
                "status_url_counter",
                "status_channel",
                "num_episodes",
            ),
            inserts=(
                (
                    str(uuid4()),
                    name,
                    feed_link,
                    channel,
                    date_now,
                    user_add,
                    feed_type,
                    envs.FEEDS_URL_SUCCESS,
                    0,
                    envs.CHANNEL_STATUS_SUCCESS,
                    0,
                )
            ),
            guild_id=guild_id,
        )
    elif feed_type == "youtube":
        await db_helper.insert_many_some(
            envs.youtube_db_schema,
            rows=(
                "uuid",
                "feed_name",
                "url",
                "channel",
                "added",
                "added_by",
                "status_url",
                "status_url_counter",
                "status_channel",
                "youtube_id",
                "playlist_id",
            ),
            inserts=(
                (
                    str(uuid4()),
                    name,
                    feed_link,
                    channel,
                    date_now,
                    user_add,
                    envs.FEEDS_URL_SUCCESS,
                    0,
                    envs.CHANNEL_STATUS_SUCCESS,
                    yt_id,
                    playlist_id,
                )
            ),
            guild_id=guild_id,
        )
    elif feed_type in ["podcast"]:
        await db_helper.insert_many_some(
            envs.rss_db_schema,
            rows=(
                "uuid",
                "feed_name",
                "url",
                "channel",
                "added",
                "added_by",
                "feed_type",
                "status_url",
                "status_url_counter",
                "status_channel",
                "num_episodes",
            ),
            inserts=(
                (
                    str(uuid4()),
                    name,
                    feed_link,
                    channel,
                    date_now,
                    user_add,
                    feed_type,
                    envs.FEEDS_URL_SUCCESS,
                    0,
                    envs.CHANNEL_STATUS_SUCCESS,
                    0,
                )
            ),
            guild_id=guild_id,
        )


async def remove_feed_from_db(feed_type, feed_name, guild_id):
    "Remove a feed from `feed file` based on `feed_name`"
    removal_ok = True
    if feed_type in ["rss", "podcast"]:
        feed_db = envs.rss_db_schema
        feed_db_filter = envs.rss_db_filter_schema
    elif feed_type == "youtube":
        feed_db = envs.youtube_db_schema
        feed_db_filter = envs.youtube_db_filter_schema
    uuid_from_db = await db_helper.get_output(
        template_info=feed_db,
        select=("uuid"),
        where=[("feed_name", feed_name)],
        single=True,
        guild_id=guild_id,
    )
    uuid_from_db = uuid_from_db["uuid"]
    logger.debug(f"`uuid_from_db` is {uuid_from_db}")
    removal = await db_helper.del_row_by_AND_filter(
        feed_db, where=("uuid", uuid_from_db), guild_id=guild_id
    )
    logger.debug(f"`removal` is {removal}")
    if not removal:
        removal_ok = False
    removal_filters = await db_helper.del_row_by_AND_filter(
        feed_db_filter, where=("uuid", uuid_from_db), guild_id=guild_id
    )
    logger.debug(f"`removal_filters` is {removal_filters}")
    if not removal_filters:
        removal_ok = False
    return removal_ok


async def get_feed_links(feed_type, feed_info, guild_id):
    "Get the links from a feed"
    UUID = feed_info["uuid"]
    if feed_type == "rss":
        URL = feed_info["url"]
        feed_db_filter = envs.rss_db_filter_schema
        feed_db_log = envs.rss_db_log_schema
    else:
        URL = feed_info["url"]
    # Get the url and make it parseable
    if feed_type in ["rss"]:
        req = await net_io.get_link(URL, status_out=True)
        if req["status"] != 200:
            logger.error(f"Got HTTP status {req['status']} for {URL}")
            return req["status"]
        filters_db = await db_helper.get_output(
            template_info=feed_db_filter,
            select=("allow_or_deny", "filter"),
            where=[("uuid", UUID)],
            guild_id=guild_id,
        )
        log_db = await db_helper.get_output(
            template_info=feed_db_log, where=[("uuid", UUID)], guild_id=guild_id
        )
        links_out = await get_items_from_rss(
            req=req["content"],
            url=URL,
            filters_in=filters_db,
            log_in=log_db,
            num_items=5,
        )
        logger.debug(
            "Got {} items from `get_items_from_rss`".format(
                len(links_out) if links_out is not None else 0
            )
        )
        return links_out


def get_member_name(guild: discord.Guild, member_in) -> str:
    """
    Get the name of the member `member_in` in `guild`, falling back to a
    placeholder with the raw id if the member has left the guild.
    #autodoc skip#
    """
    try:
        member_out = guild.get_member(int(member_in))
    except (TypeError, ValueError):
        member_out = None
    if member_out is None:
        logger.warning(f"Could not find member `{member_in}` in guild {guild.id}")
        return I18N.t("common.unknown_member", id=member_in)
    return member_out.name


async def get_feed_list(
    guild: discord.Guild,
    db_in: str = None,
    db_filter_in: str = None,
    list_type: str = None,
    link_type: str = None,
    feed_type: str = None,
):
    """
    Get a prettified list of feeds.

    Parameters
    ------------
    db_in: str
        Database to get feeds from (default: None)
    db_filter_in: str
        Database with the filters (default: None)
    list_type: str
        If specified, should show that specific list_type: `added` or
        `filter` (default: None, a plain listing)
    link_type: str
        If specified, should show that specific link_type: `channel` or
        `playlist` (default: None, both)
    feed_type: str
        If specified, should show that specific feed_type

    Note that `list_type`/`link_type` are the untranslated values - the
    cogs are the ones dealing with the localized command literals.
    """

    async def split_lengthy_list(table_in):
        def split_list(lst, chunk_size):
            chunks = [[] for _ in range((len(lst) + chunk_size - 1) // chunk_size)]
            for i, item in enumerate(lst):
                chunks[i // chunk_size].append(item)
            return chunks

        logger.debug(f"length of table_in: {len(table_in)}")
        max_post_limit = 1900
        paginated = []
        if len(table_in) >= max_post_limit:
            line_len = len(table_in.split("\n")[1])
            logger.debug(f"Each line is {line_len} chars long")
            post_limit = int(max_post_limit / line_len)
            logger.debug(f"Each post can therefore hold {post_limit} lines")
            splits = split_list(table_in.split("\n")[2:], post_limit - 2)
            header = table_in.split("\n")[0]
            header += "\n{}".format(table_in.split("\n")[1])
            temp_page = ""
            for split in splits:
                temp_page = header
                for line in split:
                    temp_page += f"\n{line}"
                paginated.append(temp_page)
        else:
            paginated.append(table_in)
        return paginated

    _guild = guild
    # Not every feed db knows about playlists (rss feeds don't)
    has_playlist_id = any(item[0] == "playlist_id" for item in db_in["items"])
    show_playlist_id = has_playlist_id and link_type in ["channel", "playlist"]

    def wanted_link_type(feed_in) -> bool:
        """
        Check a feed against `link_type`. Doing this in the query would
        need an `IS (NOT) NULL`, which `db_helper.get_output` doesn't
        support.
        #autodoc skip#
        """
        if not show_playlist_id:
            return True
        is_playlist = feed_in.get("playlist_id") not in [None, "", "None"]
        if link_type == "playlist":
            return is_playlist
        return not is_playlist

    if feed_type:
        wheres_in = [("feed_type", feed_type)]
    else:
        wheres_in = None
    selects = ["feed_name", "url", "channel"]
    if show_playlist_id:
        selects.append("playlist_id")
    selects = tuple(selects)
    if list_type is None:
        feeds_out = await db_helper.get_output(
            template_info=db_in,
            where=wheres_in,
            select=selects,
            order_by=[("feed_name", "ASC")],
            guild_id=guild.id,
        )
        # Return None if empty db
        if not feeds_out:
            logger.info("No feeds in database")
            return None
        feeds_out = [feed for feed in feeds_out if wanted_link_type(feed)]
        for feed in feeds_out:
            feed["channel"] = discord_commands.get_channel_name(_guild, feed["channel"])
            if "playlist_id" in feed:
                if feed["playlist_id"] is None:
                    feed["playlist_id"] = I18N.t("common.channel")
                else:
                    feed["playlist_id"] = I18N.t("common.playlist")
        logger.debug(f"`feeds_out` is {feeds_out}")
        headers = {
            "feed_name": I18N.t("feeds_core.list_headers.feed_name"),
            "url": I18N.t("feeds_core.list_headers.url"),
            "channel": I18N.t("feeds_core.list_headers.channel"),
            "playlist_id": I18N.t("feeds_core.list_headers.link_type"),
        }
        maxcolwidths = [None, None, None, None]
    elif list_type == "added":
        selects_added = ["feed_name", "url", "channel", "added", "added_by"]
        if has_playlist_id:
            selects_added.append("playlist_id")
        feeds_out = await db_helper.get_output(
            template_info=db_in,
            select=tuple(selects_added),
            where=wheres_in,
            order_by=[("feed_name", "ASC")],
            guild_id=guild.id,
        )
        # Return None if empty db
        if not feeds_out:
            logger.info("No feeds in database")
            return None
        feeds_out = [feed for feed in feeds_out if wanted_link_type(feed)]
        for feed in feeds_out:
            feed["channel"] = discord_commands.get_channel_name(_guild, feed["channel"])
            if feed["added_by"] and re.match(r"(\d+)", feed["added_by"]):
                feed["added_by"] = get_member_name(_guild, feed["added_by"])
            if has_playlist_id:
                if feed["playlist_id"] is None:
                    feed["playlist_id"] = I18N.t("common.channel")
                else:
                    feed["playlist_id"] = I18N.t("common.playlist")
        headers = {
            "feed_name": I18N.t("feeds_core.list_headers.feed_name"),
            "url": I18N.t("feeds_core.list_headers.url"),
            "channel": I18N.t("feeds_core.list_headers.channel"),
            "added": I18N.t("feeds_core.list_headers.added"),
            "added_by": I18N.t("feeds_core.list_headers.added_by"),
            "playlist_id": I18N.t("feeds_core.list_headers.link_type"),
        }
        maxcolwidths = [None, None, None, None, None, None]
    elif list_type == "filter":
        if db_filter_in is None:
            logger.error("`db_filter_in` is not specified")
            return None
        selects_filter = ["uuid", "feed_name", "channel"]
        if has_playlist_id:
            selects_filter.append("playlist_id")
        feeds_db = await db_helper.get_output(
            template_info=db_in,
            select=tuple(selects_filter),
            where=wheres_in,
            order_by=[("feed_name", "ASC")],
            guild_id=guild.id,
        )
        logger.debug(f"Got `feeds_db`:\n{pformat(feeds_db)}")
        # Return None if empty db
        if not feeds_db:
            logger.info("No feeds in database")
            return None
        feeds_db = [feed for feed in feeds_db if wanted_link_type(feed)]
        feeds_filter = await db_helper.get_output(
            template_info=db_filter_in,
            order_by=[("uuid", "DESC"), ("filter", "ASC")],
            guild_id=guild.id,
        )
        logger.debug(f"Got `feeds_filter`:\n{pformat(feeds_filter)}")
        if feeds_filter is None:
            feeds_filter = []
        feeds_out = []
        for feed in feeds_db:
            filter_uuid = [
                filter_item
                for filter_item in feeds_filter
                if filter_item["uuid"] == feed["uuid"]
            ]
            logger.debug(f"`filter_uuid` is {filter_uuid}")
            filter_allow = [
                filter_item["filter"]
                for filter_item in filter_uuid
                if filter_item["allow_or_deny"].lower() == "allow"
            ]
            logger.debug(f"`filter_allow` is {filter_allow}")
            filter_deny = [
                filter_item["filter"]
                for filter_item in filter_uuid
                if filter_item["allow_or_deny"].lower() == "deny"
            ]
            logger.debug(f"`filter_deny` is {filter_deny}")
            temp_list = []
            temp_list.append(feed["feed_name"])
            temp_list.append(discord_commands.get_channel_name(_guild, feed["channel"]))
            temp_list.append(", ".join(item for item in filter_allow))
            temp_list.append(", ".join(item for item in filter_deny))
            feeds_out.append(temp_list)
            logger.debug(f"`temp_list` is {temp_list}")
        headers = ("Feed", "Channel", "Allow", "Deny")
        maxcolwidths = [None, None, 30, 30]
    else:
        logger.error(f"Unknown `list_type`: {list_type}")
        return None
    if len(feeds_out) <= 0:
        return None
    table_out = tabulate(
        tabular_data=feeds_out, headers=headers, maxcolwidths=maxcolwidths
    )
    return await split_lengthy_list(table_out)


def decide_link_action(link, item_hash, log_in):
    """
    Decide what to do with a feed item, given the log for its feed.

    A link that is already logged is done with. A link that is new, but
    whose text has been posted before, is the same post under a fixed
    url - then the message that carries the old link is edited instead
    of posting the item a second time.

        ("skip", None)   - already posted
        ("replace", row) - edit the message the logged row points at
        ("post", None)   - never seen before

    #autodoc skip#
    """
    if not log_in:
        logger.debug("Log is empty, posting")
        return "post", None
    if link in [row["url"] for row in log_in]:
        logger.debug(f"`{link}` is in log, skipping")
        return "skip", None
    if not item_hash:
        logger.debug("Item has no content hash, posting")
        return "post", None
    hits = [row for row in log_in if row.get("hash") == item_hash]
    if len(hits) == 0:
        logger.debug("Neither link nor content hash in log, posting")
        return "post", None
    # Newest first: if several logged posts share a hash, the newest one
    # is the likeliest to still be within reach in the channel history
    hits.sort(key=lambda row: str(row.get("date") or ""), reverse=True)
    logger.debug("Content hash in log as `{}`, replacing".format(hits[0]["url"]))
    return "replace", hits[0]


async def update_log_link(template_info, uuid, old_link, new_link, guild):
    """
    Point the logged row for `old_link` at `new_link`.

    Without this the log keeps the old link, and the same message gets
    edited once per run for as long as the item stays in the feed.
    #autodoc skip#
    """
    logger.info(f"Moving log entry `{old_link}` to `{new_link}`")
    await db_helper.update_fields(
        template_info=template_info,
        where=[("uuid", uuid), ("url", old_link)],
        updates=[
            ("url", new_link),
            ("date", str(await datetime_handling.get_dt(format="ISO8601"))),
        ],
        guild_id=guild.id,
    )


async def log_link(template_info, uuid, feed_link, content_hash, guild, msg_id=None):
    logger.info("Logging link to db")
    logger.debug(
        f"Got these vars: template_info: {template_info}, uuid: {uuid}, "
        f"feed_link: {feed_link}, content_hash: {content_hash}, msg_id: {msg_id}"
    )
    if content_hash is None:
        content_hash = feed_link
        logger.error(f"No content hash for {feed_link}, logging link instead")
        await discord_commands.log_to_bot_channel(
            guild,
            I18N.t("feeds_core.log.no_content_hash", feed_link=feed_link),
        )
    values = {
        "uuid": uuid,
        "url": feed_link,
        "date": str(await datetime_handling.get_dt(format="ISO8601")),
        "hash": content_hash,
        "msg_id": str(msg_id) if msg_id else None,
    }
    # The log tables differ - youtube keeps neither hash nor msg_id - so
    # the schema decides what goes in, and in which order
    log_cols = [col[0].strip() for col in template_info["items"]]
    inserts = [values[col] for col in log_cols if col in values]
    logger.debug(f"Adding this to log:\n{pformat(inserts)}")
    await db_helper.insert_many_all(
        template_info=template_info, inserts=[inserts], guild_id=guild.id
    )


def channel_is_gone(guild: discord.Guild, channel_in) -> bool:
    """
    Check whether `channel_in` can still be reached in `guild`.

    A feed keeps its channel id in the database long after the channel
    itself is gone (deleted, or moved out of the bot's reach).
    #autodoc skip#
    """
    try:
        return guild.get_channel_or_thread(int(channel_in)) is None
    except (TypeError, ValueError):
        logger.error(f"Channel `{channel_in}` is not a valid channel id")
        return True


async def report_dead_channel(feed_db, uuid, feed_name, channel, guild):
    """
    Mark the feed as failed so it stops being picked up, and tell the
    guild's bot channel about it. Repeats within
    `DEAD_CHANNEL_ALERT_COOLDOWN` seconds are logged but not posted.
    #autodoc skip#
    """
    await db_helper.update_fields(
        template_info=feed_db,
        where=("uuid", uuid),
        updates=("status_channel", envs.CHANNEL_STATUS_ERROR),
        guild_id=guild.id,
    )
    alert_key = (guild.id, str(channel))
    now = monotonic()
    last_alert = dead_channel_alerts.get(alert_key)
    if last_alert is not None and (now - last_alert) < DEAD_CHANNEL_ALERT_COOLDOWN:
        logger.debug(f"Already warned about channel `{channel}`, staying quiet")
        return
    dead_channel_alerts[alert_key] = now
    await discord_commands.log_to_bot_channel(
        guild,
        I18N.t("feeds_core.log.dead_channel", feed_name=feed_name, channel=channel),
    )


async def reg_feed_error(feed_db, feed, guild, status_in):
    """
    Count a failed fetch instead of standing the feed down on the first
    one.

    Youtube answers 404 and 500 while it throttles, so a single bad
    reply is no proof the feed is dead - on 2026-08-22 that took out all
    38 feeds in a guild inside an hour, 26 of them on a 404. A feed is
    only stood down after `envs.FEEDS_URL_ERROR_LIMIT` errors in a row,
    and only left alone after as many failed retries.

        OK --3 errors--> Failed --3 errors--> Stale
        every 10 min     every 6 h           left alone
    #autodoc skip#
    """
    status_now = feed["status_url"]
    feed_name = feed["feed_name"]
    # Rows migrated from the old json files have no count yet
    count = (feed["status_url_counter"] or 0) + 1
    logger.info(
        "Feed {} returned {} ({}/{}, status `{}`)".format(
            feed_name, status_in, count, envs.FEEDS_URL_ERROR_LIMIT, status_now
        )
    )

    # Below the limit only the count moves - the feed keeps its status
    if count < envs.FEEDS_URL_ERROR_LIMIT:
        await db_helper.update_fields(
            template_info=feed_db,
            where=("uuid", feed["uuid"]),
            updates=("status_url_counter", count),
            guild_id=guild.id,
        )
        return

    # Limit reached: step down one level, and start a fresh count so the
    # next phase gets its own full set of attempts
    if status_now == envs.FEEDS_URL_ERROR:
        new_status = envs.FEEDS_URL_STALE
        msg_key = "feeds_core.log.feed_gave_up"
    else:
        new_status = envs.FEEDS_URL_ERROR
        msg_key = "feeds_core.log.feed_deactivated"
    await db_helper.update_fields(
        template_info=feed_db,
        where=("uuid", feed["uuid"]),
        updates=[("status_url", new_status), ("status_url_counter", 0)],
        guild_id=guild.id,
    )
    await discord_commands.log_to_bot_channel(
        guild,
        I18N.t(
            msg_key,
            feed_name=feed_name,
            return_value=str(status_in),
            limit=envs.FEEDS_URL_ERROR_LIMIT,
        ),
    )


async def reg_feed_ok(feed_db, feed, guild):
    """
    Clear the failure count after a good fetch, and bring the feed back
    into rotation if it had been stood down.
    #autodoc skip#
    """
    status_now = feed["status_url"]
    count = feed["status_url_counter"] or 0

    # A healthy feed with nothing to clear is the common case - don't
    # write to the db on every single tick for it
    if status_now == envs.FEEDS_URL_SUCCESS and count == 0:
        return

    await db_helper.update_fields(
        template_info=feed_db,
        where=("uuid", feed["uuid"]),
        updates=[
            ("status_url", envs.FEEDS_URL_SUCCESS),
            ("status_url_counter", 0),
        ],
        guild_id=guild.id,
    )
    if status_now != envs.FEEDS_URL_SUCCESS:
        logger.info("Feed {} is working again".format(feed["feed_name"]))
        await discord_commands.log_to_bot_channel(
            guild,
            I18N.t("feeds_core.log.feed_recovered", feed_name=feed["feed_name"]),
        )


async def retry_failed(feed_type, feed_db, guild, not_like=()):
    """
    Give feeds that `reg_feed_error()` stood down another chance, on a
    slower loop than the posting one. `Stale` feeds are past that point
    and are not touched.

    Nothing is posted from here - a revived feed goes back to `OK` and
    the normal posting loop picks it up on its next tick.
    #autodoc skip#
    """
    feeds = await db_helper.get_output(
        template_info=feed_db,
        where=[("status_url", envs.FEEDS_URL_ERROR)],
        not_like=not_like,
        guild_id=guild.id,
    )
    if not feeds:
        logger.debug(f"No failed feeds to retry for `{guild.name}`")
        return
    logger.info("Retrying {} failed feeds for `{}`".format(len(feeds), guild.name))

    for feed in feeds:
        feed_posts = await get_feed_links(
            feed_type=feed_type, feed_info=feed, guild_id=guild.id
        )
        if feed_posts is None or isinstance(feed_posts, int):
            await reg_feed_error(feed_db, feed, guild, feed_posts)
        else:
            await reg_feed_ok(feed_db, feed, guild)


async def reset_url_errors(feed_db, guild, feed_name=None):
    """
    Put feeds that were stood down for url errors back in rotation, and
    return the names that were reset. Without `feed_name`, every broken
    feed in the guild is reset.
    #autodoc skip#
    """
    feeds = await db_helper.get_output(
        template_info=feed_db,
        select=("uuid", "feed_name", "status_url"),
        guild_id=guild.id,
    )
    # `get_output`'s `where` only ever builds `=`, so pick out the
    # non-OK rows here instead
    broken = [
        feed
        for feed in (feeds or [])
        if feed["status_url"] != envs.FEEDS_URL_SUCCESS
        and (feed_name is None or feed["feed_name"] == feed_name)
    ]
    for feed in broken:
        await db_helper.update_fields(
            template_info=feed_db,
            where=("uuid", feed["uuid"]),
            updates=[
                ("status_url", envs.FEEDS_URL_SUCCESS),
                ("status_url_counter", 0),
            ],
            guild_id=guild.id,
        )
    return [feed["feed_name"] for feed in broken]


async def process_links_for_posting_or_editing(
    feed_name: str, feed_type: str, uuid, FEED_POSTS, CHANNEL, guild: discord.Guild
):
    """
    Compare links in `FEED_POSTS` items to posts belonging to `feed` to see
    if they already have been posted or not.
    - If not posted, post to `CHANNEL`
    - If posted, make a similarity check just to make sure we are not posting
    duplicate links because someone's aggregation systems can't handle
    editing urls with spelling mistakes. If it is similar, but not identical,
    replace the logged link and edit the previous post with the new link.

    `feed_name`:        Name of the feed to process
    `feed_type`:        Should be 'rss', 'youtube' or 'podcast'
    `FEED_POSTS`:       The newly received feed posts
    `CHANNEL`:          Discord channel to post/edit
    `guild`:            Guild the feed belongs to
    """
    logger.debug("Starting `process_links_for_posting_or_editing`")
    if feed_type not in ["rss", "youtube", "podcast"]:
        logger.error("Function requires `feed_type`")
        return None
    if feed_type in ["rss", "podcast"]:
        feed_db = envs.rss_db_schema
        feed_db_log = envs.rss_db_log_schema
        FEED_SETTINGS = await db_helper.get_output(
            template_info=envs.rss_db_settings_schema,
            select=("setting", "value"),
            as_settings_json=True,
            guild_id=guild.id,
        )
    elif feed_type == "youtube":
        feed_db = envs.youtube_db_schema
        feed_db_log = envs.youtube_db_log_schema
        FEED_SETTINGS = None
    if FEED_POSTS is None:
        logger.debug("`FEED_POSTS` is None")
        return None
    # Checking the channel once per feed keeps a deleted channel from
    # failing on every single item below
    if channel_is_gone(guild, CHANNEL):
        logger.error(
            f"Channel `{CHANNEL}` for `{feed_name}` is gone, marking feed as failed"
        )
        await report_dead_channel(feed_db, uuid, feed_name, CHANNEL, guild)
        return None
    logger.debug(f"Got {len(FEED_POSTS)} items in `FEED_POSTS`")
    # Not every log table keeps a hash - youtube dropped its column
    log_cols = [col[0].strip() for col in feed_db_log["items"]]
    FEED_LOG = await db_helper.get_output(
        template_info=feed_db_log,
        select=tuple(
            col for col in ("url", "date", "hash", "msg_id") if col in log_cols
        ),
        where=[("uuid", uuid)],
        guild_id=guild.id,
    )
    if not isinstance(FEED_LOG, list):
        FEED_LOG = []
    logger.debug(f"FEED_SETTINGS is {FEED_SETTINGS} for feed type {feed_type}")
    FEED_POSTS = FEED_POSTS[0:5]
    FEED_POSTS.reverse()
    for item in FEED_POSTS:
        logger.debug(f"Got this item:\n{item}")
        if isinstance(item, str):
            # A bare link carries no text to hash, so it can only ever
            # be recognized by the link itself
            feed_link = item
            item_hash = item
        elif isinstance(item, dict):
            feed_link = item["link"]
            item_hash = item.get("hash")
        # Ask the log whether this is known, new, or a known post that
        # got its link fixed
        action, old_row = decide_link_action(feed_link, item_hash, FEED_LOG)
        logger.debug(f"Link `{feed_link}` got action `{action}`")
        if action == "skip":
            continue
        if action == "replace":
            old_link = old_row["url"]
            edited = await discord_commands.replace_post(
                guild, old_link, feed_link, CHANNEL, msg_id=old_row.get("msg_id")
            )
            if edited:
                await update_log_link(feed_db_log, uuid, old_link, feed_link, guild)
                old_row["url"] = feed_link
                continue
            # The old message is out of reach - deleted, or older than
            # the history we look through - so nothing was edited
            logger.error(
                f"Found no message with `{old_link}` in channel `{CHANNEL}`, "
                f"posting `{feed_link}` as a new post"
            )
        if action in ["post", "replace"]:
            # Consider this a whole new post and post link to channel
            logger.debug(f"Posting link `{feed_link}`")
            logger.debug(
                f"Found item:\n{pformat(item)}",
            )
            # Whether this is a podcast is decided by the feed's type in
            # the db, not by the item itself. A feed registered as `rss`
            # is never posted as a podcast even if it carries audio.
            posted = True
            posted_msg = None
            if feed_type == "podcast" and isinstance(item, dict):
                embed_color = await net_io.extract_color_from_image_url(item["img"])
                embed = discord.Embed(
                    title=item["title"],
                    url=item["link"],
                    description=item["description"],
                    colour=discord.Color.from_str(f"#{embed_color}"),
                )
                embed.add_field(
                    name="",
                    value="[🎧 HØR PÅ EPISODEN 🎧]({})".format(item["link"]),
                    inline=False,
                )
                embed.set_author(name=feed_name)
                embed.set_image(url=item["img"])
                desc_setting = "show_pod_description_in_embed"
                if (
                    desc_setting in FEED_SETTINGS
                    and FEED_SETTINGS[desc_setting].lower() == "true"
                ):
                    logger.debug("Descriptions enabled")
                    if item.get("feed_description"):
                        embed.set_footer(text=item["feed_description"])
                logger.debug(f"Sending this embed to channel:\n{pformat(embed)}")
                episode_msg = await discord_commands.post_to_channel(
                    CHANNEL, embed_in=embed
                )
                posted = episode_msg is not None
                posted_msg = episode_msg
                view = None
                rating_setting = "podcast_ratings_enabled"
                if (
                    rating_setting in FEED_SETTINGS
                    and FEED_SETTINGS[rating_setting].lower() == "true"
                ):
                    logger.debug("Ratings enabled")
                    view = discord.ui.View(timeout=None)
                    view.add_item(
                        DynamicRatingSelect(
                            show_uuid=item.get("feed_uuid") or uuid,
                            episode_uuid=item["hash"],
                        )
                    )
                    await discord_commands.post_to_channel(CHANNEL, view=view)
                discussion_setting = "podcast_discussion_enabled"
                if (
                    discussion_setting in FEED_SETTINGS
                    and FEED_SETTINGS[discussion_setting].lower() == "true"
                    and episode_msg is not None
                ):
                    logger.debug("Discussion enabled")
                    # Create a thread for discussion
                    ep_name = "Diskusjon: {} - {}".format(
                        item.get("feed_name") or feed_name, item["title"]
                    )
                    if len(ep_name) > 100:
                        ep_name = ep_name[0:90]
                        ep_name += "..."
                    await episode_msg.create_thread(
                        name=ep_name, auto_archive_duration=10080
                    )
            else:
                logger.debug("Found a regular post")
                if args.testmode:
                    logger.debug(
                        f"TESTMODE: Would post this link: {feed_link}", color="yellow"
                    )
                else:
                    posted_msg = await discord_commands.post_to_channel(
                        CHANNEL, feed_link
                    )
                    posted = posted_msg is not None
            if not posted:
                # Not logging the link keeps it queued for the next run,
                # instead of silently dropping it as already posted
                logger.error(
                    f"Could not post `{feed_link}` from `{feed_name}` to channel "
                    f"`{CHANNEL}`, not logging it as posted"
                )
                continue
            # The message id is what lets a later link fix edit this
            # exact message instead of searching the channel
            msg_id = posted_msg.id if posted_msg else None
            await log_link(feed_db_log, uuid, feed_link, item_hash, guild, msg_id)
            # Later items in the same batch have to see this one too
            FEED_LOG.append(
                {
                    "url": feed_link,
                    "hash": item_hash,
                    "msg_id": str(msg_id) if msg_id else None,
                }
            )


def calculate_star_rating(rating):
    if rating == 5:
        return "★★★★★"
    elif rating >= 4.5:
        return "★★★★⯪"
    elif rating >= 4:
        return "★★★★☆"
    elif rating >= 3.5:
        return "★★★⯪☆"
    elif rating >= 3:
        return "★★★☆☆"
    elif rating >= 2.5:
        return "★★⯪☆☆"
    elif rating >= 2:
        return "★★☆☆☆"
    elif rating >= 1.5:
        return "★⯪☆☆☆"
    elif rating >= 1:
        return "★☆☆☆☆"
    elif rating >= 0.5:
        return "⯪☆☆☆☆"
    elif rating >= 0:
        return "☆☆☆☆☆"


if __name__ == "__main__":
    pass
