#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from lxml import etree
from tabulate import tabulate

from sausage_bot.util import envs, datetime_handling, file_io, discord_commands
from sausage_bot.util import net_io

from .log import log

async def check_feed_validity(url):
    'Make sure that `url` is a valid link'
    log.log_more(f'Checking `{url}`')
    req = await net_io.get_link(url)
    if req is None:
        log.log_more('Returned None')
        return False
    try:
        etree.fromstring(req, parser=etree.XMLParser(encoding='utf-8'))
        return True
    except (etree.XMLSyntaxError) as e:
        log.log_more(envs.ERROR_WITH_ERROR_MSG.format(e))
        return False


async def add_to_feed_file(
    name, feed_link=None, channel=None, user_add=None,
    feeds_filename=None, yt_id=None
):
    '''
    Add a an item to the feed-json.

    `name`:         The identifiable name of the added feed
    `feed_link`:    The link for the feed
    `channel`       The discord channel to post the feed to
    `user_add`      The user who added the feed
    '''
    # Test the link first
    test_link = await net_io.get_link(feed_link)
    if test_link is None:
        return None
    date_now = datetime_handling.get_dt(format='datetime')
    feeds_file = file_io.read_json(feeds_filename)
    feeds_file[name] = {
        'url': feed_link,
        'channel': channel,
        'filter_allow': [],
        'filter_deny': [],
        'added': date_now,
        'added by': user_add,
        'status_url': 'added',
        'status_url_counter': 0,
        'status_channel': 'ok',
        'yt_id': yt_id
    }
    file_io.write_json(feeds_filename, feeds_file)


def remove_feed_from_file(name, feed_file):
    'Remove a feed from `feed file` based on `name`'
    name = str(name)
    feeds_list = file_io.read_json(feed_file)
    try:
        feeds_list.pop(name)
        file_io.write_json(feed_file, feeds_list)
        return True
    except (KeyError):
        return False


async def update_feed(
    feed_name, feeds_file_in, actions=None, items=None, values_in=None
):
    '''
    Update the fields for a feed in `feeds_file`

    `feed_name`:        Identifiable name for the feed
    `feeds_file_in`:    The file in where to update feed
    `actions`:          What actions to perform on the item:
                        Command     Alternatives
                        'add'
                        'edit'      'change'
                        'increment'
                        'remove'    'delete'

    `items`:            What items you want to change: name, channel, url,
                        status_url, status_url_counter or status_channel
    `values_in`:        Value to change/replace `item`
    '''
    ACTION_ADD = ['add']
    ACTION_EDIT = ['edit', 'change', 'increment']
    ACTION_REMOVE = ['remove', 'delete']
    ACTION_ALL = ACTION_ADD + ACTION_EDIT + ACTION_REMOVE
    feed_name = str(feed_name)
    feeds_file = file_io.read_json(feeds_file_in)
    # Make standard input to list format
    try:
        if isinstance(actions, str):
            action = list(actions)
        if isinstance(items, str):
            items = list(items)
        if isinstance(values_in, str):
            values_in = list(values_in)
    except:
        log.log('Error when making input to list')
        return
    # Check if all relevant lists are the same length
    if len(actions) == len(items) == len(values_in):
        log.log('Not all list inputs have the same length')
        return
    # Check correct actions
    action_errors = []
    for action in actions:
        if action not in ACTION_ALL:
            action_errors.append(action)
        if len(action_errors) > 0:
            log.log(f'Got these action errors: {action_errors}')
            return None
    counter = 0
    while counter < len(actions):
        action = actions[counter]
        item = items[counter]
        value_in = values_in[counter]
        # Treat name specifically
        if item == 'name':
            log.log('Update feed name')
            if feed_name in feeds_file:
                log.log(f'Changing name from `{feed_name}` to `{value_in}`')
                feeds_file[value_in] = feeds_file[feed_name]
                feeds_file.pop(feed_name)
            else:
                log.log('Feed name does not exist')
                return False
        elif action == 'increment':
            if value_in is None:
                value_in = 1
            log.log(f'Incrementing `{item}` with {value_in}')
            feeds_file[feed_name][item] += value_in
        else:
            log.log(f'Update `{item}` status')
            if action in ACTION_ADD or action in ACTION_EDIT:
                feeds_file[feed_name][item] = value_in
            elif action in ACTION_REMOVE:
                feeds_file[feed_name][item] = ''
        counter += 1
    await file_io.write_json(feeds_file_in, feeds_file)
    return True


