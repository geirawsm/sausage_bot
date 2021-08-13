#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import io
import os
import stat
import json
from pathlib import Path
from discord_rss import log, _vars


def import_file_as_list(file_in):
    '''
    Open `file_in` and import it as a list.
    '''
    readtext = io.open(file_in, mode="r", encoding="utf-8")
    list_out = eval(readtext.read())
    readtext.close()
    return list_out


def read_list(list_in):
    '''
    Open `list_in` and convert to a list.
    '''
    readtext = io.open(list_in, mode="r", encoding="utf-8")
    list_out = readtext.read().splitlines()
    readtext.close()
    return list_out


def add_to_list(list_file_in, item_add):
    ensure_file(list_file_in, '[]')
    opened_list = import_file_as_list(list_file_in)
    opened_list.append(item_add)
    with open(list_file_in, 'w') as fout:
        fout.write(str(opened_list))


def read_json(json_file):
    '''
    Open `json_file` as a JSON and convert to as a dict
    Returns _file as a dict or an empty dict
    '''
    readtext = io.open(json_file, mode="r", encoding="utf-8")
    try:
        json_in = dict(json.loads(readtext.read()))
    except(json.JSONDecodeError):
        if readtext.read() == '':
            json_in = {}
    readtext.close()
    return json_in


def write_json(json_file, json_out):
    'Write content to json file'
    with open(json_file, 'w') as write_file:
        json.dump(json_out, write_file)


def ensure_file(file_path, file_template=False):
    '''
    Create file if it doesn't exist and include the `file_template` if
    provided.

    Returns True if file was made
    Returns False if file already existed
    '''
    def file_size(filename):
        '''
        Checks the file size of a file. If it can't find the file it will
        return False
        '''
        try:
            _stats = os.stat(filename, follow_symlinks=True)
            return _stats[stat.ST_SIZE]
        except(FileNotFoundError):
            return False

    # Make the folders if necessary
    try:
        os.makedirs(file_path.parent)
    except(FileExistsError):
        pass
    # Ooooh, this is a scary one. Don't overwrite the file unless it's empty
    log.log_more('{} size: {}'.format(file_path, file_size(file_path)))
    # Create the file if it doesn't exist
    if not file_size(file_path):
        log.log_more('File not found, creating: {}'.format(file_path))
        with open(file_path, 'w+') as fout:
            if file_template:
                fout.write(file_template)
            else:
                fout.write('')
        return True
    else:
        return False

if __name__ == "__main__":
    add_to_list(_vars.LIST_DIR / 'test.list', 'twestitem2')
