#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"cogs: Manage cogs"

import os
from contextlib import suppress
from discord.ext import commands

from sausage_bot.util import envs, config
from sausage_bot.util.args import args

logger = config.logger

# Create necessary folders before starting
check_and_create_folders = [envs.COGS_DIR]
for folder in check_and_create_folders:
    with suppress(FileExistsError):
        os.makedirs(folder)


class Cogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    async def load_cog_internal(cog_name):
        """
        Load a specific cog by `cog_name`.

        Returns True when the cog was loaded, False when it already was.
        `on_ready` runs again on every gateway reconnect/RESUME, but
        extensions loaded by an earlier run stay loaded - reloading one
        raises `ExtensionAlreadyLoaded`, which used to abort the rest of
        `on_ready` (including the bot channel check) on every reconnect.
        """
        try:
            await config.bot.load_extension(
                "{}.{}".format(envs.COGS_REL_DIR, f"{cog_name}")
            )
            return True
        except commands.ExtensionAlreadyLoaded:
            logger.debug(f"Cog `{cog_name}` is already loaded, skipping")
            return False

    async def unload_cog_internal(cog_name):
        """
        Unload a specific cog by `cog_name`
        """
        try:
            await config.bot.unload_extension(
                "{}.{}".format(envs.COGS_REL_DIR, f"{cog_name}")
            )
            return True
        except commands.ExtensionNotLoaded:
            return False

    async def reload_cog_internal(cog_name):
        """
        Reload a specific cog by `cog_name`
        """
        await config.bot.reload_extension(
            "{}.{}".format(envs.COGS_REL_DIR, f"{cog_name}")
        )
        return

    async def load_and_clean_cogs_internal():
        """
        Load cogs from the cog-dir
        """
        if args.selected_cogs:
            logger.debug(f"selected_cogs is activated: {args.selected_cogs}")
            if "none" in [item.lower() for item in args.selected_cogs]:
                logger.debug("Not Loading cogs")
            else:
                cog_files = [cog[:-3] for cog in os.listdir(envs.COGS_DIR)]
                for testing_cog in args.selected_cogs:
                    if testing_cog in cog_files:
                        if await Cogs.load_cog_internal(testing_cog):
                            logger.info("Loaded cog: {}".format(testing_cog))
                logger.debug(
                    "Loading selected cogs for testing purposes: ({})".format(
                        ", ".join(args.selected_cogs)
                    )
                )
        else:
            logger.debug(f"Got these files in `COGS_DIR`: {os.listdir(envs.COGS_DIR)}")
            for filename in os.listdir(envs.COGS_DIR):
                if filename.endswith(".py") and not filename.startswith("_"):
                    cog_name = filename[:-3]
                    if await Cogs.load_cog_internal(cog_name):
                        logger.info("Loaded cog: {}".format(cog_name))


async def ensure_guild_tables_for_loaded_cogs(guild) -> None:
    """
    Prep every loaded cog's per-guild tables for `guild`.

    Each cog preps its own tables in `setup()`, which only runs when the
    cog is loaded at startup - so a guild approved while the bot was
    already running got nothing but its `settings` and `tasks` rows, and
    every cog stayed silently inactive there until the next restart.
    Cogs that keep per-guild tables expose an idempotent
    `ensure_guild_tables(guild)` for this; the rest are skipped.

    One cog failing must not stop the others: a guild set up except for
    one cog is a lot better than a guild half set up.
    """
    if guild is None:
        # Callers resolve the guild from a registry row, and the bot is
        # not necessarily a member of it any more
        logger.error("Got no guild to prep cog tables for, skipping")
        return
    for cog_name, cog_module in list(config.bot.extensions.items()):
        ensure_tables = getattr(cog_module, "ensure_guild_tables", None)
        if ensure_tables is None:
            continue
        logger.debug(f"Prepping `{cog_name}` tables for `{guild.name}`")
        try:
            await ensure_tables(guild)
        except Exception as error:
            logger.error(
                f"Could not prep `{cog_name}` tables for `{guild.name}`: {error}"
            )
