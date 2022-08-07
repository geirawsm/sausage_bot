#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from bs4 import BeautifulSoup
import requests


def scrape_fcb_agreement_links():
    links = []
    scrape = requests.get('https://www.fcbarcelona.com/en/football/first-team/news')
    root_url = 'https://www.fcbarcelona.com'
    soup = BeautifulSoup(scrape.content, features='html5lib')
    main_dev = soup.find('section', attrs={'class': 'feed'})
    news_dev = main_dev.find_all('div', attrs={'class': 'feed__container'})
    for row in news_dev:
        for news_item in row.find_all('div', attrs={'class': 'feed__items'}):
            news_text = news_item.find ('div', attrs={'class': 'thumbnail__text'})
            if 'agreement' in news_text.text.lower():
                link = news_item.find('a')['href']
                if link[0:4] == '/en/':
                    link = f'{root_url}{link}'
                links.append(link)
    return links

print(scrape_fcb_agreement_links())
