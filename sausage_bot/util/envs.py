#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"envs: Set variables for the module like folder, files and botlines"

from pathlib import Path

from sausage_bot.util.args import args

# Folders
ROOT_DIR = Path(__file__).resolve().parent.parent
COGS_DIR = ROOT_DIR / "cogs"
if args.data_dir:
    DATA_DIR = Path(ROOT_DIR / args.data_dir).resolve()
else:
    DATA_DIR = ROOT_DIR / "data"
JSON_DIR = DATA_DIR / "json"
if args.db_dir:
    DB_DIR = Path(args.db_dir).resolve()
else:
    DB_DIR = DATA_DIR / "db"
LOG_DIR = DATA_DIR / "logs"
STATIC_DIR = DATA_DIR / "static"
TEMP_DIR = ROOT_DIR / "tempfiles"
GUILDS_DB_FILE = str(DB_DIR / "guilds.sqlite")


def guild_db_dir(guild_id) -> Path:
    "Return the per-guild database directory, e.g. data/db/guild_<id>/"
    return DB_DIR / f"guild_{guild_id}"


def resolve_db_file(template_info: dict, guild_id=None) -> str:
    """
    Resolve a schema's "db_file" into an actual path to connect to.

    Globally scoped schemas (`"scope": "global"`) already hold a full path.
    Guild-scoped schemas (the default) hold a bare filename that must be
    joined with the given guild's own database directory.
    """
    if template_info.get("scope") == "global":
        return template_info["db_file"]
    if guild_id is None:
        raise ValueError(
            "guild_id is required for guild-scoped table "
            f"'{template_info.get('name')}'"
        )
    return str(guild_db_dir(guild_id) / template_info["db_file"])


# DB schema convention: "db_file" is a relative filename resolved against
# guild_db_dir(guild_id) at query time (db_helper needs a guild_id to use
# these). A schema marked "scope": "global" is the exception - its "db_file"
# is a full path under DB_DIR directly, used for bot-wide data like the
# guild registry itself, which cannot be scoped to a guild it describes.

MERMAID_DIR = ROOT_DIR / "docs" / "mermaid_charts"
LOCALE_DIR = ROOT_DIR / "locale"
TESTPARSE_DIR = ROOT_DIR / "test/test_parse"
EXTERNAL_DIR = ROOT_DIR / "external_files"
EXT_TEMP_DIR = ROOT_DIR / "external_files" / "temp_files"

# Relative paths
COGS_REL_DIR = "sausage_bot.cogs"

# Testfiles
test_xml_good = TESTPARSE_DIR / "feed_good_angrymetalguy.xml"
test_xml_bad1 = TESTPARSE_DIR / "feed_bad_angrymetalguy.xml"
test_xml_bad2 = TESTPARSE_DIR / "feed_bad_bbc.html"
test_nifs_json_good = TESTPARSE_DIR / "nifs.json"
test_vglive_json_good = TESTPARSE_DIR / "vglive.json"
test_vglive_tv_json_good = TESTPARSE_DIR / "vglive_tv.json"
test_tv2livesport_json_good = TESTPARSE_DIR / "tv2livesport.json"

# Files
version_file = ROOT_DIR / "version.json"
env_file = DATA_DIR / ".env"
rss_feeds_file = JSON_DIR / "rss-feeds.json"
rss_feeds_logs_file = JSON_DIR / "rss-feeds-log.json"
youtube_feeds_file = JSON_DIR / "yt-feeds.json"
youtube_feeds_logs_file = JSON_DIR / "yt-feeds-log.json"
scrape_logs_file = JSON_DIR / "scrape-log.json"
quote_file = JSON_DIR / "quotes.json"
quote_log_file = JSON_DIR / "quotes-log.json"
quote_temp_img = TEMP_DIR / "quote_temp_img.png"
dilemmas_file = JSON_DIR / "dilemmas.json"
dilemmas_log_file = JSON_DIR / "dilemmas-log.json"
cogs_status_file = JSON_DIR / "cogs_status.json"
stats_file = JSON_DIR / "stats.json"
stats_logs_file = JSON_DIR / "stats_logs.json"
roles_settings_file = JSON_DIR / "roles_settings.json"

