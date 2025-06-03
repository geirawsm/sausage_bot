#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'envs: Set variables for the module like folder, files and botlines'

from pathlib import Path

from sausage_bot.util.args import args

# Folders
ROOT_DIR = Path(__file__).resolve().parent.parent
COGS_DIR = ROOT_DIR / 'cogs'
if args.data_dir:
    DATA_DIR = Path(args.data_dir).resolve()
else:
    DATA_DIR = ROOT_DIR / 'data'
JSON_DIR = DATA_DIR / 'json'
if args.db_dir:
    DB_DIR = Path(args.db_dir).resolve()
else:
    DB_DIR = DATA_DIR / 'db'
LOG_DIR = DATA_DIR / 'logs'
STATIC_DIR = DATA_DIR / 'static'
TEMP_DIR = ROOT_DIR / 'tempfiles'
MERMAID_DIR = ROOT_DIR / 'docs' / 'mermaid_charts'
LOCALE_DIR = ROOT_DIR / 'locale'
TESTPARSE_DIR = ROOT_DIR / 'test/test_parse'

# Relative paths
COGS_REL_DIR = 'sausage_bot.cogs'

# Testfiles
test_xml_good = TESTPARSE_DIR / 'feed_good_angrymetalguy.xml'
test_xml_bad1 = TESTPARSE_DIR / 'feed_bad_angrymetalguy.xml'
test_xml_bad2 = TESTPARSE_DIR / 'feed_bad_bbc.html'
test_nifs_json_good = TESTPARSE_DIR / 'nifs.json'
test_vglive_json_good = TESTPARSE_DIR / 'vglive.json'
test_vglive_tv_json_good = TESTPARSE_DIR / 'vglive_tv.json'
test_tv2livesport_json_good = TESTPARSE_DIR / 'tv2livesport.json'

# Files
version_file = ROOT_DIR / 'version.json'
env_file = DATA_DIR / '.env'
rss_feeds_file = JSON_DIR / 'rss-feeds.json'
rss_feeds_logs_file = JSON_DIR / 'rss-feeds-log.json'
youtube_feeds_file = JSON_DIR / 'yt-feeds.json'
youtube_feeds_logs_file = JSON_DIR / 'yt-feeds-log.json'
scrape_logs_file = JSON_DIR / 'scrape-log.json'
quote_file = JSON_DIR / 'quotes.json'
quote_log_file = JSON_DIR / 'quotes-log.json'
dilemmas_file = JSON_DIR / 'dilemmas.json'
dilemmas_log_file = JSON_DIR / 'dilemmas-log.json'
cogs_status_file = JSON_DIR / 'cogs_status.json'
stats_file = JSON_DIR / 'stats.json'
stats_logs_file = JSON_DIR / 'stats_logs.json'
roles_settings_file = JSON_DIR / 'roles_settings.json'

# Template content
env_template = '''
# Basic settings
DISCORD_TOKEN=
DISCORD_GUILD=
BOT_ID=
PREFIX=
LOCALE=
BOT_DUMP_CHANNEL=bot
WATCHING=
'''

# Stats
stats_template = {
    'channel': 'stats',
    'show_role_stats': True,
    'hide_bot_roles': False,
    'sort_roles_abc': True,
    'sort_roles_321': False,
    'show_code_stats': True,
    'hide_empty_roles': False
}

# Roles
roles_template = {
    'channel': 'roles',
    'reaction_messages': {},
    'unique_role': {
        'not_include_in_total': [],
        'role': 0
    }
}

# Cogs.env
tasks_db_schema = {
    'db_file': str(DB_DIR / 'tasks.sqlite'),
    'name': 'tasks',
    'items': [
        ['cog', 'TEXT NOT NULL'],
        ['task', 'TEXT NOT NULL'],
        ['status', 'TEXT NOT NULL']
    ],
    'inserts': [
        ['rss', 'post_feeds', 'stopped'],
        ['rss', 'post_podcasts', 'stopped']
    ]
}

