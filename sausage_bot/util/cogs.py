#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from discord.ext import commands
import discord

from sausage_bot.util import envs, config, db_helper
from .log import log


# Create necessary folders before starting
check_and_create_folders = [
    envs.COGS_DIR
]
for folder in check_and_create_folders:
    try:
        os.makedirs(folder)
    except (FileExistsError):
        pass


class Cogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    async def load_cog_internal(cog_name):
        '''
        Load a specific cog by `cog_name`
        #autodoc skip#
        '''
        await config.bot.load_extension(
            '{}.{}'.format(
                envs.COGS_REL_DIR, f'{cog_name}'
            )
        )
        return

    async def unload_cog_internal(cog_name):
        '''
        Unload a specific cog by `cog_name`
        #autodoc skip#
        '''
        try:
            await config.bot.unload_extension(
                '{}.{}'.format(
                    envs.COGS_REL_DIR, f'{cog_name}'
                )
            )
            return True
        except commands.ExtensionNotLoaded:
            return False

    async def reload_cog_internal(cog_name):
        '''
        Reload a specific cog by `cog_name`
        #autodoc skip#
        '''
        await config.bot.reload_extension(
            '{}.{}'.format(
                envs.COGS_REL_DIR, f'{cog_name}'
            )
        )
        return

    async def load_and_clean_cogs_internal():
        '''
        Load cogs from the cog-dir
        #autodoc skip#
        '''
        log.debug(
            f'Got these files in `COGS_DIR`: {os.listdir(envs.COGS_DIR)}'
        )
        for filename in os.listdir(envs.COGS_DIR):
            if filename.endswith('.py') and not filename.startswith('_'):
                cog_name = filename[:-3]
                log.log('Loading cog: {}'.format(cog_name))
                await Cogs.load_cog_internal(cog_name)
