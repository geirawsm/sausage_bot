#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'Arguments to use for running the bot in the terminal'
import argparse
from pprint import pprint

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
logging_args.add_argument('--error', '-e',
                          help='Log errors',
                          action='store_true',
                          default=False,
                          dest='log_error')
logging_args.add_argument('--i18n', '-i',
                          help='Log i18n errors',
                          action='store_true',
                          default=False,
                          dest='log_i18n')
logging_args.add_argument('--log-print', '-lp',
                          help='Print logging to output',
                          action='store_true',
                          default=False,
                          dest='log_print')
logging_args.add_argument('--log-file', '-lf',
                          help='Write log to files',
                          action='store_true',
                          default=False,
                          dest='log_file')
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
logging_args.add_argument('--highlight-color', '-hlc',
                          help='Chose color to Highlight',
                          action='store',
                          default='red',
                          dest='log_highlight_color')
logging_args.add_argument('--log-all',
                          help='Log all levels (log, verbose, log-print, '
                               'log-database, debug and error)',
                          action='store_true',
                          default=False,
                          dest='log_all')

testing_args = parser.add_argument_group('Testing')
testing_args.add_argument('--testmode', '-t',
                          help='Run some functions in testmode',
                          action='store_true',
                          default=False,
                          dest='testmode')
testing_args.add_argument('--force-parser',
                          help='Force what parser to use in `autoevent`',
                          action='store',
                          default=False,
                          dest='force_parser')
testing_args.add_argument('--not-write-database', '-nwd',
                          help='Do not write to databases',
                          action='store_true',
                          default=False,
                          dest='not_write_database')
testing_args.add_argument('--selected-cogs', '-c',
                          help='Load only selected cogs for testing purposes',
                          action='append',
                          dest='selected_cogs')
testing_args.add_argument('--rss-skip-url-validation',
                          help='Skip URL validation when adding RSS feeds',
                          action='store_true',
                          default=False,
                          dest='rss_skip_url_validation')
version_info_args = parser.add_argument_group('Version info')
version_info_args.add_argument('--last-commit',
                               help='Load info about last commit this bot '
                                    'runs on',
                               action='store',
                               default="",
                               dest='last_commit')
version_info_args.add_argument('--last-run-number',
                               help='Load info about last run number from '
                                    'Github this bot runs on',
                               action='store',
                               default="",
                               dest='last_run_number')

maintenance_args = parser.add_argument_group('Maintenance')
maintenance_args.add_argument('--maintenance',
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
    pprint(args)
