#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"config: Get env values and initiate the Discord bot object"

import discord
from discord.ext import commands
from sys import exit
from environs import Env, EnvError
from contextlib import suppress
import os
from pathlib import Path
import pendulum

from . import envs
from . import logger


def ensure_file(file_path_in: str, file_template=False):
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
                _path += "{}/".format(_dir)
            Path(_path).mkdir(parents=True, exist_ok=True)

    full_file_path = str(file_path_in).split(os.sep)
    folder_path = "/".join(full_file_path[0:-1])
    folder_path += "/"
    # Make the folders if necessary
    ensure_folder(folder_path)
    try:
        os.stat(str(file_path_in), follow_symlinks=True)
        file_exist = True
    except FileNotFoundError:
        file_exist = False
    if not file_exist:
        with open(file_path_in, "w+") as fout:
            if file_template:
                fout.write(file_template)
            else:
                fout.write("")


# Create necessary files before starting
print("Ensuring env file")
ensure_file(envs.env_file, envs.env_template)

try:
    env = Env()
    env.read_env(path=envs.env_file)
    # Set basic env values
    DISCORD_TOKEN = env("DISCORD_TOKEN", default=None)
    BOT_ID = env("BOT_ID", default=None)
    # ADMIN_GUILD_ID is the bot's home guild - it is auto-approved and is
    # where the /approve-guild flow and new-guild notifications run from.
    ADMIN_GUILD_ID = env("ADMIN_GUILD_ID", default=None)
    ADMIN_CHANNEL_ID = env("ADMIN_CHANNEL_ID", default=None)
    PREFIX = env("PREFIX", default="!")
    BOT_CHANNEL = env("BOT_CHANNEL", default="bot-log")
    TIMEZONE = env("BOT_TIMEZONE", default="UTC")
    LANGUAGE = env("BOT_LANGUAGE", default="en")
    LOG_ROTATION_DAYS = env("LOG_ROTATION_DAYS", default=10)
    ROLE_CHANNEL = env("ROLE_CHANNEL", default="roles")
    SPOTIFY_ID = env("SPOTIFY_ID", default=None)
    SPOTIFY_SECRET = env("SPOTIFY_SECRET", default=None)
    SCRAPEOPS_API_KEY = env("SCRAPEOPS_API_KEY", default=None)
    STATS_LOOP = env.int("STATS_LOOP", default=10)
    YT_LOOP = env.int("YT_LOOP", default=15)
    RSS_LOOP = env.int("RSS_LOOP", default=15)
    POD_LOOP = env.int("POD_LOOP", default=15)
    FCB_LOOP = env.int("FCB_LOOP", default=60)
    INVITATION_CHANNEL = env.int("INVITATION_CHANNEL", default="general")
    if any(
        envvar is None
        for envvar in [DISCORD_TOKEN, BOT_ID, ADMIN_GUILD_ID, ADMIN_CHANNEL_ID]
    ):
        print("Something is wrong with the env file.")
        exit()
except EnvError as e:
    logger.error(f"You need to set environment variables for the bot to work: {e}")
    exit()


logger.configure_logging(
    to_file=True,
)
logger = logger.logging


# Locale/timezone are per-guild settings (see util/i18n.py and
# util/datetime_handling.py for the per-guild lookup) - these bootstrap
# values are only used before any guild context is available (e.g. at
# import time) and fall back to the TIMEZONE/LANGUAGE env vars.
timezone = pendulum.timezone(TIMEZONE)
locale = pendulum.set_locale(LANGUAGE)
pendulum.week_starts_at(pendulum.MONDAY)
pendulum.week_ends_at(pendulum.SUNDAY)

# Create necessary folders before starting
check_and_create_folders = [envs.DB_DIR, envs.LOG_DIR, envs.DATA_DIR]
for folder in check_and_create_folders:
    with suppress(FileExistsError):
        os.makedirs(folder)


try:
    intents = discord.Intents.all()
    bot = commands.Bot(command_prefix=PREFIX, intents=intents)
except KeyError as e:
    logger.error(f"Couldn't load basic env: {e}")
    exit()
