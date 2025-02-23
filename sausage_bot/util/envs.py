#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'Set variables for the module like folder, files and botlines'

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
        ['youtube_id', 'TEXT']
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
        ['date', ' TEXT']
    ],
    'primary': None,
    'autoincrement': False
}

locale_db_schema = {
    'db_file': str(DB_DIR / 'locale.sqlite'),
    'name': 'locale',
    'items': [
        ['locale', 'TEXT']
    ],
    'primary': None,
    'autoincrement': False
}


def log_extra_info(type):
    infos = {
        'info': {
            'log': 'LOG',
            'verbose': 'VERBOSE',
            'db': 'DBs',
            'debug': 'DEBUG',
            'error': 'ERROR',
            'i18n': 'I18N'
        },
        'length': 7
    }
    split = int((infos['length'] - len(infos['info'][type])) / 2)
    return '{s}{text}{s}'.format(
        s=' ' * split, text=infos['info'][type]
    )


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

# COG - AUTOEVENT
AUTOEVENT_PARSE_ERROR = 'Klarte ikke parsing av {} - fikk følgende feil:\n{}'

# VARIABLES
input_split_regex = r'[\s\.\-_,;\\\/]+'
roles_ensure_separator = ('><', '> <')
scrapeops_url = 'http://headers.scrapeops.io/v1/browser-headers?api_key={}&num_results=100'


### DISCORD PERMISSIONS ###
SELECT_PERMISSIONS = {
    'general': {
        'administrator': 'Allows all permissions and bypasses channel '
                         'permission overwrites',
        'ban_members': 'Allows banning members',
        'change_nickname': 'Allows for modification of own nickname',
        'create_expressions': 'Allows for creating emojis, stickers, and '
                              'soundboard sounds, and editing and deleting '
                              'those created by the current user',
        'create_instant_invite': 'Allows creation of instant invites',
        'kick_members': 'Allows kicking members',
        'manage_channels': 'Allows management and editing of channels',
        'manage_emojis': 'Allows for editing and deleting emojis',
        'manage_events': 'Allows for creating, editing and deleting '
                         'scheduled events created by all users',
        'manage_expressions': 'Allows for creating, editing and deleting '
                              'emojis, stickers, and soundboard sounds '
                              'created by all users',
        'manage_guild': 'Allows management and editing of the guild',
        'manage_nicknames': 'Allows for modification of other users nicknames',
        'manage_roles': 'Allows management and editing of roles',
        'manage_webhooks': 'Allows management and editing of webhooks',
        'moderate_members': 'Allows for timing out users to prevent them '
                            'from sending or reacting to messages in chat '
                            'and threads, and from speaking in voice and '
                            'stage channels',
        'view_audit_log': 'Allows for viewing of audit logs',
        'view_channel': 'Allows guild members to view a channel, which '
                        'includes reading messages in text channels and '
                        'joining voice channels',
        'view_guild_insights': 'Allows for viewing guild insights',
    },
    'text': {
        'add_reactions': 'Allows for the addition of reactions to messages',
        'attach_files': 'Allows for uploading images and files',
        'create_private_threads': 'Allows for creating private threads',
        'create_public_threads': 'Allows for creating public and '
                                 'announcement threads',
        'embed_links': 'Links sent by users with this permission will be '
                       'auto-embedded',
        'external_emojis': 'Allows the usage of custom emojis from other '
                           'servers',
        'external_stickers': 'Allows the usage of custom stickers from '
                             'other servers',
        'manage_messages': 'Allows for deletion of other users messages',
        'manage_threads': 'Allows for deleting and archiving threads, and '
                          'viewing all private threads',
        'mention_everyone': 'Allows for using the @everyone tag to notify '
                            'all users in a channel, and the @here tag to '
                            'notify all online users in a channel',
        'read_messages': 'Allows for reading of message history',
        'send_messages_in_threads': 'Allows for sending messages in threads',
        'send_messages': 'Allows for sending messages in a channel and '
                         'creating threads in a forum (does not allow sending '
                         'messages in threads)',
        'send_tts_messages': 'Allows for sending of /tts messages',
        'use_application_commands': 'Allows members to use application '
                                    'commands, including slash commands and '
                                    'context menu commands.'
    },
    'voice': {
        'connect': 'Allows for joining of a voice channel',
        'deafen_members': 'Allows for deafening of members in a voice channel',
        'move_members': 'Allows for moving of members between voice channels',
        'mute_members': 'Allows for muting members in a voice channel',
        'priority_speaker': 'Allows for using priority speaker in a voice '
                            'channel',
        'request_to_speak': 'Allows for requesting to speak in stage '
                            'channels.',
        'send_voice_messages': 'Allows sending voice messages',
        'speak': 'Allows for speaking in a voice channel',
        'stream': 'Allows the user to go live',
        'use_embedded_activities': 'Allows for using Activities (applications '
                                   'with the EMBEDDED flag) in a voice '
                                   'channel',
        'use_external_sounds': 'Allows the usage of custom soundboard sounds '
                               'from other servers',
        'use_soundboard': 'Allows for using soundboard in a voice channel',
        'use_voice_activation': 'Allows for using voice-activity-detection in '
                                'a voice channel',
    }
}


if __name__ == "__main__":
    pass
