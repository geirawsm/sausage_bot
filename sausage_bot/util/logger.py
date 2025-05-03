#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import os
import stat
import json

from sausage_bot.util import envs


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
    # Create the file if it doesn't exist
    if not file_size(file_path_in):
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


def write_json(json_file, json_out):
    'Write `json_out` to `json file`'
    with open(json_file, 'w') as write_file:
        json.dump(json_out, write_file, indent=4, sort_keys=True)


class ColorFormatter(logging.Formatter):
    """Logging Formatter to add colors and count warning / errors"""

    grey = "\x1b[90m"
    green = "\x1b[92m"
    yellow = "\x1b[93m"
    red = "\x1b[91m"
    reset = "\x1b[0m"

    format = "%(asctime)s | %(levelname)-5.5s | %(message)s  -  "\
        "%(module)s:%(funcName)s:%(lineno)s"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: green + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: red + format + reset
    }

    def format(self, record):
        record.levelname = 'WARN' if record.levelname == 'WARNING'\
            else record.levelname
        record.levelname = 'ERROR' if record.levelname == 'CRITICAL'\
            else record.levelname
        log_fmt = self.FORMATS.get(record.levelno)
        date_fmt = "%Y-%m-%d %H:%M:%S"
        formatter = logging.Formatter(fmt=log_fmt, datefmt=date_fmt)
        return formatter.format(record)


def configure_logging(
    console_level=None, file_level=None, to_file=False
):
    logger = logging.getLogger()
    logger.setLevel(
        console_level if console_level is not None else logging.DEBUG
    )
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(ColorFormatter())
    logger.addHandler(console_handler)

    if to_file:
        ensure_file(envs.LOG_DIR / 'bot.log')
        file_handler = TimedRotatingFileHandler(
            filename=envs.LOG_DIR / 'bot.log',
            when="midnight",
            encoding="UTF-8",
            delay=0,
            backupCount=10
        )
        file_handler.setLevel(
            file_level if file_level is not None else logging.DEBUG
        )
        file_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-5.5s | %(message)s  -  "
            "%(module)s:%(funcName)s:%(lineno)s",
            "%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)


def main():
    configure_logging()
    logging.debug("debug message")
    logging.info("info message")
    logging.warning("warning message")
    logging.error("error message")
    logging.critical("critical message")


if __name__ == "__main__":
    main()