# Template content
env_template = """
# Basic settings
DISCORD_TOKEN=
BOT_ID=
PREFIX=
LOCALE=
BOT_DUMP_CHANNEL=bot
WATCHING=

# Multi-guild settings
# ADMIN_GUILD_ID is the bot's home guild - it is auto-approved and never
# needs to go through the /approve-guild flow. New-guild notifications and
# the /approve-guild command are used from ADMIN_CHANNEL_ID in that guild.
ADMIN_GUILD_ID=
ADMIN_CHANNEL_ID=
"""

# Guilds registry (global - not scoped to a guild, this IS the list of guilds)
guilds_db_schema = {
    "db_file": GUILDS_DB_FILE,
    "scope": "global",
    "name": "guilds",
    "items": [
        ["guild_id", "TEXT NOT NULL UNIQUE"],
        ["guild_name", "TEXT"],
        ["status", "TEXT NOT NULL"],  # pending | approved | removed
        ["joined_at", "TEXT"],
        ["approved_by", "TEXT"],
        ["approved_at", "TEXT"],
    ],
    "primary": "guild_id",
    "autoincrement": False,
}

# Stats
stats_template = {
    "channel": "stats",
    "show_role_stats": True,
    "hide_bot_roles": False,
    "sort_roles_abc": True,
    "sort_roles_321": False,
    "show_code_stats": True,
    "hide_empty_roles": False,
}

# Roles
roles_template = {
    "channel": "roles",
    "reaction_messages": {},
    "unique_role": {"not_include_in_total": [], "role": 0},
}

# Cogs.env
# Guild-scoped: tracks, per guild, whether each background posting task
# is enabled for that guild ("started"/"stopped"). The background loops
# themselves are shared, always-running infrastructure (one loop iterates
# all approved guilds internally) - this table only controls whether a
# given guild is opted in to that loop's processing on a given tick. A
# missing row is treated the same as "stopped" (safe opt-in default).
tasks_db_schema = {
    "db_file": "tasks.sqlite",
    "name": "tasks",
    "items": [
        ["cog", "TEXT NOT NULL"],
        ["task", "TEXT NOT NULL"],
        ["status", "TEXT NOT NULL"],
    ],
    "inserts": [
        ["rss", "post_feeds", "stopped"],
        ["rss", "post_podcasts", "stopped"],
        ["youtube", "post_videos", "stopped"],
        ["stats", "post_stats", "stopped"],
        ["barca_news", "post_news", "stopped"],
        ["quotes", "autopost", "stopped"],
    ],
}

# Poll
poll_db_polls_schema = {
    "db_file": "poll.sqlite",
    "name": "poll",
    "items": [
        ["uuid", "TEXT NOT NULL"],
        ["msg_id", "TEXT"],
        ["channel", "TEXT"],
        ["poll_text", "TEXT"],
        ["post_time", "TEXT"],
        ["lock_time", "TEXT"],
        ["status_wait_post", "INTEGER"],
        ["status_posted", "INTEGER"],
        ["status_wait_lock", "INTEGER"],
        ["status_locked", "INTEGER"],
    ],
}

poll_db_alternatives_schema = {
    "db_file": "poll.sqlite",
    "name": "poll_alternatives",
    "items": [
        ["uuid", "TEXT NOT NULL"],
        ["emoji", "TEXT NOT NULL"],
        ["input", "TEXT NOT NULL"],
        ["count", "INTEGER"],
    ],
}

# Dilemmas
dilemmas_db_schema = {
    "db_file": "dilemmas.sqlite",
    "name": "dilemmas",
    "items": [["id", "TEXT NOT NULL"], ["dilemmas_text", "TEXT"]],
    "primary": "id",
}

dilemmas_db_log_schema = {
    "db_file": "dilemmas.sqlite",
    "name": "log",
    "items": [["id", " TEXT NOT NULL"], ["msg_id", " TEXT"]],
}

