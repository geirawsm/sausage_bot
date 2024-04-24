#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands
import discord
import uuid

from sausage_bot.util import envs, db_helper, file_io
from sausage_bot.util.log import log


class Dilemmas(commands.Cog):
    'Post a random dilemma'

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    group = discord.app_commands.Group(
        name="dilemmas", description='Dilemmas'
    )

    @group.command(
        name="post", description="Post a random dilemma"
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

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(administrator=True)
    )
    @group.command(
        name="add", description="Add a dilemma"
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
            'Added the following dilemma: {}'.format(dilemmas_in)
        )
        return

    @group.command(
        name="count", description="Count the numbers of dilemmas"
    )
    async def count(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        # Count the dilemmas
        no_of_dilemmas = len(await db_helper.get_output(
            template_info=envs.dilemmas_db_schema,
            select=('id')
        ))
        await interaction.followup.send(
            '{}{}'.format(
                envs.DILEMMAS_COUNT.format(no_of_dilemmas),
                's' if no_of_dilemmas > 1 else ''
            ), ephemeral=True
        )
        return


async def setup(bot):
    cog_name = 'dilemmas'
    log.log(envs.COG_STARTING.format(cog_name))
    log.verbose('Checking db')
    # Convert json to sqlite db-files if exists
    dilemmas_inserts = None
    if file_io.file_size(envs.dilemmas_file):
        log.verbose('Found old json file')
        dilemmas_inserts = db_helper.json_to_db_inserts(cog_name)
    dilemmas_prep_is_ok = await db_helper.prep_table(
        envs.dilemmas_db_schema, dilemmas_inserts
    )
    await db_helper.prep_table(
        envs.dilemmas_db_log_schema
    )
    # Delete old json files if they exist
    if dilemmas_prep_is_ok:
        file_io.remove_file(envs.dilemmas_file)
    if file_io.file_size(envs.dilemmas_log_file):
        file_io.remove_file(envs.dilemmas_log_file)
    log.verbose('Registering cog to bot')
    await bot.add_cog(Dilemmas(bot))
