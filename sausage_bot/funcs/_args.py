#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'Arguments to use for running the bot in the terminal'
import argparse

parser = argparse.ArgumentParser()

logging_args = parser.add_argument_group('Logging')
logging_args.add_argument('--log', '-l',
                          help='Log important messages',
                          action='store_true',
                          default=False,
                          dest='log')
logging_args.add_argument('--log-more', '-lm',
                          help='Log absolutely everything',
                          action='store_true',
                          default=False,
                          dest='log_more')
logging_args.add_argument('--log-print', '-lp',
                          help='Print logging instead of writing to file',
                          action='store_true',
                          default=False,
                          dest='log_print')
logging_args.add_argument('--log-slow', '-ls',
                          help='Wait 3 seconds after each logging',
                          action='store_true',
                          default=False,
                          dest='log_slow')
logging_args.add_argument('--highlight', '-hl',
                          help='Highlight chosen text in logging function naming',
                          action='store',
                          default=None,
                          dest='log_highlight')

testing_args = parser.add_argument_group('Testing')
testing_args.add_argument('--local-parsing',
                          help='Use requests-testadapter instead of requests',
                          action='store_true',
                          default=False,
                          dest='local_parsing')
testing_args.add_argument('--force-parser',
                          help='Force what parser to use in `autoevent`',
                          action='store',
                          default=False,
                          dest='force_parser')

maintenance_args = parser.add_argument_group('Maintenance')
maintenance_args.add_argument('--maintenance', '-m',
                              help='Start the bot in maintenance mode',
                              action='store_true',
                              default=False,
                              dest='maintenance')
args, unknown = parser.parse_known_args()


if __name__ == "__main__":
    pass
