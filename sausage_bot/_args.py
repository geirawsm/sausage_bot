#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse

parser = argparse.ArgumentParser()

logging_args = parser.add_argument_group('Logging')
logging_args.add_argument('--log',
                          help='Log important messages',
                          action='store_true',
                          default=False,
                          dest='log')
logging_args.add_argument('--log-more',
                          help='Log absolutely everything',
                          action='store_true',
                          default=False,
                          dest='log_more')
logging_args.add_argument('--log-print',
                          help='Print logging instead of writing to file',
                          action='store_true',
                          default=False,
                          dest='log_print')
logging_args.add_argument('--no-rss',
                          help='Start the bot, but with no RSS functionality',
                          action='store_true',
                          default=False,
                          dest='no_rss')
logging_args.add_argument('--highlight', '-hl',
                          help='Highlight chosen text in logging function naming',
                          action='store',
                          default=None,
                          dest='log_highlight')

maintenance_args = parser.add_argument_group('Maintenance')
maintenance_args.add_argument('--maintenance-mode',
                              help='Start the bot in maintenance mode',
                              action='store_true',
                              default=False,
                              dest='maintenance')
args = parser.parse_args()


if __name__ == "__main__":
    print(args)
