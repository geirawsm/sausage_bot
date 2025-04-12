#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import logging
from logging.handlers import TimedRotatingFileHandler

from sausage_bot.util import envs


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
