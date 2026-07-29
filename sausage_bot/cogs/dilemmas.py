#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"dilemmas: Post a random dilemma"

import discord
from discord.ext import commands
from discord.app_commands import locale_str, describe
import uuid

from sausage_bot.util import config, envs, db_helper
from sausage_bot.util.i18n import I18N

logger = config.logger


class Dilemmas(commands.Cog):
    "Post a random dilemma"

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    group = discord.app_commands.Group(name="dilemmas", description="Dilemmas")

    @group.command(
        name="post", description=locale_str(I18N.t("dilemmas.commands.post.cmd"))
    )
    async def dilemmas(self, interaction: discord.Interaction) -> None:
        def prettify(dilemmas_in):
            """
            Enclosing `dilemmas_in` in quotation marks
            #autodoc skip#
            """
            out = "```{}```".format(dilemmas_in)
            return out

        async def get_random_dilemma():
            return await db_helper.get_random_left_exclude_output(
                envs.dilemmas_db_schema,
                envs.dilemmas_db_log_schema,
                "id",
                ("id", "dilemmas_text"),
                guild_id=interaction.guild.id,
            )

        await interaction.response.defer()
        # Check that there are dilemmas
        no_of_dilemmas = await db_helper.get_output(
            template_info=envs.dilemmas_db_schema,
            select=("id"),
            guild_id=interaction.guild.id,
        )
        if len(no_of_dilemmas) <= 0:
            await interaction.followup.send(
                I18N.t("dilemmas.commands.post.no_dilemmas_in_db"),
                envs.DILEMMAS_NO_DILEMMAS_IN_DB,
                ephemeral=True,
            )
            return
        # Get a random dilemma
        random_dilemma = await get_random_dilemma()
        if len(random_dilemma) == 0:
            await db_helper.empty_table(
                envs.dilemmas_db_log_schema, guild_id=interaction.guild.id
            )
            random_dilemma = await get_random_dilemma()
        # Post dilemma
        _dilemma = prettify(random_dilemma[0][1])
        dilemma_post = await interaction.followup.send(_dilemma)
        await db_helper.insert_many_all(
            envs.dilemmas_db_log_schema,
            [(random_dilemma[0][0], dilemma_post.id)],
            guild_id=interaction.guild.id,
        )
        return

    @commands.is_owner()
    @group.command(
        name="add", description=locale_str(I18N.t("dilemmas.commands.add.cmd"))
    )
    @describe(dilemmas_in=I18N.t("dilemmas.commands.add.desc.dilemmas_in"))
    async def dilemmas_add(
        self, interaction: discord.Interaction, dilemmas_in: str
    ) -> None:
        await interaction.response.defer()
        await db_helper.insert_many_all(
            envs.dilemmas_db_schema,
            [(str(uuid.uuid4()), dilemmas_in)],
            guild_id=interaction.guild.id,
        )
        await interaction.followup.send(
            I18N.t("dilemmas.commands.add.msg_confirm", dilemmas_in=dilemmas_in)
        )
        return

    @group.command(
        name="count", description=locale_str(I18N.t("dilemmas.commands.count.cmd"))
    )
    async def count(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        # Count the dilemmas
        no_of_dilemmas = len(
            await db_helper.get_output(
                template_info=envs.dilemmas_db_schema,
                select=("id"),
                guild_id=interaction.guild.id,
            )
        )
        await interaction.followup.send(
            I18N.t(
                "dilemmas.commands.count.msg_confirm",
                count=no_of_dilemmas,
            ),
            ephemeral=True,
        )
        return


async def setup(bot):
    cog_name = "dilemmas"
    logger.info(envs.COG_STARTING.format(cog_name))
    logger.debug("Checking db")

    approved_guilds = await db_helper.get_output(
        envs.guilds_db_schema, where=("status", "approved")
    )
    for guild_row in approved_guilds:
        guild = config.bot.get_guild(int(guild_row["guild_id"]))
        if guild is None:
            continue
        await db_helper.prep_table(envs.dilemmas_db_schema, guild_id=guild.id)
        await db_helper.prep_table(envs.dilemmas_db_log_schema, guild_id=guild.id)

    logger.debug("Registering cog to bot")
    await bot.add_cog(Dilemmas(bot))
    logger.info(envs.COG_STARTED.format(cog_name))
