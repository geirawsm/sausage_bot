#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from pathlib import Path

# Folders
ROOT_DIR = Path(__file__).resolve().parent.parent
JSON_DIR = ROOT_DIR / 'json'
LIST_DIR = ROOT_DIR / 'lists'
LOG_DIR = ROOT_DIR / 'logs'
COGS_DIR = ROOT_DIR / 'cogs'
IMG_DIR = ROOT_DIR / 'img'

# Relative paths
COGS_REL_DIR = 'sausage_bot.cogs'

# Files
env_file = ROOT_DIR / '.env'
feeds_file = JSON_DIR / 'feeds.json'
feeds_logs_file = JSON_DIR / 'feeds-log.json'
quote_file = JSON_DIR / 'quotes.json'
quote_log_file = JSON_DIR / 'quotes-log.json'
dilemmas_file = JSON_DIR / 'dilemmas.json'
dilemmas_log_file = JSON_DIR / 'dilemmas-log.json'
ps_sale_file = JSON_DIR / 'ps_sales.json'
ps_sale_log_file = LIST_DIR / 'ps_sales-log.list'

# Botlines
NOT_AUTHORIZED = 'Du har ikke tilgang til den kommandoen'
RSS_URL_NOT_OK = 'Linken du ga ser ikke ut til å være en ordenlig URL'
RSS_CHANNEL_NOT_OK = 'Jeg finner ikke kanalen du vil legge inn feeden på'
RSS_URL_AND_CHANNEL_NOT_OK = 'Du må oppgi både link og hvilken kanal du ønsker '\
    'den skal publiseres til.'
RSS_TOO_MANY_ARGUMENTS = 'Du har gitt for mange argumenter til kommandoen'
RSS_TOO_FEW_ARGUMENTS = 'Du har gitt for få argumenter til kommandoen'
RSS_ADDED = '{} ble lag til i kanalen {}'
RSS_ADDED_BOT = '{} la til feeden {} ({}) til kanalen {}'
RSS_REMOVED = 'RSS-feeden {} ble fjernet'
RSS_REMOVED_BOT = 'RSS-feeden {} ble fjernet av {}'
RSS_TRIED_REMOVED_BOT = '{} forsøkte å fjerne RSS-feeden {}'
RSS_COULD_NOT_REMOVE = 'Klarte ikke å fjerne RSS-feeden {}'
RSS_LIST_ARG_WRONG = 'Kjenner ikke til kommandoen {}'
RSS_INVALID_URL = 'Inputen `{}` er ikke en ordentlig URL. Dobbelsjekk staving.'
RSS_MISSING_SCHEME = 'URLen `{}` hadde ikke (http/https). Legger til og '\
    'prøver igjen...'
RSS_CONNECTION_ERROR = 'Feil ved oppkobling til URLen'

UNREADABLE_FILE = 'Klarte ikke å lese `{}`. Sjekk eventuelle feil.'


if __name__ == "__main__":
    print(ROOT_DIR)