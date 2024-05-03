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
DB_DIR = DATA_DIR / 'db'
LOG_DIR = DATA_DIR / 'logs'
STATIC_DIR = DATA_DIR / 'static'
MERMAID_DIR = ROOT_DIR / 'docs' / 'mermaid_charts'

# Relative paths
COGS_REL_DIR = 'sausage_bot.cogs'

# Files
env_file = DATA_DIR / '.env'
rss_feeds_file = JSON_DIR / 'rss-feeds.json'
rss_feeds_logs_file = JSON_DIR / 'rss-feeds-log.json'
yt_feeds_file = JSON_DIR / 'yt-feeds.json'
yt_feeds_logs_file = JSON_DIR / 'yt-feeds-log.json'
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
BOT_DUMP_CHANNEL=general
WATCHING=
'''

# Stats
stats_template = {
    'channel': 'stats',
    'show_role_stats': True,
    'hide_roles': '',
    'hide_bot_roles': False,
    'sort_roles_abc': True,
    'sort_roles_321': False,
    'show_code_stats': True
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

# Cogs
tasks_db_schema = {
    'db_file': str(DB_DIR / 'tasks.sqlite'),
    'name': 'tasks',
    'items': [
        'cog TEXT NOT NULL',
        'task TEXT NOT NULL',
        'status TEXT NOT NULL'
    ]
}

# Poll
poll_db_polls_schema = {
    'db_file': str(DB_DIR / 'poll.sqlite'),
    'name': 'poll',
    'items': [
        'uuid TEXT NOT NULL',
        'msg_id TEXT',
        'channel TEXT',
        'poll_text TEXT',
        'post_time TEXT',
        'lock_time TEXT',
        'status_wait_post INTEGER',
        'status_posted INTEGER',
        'status_wait_lock INTEGER',
        'status_locked INTEGER'
    ]
}

poll_db_alternatives_schema = {
    'db_file': str(DB_DIR / 'poll.sqlite'),
    'name': 'poll_alternatives',
    'items': [
        'uuid TEXT NOT NULL',
        'emoji TEXT NOT NULL',
        'input TEXT NOT NULL',
        'count INTEGER'
    ]
}

# Dilemmas
dilemmas_db_schema = {
    'db_file': str(DB_DIR / 'dilemmas.sqlite'),
    'name': 'dilemmas',
    'items': [
        'id TEXT NOT NULL',
        'dilemmas_text TEXT'
    ],
    'primary': 'id'
}

dilemmas_db_log_schema = {
    'db_file': str(DB_DIR / 'dilemmas.sqlite'),
    'name': 'log',
    'items': [
        'id TEXT NOT NULL',
        'msg_id TEXT'
    ]
}

# Quote
quote_db_schema = {
    'db_file': str(DB_DIR / 'quote.sqlite'),
    'name': 'quote',
    'items': [
        'uuid TEXT NOT NULL UNIQUE',
        'quote_text TEXT',
        'datetime TEXT'
    ],
    'primary': 'uuid',
    'autoincrement': False
}

quote_db_log_schema = {
    'db_file': str(DB_DIR / 'quote.sqlite'),
    'name': 'log',
    'items': [
        'uuid TEXT NOT NULL',
        'msg_id TEXT'
    ],
    'primary': None,
    'autoincrement': False
}

# Roles
roles_db_msgs_schema = {
    'db_file': str(DB_DIR / 'roles.sqlite'),
    'name': 'messages',
    'items': [
        'msg_id TEXT NOT NULL',
        'channel TEXT',
        'name TEXT',
        'content TEXT',
        'description TEXT',
        'msg_order INTEGER'
    ],
    'primary': 'msg_id'
}

roles_db_roles_schema = {
    'db_file': str(DB_DIR / 'roles.sqlite'),
    'name': 'roles',
    'items': [
        'msg_id TEXT NOT NULL',
        'role_name TEXT',
        'emoji TEXT'
    ]
}

roles_db_settings_schema = {
    'db_file': str(DB_DIR / 'roles.sqlite'),
    'name': 'settings',
    'items': [
        'setting TEXT',
        'value TEXT'
    ]
}

# Stats
stats_db_schema = {
    'db_file': str(DB_DIR / 'stats.sqlite'),
    'name': 'settings',
    'items': [
        'setting TEXT NOT NULL',
        'value TEXT NOT NULL',
        'value_check TEXT',
        'value_help TEXT'
    ],
    'inserts': [
        ['channel', '', 'str', 'Text'],
        ['hide_roles', '', 'str', 'Text'],
        ['hide_bot_roles', 'True', 'bool', 'True/False'],
        ['show_code_stats', 'False', 'bool', 'True/False'],
        ['show_role_stats', 'True', 'bool', 'True/False'],
        ['sort_roles_abc', 'True', 'bool', 'True/False'],
        ['sort_roles_321', 'False', 'bool', 'True/False'],
        ['sort_min_role_members', 0, 'int', 'Number']
    ]
}

stats_db_log_schema = {
    'db_file': str(DB_DIR / 'stats_log.sqlite'),
    'name': 'log',
    'items': [
        'datetime TEXT',
        'code_files INTEGER',
        'code_lines INTEGER',
        'members INTEGER'
    ]
}

# RSS
rss_db_schema = {
    'db_file': str(DB_DIR / 'rss_feeds.sqlite'),
    'name': 'rss_feeds',
    'items': [
        'uuid TEXT NOT NULL',
        'feed_name TEXT',
        'url TEXT',
        'channel TEXT',
        'added TEXT',
        'added_by TEXT',
        'status_url TEXT',
        'status_url_counter INTEGER',
        'status_channel TEXT'
    ],
    'primary': 'uuid',
    'autoincrement': False
}

rss_db_filter_schema = {
    'db_file': str(DB_DIR / 'rss_feeds.sqlite'),
    'name': 'filter',
    'items': [
        'uuid TEXT NOT NULL',
        'allow_or_deny TEXT NOT NULL',
        'filter TEXT NOT NULL'
    ],
    'primary': None,
    'autoincrement': False
}

rss_db_log_schema = {
    'db_file': str(DB_DIR / 'rss_log.sqlite'),
    'name': 'log',
    'items': [
        'uuid TEXT NOT NULL',
        'url TEXT',
        'date TEXT'
    ],
    'primary': None,
    'autoincrement': False
}

# Youtube
youtube_db_schema = {
    'db_file': str(DB_DIR / 'youtube_feeds.sqlite'),
    'name': 'youtube_feeds',
    'items': [
        'uuid TEXT NOT NULL',
        'feed_name TEXT',
        'url TEXT',
        'channel TEXT',
        'added TEXT',
        'added_by TEXT',
        'status_url TEXT',
        'status_url_counter INTEGER',
        'status_channel TEXT',
        'youtube_id TEXT'
    ],
    'primary': 'uuid',
    'autoincrement': False
}

youtube_db_filter_schema = {
    'db_file': str(DB_DIR / 'youtube_feeds.sqlite'),
    'name': 'filter',
    'items': [
        'uuid TEXT NOT NULL',
        'allow_or_deny TEXT NOT NULL',
        'filter TEXT NOT NULL'
    ],
    'primary': None,
    'autoincrement': False
}


youtube_db_log_schema = {
    'db_file': str(DB_DIR / 'youtube_log.sqlite'),
    'name': 'log',
    'items': [
        'uuid TEXT NOT NULL',
        'url TEXT',
        'date TEXT'
    ],
    'primary': None,
    'autoincrement': False
}


def log_extra_info(type):
    infos = {
        'info': {
            'log': 'LOG',
            'verbose': 'VERBOSE',
            'database': 'DATABASES',
            'debug': 'DEBUG',
            'error': 'ERROR'
        },
        'length': 9
    }
    split = int((infos['length'] - len(infos['info'][type])) / 2)
    return '{s}{text}{s}'.format(
        s=' '*split, text=infos['info'][type]
    )


### Botlines ###
# Generiske
GUILD_NOT_FOUND = 'Fant ikke serveren {}, dobbeltsjekk navnet i .env'
NOT_AUTHORIZED = 'Du har ikke tilgang til den kommandoen'
TOO_MANY_ARGUMENTS = 'Du har gitt for mange argumenter til kommandoen'
TOO_FEW_ARGUMENTS = 'Du har gitt for få argumenter til kommandoen'
CHANNEL_NOT_FOUND = 'Finner ikke kanalen `{}` på denne discord-serveren'
POST_TO_NON_EXISTING_CHANNEL = 'Prøver å poste til {}, men kanalen '\
    'finnes ikke'
ERROR_WITH_ERROR_MSG = 'Feil: {}'
COMPARING_IDS = 'Sammenligner med `{}` ({}) med `{}` ({})'
CREATING_DB_FILES = 'Sjekker databasefil'
BOT_NOT_SET_UP = 'The bot is not properly set up'

# MAIN
PURGE_DESC = 'Successfully purged {} messages.\nCommand executed by {}.'

# COG - COG ADMIN IN MAIN
COGS_TOO_FEW_ARGUMENTS = 'Du har gitt for få argumenter til kommandoen'
COGS_CHANGE_STATUS_FAIL = 'Klarte ikke å endre status. Feilmelding: {}'
COGS_WRONG_STATUS = 'Kjente ikke igjen status `{}`'
COGS_ENABLED = 'Aktiverte `{}`'
COGS_DISABLED = 'Deaktiverte `{}`'
ALL_COGS_ENABLED = 'Aktiverte alle cogs'
ALL_COGS_DISABLED = 'Deaktiverte alle cogs'

# COG - GENERIC MESSAGES
COG_STARTING = 'Starting cog: `{}`'

# COG
# RSS
RSS_URL_NOT_OK = 'Linken du ga ser ikke ut til å være en ordenlig URL'
RSS_URL_AND_CHANNEL_NOT_OK = 'Du må oppgi både link og hvilken kanal '\
    'du ønsker den skal publiseres til.'
RSS_ADDED = '{} ble lag til i kanalen {}'
RSS_ADDED_BOT = '{} la til feeden {} ({}) til kanalen {}'
RSS_REMOVED = 'RSS-feeden `{}` ble fjernet'
RSS_REMOVED_BOT = 'RSS-feeden `{}` ble fjernet av {}'
RSS_TRIED_REMOVED_BOT = '{} forsøkte å fjerne RSS-feeden `{}`, '\
    'men det oppsto en feil'
RSS_COULD_NOT_REMOVE = 'Klarte ikke å fjerne RSS-feeden {}'
RSS_FEED_CHANNEL_CHANGE = 'rss: {} endret kanalen til feeden `{}` til `{}`'
RSS_LIST_ARG_WRONG = 'Kjenner ikke til kommandoen {}'
RSS_INVALID_URL = 'Inputen `{}` er ikke en ordentlig URL. Dobbelsjekk staving.'
RSS_MISSING_SCHEME = 'URLen `{}` hadde ikke (http/https). Legger til og '\
    'prøver igjen...'
RSS_CONNECTION_ERROR = 'Feil ved oppkobling til URLen: {}'
RSS_NOT_ABLE_TO_SCRAPE = 'Klarte ikke å scrape {}: {}'
RSS_NO_FEEDS_FOUND = 'Fant ingen RSS-feeds'
RSS_FEED_POSTS_IS_NONE = '{}: this feed returned NoneType.'
RSS_CHANGED_CHANNEL = 'Endret kanal for feeden `{}` til `{}`'
RSS_VARS = {
    'feed_name': {
        'title': 'Name', 'db_col': 'feed_name', 'max_len': 0, 'list_type': []
    },
    'url': {
        'title': 'Feed', 'db_col': 'url', 'max_len': 0, 'list_type': []
    },
    'channel': {
        'title': 'Channel', 'db_col': 'channel', 'max_len': 0, 'list_type': []
    },
    'added': {
        'title': 'Added', 'db_col': 'added', 'max_len': 0,
        'list_type': ['added']
    },
    'added_by': {
        'title': 'Added by', 'db_col': 'added_by', 'max_len': 0,
        'list_type': ['added']
    },
    'filter': {
        'title': 'Filter', 'db_col': 'Filter', 'max_len': 30,
        'list_type': ['filter']
    }
}

# CORE
FEEDS_SOUP_ERROR = 'Feil ved lesing av `soup` fra {}: {}'
FEEDS_LINK_INDEX_ERROR = 'Fikk IndexError ved henting av link til {} i {}'
FEEDS_NONE_VALUE_AS_TEXT = 'Ingen'
FEEDS_URL_ERROR = 'Failed'
FEEDS_URL_STALE = 'Stale'
FEEDS_URL_ERROR_LIMIT = 3
FEEDS_URL_SUCCESS = 'OK'
CHANNEL_STATUS_ERROR = 'Failed'
CHANNEL_STATUS_SUCCESS = 'OK'
NET_IO_CONNECTION_ERROR = 'Feil ved oppkobling til `{}`: {}'
NET_IO_TIMEOUT = 'Oppkobling til `{}` gikk ut på tid: {}'
NET_IO_ERROR_RESPONSE = 'Got a {} response (HTTP {}) when fetching {}. '\
    'If this causes problems, you need to check the link.'

# COG - QUOTE
QUOTE_NO_NUMBER_GIVEN = 'Du oppga ikke hvilket sitatnummer som skal '\
    'redigeres'
QUOTE_EDIT_NO_TEXT_GIVEN = 'Du oppga ikke sitattekst'
QUOTE_EDIT_NEED_CONFIRMATION = 'Endre sitat #{}?\nFra:\n```\n{}\n({})```'\
    '\n...til:\n```\n{}\n({})```'
QUOTE_EDIT_CONFIRMED = 'Endret sitat'
QUOTE_NO_EDIT_CONFIRMED = 'Endret *ikke* sitat'
QUOTE_ADD_CONFIRMATION = 'La til følgende sitat: ```#{}\n{}\n({})```'
QUOTE_CONFIRM_DELETE = 'Er du sikker på at du vil slette følgende sitat '\
    '(Svar med reaksjon 👍 eller 👎):\n```#{}\n{}\n({})```\n'
QUOTE_NO_CONFIRMATION_RECEIVED = 'Ikke fått svar på 15 sekunder, stopper '\
    'sletting'
QUOTE_DELETE_CONFIRMED = 'Slettet sitat #{}'
QUOTE_KEY_PHRASES = [
    QUOTE_CONFIRM_DELETE[0:46],         # Er du sikker på at du vil slette f...
    QUOTE_NO_CONFIRMATION_RECEIVED,     # Ikke fått svar på 15 sekunder, sto...
    QUOTE_DELETE_CONFIRMED[0:14]        # Slettet sitat #
]
QUOTE_COUNT = 'Jeg har {} sitater på lager'
QUOTE_DOES_NOT_EXIST = 'Sitat nummer {} finnes ikke'

# COG - YOUTUBE
YOUTUBE_NO_FEEDS_FOUND = 'Fant ingen Youtube-feeds'
YOUTUBE_RSS_LINK = 'https://www.youtube.com/feeds/videos.xml?channel_id={}'
YOUTUBE_ADDED = '{} ble lag til i kanalen {}'
YOUTUBE_ADDED_BOT = '{} la til feeden {} (`{}`) til kanalen {}'
YOUTUBE_REMOVED = 'Youtube-feeden {} ble fjernet'
YOUTUBE_REMOVED_BOT = 'Youtube-feeden {} ble fjernet av {}'
YOUTUBE_TRIED_REMOVED_BOT = '{} forsøkte å fjerne Youtube-feeden {}'
YOUTUBE_COULD_NOT_REMOVE = 'Klarte ikke å fjerne Youtube-feeden {}'
YOUTUBE_FEED_POSTS_IS_NONE = '{}: this feed returned NoneType.'
YOUTUBE_EMPTY_LINK = 'Klarer ikke å hente linken: `{}`'
YOUTUBE_VARS = {
    'url': {
        'title': 'Feed', 'max_len': 0, 'list_type': []
    },
    'channel': {
        'title': 'Channel', 'max_len': 0, 'list_type': []
    },
    'filter_allow': {
        'title': 'Allow', 'max_len': 30, 'list_type': ['filter']
    },
    'filter_deny': {
        'title': 'Deny', 'max_len': 30, 'list_type': ['filter']
    },
    'added': {
        'title': 'Added', 'max_len': 0, 'list_type': ['added']
    },
    'added_by': {
        'title': 'Added by', 'max_len': 0, 'list_type': ['added']
    }
}

# COG - AUTOEVENT
AUTOEVENT_PARSE_ERROR = 'Klarte ikke parsing av {} - fikk følgende feil:\n{}'
AUTOEVENT_NO_EVENTS_LISTED = 'Ingen events ligger inne for øyeblikket'
AUTOEVENT_EVENT_FOUND = 'Fant event: {}'
AUTOEVENT_EVENT_NOT_FOUND = 'Fant ingen eventer med den IDen. Sjekk '\
    'liste på nytt med `!autoevent list`'
AUTOEVENT_START_TIME_NOT_CORRECT_FORMAT = '`start_time` ser ikke ut til å '\
    'være i riktig format'
AUTOEVENT_EVENT_START_IN_PAST = 'Kan ikke lage en event med starttid i fortida'
AUTOEVENT_HTTP_EXCEPTION_ERROR = 'Got an error when posting event: {}'

# COG - ROLES
ROLES_KEY_PHRASES = [
    'Svar på denne meldingen med navnet på en rolle',
    'Timed out'
]

# COG - DILEMMAS
DILEMMAS_NO_DILEMMAS_IN_DB = 'Fant ingen lagrede dilemmas'
DILEMMAS_COUNT = 'Fant {} dilemma'


# VARIABLES
input_split_regex = r'[\s\.\-_,;\\\/]+'
roles_ensure_separator = ('><', '> <')

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