async def get_feed_links(
        feed_name, url, filter_allow, filter_deny, cog_mode,
        include_shorts, filter_priority=None
):
    'Get the links from a RSS-feeds `url`'

    def filter_link(link, filter_allow, filter_deny, filter_priority):
        '''
        Filter incoming links based on active filters and settings in
        `env.json`
        '''

        def post_based_on_filter(
            filter_priority, filter_allow, filter_deny, title_in, desc_in
        ):
            _filter_priority = eval(f'filter_{filter_priority}')
            log.debug(
                f'Sjekker link ({title_in}) opp mot følgende '
                f'filtere: {_filter_priority}'
            )
            if len(_filter_priority) >= 1:
                for filter in _filter_priority:
                    if title_in:
                        if filter.lower() in title_in.lower():
                            log.debug(
                                f'Fant filter `{filter}` i '
                                f'tittel ({title_in})'
                            )
                            return False
                    if desc_in:
                        if filter.lower() in desc_in.lower():
                            log.debug(
                                f'Fant filter `{filter}` i '
                                f'beskrivelse ({desc_in})')
                            return False
                log.debug(
                    'Fant ikke noe filter i tittel eller beskrivelse'
                )
                return True

        log.debug('Starting `filter_link`')
        title_in = link['title']
        link_in = link['link']
        desc_in = link['description']
        if filter_priority:
            log.debug(
                f'Based on settings, the `{filter_priority}` filter'
                f' is prioritized'
            )
        elif filter_priority is None or filter_priority == '':
            log.debug(
                'No `filter_priority` given, setting `deny` as standard'
            )
            if not filter_priority:
                filter_priority = 'deny'
        log.debug('Got these filters:')
        log.debug(f'Allow: {filter_allow}')
        log.debug(f'Deny: {filter_deny}')
        if post_based_on_filter(
            filter_priority, filter_allow, filter_deny, title_in, desc_in
        ):
            return link_in
        else:
            return False

    async def get_items_from_rss(req, url, include_shorts):
        try:
            soup = BeautifulSoup(req, features='xml')
        except Exception as e:
            log.log(envs.FEEDS_SOUP_ERROR.format(url, e))
            return None
        links_out = []
        # Gets podcast urls
        if soup.find('enclosure'):
            channel_link = soup.find('channel').find('link')
            log.debug('Found podcast feed')
            all_items = soup.find_all('item')
            for item in all_items[0:3]:
                link = item.find('link').text
                if link == channel_link:
                    link = item.find('enclosure')['url']
                links_out.append(link)
        # Gets Youtube urls
        elif soup.find('yt:channelId'):
            log.debug('Found Youtube feed')
            log.debug(f'`include_shorts` is {include_shorts}')
            all_entries = soup.find_all('entry')
            max_no_of_entries = 5
            entry_counter = 0
            for entry in all_entries:
                if entry_counter < max_no_of_entries:
                    link = entry.find('link')['href']
                    if include_shorts is False:
                        title = entry.find('title')
                        media_title = entry.find('media:title')
                        shorts_keyword = '#shorts'
                        if shorts_keyword in str(title).lower() or\
                                shorts_keyword in str(media_title).lower():
                            log.debug(f'Skipped {link} because of #Shorts')
                            pass
                        else:
                            links_out.append(link)
                            entry_counter += 1
                    elif include_shorts is True:
                        links_out.append(link)
                        entry_counter += 1
        # Gets plain articles
        else:
            all_items = soup.find_all('item')
            for item in all_items[0:3]:
                link = item.find('link').text
                links_out.append(link)
        links_out.reverse()
        return links_out

    if cog_mode == 'rss':
        FEEDS_FILE = envs.rss_feeds_file
    elif cog_mode == 'youtube':
        FEEDS_FILE = envs.yt_feeds_file
    # Get the url and make it parseable
    req = await net_io.get_link(url)
    if req is None:
        # Each time this happens, increment a counter and change url_status.
        # If the counter is more than x, post a message to bot channel.
        # When successfull, set the counter to 0 and reset status to OK
        feeds_file_in = file_io.read_json(FEEDS_FILE)
        _status_url = feeds_file_in[feed_name]['status_url']
        _status_url_counter = feeds_file_in[feed_name]['status_url_counter']
        if _status_url == envs.FEEDS_URL_ERROR and\
                _status_url_counter == envs.FEEDS_URL_ERROR_LIMIT:
            log.debug(f'Changing url status after error with url  ({url})')
            await log.log_to_bot_channel(f'Problemer med å hente `{url}`')
        elif _status_url == envs.FEEDS_URL_ERROR:
            log.debug(
                f'Incrementing error counter after error with url ({url})'
            )
            update_feed(
                feed_name, envs.rss_feeds_file, actions=['edit', 'increment'],
                items=['status_url', 'status_url_counter'],
                values_in=[envs.FEEDS_URL_ERROR, 1]
            )
    elif req is not None:
        # Clear the counter
        feeds_file_in = file_io.read_json(FEEDS_FILE)
        _status_url = feeds_file_in[feed_name]['status_url']
        _status_url_counter = feeds_file_in[feed_name]['status_url_counter']
        if _status_url == envs.FEEDS_URL_ERROR and\
                _status_url_counter > 0:
            log.debug('Changing url status after success')
            update_feed(
                feed_name, envs.rss_feeds_file, actions=['edit', 'edit'],
                items=['status_url', 'status_url_counter'],
                values_in=[envs.FEEDS_URL_SUCCESS, 0]
            )
        links_out = await get_items_from_rss(req, url, include_shorts)
        links = []
        for link in links_out:
            if (len(filter_allow) + len(filter_deny)) > 0:
                _link = filter_link(
                    link, filter_allow, filter_deny, filter_priority
                )
                if _link:
                    log.debug(f'Appending link: `{_link}`')
                    links.append(_link)
            else:
                links.append(link)
        log.debug(f'Returning `links`: {links}')
        return links