# Poll
poll_db_polls_schema = {
    'db_file': str(DB_DIR / 'poll.sqlite'),
    'name': 'poll',
    'items': [
        ['uuid', 'TEXT NOT NULL'],
        ['msg_id', 'TEXT'],
        ['channel', 'TEXT'],
        ['poll_text', 'TEXT'],
        ['post_time', 'TEXT'],
        ['lock_time', 'TEXT'],
        ['status_wait_post', 'INTEGER'],
        ['status_posted', 'INTEGER'],
        ['status_wait_lock', 'INTEGER'],
        ['status_locked', 'INTEGER']
    ]
}

poll_db_alternatives_schema = {
    'db_file': str(DB_DIR / 'poll.sqlite'),
    'name': 'poll_alternatives',
    'items': [
        ['uuid', 'TEXT NOT NULL'],
        ['emoji', 'TEXT NOT NULL'],
        ['input', 'TEXT NOT NULL'],
        ['count', 'INTEGER']
    ]
}

# Dilemmas
dilemmas_db_schema = {
    'db_file': str(DB_DIR / 'dilemmas.sqlite'),
    'name': 'dilemmas',
    'items': [
        ['id', 'TEXT NOT NULL'],
        ['dilemmas_text', 'TEXT']
    ],
    'primary': 'id'
}

dilemmas_db_log_schema = {
    'db_file': str(DB_DIR / 'dilemmas.sqlite'),
    'name': 'log',
    'items': [
        ['id', ' TEXT NOT NULL'],
        ['msg_id', ' TEXT']
    ]
}

# Quote
quote_db_schema = {
    'db_file': str(DB_DIR / 'quote.sqlite'),
    'name': 'quote',
    'items': [
        ['uuid', 'TEXT NOT NULL UNIQUE'],
        ['quote_text', 'TEXT'],
        ['datetime', 'TEXT']
    ],
    'primary': 'uuid',
    'autoincrement': False
}

quote_db_log_schema = {
    'db_file': str(DB_DIR / 'quote.sqlite'),
    'name': 'log',
    'items': [
        ['uuid', 'TEXT NOT NULL'],
        ['msg_id', 'TEXT']
    ],
    'primary': None,
    'autoincrement': False
}

quote_db_settings_schema = {
    'db_file': str(DB_DIR / 'quote.sqlite'),
    'name': 'settings',
    'items': [
        ['setting', 'TEXT NOT NULL'],
        ['value', 'TEXT']
    ],
    'inserts': [
        ['channel', 'quotes'],
        ['autopost_prefix', 'Dagens sitat!'],
        ['autopost_tag_role', ''],
    ],
    'type_checking': {
        'channel': 'int',
        'autopost_prefix': 'str',
        'autopost_tag_role': 'role_id'
    },
}

# Roles
roles_db_msgs_schema = {
    'db_file': str(DB_DIR / 'roles.sqlite'),
    'name': 'messages',
    'items': [
        ['msg_id', ' TEXT NOT NULL'],
        ['channel', ' TEXT'],
        ['name', ' TEXT'],
        ['header', ' TEXT'],
        ['content', ' TEXT'],
        ['description', ' TEXT'],
        ['msg_order', ' INTEGER']
    ],
    'primary': 'msg_id'
}

roles_db_roles_schema = {
    'db_file': str(DB_DIR / 'roles.sqlite'),
    'name': 'roles',
    'items': [
        ['msg_id', 'TEXT NOT NULL'],
        ['role', 'TEXT'],
        ['emoji', 'TEXT']
    ]
}

roles_db_settings_schema = {
    'db_file': str(DB_DIR / 'roles.sqlite'),
    'name': 'settings',
    'items': [
        ['setting', 'TEXT NOT NULL'],
        ['value', 'TEXT']
    ]
}

