#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from pathlib import Path

# Folders
ROOT_DIR = Path(__file__).resolve().parent
JSON_DIR = ROOT_DIR / 'json'
LIST_DIR = ROOT_DIR / 'lists'
LOG_DIR = ROOT_DIR / 'logs'
COGS_DIR = ROOT_DIR / 'cogs'
IMG_DIR = ROOT_DIR / 'img'

# Relative paths
COGS_REL_DIR = 'discord_rss.cogs'

# Files
env_file = ROOT_DIR / '.env'
feed_file = JSON_DIR / 'feeds.json'
feed_log_file = JSON_DIR / 'feeds-log.json'
quote_file = JSON_DIR / 'quotes.json'
test_list_file = LIST_DIR / 'test.list'

# Botlines
NOT_AUTHORIZED = 'Du har ikke tilgang til den kommandoen'
RSS_URL_NOT_OK = 'Linken du ga ser ikke ut til å være en ordenlig URL'
RSS_CHANNEL_NOT_OK = 'Jeg finner ikke kanalen du vil legge inn feeden på'
RSS_URL_AND_CHANNEL_NOT_OK = 'Du må oppgi både link og hvilken kanal du ønsker '\
    'den skal publiseres til.'
RSS_TOO_MANY_ARGUMENTS = 'Du har gitt for mange argumenter til kommandoen'
RSS_REMOVED = 'RSS-feeden {} ble fjernet'
RSS_COULD_NOT_REMOVE = 'Klarte ikke å fjerne RSS-feeden {}'
RSS_LIST_ARG_WRONG = 'Kjenner ikke til kommandoen {}'
