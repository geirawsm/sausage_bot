#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import json
import logging
import os
import stat
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from sausage_bot.util import envs, guild_context

# Both handlers share this, so console and file output stay in step.
# The guild column is padded to the width of a Discord snowflake so the
# module/function/line field starts in the same column on every line,
# guild or no guild.
LOG_FORMAT = (
    "%(asctime)s | %(levelname)-5.5s | [ %(guild)-19s ] | "
    "[ %(module)s : %(funcName)s : %(lineno)s ]\t%(message)s"
)


def truncate_for_log(data, max_len=100):
    """
    Returns a copy of `data` where all string values longer than
    `max_len` characters are cut and marked with '...'.
    Works recursively on dict, list and tuple.
    """
    if isinstance(data, str):
        if len(data) > max_len:
            return f"{data[:max_len]}... [truncated, {len(data)} chars total]"
        return data
    elif isinstance(data, dict):
        return {k: truncate_for_log(v, max_len) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [truncate_for_log(v, max_len) for v in data]
    else:
        return data


def file_size(filename):
    """
    Checks the file size of a file. If it can't find the file it will
    return False
    """
    try:
        _stats = os.stat(filename, follow_symlinks=True)
        return _stats[stat.ST_SIZE]
    except FileNotFoundError:
        return False


def ensure_folder(folder_path: str):
    """
    Create folders in `folder_path` if it doesn't exist
    """
    folder_path = str(folder_path)
    # Make the folders if necessary
    if not os.path.exists(folder_path):
        _dirs = str(folder_path).split(os.sep)
        _path = ""
        for _dir in _dirs:
            _path += f"{_dir}/"
        Path(_path).mkdir(parents=True, exist_ok=True)


def ensure_file(file_path_in: str, file_template: str = ""):
    """
    Create file `file_path_in` if it doesn't exist and include the
    `file_template` if provided.
    """
    full_file_path = str(file_path_in).split(os.sep)
    folder_path = "/".join(full_file_path[0:-1])
    folder_path += "/"
    file_name = full_file_path[-1]
    # Make the folders if necessary
    if not os.path.exists(file_path_in):
        ensure_folder(folder_path)
    # Ooooh, this is a scary one. Don't overwrite the file unless it's empty
    # Create the file if it doesn't exist
    if not file_size(file_path_in):
        if file_name.split(".")[-1] == "json":
            write_json(file_path_in, file_template if file_template else {})
        else:
            with open(file_path_in, "w+") as fout:
                fout.write(file_template if file_template else "")


def write_json(json_file, json_out):
    "Write `json_out` to `json file`"
    with open(json_file, "w") as write_file:
        json.dump(json_out, write_file, indent=4, sort_keys=True)


class GuildContextFilter(logging.Filter):
    """
    Stamp every record with the guild the current asyncio Task is working
    on, so output from concurrently running guilds can be told apart.

    The value is read from `guild_context.current_guild_id`, which
    `db_helper.guild_locale_context()` sets for the duration of a command
    or a background-task iteration. Passing
    `extra={"guild_id": <id>}` to the logging call overrides it, for the
    code paths that know their guild but don't enter that context.

    Records with no guild in scope - startup, global commands - get an
    empty string, which `LOG_FORMAT` pads out to a blank column of the
    same width, so every line's module field lines up.

    Attached to the handlers rather than to the logger: a logger's own
    filters only see records logged directly on it, so records that
    propagate up from a child logger (discord.py, aiosqlite) would reach
    the formatter without a `guild` attribute and raise on format.
    """

    def filter(self, record):
        guild_id = getattr(record, "guild_id", None)
        if guild_id is None:
            guild_id = guild_context.current_guild_id.get()
        record.guild = str(guild_id) if guild_id else ""
        return True


class ColorFormatter(logging.Formatter):
    """Logging Formatter to add colors and count warning / errors"""

    red = "\x1b[31m"
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    blue = "\x1b[34m"
    magenta = "\x1b[35m"
    cyan = "\x1b[36m"
    white = "\x1b[37m"
    grey = "\x1b[90m"
    reset = "\x1b[0m"

    format = LOG_FORMAT

    FORMATS = {
        logging.DEBUG: f"{white}{format}{reset}",
        logging.INFO: f"{green}{format}{reset}",
        logging.WARNING: f"{yellow}{format}{reset}",
        logging.ERROR: f"{red}{format}{reset}",
        logging.CRITICAL: f"{red}{format}{reset}",
    }

    def format(self, record):
        record.levelname = "WARN" if record.levelname == "WARNING" else record.levelname
        record.levelname = (
            "ERROR" if record.levelname == "CRITICAL" else record.levelname
        )
        log_fmt = self.FORMATS.get(record.levelno)
        date_fmt = "%Y-%m-%d %H:%M:%S"
        formatter = logging.Formatter(fmt=log_fmt, datefmt=date_fmt)
        return formatter.format(record)


def _level(level_in, default):
    """
    Accept `debug`, `DEBUG` or `logging.DEBUG`, falling back to
    `default` for None and for a name that is not a level.

    `logging.getLevelName()` is not used for the lookup: it hands back
    the string `"Level DBEUG"` for a typo rather than failing, and a
    handler holding a string as its level lets everything through.
    """
    if level_in is None:
        return default
    if isinstance(level_in, int):
        return level_in
    return logging.getLevelNamesMapping().get(str(level_in).upper(), default)


def configure_logging(
    console_level=None,
    file_level=None,
    to_file=False,
    log_days=envs.LOG_ROTATION_DAYS,
):
    logger = logging.getLogger()
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    console_level = _level(console_level, logging.INFO)
    file_level = _level(file_level, logging.INFO)

    # The logger's own level is checked before any handler sees the
    # record, and it defaults to WARNING. Without this line the handlers
    # below never get an INFO or DEBUG record to print, whatever level
    # they are set to.
    logger.setLevel(min(console_level, file_level) if to_file else console_level)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(ColorFormatter())
    console_handler.addFilter(GuildContextFilter())
    logger.addHandler(console_handler)

    if to_file:
        ensure_file(str(envs.LOG_DIR / "bot.log"))
        file_handler = TimedRotatingFileHandler(
            filename=envs.LOG_DIR / "bot.log",
            when="midnight",
            encoding="UTF-8",
            delay=False,
            backupCount=log_days,
        )
        file_handler.setLevel(file_level)
        file_formatter = logging.Formatter(LOG_FORMAT, "%Y-%m-%d %H:%M:%S")
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(GuildContextFilter())
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