# Invitations
invitations_db_schema = {
    "db_file": "invitations.sqlite",
    "name": "invitations",
    "items": [
        ["invitation_uuid", "TEXT NOT NULL"],
        ["contest_uuid", "TEXT NOT NULL"],
        ["invite_id", "TEXT"],
        ["user_id", "TEXT"],
    ],
    "primary": "invitation_uuid",
}

invitations_db_contest_schema = {
    "db_file": "invitations.sqlite",
    "name": "contest",
    "items": [
        ["contest_uuid", "TEXT NOT NULL"],
        ["contest_name", "TEXT"],
        ["start_datetime", "TEXT"],
        ["stop_datetime", "TEXT"],
        ["channel_id", "INT"],
        ["start_msg", "TEXT"],
        ["active", "INT"],
        ["done", "INT"],
    ],
    "primary": "contest_uuid",
}

invitations_db_log_schema = {
    "db_file": "invitations.sqlite",
    "name": "log",
    "items": [
        ["invite_id", "TEXT NOT NULL"],
        ["visitor_id", "TEXT"],
        ["datetime", "TEXT"],
    ],
    "primary": "invite_id",
}

# Quote
quote_db_schema = {
    "db_file": "quote.sqlite",
    "name": "quote",
    "items": [
        ["uuid", "TEXT NOT NULL UNIQUE"],
        ["channel_id", "INT"],
        ["channel_backup", "TEXT"],
        ["datetime", "TEXT"],
    ],
    "primary": "uuid",
    "autoincrement": False,
}

quote_content_db_schema = {
    "db_file": "quote.sqlite",
    "name": "quote_content",
    "items": [
        ["uuid", "TEXT NOT NULL"],
        ["comment_id", "INT"],
        ["author_id", "INT"],
        ["author_backup", "TEXT"],
        ["content_text", "TEXT"],
        ["content_order", "INT"],
    ],
}

quote_img_db_schema = {
    "db_file": "quote.sqlite",
    "name": "quote_img",
    "items": [
        ["comment_id", "INT"],
        ["img_no", "INT"],
        ["base64", "TEXT"],
    ],
}

quote_db_log_schema = {
    "db_file": "quote.sqlite",
    "name": "log",
    "items": [["uuid", "TEXT NOT NULL"], ["channel_id", "INT"], ["datetime", "TEXT"]],
    "primary": None,
    "autoincrement": False,
}

quote_db_settings_schema = {
    "db_file": "quote.sqlite",
    "name": "settings",
    "items": [["setting", "TEXT NOT NULL"], ["value", "TEXT"]],
    "inserts": [
        ["channel", "quotes"],
        ["autopost_prefix", "Dagens sitat!"],
        ["autopost_tag_role", ""],
        ["autopost_time", ""],
    ],
    "type_checking": {
        "channel": "int",
        "autopost_prefix": "str",
        "autopost_tag_role": "role_id",
        "autopost_time": "str",
    },
}

# Roles
roles_db_msgs_schema = {
    "db_file": "roles.sqlite",
    "name": "messages",
    "items": [
        ["msg_id", " TEXT NOT NULL"],
        ["channel", " TEXT"],
        ["name", " TEXT"],
        ["header", " TEXT"],
        ["content", " TEXT"],
        ["description", " TEXT"],
        ["msg_order", " INTEGER"],
    ],
    "primary": "msg_id",
}

roles_db_roles_schema = {
    "db_file": "roles.sqlite",
    "name": "roles",
    "items": [["msg_id", "TEXT NOT NULL"], ["role", "TEXT"], ["emoji", "TEXT"]],
}

roles_db_settings_schema = {
    "db_file": "roles.sqlite",
    "name": "settings",
    "items": [["setting", "TEXT NOT NULL"], ["value", "TEXT"]],
}

# Stats
log_db_schema = {
    "db_file": "log.sqlite",
    "name": "log",
    "items": [
        ["setting", "TEXT NOT NULL"],
        ["value", "TEXT NOT NULL"],
        ["value_check", "TEXT"],
        ["value_help", "TEXT"],
    ],
    "inserts": [
        ["type", "size", "str", "`size` or `days`"],
        ["limit", "1073741824", "int", "Size in bytes or number of days"],
    ],
}