# Stats
log_db_schema = {
    'db_file': str(DB_DIR / 'log.sqlite'),
    'name': 'log',
    'items': [
        ['setting', 'TEXT NOT NULL'],
        ['value', 'TEXT NOT NULL'],
        ['value_check', 'TEXT'],
        ['value_help', 'TEXT']
    ],
    'inserts': [
        ['type', 'size', 'str', '`size` or `days`'],
        ['limit', '1073741824', 'int', 'Size in bytes or number of days']
    ]
}

stats_db_settings_schema = {
    'db_file': str(DB_DIR / 'stats.sqlite'),
    'name': 'settings',
    'items': [
        ['setting', 'TEXT NOT NULL'],
        ['value', 'TEXT NOT NULL']
    ],
    'inserts': [
        ['channel', 'stats'],
        ['stats_msg_id', ''],
        ['hide_bot_roles', 'True'],
        ['show_code_stats', 'False'],
        ['show_role_stats', 'True'],
        ['sort_roles_abc', 'True'],
        ['sort_roles_321', 'False'],
        ['sort_min_role_members', -1],
        ['hide_empty_roles', 'False']
    ],
    'type_checking': {
        'channel': 'str',
        'hide_bot_roles': 'bool',
        'hide_empty_roles': 'bool',
        'show_code_stats': 'bool',
        'show_role_stats': 'bool',
        'sort_min_role_members': 'int',
        'sort_roles_321': 'bool',
        'sort_roles_abc': 'bool',
        'stats_msg_id': 'str'
    }
}

stats_db_hide_roles_schema = {
    'db_file': str(DB_DIR / 'stats.sqlite'),
    'name': 'hide_roles',
    'items': [
        ['role_id', 'TEXT NOT NULL'],
    ]
}

stats_db_log_schema = {
    'db_file': str(DB_DIR / 'stats_log.sqlite'),
    'name': 'log',
    'items': [
        ['datetime', 'TEXT'],
        ['code_files', 'INTEGER'],
        ['code_lines', 'INTEGER'],
        ['members', 'INTEGER']
    ]
}

# RSS
rss_db_schema = {
    'db_file': str(DB_DIR / 'rss_feeds.sqlite'),
    'name': 'rss_feeds',
    'items': [
        ['uuid', 'TEXT NOT NULL'],
        ['feed_name', 'TEXT'],
        ['url', 'TEXT'],
        ['channel', 'TEXT'],
        ['added', 'TEXT'],
        ['added_by', 'TEXT'],
        ['feed_type', 'TEXT'],
        ['status_url', 'TEXT'],
        ['status_url_counter', 'INTEGER'],
        ['status_channel', 'TEXT'],
        ['num_episodes', 'INTEGER']
    ],
    'primary': 'uuid',
    'autoincrement': False
}

rss_db_filter_schema = {
    'db_file': str(DB_DIR / 'rss_feeds.sqlite'),
    'name': 'filter',
    'items': [
        ['uuid', 'TEXT NOT NULL'],
        ['allow_or_deny', 'TEXT NOT NULL'],
        ['filter', 'TEXT NOT NULL']
    ],
    'primary': None,
    'autoincrement': False
}

rss_db_settings_schema = {
    'db_file': str(DB_DIR / 'rss_feeds.sqlite'),
    'name': 'settings',
    'items': [
        ['setting', 'TEXT NOT NULL'],
        ['value', 'TEXT'],
        ['value_check', 'TEXT NOT NULL']
    ],
    'inserts': [
        ['show_pod_description_in_embed', 'False', 'bool']
    ],
    'primary': None,
    'autoincrement': False
}

rss_db_log_schema = {
    'db_file': str(DB_DIR / 'rss_log.sqlite'),
    'name': 'log',
    'items': [
        ['uuid', 'TEXT NOT NULL'],
        ['url', 'TEXT'],
        ['date', 'TEXT'],
        ['hash', 'TEXT']
    ],
    'primary': None,
    'autoincrement': False
}