async def get_feed_list(feeds_file, feeds_vars: dict, list_type: str = None):
    '''
    Get a prettified list of feeds from `feeds_file`.

    feeds_file  The file containing feeds or other things to list
    feeds_vars  The titles and lengths of the fields to be used
    list_type   If specified, should show that specific list_type,
                as specified in the feeds_vars 'list_type' field
    '''

    def split_lengthy_lists(feeds_file_in, feeds_vars, list_type=None):
        def wanted_fields(feeds_vars, list_type=None):
            # Get wanted fields
            fields = {}
            for item in feeds_vars:
                if list_type is None:
                    if len(feeds_vars[item]['list_type']) == 0:
                        if item not in fields:
                            fields[item] = {}
                        fields[item]['title'] = feeds_vars[item]['title']
                        if feeds_vars[item]['max_len'] > 0:
                            if item not in fields:
                                fields[item] = {}
                            fields[item]['max_len'] = feeds_vars[item][
                                'max_len'
                            ]
                        else:
                            if item not in fields:
                                fields[item] = {}
                            fields[item]['max_len'] = None
                elif list_type == 'added':
                    if len(feeds_vars[item]['list_type']) == 0 or\
                            'added' in feeds_vars[item]['list_type']:
                        if item not in fields:
                            fields[item] = {}
                        fields[item]['title'] = feeds_vars[item]['title']
                        if feeds_vars[item]['max_len'] > 0:
                            if item not in fields:
                                fields[item] = {}
                            fields[item]['max_len'] = feeds_vars[item][
                                'max_len'
                            ]
                        else:
                            if item not in fields:
                                fields[item] = {}
                            fields[item]['max_len'] = None
                elif list_type == 'filter':
                    if len(feeds_vars[item]['list_type']) == 0 or\
                            'filter' in feeds_vars[item]['list_type']:
                        if item not in fields:
                            fields[item] = {}
                        fields[item]['title'] = feeds_vars[item]['title']
                        if feeds_vars[item]['max_len'] > 0:
                            if item not in fields:
                                fields[item] = {}
                            fields[item]['max_len'] = feeds_vars[item][
                                'max_len'
                            ]
                        else:
                            if item not in fields:
                                fields[item] = {}
                            fields[item]['max_len'] = None
                else:
                    log.debug(f'Skipping `item` {item}')
            return fields

        def make_table(feeds_in, want_fields):
            tabulatify = []
            # Add headers
            header_list = ['Name']
            for header in want_fields:
                header_list.append(want_fields[header]['title'])
            tabulatify.append(header_list)
            # Add rest of values
            for feed in feeds_in:
                temp_list = []
                temp_list.append(feed)
                for item in want_fields:
                    if feeds_in[feed][item] == []:
                        temp_list.append(envs.FEEDS_NONE_VALUE_AS_TEXT)
                    elif isinstance(feeds_in[feed][item], list):
                        temp_out = ''
                        for list_item in feeds_in[feed][item]:
                            temp_out += list_item
                            if list_item != feeds_in[feed][item][-1]:
                                temp_out += ', '
                        temp_list.append(temp_out)
                    else:
                        temp_list.append(feeds_in[feed][item])
                tabulatify.append(temp_list)
            # Get info about max_len
            max_col_widths = [None]
            for item in want_fields:
                max_col_widths.append(want_fields[item]['max_len'])
            print(max_col_widths)
            table = tabulate(
                tabulatify, tablefmt='plain',
                headers="firstrow",
                maxcolwidths=max_col_widths
            )
            return table

        def make_pretty_header(header, max_len):
            out = ''
            out += header
            out += '\n'
            out += '-' * max_len
            out += '\n'
            return out

        out = ''
        list_paginated = []
        table = make_table(
            feeds_file_in, wanted_fields(feeds_vars, list_type)
        ).split('\n')
        # Get max len from paginated list
        max_total_len = 0
        for line in table:
            if len(line) > max_total_len:
                max_total_len = len(line)
        # Actual limit is 2000, this is just a buffer
        max_len_discord_post = 1800
        out += make_pretty_header(
            table[0], max_total_len
        )
        # Make content from feeds
        for line in table[1:]:
            log.debug(f'`out` as of now is {len(out)} long')
            if (len(out) + len(line)) >= max_len_discord_post:
                log.debug('Reached `max_len_discord_post`')
                list_paginated.append(out)
                out = make_pretty_header(
                    table[0], max_total_len
                )
                out += line
                out += '\n'
            else:
                log.debug('No limit reached')
                out += line
                if line != table[-1]:
                    out += '\n'
            log.debug('Status:')
            log.debug(f'´list_paginated´: {len(list_paginated)}')
            log.debug(f'´out´:\n{out}')
        list_paginated.append(out)
        log.debug(f'`len(list_paginated): `{len(list_paginated)}')
        for page in list_paginated:
            log.debug(f'`len(page): `{len(page)}')
        return list_paginated

    feeds_file = file_io.read_json(feeds_file)
    feeds_file = dict(sorted(
        feeds_file.items(), key=lambda x: x[0].lower()
    ))
    # Return None if empty file
    if len(feeds_file) <= 0:
        return None
    return split_lengthy_lists(
        feeds_file, feeds_vars, list_type=list_type
    )


