#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands
import random
import asyncio
import re
import pendulum
import uuid
import discord

from sausage_bot.util import db_helper, envs
from sausage_bot.util import datetime_handling
from sausage_bot.util.log import log

_tz = 'local'


class MakePoll(commands.Cog):
    'Make polls'

    def __init__(self, bot):
        self.bot = bot

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_messages=True)
    )
    @discord.app_commands.command(
        name="poll",
        description='Make a poll for voting on something'
    )
    async def poll(
        self, interaction: discord.Interaction, channel: discord.TextChannel,
        post_time: str, lock_time: str, poll_text: str, alternatives: str
    ):
        '''
        Make a poll for voting on something.

        Parameters
        ------------
        channel: discord.TextChannel
            Channel to post poll in
        post_time: str
            What to post the poll. Accepts time in 0000
        lock_time: str
            Lock poll after x m(inutes) or h(ours)
        poll_text: str
            Input for the poll
        alternatives: str
            Alternatives for the poll, separated by semicolon
        '''
        await interaction.response.defer(ephemeral=True)
        if post_time in [None, 'no', 'now']:
            dt_post = None
        elif re.match(r'^\d{2}([\D]+)?\d{2}$', post_time):
            log.verbose(f'`post_time`: {post_time}')
            re_search = re.search(
                r'(\d{2})([,.\-;:_]+)?(\d{2})', post_time
            )
            post_time = post_time.replace(str(re_search.group(2)), '')
            log.verbose(f'`post_time`: {post_time}')
            dt_post = pendulum.from_format(
                post_time, 'HHmm', 'local'
            )
            log.verbose(f'dt_post: {dt_post} ({type(dt_post)})')
            dt_now = datetime_handling.get_dt()
            dt_post_secs = datetime_handling.get_dt(dt=dt_post)
            if dt_post_secs < dt_now:
                await interaction.followup.send(
                    'Posting time is in the past'
                )
                return
        else:
            await interaction.followup.send(
                f'`post_time` "{post_time}" gives error'
            )
            return
        # Check lock_time
        if lock_time in [None, 'no', 'now']:
            await interaction.followup.send(
                'No lock_time is given', ephemeral=True
            )
            return
        lock_time_regex = r'^(\d+)(\s)?(h|m)$'
        if not re.match(lock_time_regex, lock_time):
            await interaction.followup.send(
                'Error with given `lock_time`', ephemeral=True
            )
            return
        _uuid = str(uuid.uuid4())
        await db_helper.insert_many_some(
            envs.poll_db_polls_schema,
            (
                'uuid', 'channel', 'post_time', 'lock_time',
                'poll_text', 'status_wait_post', 'status_posted',
                'status_wait_lock', 'status_locked'
            ),
            [
                (
                    _uuid, channel.name, post_time, str(lock_time),
                    str(poll_text), 0, 0, 0, 0
                )
            ]
        )
        random_emojis = [
            '📺', '🧱', '🔧', '🔑', '🔒', '🎹', '🎷', '🪗', '🎧',
            '🎸', '🎤', '🎵', '♣️', '🪅', '⏱', '💎', '💊', '🩸',
            '🪣', '🛌', '🪟', '🎁', '♻️', '🫎'
        ]
        try:
            alts_in = []
            alts_in.extend(
                line.strip() for line in str(alternatives).split(';')
            )
            log.verbose(f'Got `alts_in`: {alts_in}')
            needed_emojis = random.sample(random_emojis, k=len(alts_in))
            reactions = []
            alts_db = []
            for idx, alt in enumerate(alts_in):
                alts_db.append((_uuid, needed_emojis[idx], alt, 0))
            log.debug(f'`alts_db`: {alts_db}')
            # Add to db
            await db_helper.insert_many_some(
                envs.poll_db_alternatives_schema,
                ('uuid', 'emoji', 'input', 'count'),
                alts_db
            )
            # Post info about when the post is coming
            if dt_post is None:
                post_wait = 0
                coming_post = await interaction.followup.send(
                    'Avstemningen postes straks'
                )
            else:
                dt_now = pendulum.now('local')
                post_wait = dt_now.diff(dt_post).in_seconds()
                dt_post_epoch = dt_post.format('x')[0:-3]
                coming_post = await interaction.followup.send(
                    f'Avstemningen postes om <t:{dt_post_epoch}:R>',
                    ephemeral=False
                )
            log.debug(f'post_wait: {post_wait}')
            desc_out = f'{poll_text}\n'
            for idx, line in enumerate(alts_in):
                # TODO var msg
                desc_out += '\n{} - *"{}"*'.format(
                    needed_emojis[idx], line
                )
                reactions.append(needed_emojis[idx])
            lock_split = re.match(lock_time_regex, lock_time)
            dt_lock = None
            if dt_post is None:
                dt_post = pendulum.now('local')
            if lock_split.group(3) == "h":
                dt_lock = dt_post.add(
                    hours=int(lock_split.group(1))
                ).in_tz(_tz)
                dt_lock_text = f'{lock_split.group(1)} time'
                if int(lock_split.group(1)) > 1:
                    dt_lock_text += 'r'
            elif lock_split.group(3) == "m":
                dt_lock = dt_post.add(
                    minutes=int(lock_split.group(1))
                ).in_tz(_tz)
                dt_lock_text = f'{lock_split.group(1)} minutt'
                if int(lock_split.group(1)) > 1:
                    dt_lock_text += 'er'
            log.debug(f'dt_lock: {dt_lock}')
            lock_diff = (dt_lock - dt_post).in_seconds()
            log.debug(f'`lock_diff` in seconds: {lock_diff}')
            dt_lock_epoch = dt_lock.format('x')[0:-3]
            log.debug(
                f'Converting `dt_lock` ({dt_lock}) to epoch: {dt_lock_epoch}'
            )
            embed_json = discord.Embed.from_dict(
                {
                    'title': 'Avstemning',
                    'description': desc_out,
                }
            )
        except TimeoutError:
            # TODO var msg
            await interaction.followup.send(
                'Timed out', ephemeral=True
            )
            return
        # Post the poll message
        await db_helper.update_fields(
            template_info=envs.poll_db_polls_schema,
            where=('uuid', _uuid),
            updates=[
                ('status_wait_post', 1)
            ]
        )
        await asyncio.sleep(post_wait)
        post_text = pendulum.now('local').format('DD.MM.YY, HH:mm')
        await coming_post.delete()
        await interaction.followup.send(
            content=f"Avstemningen ble postet {post_text}",
            ephemeral=True
        )
        message_text = f'Avstemning blir stengt om <t:{dt_lock_epoch}:R>'
        poll_msg = await channel.send(
            content=message_text,
            embed=embed_json
        )
        log.debug(f'Got `poll_msg`: {poll_msg}')
        await db_helper.update_fields(
            template_info=envs.poll_db_polls_schema,
            where=('uuid', _uuid),
            updates=[
                ('msg_id', poll_msg.id),
                ('status_posted', 1)
            ]
        )
        for reaction in reactions:
            log.debug(f'Adding emoji {reaction}')
            await poll_msg.add_reaction(reaction)
        log.debug('Waiting to lock...')
        await db_helper.update_fields(
            envs.poll_db_polls_schema,
            ('uuid', _uuid),
            [
                ('status_wait_lock', 1)
            ]
        )
        log.verbose(f'dt_post: {dt_post}')
        log.verbose(f'dt_lock: {dt_lock}')
        lock_diff = (dt_lock - pendulum.now()).in_seconds()
        log.debug(f'`lock_diff` in seconds: {lock_diff}')
        await asyncio.sleep(lock_diff)
        log.debug('Ready to lock!')
        # Get all reactions
        poll_cache = await channel.fetch_message(poll_msg.id)
        poll_reacts = poll_cache.reactions
        for alts in alts_db:
            for react in poll_reacts:
                if react.emoji in alts:
                    await db_helper.update_fields(
                        envs.poll_db_alternatives_schema,
                        [
                            ('uuid', _uuid),
                            ('emoji', react.emoji)
                        ],
                        [
                            ('count', int(react.count - 1))
                        ]
                    )
                    break
        sorted_reacts = await db_helper.get_output(
            template_info=envs.poll_db_alternatives_schema,
            where=[
                ('uuid', _uuid)
            ],
            select=('input', 'count'),
            order_by=[
                ('count', 'DESC')
            ]
        )
        # Remove old poll_msg
        await poll_msg.delete()
        # Move reaction to the text
        desc_out = f'{poll_text}\n'
        for reaction in sorted_reacts:
            desc_out += f'\n{reaction[0]}: {reaction[1]}'
        embed_json = discord.Embed.from_dict(
            {
                'title': 'Avstemning',
                'description': desc_out,
                'footer': {
                    # TODO var msg
                    'text': f'Avstemning ble stengt etter {dt_lock_text}'
                }
            }
        )
        await channel.send(
            embed=embed_json
        )
        await db_helper.update_fields(
            envs.poll_db_polls_schema,
            ('uuid', _uuid),
            [
                ('status_locked', 1)
            ]
        )


async def setup(bot):
    cog_name = 'poll'
    log.log(envs.COG_STARTING.format(cog_name))
    log.verbose('Checking db')
    await db_helper.prep_table(
        envs.poll_db_polls_schema
    )
    await db_helper.prep_table(
        envs.poll_db_alternatives_schema
    )
    log.verbose('Registering cog to bot')
    await bot.add_cog(MakePoll(bot))
