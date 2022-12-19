#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from lxml import etree
from sausage_bot.util import mod_vars, datetime_handling, file_io, discord_commands
from sausage_bot.util import net_io

from .log import log


def check_feed_validity(url):
    'Make sure that `url` is a valid link'
    log.log_more(f'Checking `{url}`')
    req = net_io.get_link(url)
    if req is None:
        log.log_more(f'Returned None')
        return False
    try:
        etree.fromstring(req.content, parser=etree.XMLParser(encoding='utf-8'))
        return True
    except (etree.XMLSyntaxError) as e:
        log.log_more(mod_vars.ERROR_WITH_ERROR_MSG.format(e))
        return False


def add_to_feed_file(
        name, feed_link=None, channel=None, user_add=None,
        feeds_filename=None, filter_allow=None,
        filter_deny=None):
    '''
    Add a an item to the feed-json.

    `name`:         The identifiable name of the added feed
    `feed_link`:    The link for the feed
    `channel`       The discord channel to post the feed to
    `user_add`      The user who added the feed
    `filter_allow`  The allow-filter for the feed
    `filter_deny`   The deny-filter for the feed
    '''
    # Test the link first
    test_link = net_io.get_link(feed_link)
    if test_link is None:
        return None
    date_now = datetime_handling.get_dt(format='datetime')
    feeds_file = file_io.read_json(feeds_filename)
    feeds_file[name] = {
        'url': feed_link,
        'channel': channel,
        'filter': {
            'allow': [],
            'deny': []
        },
        'added': date_now,
        'added by': user_add,
        'status': {
            'url': 'added',
            'channel': 'ok'
        }
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


def update_feed_status(
    feed_name, feeds_file_in, action=None, channel=None, url=None,
    status_url=None, status_channel=None, name=None
):
    '''
    Update the fields for a feed in `feeds_file`

    `feed_name`:        Identifiable name for the feed
    `feeds_file_in`:    The file in where to update feed
    `action`:           What action to perform on the item:
                        Command     Alternatives
                        'add'
                        'edit'      'change'
                        'remove'    'delete'

    `channel`:       The channel to receive feed updates
    `url`:           The feed's url
    `status_url`:       The status of the url
    `status_channel`:   The status of the channel
    '''
    ACTION_ADD = ['add']
    ACTION_EDIT = ['edit', 'change']
    ACTION_REMOVE = ['remove', 'delete']
    ACTION_ALL = ACTION_ADD + ACTION_EDIT + ACTION_REMOVE
    feed_name = str(feed_name)
    feeds_file = file_io.read_json(feeds_file_in)
    func_args = locals()
    for arg_name in ['feed_name', 'feeds_file_in', 'action', 'name']:
        func_args.pop(arg_name)
    if not action or action not in ACTION_ALL:
        log.log('Check your input for `action`')
        return None
    for arg in func_args:
        if func_args[arg]:
            log.log(f'Update `{arg}` status')
            dict_item = feeds_file[feed_name]
            if '_' in arg:
                arg_split = arg.split('_')
                dict_item = dict_item[arg_split[0]][arg_split[1]]
            else:
                dict_item = dict_item[arg]
            if action in ACTION_ADD or action in ACTION_EDIT:
                dict_item = str(func_args[arg]).lower()
            elif action in ACTION_REMOVE:
                feeds_file[feed_name]['status'][arg] = None
    if name:
        log.log('Update feed name')
        if feed_name in feeds_file:
            log.log(f'Changing name from `{feed_name}` to `{name}`')
            feeds_file[name] = feeds_file[feed_name]
            feeds_file.pop(feed_name)
        else:
            log.log('Feed name does not exist')
            return False
    file_io.write_json(feeds_file_in, feeds_file)
    return True


def get_feed_links(url, filters=None, filter_priority=None):
    'Get the links from a RSS-feeds `url`'

    def filter_link(link, filters, filter_priority):
        '''
        Filter incoming links based on active filters and settings in
        `env.json`
        '''

        def post_based_on_filter(filter_priority, filters, title_in, desc_in):
            log.debug(f'Sjekker link ({title_in}) opp mot følgende filtere: {filters[filter_priority]}')
            if len(filters[filter_priority]) >= 1:
                for filter in filters[filter_priority]:
                    log.debug(f'Is `{filter}` in `{title_in}` or `{desc_in}`?')
                    if filter.lower() in title_in.lower():
                        log.debug(f'Fant et filter i tittel ({title_in})')
                        return False
                    elif filter.lower() in desc_in.lower():
                        log.debug(f'Fant et filter i beskrivelse ({desc_in})')
                        return False
                log.debug(
                    f'Fant ikke noe filter i tittel eller beskrivelse'
                )
                return True
            else:
                log.debug(f'No {filter_priority} filters')
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
        elif filter_priority is None:
            log.debug(
                f'No `filter_priority` given, setting `deny` as standard'
            )
            if not filter_priority:
                filter_priority = 'deny'
        log.debug('Got these filters:')
        log.debug(f'Allow: {filters["allow"]}')
        log.debug(f'Deny: {filters["deny"]}')
        if post_based_on_filter(
            filter_priority, filters, title_in, desc_in
        ):
            return link_in
        else:
            return False

    # Get the url and make it parseable
    log.debug(f'Got these arguments: {locals()}')
    req = net_io.get_link(url)
    if req is None:
        return None
    try:
        soup = BeautifulSoup(req.content, features='xml')
    except Exception as e:
        log.log(mod_vars.RSSCORE_SOUP_ERROR.format(url, e))
        return None
    links_filter = []
    links = []
    # Try normal RSS
    if '<rss version="' in str(soup).lower():
        try:
            feed_in = etree.fromstring(
                req.content, parser=etree.XMLParser(encoding='utf-8'))
        except (etree.XMLSyntaxError):
            return None
        for item in feed_in.xpath('/rss/channel/item'):
            try:
                link = item.xpath("./link/text()")[0].strip()
                title = item.findtext("./title")
                description = item.findtext("./description")
                links_filter.append(
                    {
                        'title': title,
                        'description': description,
                        'link': link
                    }
                )
            except (IndexError):
                log.log(mod_vars.RSSCORE_LINK_INDEX_ERROR.format(item, url))
    elif '<feed xml' in str(soup):
        for entry in soup.findAll('entry')[0:2]:
            link = entry.find('link')['href']
            title = entry.find('title')
            description = entry.find('description')
            if 'wp.blgr.app' in link:
                link = link.replace('wp.blgr.app', 'www.blaugrana.no')
            links_filter.append(
                {
                    'title': title,
                    'description': description,
                    'link': link
                }
            )
    for link in links_filter:
        if filters:
            link = filter_link(link, filters, filter_priority)
            if link:
                log.debug(f'Appending link: `{link}`')
                links.append(link)
        else:
            links.append(link['link'])
    log.debug(f'Returning `links`: {links}')
    return links


def get_feed_list(feeds_file, long=False, filters=False):
    '''
    Get a prettified list of feeds from `feeds_file`.

    Get some extra field if `long` is given.
    '''
    def get_feed_item_lengths(feeds_file):
        'Get max lengths of items in `feeds_file`'
        feed_len = 0
        url_len = 0
        channel_len = 8
        filters_len = 7
        filter_allow_len = 12
        filter_deny_len = 11
        added_len = 0
        added_by_len = 0
        for feed in feeds_file:
            _feed = feeds_file[feed]
            if len(feed) > feed_len:
                feed_len = len(feed)
            if len(_feed['url']) > url_len:
                url_len = len(_feed['url'])
            if len(_feed['channel']) > channel_len:
                channel_len = len(_feed['channel'])
            if len(_feed['filter']['allow']) > 0:
                for _allow in _feed['filter']['allow']:
                    if len(_allow) > filter_allow_len:
                        filter_allow_len = len(_allow)
                        filter_allow_len += len(_feed['filter']['allow']) * 2
            if len(_feed['filter']['deny']) > 0:
                for _deny in _feed['filter']['deny']:
                    if len(_deny) > filter_deny_len:
                        filter_deny_len = len(_feed['filter']['deny'])
                        filter_deny_len += len(_feed['filter']['deny']) * 2
            if len(_feed['added']) > added_len:
                added_len = len(_feed['added'])
            if len(_feed['added by']) > added_by_len:
                added_by_len = len(_feed['added by'])
        return {
            'feed_len': feed_len,
            'url_len': url_len,
            'channel_len': channel_len,
            'filters_len': filters_len,
            'filter_allow_len': filter_allow_len,
            'filter_deny_len': filter_deny_len,
            'added_len': added_len,
            'added_by_len': added_by_len
        }

    feeds_file = file_io.read_json(feeds_file)
    # Return None if empty file
    if len(feeds_file) <= 0:
        return None
    text_out = ''
    lengths = get_feed_item_lengths(feeds_file)
    if long:
        template_line = '{:<{feed_len}} | {:<{url_len}} | {:<{channel_len}} | {:<{filters}} | {:<{added_len}} | {:<{added_by_len}}'
        # Add headers first
        text_out += template_line.format(
            'Name', 'Feed', 'Channel', 'Filters', 'Added', 'Added by',
            feed_len=lengths['feed_len'],
            url_len=lengths['url_len'],
            channel_len=lengths['channel_len'],
            filters=lengths['filters_len'],
            added_len=lengths['added_len'],
            added_by_len=lengths['added_by_len']
        )
        text_out += '\n'
        for feed in feeds_file:
            _feed = feeds_file[feed]
            if len(_feed['filter']['allow']) > 0 or\
                    len(_feed['filter']['deny']) > 0:
                filter_status = 'Yes'
            else:
                filter_status = 'No'
            text_out += template_line.format(
                feed, _feed['url'], _feed['channel'],
                filter_status, _feed['added'], _feed['added by'],
                feed_len=lengths['feed_len'],
                url_len=lengths['url_len'],
                channel_len=lengths['channel_len'],
                filters=lengths['filters_len'],
                added_len=lengths['added_len'],
                added_by_len=lengths['added_by_len']
            )
            if feed != list(feeds_file)[-1]:
                text_out += '\n'
    elif filters:
        template_line = '{:<{feed_len}} | {:<{filter_allow}} | {:<{filter_deny}}'
        # Add headers first
        text_out += template_line.format(
            'Name', 'Filter allow', 'Filter deny',
            feed_len=lengths['feed_len'],
            filter_allow=lengths['filter_allow_len'],
            filter_deny=lengths['filter_deny_len']
        )
        text_out += '\n'
        for feed in feeds_file:
            _feed = feeds_file[feed]
            if _feed['filter']['allow'] == 0:
                _feed['filter']['allow'] = ""
            if _feed['filter']['deny'] == 0:
                _feed['filter']['deny'] = ""
            allow_items = ''
            deny_items = ''
            for item in _feed['filter']['allow']:
                allow_items += item
                if item != _feed['filter']['allow'][:-1]:
                    allow_items += ', '
            for item in _feed['filter']['deny']:
                deny_items += item
                if item != _feed['filter']['deny'][:-1]:
                    deny_items += ', '
            text_out += template_line.format(
                feed, allow_items, deny_items,
                feed_len=lengths['feed_len'],
                filter_allow=lengths['filter_allow_len'],
                filter_deny=lengths['filter_deny_len']
            )
            if feed != list(feeds_file)[-1]:
                text_out += '\n'
    else:
        template_line = '{:<{feed_len}} | {:<{url_len}} | {:<{channel_len}}'
        # Add headers first
        text_out += template_line.format(
            'Name', 'Feed', 'Channel', feed_len=lengths['feed_len'],
            url_len=lengths['url_len'], channel_len=lengths['channel_len']
        )
        text_out += '\n'
        for feed in feeds_file:
            _feed = feeds_file[feed]
            text_out += template_line.format(
                feed, _feed['url'], _feed['channel'],
                feed_len=lengths['feed_len'], url_len=lengths['url_len'],
                channel_len=lengths['channel_len']
            )
            if feed != list(feeds_file)[-1]:
                text_out += '\n'
    text_out = '```{}```'.format(text_out)
    return text_out


def review_feeds_status(feeds_file):
    'Get a status for a feed from `feeds` and update it in source file'
    feeds_file_in = file_io.read_json(feeds_file)
    for feed in feeds_file_in:
        log.log('{}: {}'.format(feed, feeds_file_in[feed]['status']))
        URL = feeds_file_in[feed]['url']
        URL_STATUS = feeds_file_in[feed]['status']['url']
        if URL_STATUS == 'stale':
            log.log('Feed url for {} is stale, checking it...'.format(feed))
            if get_feed_links(URL) is not None:
                log.log('Feed url for {} is ok, reactivating!'.format(feed))
                update_feed_status(feed, feeds_file, url='ok')
                break
            elif get_feed_links(URL) is None:
                log.log('Feed url for {} is still stale, skipping'.format(feed))
                break
        CHANNEL = feeds_file_in[feed]['channel']
        CHANNEL_STATUS = feeds_file_in[feed]['status']['channel']
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
                update_feed_status(feed, feeds_file, channel='ok')


def link_is_in_log(link: str, feed_log: list) -> bool:
    'Checks if `link` is in the `feed_log`'
    if link in feed_log:
        return True
    else:
        return False


def link_similar_to_logged_post(link: str, feed_log: list):
    '''
    Checks if `link` is similar to any other logged link in `feed_log`.
    If simliar, return the similar link from log.
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
    If not posted, post to `CHANNEL`
    If posted, make a similarity check just to make sure we are not posting
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
        if not link_is_in_log(feed_link, FEED_LOG[feed]):
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
                FEED_LOG[feed].remove(feed_link_similar)
                FEED_LOG[feed].append(feed_link)
        elif link_is_in_log(feed_link, FEED_LOG[feed]):
            log.log_more(f'Link `{feed_link}` already logged. Skipping.')
        # Write to the logs-file at the end
        file_io.write_json(feed_log_file, FEED_LOG)


if __name__ == "__main__":
    pass
