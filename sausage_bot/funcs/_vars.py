#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'Set variables for the module like folder, files and botlines'

from pathlib import Path

# Folders
ROOT_DIR = Path(__file__).resolve().parent.parent
JSON_DIR = ROOT_DIR / 'json'
LIST_DIR = ROOT_DIR / 'lists'
LOG_DIR = ROOT_DIR / 'logs'
COGS_DIR = ROOT_DIR / 'cogs'
IMG_DIR = ROOT_DIR / 'img'
STATIC_DIR = ROOT_DIR / 'static'

# Relative paths
COGS_REL_DIR = 'sausage_bot.cogs'

# Files
env_file = ROOT_DIR / '.env'
rss_feeds_file = JSON_DIR / 'rss-feeds.json'
rss_feeds_logs_file = JSON_DIR / 'rss-feeds-log.json'
yt_feeds_file = JSON_DIR / 'yt-feeds.json'
yt_feeds_logs_file = JSON_DIR / 'yt-feeds-log.json'
scrape_logs_file = JSON_DIR / 'scrape-log.json'
quote_file = JSON_DIR / 'quotes.json'
quote_log_file = JSON_DIR / 'quotes-log.json'
dilemmas_file = JSON_DIR / 'dilemmas.json'
dilemmas_log_file = JSON_DIR / 'dilemmas-log.json'
ps_sale_file = JSON_DIR / 'ps_sales.json'
ps_sale_log_file = LIST_DIR / 'ps_sales-log.list'
cogs_status_file = JSON_DIR / 'cogs_status.json'
stats_logs_file = JSON_DIR / 'stats_logs.json'

# Template content
env_template = '''discord_token=
discord_guild=
bot_prefix=!
locale=
bot_dump_channel=general
patreon_role_id=
stats_channel=general
bot_id=
watching=
youtube_api_key=
# Scrape FCB channels
firstteam=
femeni=
atletic=
juvenil=
club='''

### Botlines ###
# Generiske
GUILD_NOT_FOUND = 'Fant ikke serveren {}, dobbeltsjekk navnet i .env'
NOT_AUTHORIZED = 'Du har ikke tilgang til den kommandoen'
TOO_MANY_ARGUMENTS = 'Du har gitt for mange argumenter til kommandoen'
TOO_FEW_ARGUMENTS = 'Du har gitt for få argumenter til kommandoen'
CHANNEL_NOT_FOUND = 'Finner ikke kanalen du vil legge inn feeden på'
POST_TO_NON_EXISTING_CHANNEL = 'Prøver å poste til {}, men kanalen '\
    'finnes ikke'
UNREADABLE_FILE = 'Klarte ikke å lese `{}`. Sjekk eventuelle feil.'
ERROR_WITH_ERROR_MSG = 'Feil: {}'
GOT_CHANNEL_LIST = 'Henter kanalliste:\n{}'
GOT_SPECIFIC_CHANNEL = 'Fant kanal `{}` med id `{}`'
COMPARING_IDS = 'Sammenligner med `{}` to `{}`'
CREATING_FILES = 'Lager nødvendige filer'
BOT_NOT_SET_UP = 'The bot is not properly set up'

# MAIN
PURGE_DESC = 'Successfully purged {} messages.\nCommand executed by {}.'

# COG - COG ADMIN IN MAIN
COGS_TOO_FEW_ARGUMENTS = 'Du har gitt for få argumenter til kommandoen'
COGS_CHANGE_STATUS_FAIL = 'Klarte ikke å endre status. Feilmelding: {}'
COGS_WRONG_STATUS = 'Kjente ikke igjen status `{}`'
COGS_ENABLED = 'Aktiverte cog `{}`'
COGS_DISABLED = 'Deaktiverte cog `{}`'

# COG - GENERIC MESSAGES
COG_STARTING = 'Starting cog: `{}`'

# COG
## RSS
RSS_URL_NOT_OK = 'Linken du ga ser ikke ut til å være en ordenlig URL'
RSS_URL_AND_CHANNEL_NOT_OK = 'Du må oppgi både link og hvilken kanal du ønsker '\
    'den skal publiseres til.'
