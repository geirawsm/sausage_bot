#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import io
import os
import stat
import json
from pathlib import Path
from sausage_bot import log, _vars
import pathlib


def write_file(file_out, contents):
    with open(file_out, 'w') as fout:
        fout.write(str(contents))


def import_file_as_list(file_in):
    '''
    Open `file_in` and import it as a list.
    '''
    ensure_file(file_in, '[]')
    readtext = open(file_in, 'r', encoding='utf-8')
    list_out = eval(str(readtext.read()))
    readtext.close()
    return list_out


def import_file_as_dict(file_in):
    '''
    Open `file_in` as a JSON and convert to as a dict
    Returns file_in as a dict or an empty dict
    '''
    _ensure = ensure_file(file_in, '{}')
    if _ensure:
        return {}
    else:
        readtext = open(file_in, 'r', encoding='utf-8')
        try:
            _json = dict(json.loads(readtext.read()))
        except Exception as e:
            print('Error when reading JSON ({}), writing empty file'.format(file_in))
            print('Error: {}'.format(e))
            return {}
        readtext.close()
        return _json


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
    write_file(list_file_in, str(opened_list))


def read_json(json_file):
    '''
    Open `json_file` as a JSON and convert to as a dict
    Returns _file as a dict or an empty dict
    '''
    ensure_file(json_file)
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
    if not os.path.exists(file_path):
        _dirs = str(file_path).split(os.sep)[0:-1]
        _path = ''
        for _dir in _dirs:
            _path += '{}/'.format(_dir)
        pathlib.Path(_path).mkdir(parents=True, exist_ok=True)
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
