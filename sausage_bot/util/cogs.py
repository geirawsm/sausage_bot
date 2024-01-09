#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from discord.ext import commands
from tabulate import tabulate

from sausage_bot.util import envs, file_io, config, db_helper
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


class Loading:
    '''
    Control the cogs for the bot
    #autodoc skip#
    '''
    async def change_cog_status(cog_name, status):
        '''
        Change a cog status in the status file

        `cog_name` should be name of cog

        `status` should be `enable` or `disable`
        #autodoc skip#
        '''
        accepted_status = ['enable', 'e', 'disable', 'd']
        if not any(status == ok_status for ok_status in accepted_status):
            log.log(
                'This command only accept `enable` (e) or `disable` (d)'
            )
            return False
        try:
            log.debug(f'Change cog `{cog_name}` status')
            # Change status
            await db_helper.update_fields(
                template_info=envs.cogs_db_schema,
                where=[('cog_name', cog_name)],
                updates=[status]
            )
            return True
        except Exception as e:
            log.log(envs.COGS_CHANGE_STATUS_FAIL.format(e))
            return False

    async def load_cog(cog_name):
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

    async def unload_cog(cog_name):
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

    async def reload_cog(cog_name):
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

    async def load_and_clean_cogs():
        '''
        This does three things:
        1. Adds cogs from folder that are not already present in the
            cogs db
        2. Removes cogs from the cogs db if a file doesn't exist
        3. Start cogs based on status in `cogs_status` file
        #autodoc skip#
        '''
        cog_files = []
        # Add cogs that are not present in the cogs db
        already_registered_cogs = await db_helper.get_output(
            template_info=envs.cogs_db_schema,
            order_by=[('cog_name', 'ASC')]
        )
        log.debug(
            f'These cogs are already registered: {already_registered_cogs}'
        )
        log.debug(
            f'Got these files in `COGS_DIR`: {os.listdir(envs.COGS_DIR)}'
        )
        filelist = []
        for filename in os.listdir(envs.COGS_DIR):
            if filename.endswith('.py') and not filename.startswith('_'):
                cog_name = filename[:-3]
                # Add all cog names to `cog_files` for easier cleaning
                filelist.append(cog_name)
                if cog_name not in [
                        name[0] for name in already_registered_cogs
                ]:
                    # Added as disable
                    cog_files.append((cog_name, 'disable'))
                    log.log(
                        'Added cog {}'.format(cog_name)
                    )
        if len(cog_files) > 0:
            log.debug(f'`cog_files` is {cog_files}')
            await db_helper.insert_many_all(
                template_info=envs.cogs_db_schema,
                inserts=cog_files
            )
        # Clean out cogs that no longer has a file
        # Reload all registered cogs
        already_registered_cogs = await db_helper.get_output(
            template_info=envs.cogs_db_schema,
            order_by=[('cog_name', 'ASC')]
        )
        to_be_removed = []
        for cog_name in [name[0] for name in already_registered_cogs]:
            log.debug(f'`cog_name` is {cog_name}')
            if cog_name not in filelist:
                log.log(f'Removing `{cog_name}`')
                to_be_removed.append(('cog_name', cog_name))
        log.debug(f'`to_be_removed` is {to_be_removed}')
        if len(to_be_removed) > 0:
            await db_helper.del_row_by_OR_filters(
                template_info=envs.cogs_db_schema,
                where=to_be_removed
            )
        # Start cogs based on status
        log.log('Checking `cogs_status` file for enabled cogs')
        for cog_name in already_registered_cogs:
            if cog_name[1] in ['enable', 'e']:
                log.log('Loading cog: {}'.format(cog_name))
                await Loading.load_cog(cog_name)

    async def reload_all_cogs():
        '''
        Reload all cogs which is already enabled
        #autodoc skip#
        '''
        cogs_status = await db_helper.get_output(
            template_info=envs.cogs_db_schema,
            where=('status', 'enable')
        )
        for cog_name in cogs_status:
            if cog_name[1] == 'enable':
                log.log('Reloading cog: {}'.format(cog_name))
                await Loading.reload_cog(cog_name)


@config.bot.command()
@commands.check_any(
    commands.is_owner(),
    commands.has_permissions(administrator=True)
)
async def cog(ctx, cmd_in=None, *cog_names):
    '''
    Enable, disable, reload or list cogs for this bot

    cmd_in      "enable"/"e" or "disable"/"d"
    cog_names   Name(s) of wanted cog, or "all"
    '''

    async def action_on_cog(cmd_in, cog_names):
        '#autodoc skip#'
        if cmd_in in ['enable', 'e']:
            for cog_name in cog_names:
                _loading = await Loading.load_cog(cog_name)
                await Loading.change_cog_status(cog_name, 'enable')
        elif cmd_in in ['disable', 'd']:
            for cog_name in cog_names:
                _unloading = await Loading.unload_cog(cog_name)
                await Loading.change_cog_status(cog_name, 'disable')
        elif not cmd_in:
            await ctx.send(
                envs.COGS_TOO_FEW_ARGUMENTS
            )
            return

    if cmd_in in ['enable', 'e', 'disable', 'd']:
        if cmd_in == 'e':
            cmd_in = 'enable'
        if cmd_in == 'd':
            cmd_in = 'disable'
        if cmd_in in ['enable', 'e']:
            if cog_names[0] == 'all':
                conf_msg = envs.ALL_COGS_ENABLED
            else:
                conf_msg = envs.COGS_ENABLED.format(', '.join(cog_names))
        elif cmd_in in ['disable', 'd']:
            if cog_names[0] == 'all':
                conf_msg = envs.ALL_COGS_DISABLED
            else:
                conf_msg = envs.COGS_DISABLED.format(', '.join(cog_names))
        cogs_db = await db_helper.get_output(
            template_info=envs.cogs_db_schema
        )
        cogs_db = [name[0] for name in cogs_db]
        if cog_names[0] == 'all':
            # Use all names from cogs_db
            await action_on_cog(cmd_in, cogs_db)
        else:
            # Only use given names in function
            await action_on_cog(cmd_in, cog_names)
        await ctx.send(conf_msg)
        return True
    elif cmd_in == 'list':
        # List cogs and their status
        cogs_db = await db_helper.get_output(
            template_info=envs.cogs_db_schema,
            order_by=[('cog_name', 'ASC')]
        )
        await ctx.send(
            get_cogs_list(cogs_db)
        )
        return
    elif cmd_in == 'reload':
        # Reload all cogs
        await Loading.reload_all_cogs()
        await ctx.send(envs.ALL_COGS_RELOADED)
        return
    elif cmd_in is None:
        await ctx.send(
            envs.COGS_TOO_FEW_ARGUMENTS
        )
        return


def get_cogs_list(cogs_file):
    '''
    Get a pretty list of all the cogs
    #autodoc skip#
    '''
    log.debug(f'Got this from `cogs_file`: {cogs_file}')
    text_out = '```{}```'.format(
        tabulate(
            cogs_file, headers=['Cog', 'Status'],
            tablefmt='presto'
        )
    )
    log.debug(f'Returning:\n{text_out}')
    return text_out