RSS_ADDED = '{} ble lag til i kanalen {}'
RSS_ADDED_BOT = '{} la til feeden {} ({}) til kanalen {}'
RSS_REMOVED = 'RSS-feeden {} ble fjernet'
RSS_REMOVED_BOT = 'RSS-feeden {} ble fjernet av {}'
RSS_TRIED_REMOVED_BOT = '{} forsøkte å fjerne RSS-feeden {}'
RSS_COULD_NOT_REMOVE = 'Klarte ikke å fjerne RSS-feeden {}'
RSS_FEED_CHANNEL_CHANGE = 'rss: {} endret kanalen til feeden `{}` til `{}`'
RSS_LIST_ARG_WRONG = 'Kjenner ikke til kommandoen {}'
RSS_INVALID_URL = 'Inputen `{}` er ikke en ordentlig URL. Dobbelsjekk staving.'
RSS_MISSING_SCHEME = 'URLen `{}` hadde ikke (http/https). Legger til og '\
    'prøver igjen...'
RSS_CONNECTION_ERROR = 'Feil ved oppkobling til URLen'
RSS_NOT_ABLE_TO_SCRAPE = 'Klarte ikke å scrape {}: {}'
RSS_NO_FEEDS_FOUND = 'Fant ingen RSS-feeds'
RSS_FEED_POSTS_IS_NONE = '{}: this feed returned NoneType.'
RSS_CHANGED_CHANNEL = 'Endret kanal for feeden `{}` til `{}`'

## CORE
RSSCORE_SOUP_ERROR = 'Feil ved lesing av `soup` fra {}: {}'
RSSCORE_LINK_INDEX_ERROR = 'Fikk IndexError ved henting av link til {} i {}'

# COG - QUOTE
QUOTE_EDIT_NO_NUMBER_GIVEN = 'Du oppga ikke hvilket sitatnummer som skal '\
    'redigeres'
QUOTE_EDIT_NO_TEXT_GIVEN = 'Du oppga ikke sitattekst'
QUOTE_EDIT_CONFIRMATION = 'Endret sitat #{} fra:\n```\n{}\n({})```\n...til:\n'\
    '```\n{}\n({})```'
QUOTE_ADD_CONFIRMATION = 'La til følgende sitat: ```#{}\n{}\n({})```'
QUOTE_KEY_PHRASES = [
    'Er du sikker på at du vil slette følgende sitat',
    'Ikke fått svar på 60 sekunder',
    'Slettet sitat #'
]
QUOTE_CONFIRM_DELETE = 'Er du sikker på at du vil slette følgende sitat '\
    '(Svar med reaksjon 👍 eller 👎):\n```#{}\n{}\n({})```\n'
QUOTE_NO_CONFIRMATION_RECEIVED = 'Ikke fått svar på 30 sekunder, stopper '\
    'sletting'
QUOTE_DELETE_CONFIRMED = 'Slettet sitat #{}'
QUOTE_COUNT = 'Jeg har {} sitater på lager'

# COG - YOUTUBE
YOUTUBE_ADDED = '{} ble lag til i kanalen {}'
YOUTUBE_ADDED_BOT = '{} la til feeden {} (`{}`) til kanalen {}'
YOUTUBE_REMOVED = 'Youtube-feeden {} ble fjernet'
YOUTUBE_REMOVED_BOT = 'Youtube-feeden {} ble fjernet av {}'
YOUTUBE_EMPTY_LINK = 'Klarer ikke å hente linken: `{}`'

# COG - AUTOEVENT
AUTOEVENT_PARSE_ERROR = 'Klarte ikke parsing av {} - fikk følgende feil:\n{}'
AUTOEVENT_NO_EVENTS_LISTED = 'Ingen events ligger inne for øyeblikket'
AUTOEVENT_NO_EVENTS_LISTED = 'Ingen events ligger inne for øyeblikket'
AUTOEVENT_EVENT_FOUND = 'Fant event: {}'
AUTOEVENT_EVENT_NOT_FOUND = 'Fant ingen eventer med den IDen. Sjekk '\
    'liste på nytt med `!autoevent list`'
AUTOEVENT_START_TIME_NOT_CORRECT_FORMAT = '`start_time` ser ikke ut til å være i riktig format'


if __name__ == "__main__":
    pass
