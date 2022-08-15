#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from sausage_bot.funcs import _vars


def get_link(url):
    if type(url) is not str:
        log.log(_vars.RSS_INVALID_URL)
        return None
    try:
        req = requests.get(url)
    except(requests.exceptions.InvalidSchema):
        log.log(_vars.RSS_INVALID_URL)
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