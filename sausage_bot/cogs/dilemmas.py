#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'dilemmas: Post a random dilemma'
import discord
from discord.ext import commands
from discord.app_commands import locale_str, describe
import uuid

from sausage_bot.util import config, envs, db_helper, file_io
from sausage_bot.util.i18n import I18N

logger = config.logger

class Dilemmas(commands.Cog):
    'Post a random dilemma'

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    group = discord.app_commands.Group(
        name="dilemmas", description='Dilemmas'
    )

    @group.command(
        name="post", description=locale_str(I18N.t(
            'dilemmas.commands.post.cmd'
        ))
    )
    async def dilemmas(self, interaction: discord.Interaction) -> None:
        def prettify(dilemmas_in):
            '''
            Enclosing `dilemmas_in` in quotation marks
            #autodoc skip#
            '''
            out = '```{}```'.format(dilemmas_in)
            return out

        async def get_random_dilemma():
            return await db_helper.get_random_left_exclude_output(
                envs.dilemmas_db_schema,
                envs.dilemmas_db_log_schema,
                'id',
                ('id', 'dilemmas_text')
            )

        await interaction.response.defer()
        # Check that there are dilemmas
        no_of_dilemmas = await db_helper.get_output(
            template_info=envs.dilemmas_db_schema,
            select=('id')
        )
        if len(no_of_dilemmas) <= 0:
            await interaction.followup.send(
                I18N.t('dilemmas.commands.post.no_dilemmas_in_db'),
                envs.DILEMMAS_NO_DILEMMAS_IN_DB,
                ephemeral=True
            )
            return
        # Get a random dilemma
        random_dilemma = await get_random_dilemma()
        if len(random_dilemma) == 0:
            await db_helper.empty_table(envs.dilemmas_db_log_schema)
            random_dilemma = await get_random_dilemma()
        # Post dilemma
        _dilemma = prettify(random_dilemma[0][1])
        dilemma_post = await interaction.followup.send(_dilemma)
        await db_helper.insert_many_all(
            envs.dilemmas_db_log_schema,
            [
                (
                    random_dilemma[0][0],
                    dilemma_post.id
                )
            ]
        )
        return

    @commands.is_owner()
    @group.command(
        name="add", description=locale_str(
            I18N.t('dilemmas.commands.add.cmd')
        )
    )
    @describe(
        dilemmas_in=I18N.t('dilemmas.commands.add.desc.dilemmas_in')
    )
    async def dilemmas_add(
        self, interaction: discord.Interaction, dilemmas_in: str
    ) -> None:
        await interaction.response.defer()
        await db_helper.insert_many_all(
            envs.dilemmas_db_schema,
            [(str(uuid.uuid4()), dilemmas_in)]
        )
        await interaction.followup.send(
            I18N.t(
                'dilemmas.commands.add.msg_confirm',
                dilemmas_in=dilemmas_in)
        )
        return

    @group.command(
        name="count", description=locale_str(
            I18N.t('dilemmas.commands.count.cmd')
        )
    )
    async def count(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        # Count the dilemmas
        no_of_dilemmas = len(await db_helper.get_output(
            template_info=envs.dilemmas_db_schema,
            select=('id')
        ))
        await interaction.followup.send(
            I18N.t(
                'dilemmas.commands.count.msg_confirm',
                count=no_of_dilemmas,
            ), ephemeral=True
        )
        return


async def setup(bot):
    # Create necessary databases before starting
    cog_name = 'dilemmas'
    logger.info(envs.COG_STARTING.format(cog_name))
    logger.debug('Checking db')

    # Convert json to sqlite db-files if exists
    # Define inserts
    dilemmas_inserts = None

    # Populate the inserts if json file exist
    if file_io.file_exist(envs.dilemmas_file):
        logger.debug('Found old json file')
        dilemmas_inserts = await db_helper.json_to_db_inserts(cog_name)
        logger.debug(f'`dilemmas_inserts` is {dilemmas_inserts}')

    # Prep of DBs should only be done if the db files does not exist
    dilemmas_prep_is_ok = False
    if not file_io.file_exist(envs.dilemmas_db_schema['db_file']):
        logger.debug('Dilemmas db does not exist')
        dilemmas_prep_is_ok = await db_helper.prep_table(
            envs.dilemmas_db_schema, dilemmas_inserts
        )
        await db_helper.prep_table(
            envs.dilemmas_db_log_schema
        )
    else:
        logger.debug('Dilemmas db exist!')
    # Delete old json files if they are not necessary anymore
    if dilemmas_prep_is_ok:
        file_io.remove_file(envs.dilemmas_file)
    if file_io.file_size(envs.dilemmas_log_file):
        file_io.remove_file(envs.dilemmas_log_file)
    logger.debug('Registering cog to bot')
    await bot.add_cog(Dilemmas(bot))
