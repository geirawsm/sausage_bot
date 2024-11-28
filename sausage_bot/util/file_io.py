#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import stat
import json
from pathlib import Path
from difflib import SequenceMatcher
from ..util.log import log


def remove_file(filename):
    os.remove(filename)


def write_file(filename, content_to_write, append=False):
    '''
    Write `content_to_write` to the file `filename`
    Appends instead if set to True
    '''
    if not isinstance(filename, str):
        filename = str(filename)
    ensure_file(filename)
    if append:
        with open(filename, 'a') as fout:
            fout.write(str(content_to_write))
            return True
    else:
        with open(filename, 'w') as fout:
            fout.write(str(content_to_write))
            return True


def import_file_as_list(file_in):
    '''
    Open `file_in`, import it as a list and return ut.
    If this fails, return None.
    '''
    file_in = str(file_in)
    ensure_file(file_in, '[]')
    try:
        with open(file_in, 'r', encoding='utf-8') as f:
            list_out = eval(str(f.read()))
        return list_out
    except Exception as e:
        log.error(f"Couldn't open file `{file_in}` ({e})")
        return None


def add_to_list(list_file_in, item_add):
    'Add `item_add` to a list in file `list_file_in`'
    list_file_in = str(list_file_in)
    if not isinstance(item_add, (str, float, int)):
        return None
    ensure_file(list_file_in, '[]')
    opened_list = import_file_as_list(list_file_in)
    opened_list.append(item_add)
    write_file(list_file_in, str(opened_list))
    return opened_list


def read_json(json_file):
    '''
    Open `json_file` as a JSON and convert to as a dict.
    Returns _file as a dict or an empty dict.
    '''
    ensure_file(json_file, {})
    try:
        with open(json_file, encoding='utf-8') as f:
            log.verbose('Loaded json file')
            return dict(json.load(f))
    except json.JSONDecodeError as e:
        log.error(f"Error when reading json from {json_file}:\n{e}")
        return None
    except OSError as e:
        log.error(f"File can't be read {json_file}:\n{e}")
        return None


def write_json(json_file, json_out):
    'Write `json_out` to `json file`'
    with open(json_file, 'w') as write_file:
        json.dump(json_out, write_file, indent=4, sort_keys=True)


def file_size(filename):
    '''
    Checks the file size of a file. If it can't find the file it will
    return False
    '''
    try:
        _stats = os.stat(filename, follow_symlinks=True)
        return _stats[stat.ST_SIZE]
    except FileNotFoundError:
        return False


def folder_size(path_to_folder, human=False):
    '''
    Checks the size of files in a folder. If it can't find the folder it will
    return False
    '''
    # Check if path exist
    log.debug(f'Checking `path_to_folder`: {path_to_folder}')
    if file_exist(str(path_to_folder)):
        path_files = os.listdir(path_to_folder)
        log.debug(f'Got files: {path_files}')
        temp_size = 0
        for _file in path_files:
            _size = os.stat(
                f'{path_to_folder}/{_file}', follow_symlinks=True
            )[stat.ST_SIZE]
            temp_size += _size
        if human:
            return size_in_human(temp_size)
        else:
            return temp_size


def size_in_human(num, suffix="B"):
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


def file_exist(filename):
    '''
    Checks if the file exist. If it can't find the file it will return
    False
    '''
    try:
        os.stat(str(filename), follow_symlinks=True)
        return True
    except FileNotFoundError:
        return False


def ensure_folder(folder_path: str):
    '''
    Create folders in `folder_path` if it doesn't exist
    '''
    folder_path = str(folder_path)
    # Make the folders if necessary
    if not os.path.exists(folder_path):
        _dirs = str(folder_path).split(os.sep)
        _path = ''
        for _dir in _dirs:
            _path += '{}/'.format(_dir)
        Path(_path).mkdir(parents=True, exist_ok=True)


