#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands
import random
import asyncio
from time import sleep
import re
import pendulum
import uuid

from sausage_bot.util import db_helper, config, envs
from sausage_bot.util import discord_commands
from sausage_bot.util.log import log

_tz = 'local'


class Poll(commands.Cog):
    'Make polls'

    def __init__(self, bot):
        self.bot = bot

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_messages=True)
    )
    @commands.group(name='poll')
    async def poll(
        self, ctx, channel: str = None, post_time: str = None,
        lock_time: str = None, *poll_text
    ):
        '''
        Make a poll for voting on something. After posting this command,
        you will be asked to reply with the alternatives

        Parameters
        ------------
        channel: str
            Channel to post poll in
        post_time: str
            What time to post the poll
        lock_time: str
            When will the poll be locked for more answers after posting
        *poll_text
            Input for the poll

        Examples
        ------------
        >>> !poll general 2000 5minutes Who will win the next match?
        Creates a poll in the channel "general" that will post "Who will
        win the next match?" at 20.00 / 8 pm local time which will lock
        for answers after 5 minutes

        >>> !poll polls 1100 2h Who will win the Golden Boot?
        Creates a poll in the channel "polls" that will post "Who will win
        the Golden Boot" at 11.00 / 11 am local time which will lock
        for answers after 2 hours
        '''
        # Check channel
        if channel is None or not discord_commands.channel_exist(channel):
            await ctx.reply(f'Channel {channel} does not exist')
            return
        # Check post_time
        if post_time in [None, 'no']:
            await ctx.reply('No post_time is given')
            return
        try:
            if post_time == 'now':
                dt_post = None
            else:
                log.log_more(f'`post_time`: {post_time}')
                re_search = re.search(
                    r'(\d{2})([,.\-;:_]+)?(\d{2})', post_time
                )
                post_time = post_time.replace(str(re_search.group(2)), '')
                log.log_more(f'`post_time`: {post_time}')
                dt_post = pendulum.from_format(
                    post_time, 'HHmm', 'local'
                )
                log.log_more(f'dt_post: {dt_post}')
        except Exception as e:
            log.log(f'Got error when parsing post_time: {e}')
            return
        # Check lock_time
        if lock_time in [None, 'no']:
            await ctx.reply('No lock_time is given')
            return
        poll_text = ' '.join(_ for _ in poll_text)
        _uuid = str(uuid.uuid4())
        await db_helper.db_insert_many_some(
            envs.db_poll,
            envs.poll_db_polls_schema['name'],
            (
                'uuid', 'channel', 'post_time', 'lock_time',
                'poll_text', 'status_wait_post', 'status_posted',
                'status_wait_lock', 'status_locked'
            ),
            [
                (
                    _uuid, channel, post_time, str(lock_time),
                    str(poll_text), 0, 0, 0, 0
                )
            ]
        )
        random_emojis = [
            '📕', '📺', '📀', '🪪', '🧲', '🧱', '🔧', '🔑', '🔒', '🎹',
            '🎷', '🪗', '🎧', '🎸', '🎤', '🎵', '♣️', '🪅', '⏱', '💵',
            '💎', '🩹', '💊', '🩸', '🪣', '🛌', '🪟', '🎁', '♻️', '🫎'
        ]
        _msg_addalternatives = 'Svar på denne meldingen innen 60 sekunder '\
            'med alternativene du ønsker skal være i pollen\nBruk shift + '\
            'enter mellom hvert sett for å legge til flere om gangen.'
        _msg_addalternatives_msg = await ctx.message.reply(
            _msg_addalternatives
        )
        try:
            _msg_alts_in = await config.bot.wait_for('message', timeout=60.0)
            await _msg_alts_in.add_reaction('✅')
            alts_in = []
            alts_in.extend(
                line for line in str(_msg_alts_in.content).split('\n')
            )
            needed_emojis = random.sample(random_emojis, k=len(alts_in))
            reactions = []
            alts_db = []
            for idx, alt in enumerate(alts_in):
                alts_db.append((_uuid, needed_emojis[idx], alt, 0))
            log.debug(f'`alts_db`: {alts_db}')
            # Add to db
            await db_helper.db_insert_many_some(
                envs.db_poll,
                envs.poll_db_alternatives_schema['name'],
                ('uuid', 'emoji', 'input', 'count'),
                alts_db
            )
            # Post info about when the post is coming
            if dt_post is None:
                post_wait = 0
                post_status_reply = await _msg_alts_in.reply(
                    'Avstemningen postes straks'
                )
            else:
                dt_now = pendulum.now('local')
                post_wait = dt_now.diff(dt_post).in_seconds()
                dt_post_epoch = dt_post.format('x')[0:-3]
                post_status_reply = await _msg_alts_in.reply(
                    f'Avstemningen postes om <t:{dt_post_epoch}:R>'
                )
            log.debug(f'post_wait: {post_wait}')
            desc_out = f'{poll_text}\n'
            for idx, line in enumerate(alts_in):
                # TODO var msg
                desc_out += '\n{} - "{}"'.format(
                    needed_emojis[idx], line
                )
                reactions.append(needed_emojis[idx])
            lock_split = re.match(r'^(\d+)(\w).*', lock_time)
            dt_lock = None
            if lock_split.group(2)[0] not in ['h', 'm']:
                log.debug(f'lock_time unit is `{lock_split.group(2)}`')
                await ctx.reply('lock_time provided, but is not `h` or `m`')
                return
            if dt_post is None:
                dt_post = pendulum.now('local')
            if lock_split.group(2) == "h":
                dt_lock = dt_post.add(
                    hours=int(lock_split.group(1))
                ).in_tz(_tz)
                dt_lock_text = f'{lock_split.group(1)} time'
                if int(lock_split.group(1)) > 1:
                    dt_lock_text += 'r'
            elif lock_split.group(2) == "m":
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
            embed_json = {
                'title': 'Avstemning',
                'description': desc_out,
            }
        except TimeoutError:
            # TODO var msg
            await ctx.reply('Timed out')
            sleep(3)
            await _msg_addalternatives_msg.delete()
            await ctx.message.delete()
            return
        # Post the poll message
        await db_helper.db_update_fields(
            envs.db_poll,
            envs.poll_db_polls_schema['name'],
            ('uuid', _uuid),
            [
                ('status_wait_post', 1)
            ]
        )
        await asyncio.sleep(post_wait)
        post_text = pendulum.now('local').format('DD.MM.YY, HH:mm')
        await post_status_reply.edit(
            content=f"Avstemningen ble postet {post_text}"
        )
        message_text = f'Avstemning blir stengt om <t:{dt_lock_epoch}:R>'
        poll_msg = await discord_commands.post_to_channel(
            channel, content_in=message_text,
            content_embed_in=embed_json
        )
        await db_helper.db_update_fields(
            envs.db_poll,
            envs.poll_db_polls_schema['name'],
            ('uuid', _uuid),
            [
                ('msg_id', poll_msg.id),
                ('status_posted', 1)
            ]
        )
        for reaction in reactions:
            log.debug(f'Adding emoji {reaction}')
            await poll_msg.add_reaction(reaction)
        log.debug('Waiting to lock...')
        await db_helper.db_update_fields(
            envs.db_poll,
            envs.poll_db_polls_schema['name'],
            ('uuid', _uuid),
            [
                ('status_wait_lock', 1)
            ]
        )
        log.log_more(f'dt_post: {dt_post}')
        log.log_more(f'dt_lock: {dt_lock}')
        log.debug(f'pendulum.now() - {pendulum.now()}', color='red')
        lock_diff = (dt_lock - pendulum.now()).in_seconds()
        log.debug(f'`lock_diff` in seconds: {lock_diff}')
        await asyncio.sleep(lock_diff)
        log.debug('Ready to lock!')
        log.debug(f'pendulum.now() - {pendulum.now()}', color='red')
        _guild = discord_commands.get_guild()
        _channels = discord_commands.get_text_channel_list()
        _channel = _guild.get_channel(
            _channels[channel]
        )
        # Get all reactions
        poll_cache = await _channel.fetch_message(poll_msg.id)
        poll_reacts = poll_cache.reactions
        for alts in alts_db:
            for react in poll_reacts:
                if react.emoji in alts:
                    await db_helper.db_update_fields(
                        envs.db_poll,
                        envs.poll_db_alternatives_schema['name'],
                        [
                            ('uuid', _uuid),
                            ('emoji', react.emoji)
                        ],
                        [
                            ('count', int(react.count - 1))
                        ]
                    )
                    break
        log.debug(f'pendulum.now() - {pendulum.now()}', color='red')
        sorted_reacts = await db_helper.get_output(
            envs.db_poll, envs.poll_db_alternatives_schema['name'],
            [
                ('uuid', _uuid)
            ],
            ('input', 'count'),
            [
                ('count', 'DESC')
            ]
        )
        # Remove old poll_msg
        await poll_msg.delete()
        log.debug(f'pendulum.now() - {pendulum.now()}', color='red')
        # Move reaction to the text
        desc_out = f'{poll_text}\n'
        for reaction in sorted_reacts:
            desc_out += f'\n{reaction[0]}: {reaction[1]}'
        embed_json = {
            'title': 'Avstemning',
            'description': desc_out,
            'footer': {
                # TODO var msg
                'text': f'Avstemning ble stengt etter {dt_lock_text}'
            }
        }
        log.debug(f'pendulum.now() - {pendulum.now()}', color='red')
        await discord_commands.post_to_channel(
            channel, content_in='',
            content_embed_in=embed_json
        )
        await db_helper.db_update_fields(
            envs.db_poll,
            envs.poll_db_polls_schema['name'],
            ('uuid', _uuid),
            [
                ('status_locked', 1)
            ]
        )
        log.debug(f'pendulum.now() - {pendulum.now()}', color='red')


async def setup(bot):
    log.log(envs.COG_STARTING.format('poll'))
    log.log_more('Checking db')
    await db_helper.prep_table(
        envs.db_poll, envs.poll_db_polls_schema
    )
    await db_helper.prep_table(
        envs.db_poll, envs.poll_db_alternatives_schema
    )
    log.log_more('Registering cog to bot')
    await bot.add_cog(Poll(bot))


# Maintain active polls