# Youtube
youtube_db_schema = {
    'db_file': str(DB_DIR / 'youtube_feeds.sqlite'),
    'name': 'youtube_feeds',
    'items': [
        ['uuid', 'TEXT NOT NULL'],
        ['feed_name', 'TEXT'],
        ['url', 'TEXT'],
        ['channel', 'TEXT'],
        ['added', 'TEXT'],
        ['added_by', 'TEXT'],
        ['status_url', 'TEXT'],
        ['status_url_counter', 'INTEGER'],
        ['status_channel', 'TEXT'],
        ['youtube_id', 'TEXT'],
        ['playlist_id', 'TEXT']
    ],
    'primary': 'uuid',
    'autoincrement': False
}

youtube_db_filter_schema = {
    'db_file': str(DB_DIR / 'youtube_feeds.sqlite'),
    'name': 'filter',
    'items': [
        ['uuid', 'TEXT NOT NULL'],
        ['allow_or_deny', 'TEXT NOT NULL'],
        ['filter', 'TEXT NOT NULL']
    ],
    'primary': None,
    'autoincrement': False
}

youtube_db_log_schema = {
    'db_file': str(DB_DIR / 'youtube_log.sqlite'),
    'name': 'log',
    'items': [
        ['uuid', ' TEXT NOT NULL'],
        ['url', ' TEXT'],
        ['date', ' TEXT'],
        ['hash', 'TEXT']
    ],
    'primary': None,
    'autoincrement': False
}

locale_db_schema = {
    'db_file': str(DB_DIR / 'locale.sqlite'),
    'name': 'locale',
    'items': [
        ['setting', 'TEXT NOT NULL'],
        ['value', 'TEXT NOT NULL']
    ],
    'inserts': [
        ['language', 'en'],
        ['timezone', 'UTC']
    ],
    'primary': None,
    'autoincrement': False
}

### Botlines ###
# Generiske
GUILD_NOT_FOUND = 'Fant ikke serveren {}, dobbeltsjekk navnet i .env'

# COG - GENERIC MESSAGES
COG_STARTING = 'Starting cog: `{}`'

# COG

# CORE
FEEDS_URL_ERROR = 'Failed'
FEEDS_URL_STALE = 'Stale'
FEEDS_URL_ERROR_LIMIT = 3
FEEDS_URL_SUCCESS = 'OK'
CHANNEL_STATUS_ERROR = 'Failed'
CHANNEL_STATUS_SUCCESS = 'OK'

# COG - YOUTUBE
YOUTUBE_RSS_LINK = 'https://www.youtube.com/feeds/videos.xml?channel_id={}'
YOUTUBE_PLAYLIST_RSS_LINK = 'https://www.youtube.com/feeds/videos.xml?'\
    'playlist_id={}'

# VARIABLES
input_split_regex = r'[\s\.\-_,;\\\/]+'
roles_ensure_separator = ('><', '> <')
scrapeops_url = 'http://headers.scrapeops.io/v1/browser-headers?api_key={}&num_results=100'


### DISCORD PERMISSIONS ###
SELECT_PERMISSIONS = {
    'general': [
        'administrator', 'ban_members', 'change_nickname',
        'create_expressions','create_instant_invite', 'kick_members',
        'manage_channels', 'manage_emojis', 'manage_events',
        'manage_expressions', 'manage_guild', 'manage_nicknames',
        'manage_roles', 'manage_webhooks', 'moderate_members'
        'view_audit_log', 'view_channel', 'view_guild_insights'
    ],
    'text': [
        'add_reactions', 'attach_files', 'create_private_threads',
        'create_public_threads', 'embed_links', 'auto-embedded',
        'external_emojis', 'external_stickers', 'manage_messages',
        'manage_threads', 'mention_everyone', 'read_messages',
        'send_messages_in_threads', 'send_messages', 'send_tts_messages',
        'use_application_commands'
    ],
    'voice': [
        'connect', 'deafen_members', 'move_members', 'mute_members',
        'priority_speaker', 'request_to_speak', 'send_voice_messages',
        'speak', 'stream', 'use_embedded_activities',
        'use_external_sounds', 'use_soundboard', 'use_voice_activation'
    ]
}


if __name__ == "__main__":
    pass