stats_db_settings_schema = {
    "db_file": "stats.sqlite",
    "name": "settings",
    "items": [["setting", "TEXT NOT NULL"], ["value", "TEXT NOT NULL"]],
    "inserts": [
        ["channel", "stats"],
        ["stats_msg_id", ""],
        ["hide_bot_roles", "True"],
        ["show_code_stats", "False"],
        ["show_members_total", "True"],
        ["show_role_stats", "True"],
        ["sort_roles_abc", "True"],
        ["sort_roles_321", "False"],
        ["sort_min_role_members", -1],
        ["hide_empty_roles", "False"],
    ],
    "type_checking": {
        "channel": "str",
        "hide_bot_roles": "bool",
        "hide_empty_roles": "bool",
        "show_code_stats": "bool",
        "show_members_total": "bool",
        "show_role_stats": "bool",
        "sort_min_role_members": "int",
        "sort_roles_321": "bool",
        "sort_roles_abc": "bool",
        "stats_msg_id": "str",
    },
}

stats_db_hide_roles_schema = {
    "db_file": "stats.sqlite",
    "name": "hide_roles",
    "items": [
        ["role_id", "TEXT NOT NULL"],
    ],
}

stats_db_log_schema = {
    "db_file": "stats_log.sqlite",
    "name": "log",
    "items": [
        ["datetime", "TEXT"],
        ["code_files", "INTEGER"],
        ["code_lines", "INTEGER"],
        ["members", "INTEGER"],
    ],
}

# RSS
rss_db_schema = {
    "db_file": "rss_feeds.sqlite",
    "name": "rss_feeds",
    "items": [
        ["uuid", "TEXT NOT NULL"],
        ["feed_name", "TEXT"],
        ["url", "TEXT"],
        ["channel", "TEXT"],
        ["added", "TEXT"],
        ["added_by", "TEXT"],
        ["feed_type", "TEXT"],
        ["status_url", "TEXT"],
        ["status_url_counter", "INTEGER"],
        ["status_channel", "TEXT"],
        ["num_episodes", "INTEGER"],
    ],
    "primary": "uuid",
    "autoincrement": False,
}

rss_db_filter_schema = {
    "db_file": "rss_feeds.sqlite",
    "name": "filter",
    "items": [
        ["uuid", "TEXT NOT NULL"],
        ["allow_or_deny", "TEXT NOT NULL"],
        ["filter", "TEXT NOT NULL"],
    ],
    "primary": None,
    "autoincrement": False,
}

rss_db_settings_schema = {
    "db_file": "rss_feeds.sqlite",
    "name": "settings",
    "items": [
        ["setting", "TEXT NOT NULL"],
        ["value", "TEXT"],
        ["value_check", "TEXT NOT NULL"],
    ],
    "inserts": [
        ["show_pod_description_in_embed", "False", "bool"],
        ["podcast_ratings_enabled", "True", "bool"],
        ["podcast_discussion_enabled", "True", "bool"],
    ],
    "primary": None,
    "autoincrement": False,
}

rss_db_ratings_schema = {
    "db_file": "rss_feeds.sqlite",
    "name": "ratings",
    "items": [
        ["user_id", "TEXT NOT NULL"],
        ["show_uuid", "TEXT NOT NULL"],
        ["episode_uuid", "TEXT NOT NULL"],
        ["rating", "TEXT NOT NULL"],
        ["datetime", "TEXT"],
    ],
    "primary": None,
    "autoincrement": False,
}

rss_db_log_schema = {
    "db_file": "rss_log.sqlite",
    "name": "log",
    "items": [
        ["uuid", "TEXT NOT NULL"],
        ["url", "TEXT"],
        ["date", "TEXT"],
        ["hash", "TEXT"],
    ],
    "primary": None,
    "autoincrement": False,
}