def ensure_file(file_path_in: str, file_template=False):
    '''
    Create file `file_path_in` if it doesn't exist and include the
    `file_template` if provided.
    '''
    full_file_path = str(file_path_in).split(os.sep)
    folder_path = '/'.join(full_file_path[0:-1])
    folder_path += '/'
    file_name = full_file_path[-1]
    # Make the folders if necessary
    if not os.path.exists(file_path_in):
        ensure_folder(folder_path)
    # Ooooh, this is a scary one. Don't overwrite the file unless it's empty
    log.debug('{} size: {}'.format(file_name, file_size(file_path_in)))
    # Create the file if it doesn't exist
    if not file_size(file_path_in):
        log.verbose('File not found, creating: {}'.format(file_path_in))
        if file_name.split('.')[-1] == 'json':
            if file_template:
                write_json(file_path_in, file_template)
            else:
                write_json(file_path_in, {})
        else:
            with open(file_path_in, 'w+') as fout:
                if file_template:
                    fout.write(file_template)
                else:
                    fout.write('')


def get_max_item_lengths(headers, dict_in):
    'Get the maximum lengths for keys in dicts `headers` and `dict_in`'
    lengths = {}
    for item in headers:
        lengths[item] = len(item)
    for item in dict_in:
        for x in dict_in[item]:
            if lengths[x] < len(str(dict_in[item][x])):
                lengths[x] = len(str(dict_in[item][x]))
    return lengths


def check_similarity(
        input1: str, input2=None, ratio_floor: float = None,
        ratio_roof: float = None
):
    '''
    Check similarities between `input1` and `input2` (str), or `input1` and
    items in `input2` (list). As standard it will check if the similarity
    has a ratio between 95 % and 99.999999999999999999999999995 %. If that
    ratio hits, it will return the object it is similar with.
    Otherwise, return False.

    If `input1` is not a string, it will return None.
    If `input2` is None, or not a string or list, it will return None.

    '''

    def similarity_helper(input1, input2, ratio_floor, ratio_roof):
        ratio = float(SequenceMatcher(a=input1, b=input2).ratio())
        # Our "similarity" is defined by the following equation:
        if ratio_floor is None:
            ratio_floor = 0.95
        if ratio_roof is None:
            ratio_roof = 0.99999999999999999999999999995
        if ratio_floor <= ratio <= ratio_roof:
            log.debug(
                f'These inputs seem similiar (ratio: {ratio}):\n'
                f'`{input1}` vs `{input2}`'
            )
            return input2
        else:
            log.verbose(
                f'Not similar, ratio too low or identical (ratio: {ratio}):\n'
                f'`{input1}` vs `{input2}`'
            )
            return False

    # Stop function if not correct input
    if type(input1) is not str:
        log.error('`input1` is not string')
        return None
    elif input2 is None or not isinstance(input2, (str, list)):
        log.error(f'Incorrect input given to `input2`: {input2}')
        return None
    elif isinstance(input2, list):
        for list_item in input2:
            log.debug(list_item)
            _check = similarity_helper(
                input1, list_item, ratio_floor, ratio_roof
            )
            if _check is not False:
                return _check
        return False
    elif isinstance(input2, str):
        return similarity_helper(input1, input2, ratio_floor, ratio_roof)


def create_necessary_files(file_list):
    'Get `file_list` (list) and create necessary files before running code'
    log.verbose('Creating necessary files')
    for file in file_list:
        if isinstance(file, tuple):
            ensure_file(file[0], file_template=file[1])
            if isinstance(file[1], dict):
                file_out = read_json(file[0])
                for item in file[1]:
                    if item not in file_out:
                        file_out[item] = file[1][item]
                write_json(file[0], file_out)
        else:
            ensure_file(file)


def make_db_output_to_json(cols, db_output):
    'Make `db_output` into a json file'
    # Length check
    if len(cols) != len(db_output[0]):
        log.error('Length of `cols` and `db_output` does not match')
        return None
    json_out = {}
    for item in db_output:
        json_out[item[0]] = {}
        for col in enumerate(cols):
            json_out[item[0]][col[1]] = item[col[0]]
    return json_out


if __name__ == "__main__":
    pass
