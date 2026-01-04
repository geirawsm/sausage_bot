#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'Arguments to use for running the autodocumentation part of the bot'
import argparse

parser = argparse.ArgumentParser()

autodoc_args = parser.add_argument_group('Autodocumentation')
autodoc_args.add_argument('--file', '-f',
                          help='Only check a specific file within '
                          'project root',
                          action='store',
                          default=None,
                          dest='file'
                          )
autodoc_args.add_argument('--file-out', '-fo',
                          help='Specify name of output file (from '
                          'docs-folder as root)',
                          action='store',
                          default=None,
                          dest='file_out'
                          )

doc_args, unknown = parser.parse_known_args()


if __name__ == "__main__":
    pass
