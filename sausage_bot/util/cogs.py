#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'cogs: Manage cogs'
import os
from discord.ext import commands
from contextlib import suppress

from sausage_bot.util import envs, config
from sausage_bot.util.args import args

logger = config.logger

# Create necessary folders before starting
check_and_create_folders = [
    envs.COGS_DIR
]
for folder in check_and_create_folders:
    with suppress(FileExistsError):
        os.makedirs(folder)


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
        if args.selected_cogs:
            if 'none' in [item.lower() for item in args.selected_cogs]:
                logger.debug('Not Loading cogs')
            else:
                cog_files = [cog[:-3] for cog in os.listdir(envs.COGS_DIR)]
                for testing_cog in args.selected_cogs:
                    if testing_cog in cog_files:
                        logger.info('Loading cog: {}'.format(testing_cog))
                        await Cogs.load_cog_internal(testing_cog)
                logger.debug(
                    'Loading selected cogs for testing purposes: ({})'.format(
                        ', '.join(args.selected_cogs)
                    )
                )
        else:
            logger.debug(
                f'Got these files in `COGS_DIR`: {os.listdir(envs.COGS_DIR)}'
            )
            for filename in os.listdir(envs.COGS_DIR):
                if filename.endswith('.py') and not filename.startswith('_'):
                    cog_name = filename[:-3]
                    logger.info('Loading cog: {}'.format(cog_name))
                    await Cogs.load_cog_internal(cog_name)