# Youtube
youtube_db_schema = {
    "db_file": "youtube_feeds.sqlite",
    "name": "youtube_feeds",
    "items": [
        ["uuid", "TEXT NOT NULL"],
        ["feed_name", "TEXT"],
        ["url", "TEXT"],
        ["channel", "TEXT"],
        ["added", "TEXT"],
        ["added_by", "TEXT"],
        ["status_url", "TEXT"],
        ["status_url_counter", "INTEGER"],
        ["status_channel", "TEXT"],
        ["youtube_id", "TEXT"],
        ["playlist_id", "TEXT"],
    ],
    "primary": "uuid",
    "autoincrement": False,
}

youtube_db_filter_schema = {
    "db_file": "youtube_feeds.sqlite",
    "name": "filter",
    "items": [
        ["uuid", "TEXT NOT NULL"],
        ["allow_or_deny", "TEXT NOT NULL"],
        ["filter", "TEXT NOT NULL"],
    ],
    "primary": None,
    "autoincrement": False,
}

youtube_db_log_schema = {
    "db_file": "youtube_log.sqlite",
    "name": "log",
    "items": [
        ["uuid", " TEXT NOT NULL"],
        ["url", " TEXT"],
        ["date", " TEXT"],
        ["hash", "TEXT"],
    ],
    "primary": None,
    "autoincrement": False,
}

locale_db_schema = {
    "db_file": "locale.sqlite",
    "name": "locale",
    "items": [["setting", "TEXT NOT NULL"], ["value", "TEXT NOT NULL"]],
    "inserts": [["language", "en"], ["timezone", "UTC"]],
    "primary": None,
    "autoincrement": False,
}

### Botlines ###
# Generiske
GUILD_NOT_FOUND = "Fant ikke serveren {}, dobbeltsjekk navnet i .env"

# COG - GENERIC MESSAGES
COG_STARTING = "Starting cog: `{}`"
COG_STARTED = "Started cog: `{}`"

# COG

# CORE
FEEDS_URL_ERROR = "Failed"
FEEDS_URL_STALE = "Stale"
FEEDS_URL_ERROR_LIMIT = 3
FEEDS_URL_SUCCESS = "OK"
CHANNEL_STATUS_ERROR = "Failed"
CHANNEL_STATUS_SUCCESS = "OK"

# COG - YOUTUBE
YOUTUBE_RSS_LINK = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
YOUTUBE_PLAYLIST_RSS_LINK = "https://www.youtube.com/feeds/videos.xml?playlist_id={}"

# VARIABLES
input_split_regex = r"[\s\.\-_,;\\\/]+"
roles_ensure_separator = ("><", "> <")
scrapeops_url = (
    "http://headers.scrapeops.io/v1/browser-headers?api_key={}&num_results=100"
)


### DISCORD PERMISSIONS ###
SELECT_PERMISSIONS = {
    "general": [
        "administrator",
        "ban_members",
        "change_nickname",
        "create_expressions",
        "create_instant_invite",
        "kick_members",
        "manage_channels",
        "manage_emojis",
        "manage_events",
        "manage_expressions",
        "manage_guild",
        "manage_nicknames",
        "manage_roles",
        "manage_webhooks",
        "moderate_membersview_audit_log",
        "view_channel",
        "view_guild_insights",
    ],
    "text": [
        "add_reactions",
        "attach_files",
        "create_private_threads",
        "create_public_threads",
        "embed_links",
        "auto-embedded",
        "external_emojis",
        "external_stickers",
        "manage_messages",
        "manage_threads",
        "mention_everyone",
        "read_messages",
        "send_messages_in_threads",
        "send_messages",
        "send_tts_messages",
        "use_application_commands",
    ],
    "voice": [
        "connect",
        "deafen_members",
        "move_members",
        "mute_members",
        "priority_speaker",
        "request_to_speak",
        "send_voice_messages",
        "speak",
        "stream",
        "use_embedded_activities",
        "use_external_sounds",
        "use_soundboard",
        "use_voice_activation",
    ],
}

if __name__ == "__main__":
    pass
