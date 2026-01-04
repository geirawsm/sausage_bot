#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import glob
import re
import os
from sys import exit
from tabulate import tabulate

from sausage_bot.util import envs


def read_file(file_in):
    try:
        with open(file_in, encoding='utf-8') as f:
            return f.read()
    except OSError as e:
        print(f"File can't be read {file_in}:\n{e}")
        return None


def test_local_variables():
    errors_out = []
    filelist = glob.glob(f'{envs.LOCALE_DIR}/*.*.yml', recursive=True)
    _list = ['{', '}', '%']
    for _file in filelist:
        filename = str(_file).split(os.sep)[-1].split('.')
        _cog = filename[0]
        _lang = filename[1]
        _yaml = read_file(_file)
        for line in enumerate(_yaml.split('\n')):
            if ':' in line[1]:
                after_split = line[1].split(':')[1]
                if len(after_split) > 0:
                    for word in re.split(
                        r'[\.:,;\-\'\s\(\)`#\"]', after_split
                    ):
                        if any(
                            _list_item in word for _list_item in _list
                        ) and not re.match(r'%{.*}', word):
                            errors_out.append(
                                [_cog, _lang, line[0] + 1, word]
                            )
    if len(errors_out) > 0:
        print('ERRORS FOUND:')
        print(tabulate(errors_out, headers=['Cog', 'Lang', 'Line', 'Word']))
        exit(1)


def main():
    test_local_variables()


if __name__ == "__main__":
    main()
