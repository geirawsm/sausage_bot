#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands
import uuid

from sausage_bot.util import config, envs, db_helper
from sausage_bot.util.log import log


class Dilemmas(commands.Cog):
    'Post a random dilemma'

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='dilemmas')
    async def dilemmas(self, ctx):
        f'''
        Post a random dilemma:
        `{config.PREFIX}dilemmas`
        '''

        def prettify(dilemmas_in):
            'Enclosing `dilemmas_in` in quotation marks'
            out = '```{}```'.format(dilemmas_in)
            return out

        async def get_random_dilemma():
            return await db_helper.get_random_left_exclude_output(
                envs.dilemmas_db_schema,
                envs.dilemmas_db_log_schema,
                'id',
                ('id', 'dilemmas_text')
            )

        # Get a random dilemma
        if ctx.invoked_subcommand is None:
            random_dilemma = await get_random_dilemma()
            if len(random_dilemma) == 0:
                await db_helper.empty_table(envs.dilemmas_db_log_schema)
                random_dilemma = await get_random_dilemma()
            # Post dilemma
            _dilemma = prettify(random_dilemma[0][1])
            dilemma_post = await ctx.send(_dilemma)
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
    @dilemmas.group(name='add')
    async def dilemmas_add(self, ctx, *dilemmas_in):
        'Add a dilemma: `!dilemmas add [dilemmas_in]`'
        dilemmas_in = ' '.join(_ for _ in dilemmas_in)
        await db_helper.insert_many_all(
            envs.dilemmas_db_schema,
            [(str(uuid.uuid4()), dilemmas_in)]
        )
        await ctx.message.reply(
            'Added the following dilemma: {}'.format(dilemmas_in)
        )
        return


async def setup(bot):
    log.log(envs.COG_STARTING.format('dilemmas'))
    log.log_more('Checking db')
    await db_helper.prep_table(
        envs.dilemmas_db_schema
    )
    await db_helper.prep_table(
        envs.dilemmas_db_log_schema
    )
    log.log_more('Registering cog to bot')
    await bot.add_cog(Dilemmas(bot))