async def review_feeds_status(feeds_file):
    'Get a status for a feed from `feeds` and update it in source file'
    feeds_file_in = file_io.read_json(feeds_file)
    for feed in feeds_file_in:
        URL = feeds_file_in[feed]['url']
        URL_STATUS = feeds_file_in[feed]['status_url']
        if URL_STATUS == 'stale':
            log.log('Feed url for {} is stale, checking it...'.format(feed))
            if get_feed_links(URL) is not None:
                log.log('Feed url for {} is ok, reactivating!'.format(feed))
                update_feed(
                    feed, feeds_file, actions='edit', items='status_url',
                    url='ok'
                )
                break
            elif get_feed_links(URL) is None:
                log.log(f'Feed url for {feed} is still stale, skipping')
                break
        CHANNEL = feeds_file_in[feed]['channel']
        CHANNEL_STATUS = feeds_file_in[feed]['status_channel']
        if CHANNEL_STATUS == 'unlisted':
            log.log(
                'Feed channel {} for {} is unlisted, checking it...'.format(
                    CHANNEL, feed
                )
            )
            if CHANNEL in discord_commands.get_text_channel_list():
                log.log(
                    'Feed channel {} for {} is ok, reactivating!'.format(
                        CHANNEL, feed
                    )
                )
                update_feed(
                    feed, feeds_file, actions='edit',
                    items='status_channel', values_in='ok'
                )


