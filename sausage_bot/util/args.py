#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'Arguments to use for running the bot in the terminal'
import argparse

parser = argparse.ArgumentParser()

settings_args = parser.add_argument_group('Settings')
settings_args.add_argument('--data-dir',
                           help='Set custom data dir',
                           action='store',
                           default=False,
                           dest='data_dir')

logging_args = parser.add_argument_group('Logging')
logging_args.add_argument('--log', '-l',
                          help='Log important messages',
                          action='store_true',
                          default=False,
                          dest='log')
logging_args.add_argument('--verbose', '-V',
                          help='Log verbose',
                          action='store_true',
                          default=False,
                          dest='log_verbose')
logging_args.add_argument('--log-print', '-lp',
                          help='Print logging instead of writing to file',
                          action='store_true',
                          default=False,
                          dest='log_print')
logging_args.add_argument('--log-database', '-ld',
                          help='Log database actions',
                          action='store_true',
                          default=False,
                          dest='log_db')
logging_args.add_argument('--debug', '-d',
                          help='Show debug messages',
                          action='store_true',
                          default=False,
                          dest='debug')
logging_args.add_argument('--log-slow', '-ls',
                          help='Wait 3 seconds after each logging',
                          action='store_true',
                          default=False,
                          dest='log_slow')
logging_args.add_argument('--highlight', '-hl',
                          help='Highlight chosen text in logging '
                          'function naming',
                          action='store',
                          default=None,
                          dest='log_highlight')

testing_args = parser.add_argument_group('Testing')
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

autodoc_args = parser.add_argument_group('Autodocumentation')
autodoc_args.add_argument('--file', '-f',
                          help='Only check a specific file within '
                          'project root',
                          action='store',
                          default=None,
                          dest='file'
                          )
autodoc_args.add_argument('--function-filter', '-ff',
                          help='Specify a function to check (and only '
                          'that)',
                          action='store',
                          default=None,
                          dest='function_filter'
                          )
autodoc_args.add_argument('--file-out', '-fo',
                          help='Specify name of output file (from '
                          'docs-folder as root)',
                          action='store',
                          default=None,
                          dest='file_out'
                          )

args, unknown = parser.parse_known_args()


if __name__ == "__main__":
    pass
