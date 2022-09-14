#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse

parser = argparse.ArgumentParser()

parser.add_argument('--print', '-p',
    help='Print info',
    action='store_true',
    default=False,
    dest='print'
)
parser.add_argument('--slow', '-s',
    help='Print info slow',
    action='store_true',
    default=False,
    dest='slow'
)
parser.add_argument('--file', '-f',
    help='Only check a specific file within project root',
    action='store',
    default=None,
    dest='file'
)

doc_args, unknown = parser.parse_known_args()


if __name__ == "__main__":
    pass