def link_is_in_log(link: str, feed_name: str, feed_log: list) -> bool:
    'Checks if `link` is in the `feed_log`'
    log.debug(
        f'Checking if `{link}` is in `{feed_name}` in feed_log'
    )
    if feed_name in feed_log:
        log.debug(f'Found `{feed_name}`')
        if link in feed_log[feed_name]:
            log.debug('Found link in log')
            return True
        else:
            log.debug('Found NOT link in log')
            return False
    else:
        log.debug(f'{feed_name} not in `feed_log`')
        return False


def link_similar_to_logged_post(link: str, feed_log: list):
    '''
    Checks if `link` is similar to any other logged link in `feed_log`.
    If similiar, return the similar link from log.
    If no links are found to be similar, return None.
    '''
    for log_item in feed_log:
        if file_io.check_similarity(log_item, link):
            return log_item


async def process_links_for_posting_or_editing(
    feed, FEED_POSTS, feed_log_file, CHANNEL
):
    '''
    Compare `FEED_POSTS` to posts belonging to `feed` in `feed_log_file`
    to see if they already have been posted or not.
    - If not posted, post to `CHANNEL`
    - If posted, make a similarity check just to make sure we are not posting
    duplicate links because someone's aggregation systems can't handle
    editing urls with spelling mistakes. If it is simliar, but not identical,
    replace the logged link and edit the previous post with the new link.

    `feed`:             Name of the feed to process
    `FEED_POSTS`:       The newly received feed posts
    `feed_log_file`:    File containing the logs of posts
    `CHANNEL`:          Discord channel to post/edit
    '''
    log.debug(f'Here\'s the `FEED_POSTS`: {FEED_POSTS}')
    FEED_LOG = file_io.read_json(feed_log_file)
    try:
        FEED_LOG[feed]
    except (KeyError):
        FEED_LOG[feed] = []
    for feed_link in FEED_POSTS[0:2]:
        log.debug(f'Got feed_link `{feed_link}`')
        # Check if the link is in the log
        if not link_is_in_log(feed_link, feed, FEED_LOG):
            feed_link_similar = link_similar_to_logged_post(
                feed_link, FEED_LOG[feed])
            if not feed_link_similar:
                # Consider this a whole new post and post link to channel
                log.log_more(f'Posting link `{feed_link}`')
                await discord_commands.post_to_channel(CHANNEL, feed_link)
                # Add link to log
                FEED_LOG[feed].append(feed_link)
            elif feed_link_similar:
                # Consider this a similar post that needs to
                # be edited in the channel
                await discord_commands.replace_post(
                    feed_link_similar, feed_link, CHANNEL
                )
                # Replace original link with new
                FEED_LOG[feed].remove(feed_link_similar)
                FEED_LOG[feed].append(feed_link)
        elif link_is_in_log(feed_link, feed, FEED_LOG):
            log.log_more(f'Link `{feed_link}` already logged. Skipping.')
        # Write to the logs-file at the end
        file_io.write_json(feed_log_file, FEED_LOG)


if __name__ == "__main__":
    pass
