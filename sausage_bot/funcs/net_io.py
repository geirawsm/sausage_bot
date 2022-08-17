#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import re
from bs4 import BeautifulSoup
from sausage_bot.funcs import _vars, datetimefuncs

from ..log import log


def get_link(url):
    if type(url) is not str:
        log.log(_vars.RSS_INVALID_URL.format(url))
        return None
    try:
        req = requests.get(url)
    except(requests.exceptions.InvalidSchema):
        log.log(_vars.RSS_INVALID_URL.format(url))
        return None
    except(requests.exceptions.MissingSchema):
        log.log(_vars.RSS_MISSING_SCHEME)
        req = get_link(f'https://{url}')
    except(requests.exceptions.ConnectionError):
        log.log(_vars.RSS_CONNECTION_ERROR)
        return None
    if req is None:
        return None
    log.log_more('Got a {} when fetching {}'.format(req.status_code, url))
    if req.status_code != 200:
        return None
    else:
        return req


def scrape_page(url):
    scrape = get_link(url)
    try:
        soup = BeautifulSoup(scrape.content, features='html5lib')
        return soup
    except:
        return None

def parse(url):
    ''''''
    def make_relative_date(epoch):
        return f'<t:{epoch}:R>'.strip()
    
    def make_event_start_stop(date, time):
        '''
        `date` and ´time´ is for the start of the match.
        The event should start 30 minutes prior
        The event should end 2 hours and 30 minutes after
        '''
        startdt_obj = datetimefuncs.make_dt(f'{date} {time}')
        startdt_new = datetimefuncs.change_dt(startdt_obj, 'remove', 30, 'minutes')
        enddt_new = datetimefuncs.change_dt(startdt_obj, 'add', 2.5, 'hours')
        startdt = datetimefuncs.get_dt(format='datetextfull', dt=startdt_new)
        enddt = datetimefuncs.get_dt(format='datetextfull', dt=enddt_new)
        return {
            'start': startdt,
            'end': enddt}

#    def parse_aof(soup):
#        '''
#        Emne: Kampchat - [lag1] vs [lag2]
#        startdato
#        startklokkeslett
#        beskrivelse: kom opp med en standardtekst som også har med
#            hvor lenge det er igjen til det starter
#        '''
#        infoboks = soup.find('table', attrs={'class': 'sd_game'})
#        info_upper = infoboks.find('tr', attrs={'class': 'sd_game_big'})
#        hjemmelag = info_upper.find(
#            'td', attrs={'class': 'sd_game_home'}
#        ).text.strip()
#        bortelag = info_upper.find(
#            'td', attrs={'class': 'sd_game_away'}
#        ).text.strip()
#        info_lower = infoboks.find('tr', attrs={'class': 'sd_game_small'})
#        _info = info_lower.find(
#            'td', attrs={'class': 'sd_game_home'}
#        ).text.strip()
#
#        _runde = info_lower.find(
#            'td', attrs={'class': 'sd_game_away'}
#        ).text.strip()
#        ###
#        return {
#            'teams': {
#                'home': team_home,
#                'away': team_away
#            },
#            'tournament': tournament,
#            'datetime': {
#                'date': date,
#                'time': time,
#                'rel_date': rel_date
#            },
#            'stadium': stadium
#        }

    def parse_nifs(soup):
        info_tbl = soup.find('table', attrs={'class': 'nifs_table_l_nb'})
        rows = info_tbl.find_all('tr')
        # Get team names
        info0 = rows[0].find_all('a', attrs={'class': 'nifs_link_style'})
        team_home = info0[0].text.strip()
        team_away = info0[1].text.strip()
        info1 = rows[1].find_all('td')
        tournament = info1[1].text.strip().replace('\t', '').replace('\n', ' ')
        date = info1[3].text.strip()
        time = rows[2].find_all('td')[3].text.strip()
        dt_in = make_event_start_stop(date, time)
        startdt = dt_in['start']
        enddt = dt_in['end']
        
        # Make epochdate
        epoch = datetimefuncs.get_dt(
            dt=datetimefuncs.make_dt(
                f'{date} {time}'
            )
        )
        rel_date = make_relative_date(epoch)
        stadium = rows[3].find_all('td')[3].text.strip()
        return {
            'teams': {
                'home': team_home,
                'away': team_away
            },
            'tournament': tournament,
            'datetime': {
                'date': date,
                'time': time,
                'rel_date': rel_date,
                'startdt': startdt,
                'enddt': enddt
            },
            'stadium': stadium
        }

    soup = scrape_page(url)
    if 'nifs.no' in url:
        return parse_nifs(soup)
    elif 'altomfotball.no' in url:
        return parse_aof(soup)
    else:
        log.log('Linken er ikke kjent')
        return None

if __name__ == "__main__":
    # Barca
    url = 'https://www.nifs.no/kampfakta.php?kamp_id=2133607&land=20&t=45&u=690408&lag1=835&lag2=844'
    # Bundesliga
    #url = 'https://www.nifs.no/kampfakta.php?kamp_id=2125660&land=9&t=36&u=690357&lag1=673&lag2=6455'
    # CL
    #url = 'https://www.nifs.no/kampfakta.php?kamp_id=1980909'
    #
    #url = 'https://www.altomfotball.no/element.do?cmd=match&matchId=1127006&tournamentId=238&seasonId=344&useFullUrl=false
    print(parse(url))
