#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from pathlib import Path

# Folders
ROOT_DIR = Path(__file__).resolve().parent
JSON_DIR = ROOT_DIR / 'json'
LIST_DIR = ROOT_DIR / 'lists'
LOG_DIR = ROOT_DIR / 'logs'

# Files
env_file = ROOT_DIR / '.env'
admins_file = LIST_DIR / 'admins.list'
feed_file = JSON_DIR / 'feeds.json'
feed_log_file = JSON_DIR / 'feeds-log.json'

# Botlines
NOT_AUTHORIZED = 'Du har ikke tilgang til den kommandoen'
RSS_URL_NOT_OK = 'Linken du ga ser ikke ut til å være en ordenlig URL'
RSS_CHANNEL_NOT_OK = 'Jeg finner ikke kanalen du vil legge inn feeden på'
RSS_URL_AND_CHANNEL_NOT_OK = 'Du må oppgi både link og hvilken kanal du ønsker '\
    'den skal publiseres til.'
RSS_TOO_MANY_ARGUMENTS = 'Du har gitt for mange argumenter til kommandoen'
RSS_REMOVED = 'RSS-feeden {} ble fjernet'
RSS_COULD_NOT_REMOVE = 'Klarte ikke å fjerne RSS-feeden {}'
RSS_HELP_TEXT = '''pølsebot kan følgende kommandoer:

`{prefix}sitat`: Henter et tilfeldig sitat fra telegram-chaten (2019 - 2021)

`{prefix}pølse`: Poster det famøse "Pølse-gate"-klippet fra Tangerudbakken

`{prefix}admin`: List opp admins som har tilgang til funksjoner som krever høyere tilgang

`{prefix}rss`: bruker `add` og `remove` for å legge til og fjerne RSS-feeder
Eksempler:
`{prefix}rss add [navn på rss] [rss url] [kanal som rss skal publiseres til]`
`{prefix}rss remove [navn på rss]`

Tips til nye funksjoner kan sendes til geirawsm (geirawsm@pm.me)
'''
