#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands
import discord
from tabulate import tabulate
from asyncio import TimeoutError
from time import sleep
import re

from sausage_bot.util import config, envs, file_io, discord_commands, db_helper
from sausage_bot.util.log import log


async def get_message_obj(
        msg_id: str = None, channel: str = None
) -> dict:
    '''
    Get a message object

    Parameters
    ------------
    msg_id: int/str
        The message ID to look for, or name of the saved message in
        settings file
    channel: str
        Channel to get message from (default: None)
    '''

    _guild = discord_commands.get_guild()
    _channels = discord_commands.get_text_channel_list()
    _channel = _guild.get_channel(
        _channels[channel]
    )
    try:
        msg_out = await _channel.fetch_message(msg_id)
    except discord.errors.NotFound:
        msg_out = None
    return msg_out


async def get_msg_id_and_name(msg_id_or_name):
    '''
    Get msg id, channel and message name from database
    based on msg id or msg name
    '''
    log.debug(f'Got `msg_id_or_name`: {msg_id_or_name}')
    if re.match(r'^[0-9]+$', msg_id_or_name):
        log.verbose('Got numeric input')
        where_in = 'msg_id'
    else:
        log.verbose('Got alphanumeric input')
        where_in = 'name'
    db_message = await db_helper.get_output(
        template_info=envs.roles_db_msgs_schema,
        where=[
            (where_in, msg_id_or_name)
        ],
        select=('msg_id', 'channel', 'name')
    )
    log.verbose(f'db_message: {db_message}', color='yellow')
    return {
        'id': db_message[0][0],
        'channel': db_message[0][1],
        'name': db_message[0][2]
    }


async def sync_reaction_message_from_settings(
        msg_id_or_name, sorting: list = None
):
    # Assert that the reaction message exist on discord
    msg_info = await get_msg_id_and_name(msg_id_or_name)
    msg_id = msg_info['id']
    msg_channel = msg_info['channel']
    log.verbose(f'`msg_info` is {msg_info}')
    msg_obj = await get_message_obj(
        msg_id=msg_id,
        channel=msg_channel
    )
    log.verbose(f'`msg_obj` is {msg_obj}')
    if msg_obj is None:
        # If the message has been deleted, it needs to be recreated,
        # and msg_id in databases must be updated
        log.verbose('Creating av new message')
        db_message = await db_helper.get_output(
            template_info=envs.roles_db_msgs_schema,
            where=[
                ('msg_id', msg_id)
            ]
        )
        # Make a placeholder message
        msg_obj = await discord_commands.post_to_channel(
            msg_channel, content_in=str(db_message[0][3])
        )
        # Update databases with correct message ID
        log.verbose(
            'Replace old id ({}) with new ({})'.format(
                str(msg_id)[-5],
                str(msg_obj.id)[-5]
            )
        )
        msg_id = msg_obj.id
        await db_helper.update_fields(
            envs.roles_db_msgs_schema,
            updates=[
                ('msg_id', msg_id)
            ],
            where=('msg_id', msg_info['id'])
        )
        await db_helper.update_fields(
            envs.roles_db_roles_schema,
            updates=[
                ('msg_id', msg_id)
            ],
            where=('msg_id', msg_info['id'])
        )
        log.debug(f'`msg_obj` is {msg_obj}')

    db_message = await db_helper.get_output(
        template_info=envs.roles_db_msgs_schema,
        where=[
            ('msg_id', msg_id)
        ]
    )
    log.verbose(f'db_message: {db_message}')
    db_reactions = await db_helper.get_combined_output(
        envs.roles_db_msgs_schema,
        envs.roles_db_roles_schema,
        key='msg_id',
        select=[
            'role_name',
            'emoji'
        ],
        where=[
            ('A.msg_id', msg_id)
        ],
        order_by=sorting
    )
    log.verbose(f'db_reactions: {db_reactions}', color='yellow')
    # Recreate the embed
    _roles = discord_commands.get_roles()
    new_embed_desc = ''
    new_embed_content = ''
    await msg_obj.clear_reactions()
    _errors_out = ''
    removals = []
    for reaction in db_reactions:
        try:
            await msg_obj.add_reaction(reaction[1])
        except Exception as e:
            log.debug(f'Could not add reaction to message: {e}')
            if len(_errors_out) > 0:
                _errors_out += '\n'
            _errors_out += 'Could not add reaction {} to message'.format(
                reaction[1]
            )
            removals.append(('emoji', reaction[1]))
            continue
        new_embed_content = db_message[0][3]
        if len(new_embed_desc) > 0:
            new_embed_desc += '\n'
        if reaction[0].lower() in _roles:
            new_embed_desc += '{} <@&{}>'.format(
                reaction[1], _roles[reaction[0].lower()]['id']
            )
        else:
            log.log('Could not find `{}` in roles'.format(
                reaction[0]
            ))
            if len(_errors_out) > 0:
                _errors_out += '\n'
            _errors_out += 'Could not find role {}'.format(
                reaction[0]
            )
            removals.append(('role_name', reaction[0]))
            continue
    embed_json = {
        'description': new_embed_desc,
        'content': new_embed_content
    }
    # Edit discord message if it exist
    log.debug(f'`db_message` is {db_message}')
    await msg_obj.edit(
        content=db_message[0][3],
        embed=discord.Embed.from_dict(embed_json)
    )
    # Remove roles/reactions with errors (if needed)
    if len(removals) > 0:
        log.log('Cleaning removals from db...')
        await db_helper.del_row_by_OR_filters(
            template_info=envs.roles_db_roles_schema,
            where=removals
        )
    return _errors_out


def paginate_tabulate(tabulated):
    # Test that this works as intended
    log.debug(f'Length of `tabulated` is {len(tabulated)}')
    paginated = []
    temp_out = ''
    if len(tabulated) >= 1800:
        tabulated_split = tabulated.splitlines(keepends=True)
        temp_out += tabulated_split[0]
        temp_out += tabulated_split[1]
        for line in tabulated_split[2:]:
            if len(temp_out) + len(line) > 1800:
                log.debug('Hit 1800 mark')
                paginated.append(temp_out)
                temp_out = ''
                temp_out += tabulated_split[0]
                temp_out += tabulated_split[1]
                temp_out += line
            else:
                temp_out += line
        paginated.append(temp_out)
    else:
        paginated.append(tabulated)
    return paginated


class Autoroles(commands.Cog):
    'Manage roles and settings'

    def __init__(self, bot):
        self.bot = bot

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @commands.group(name='roles')
    async def guildroles(self, ctx):
        '''
        Control roles on the server
        If no subcommand is given, list all roles
        '''
        if ctx.invoked_subcommand is None:
            out = {
                'name': [],
                'members': [],
                'bot_managed': []
            }
            for role in discord_commands.get_guild().roles:
                if role.name == '@everyone':
                    continue
                out['name'].append(role.name)
                out['members'].append(len(role.members))
                _bot_rolle = role.is_bot_managed()
                if _bot_rolle:
                    _bot_rolle = 'Ja'
                else:
                    _bot_rolle = 'Nei'
                out['bot_managed'].append(_bot_rolle)
            _tab = '```{}```'.format(
                tabulate(
                    # TODO i18n?
                    out, headers=['Rolle', 'Ant.medl.', 'Bot-rolle'],
                    numalign='center'
                )
            )
            await ctx.reply(_tab)
            return
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @guildroles.group(name='info', aliases=['i'])
    async def role_info(self, ctx, role_name: str = None):
        '''
        Get info about a specific role (`role_name`)

        Parameters
        ------------
        role_name: str
            The role name to get info about (default: None)
        '''

        _guild = discord_commands.get_guild()
        if role_name is not None and len(role_name) > 0:
            _roles = _guild.roles
            for _role in _roles:
                log.verbose(f'Sjekker `_role`: {_role}')
                if str(_role.name).lower() == role_name.lower():
                    log.debug(f'Fant `{role_name}`')
                    embed = discord.Embed(color=_role.color)
                    embed.set_thumbnail(url=_role.icon)
                    embed.add_field(name="ID", value=_role.id, inline=True)
                    embed.add_field(
                        name="Farge", value=_role.color, inline=True
                    )
                    if _role.is_bot_managed():
                        embed.add_field(
                            name="Autohåndteres",
                            value='Ja, av {}'.format(
                                _guild.get_member(
                                    _role.tags.integration_id
                                ).name
                            ),
                            inline=True
                        )
                    elif _role.is_integration():
                        embed.add_field(
                            name="Autohåndteres",
                            value='Ja, av {}'.format(
                                _guild.get_member(_role.tags.bot_id).name
                            ),
                            inline=True
                        )
                    else:
                        embed.add_field(
                            name="Autohåndteres", value="Nei", inline=True
                        )
                    if _role.hoist:
                        embed.add_field(
                            name="Spesielt synlig",
                            value='Ja',
                            inline=True
                        )
                    else:
                        embed.add_field(
                            name="Spesielt synlig",
                            value='Nei',
                            inline=True
                        )
                    embed.add_field(
                        name="Brukere med rollen",
                        value=len(_role.members), inline=True
                    )
                    permissions = ", ".join(
                        [permission for permission, value in
                            iter(_role.permissions) if value is True]
                    )
                    if permissions:
                        embed.add_field(
                            name="Tillatelser", value=permissions,
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="Tillatelser", value='Ingen',
                            inline=False
                        )
                    await ctx.reply(embed=embed)
                    return
            # TODO var msg
            _var_msg = f'Fant ikke rollen `{role_name}`'
            log.debug(_var_msg)
            await ctx.reply(_var_msg)
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @guildroles.group(name='list', aliases=['l'])
    async def role_list(self, ctx):
        'List roles, emojis or reactions'
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @role_list.group(name='roles', aliases=['r'])
    async def list_roles(self, ctx, sort: str = None):
        '''
        List roles

        Parameters
        ------------
        sort: str
            Sort roles alphabetically
        '''
        _guild = discord_commands.get_guild()
        tabulate_dict = {
            'name': [],
            'id': [],
            'members': [],
            'bot_managed': []
        }
        if sort is not None:
            _roles = tuple(sorted(
                _guild.roles, key=lambda role: role.name.lower()
            ))
        else:
            _roles = _guild.roles
        for role in _roles:
            tabulate_dict['name'].append(role.name)
            tabulate_dict['id'].append(role.id)
            tabulate_dict['members'].append(len(role.members))
            if role.managed:
                # TODO i18n?
                tabulate_dict['bot_managed'].append('Ja')
            elif not role.managed:
                # TODO i18n?
                tabulate_dict['bot_managed'].append('Nei')
        tabulated = tabulate(
            # TODO var msg i18n?
            tabulate_dict, headers=[
                'Navn', 'ID', 'Medl.', 'Bot-rolle'
            ]
        )
        paginated = paginate_tabulate(tabulated)
        for page in paginated:
            log.verbose(f'`{page}`')
            await ctx.reply(f'```{page}```')
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @role_list.group(name='emojis', aliases=['e'])
    async def list_emojis(self, ctx, sort: str = None):
        '''
        List server emojis

        Parameters
        ------------
        sort: str
            Sort emojis alphabetically
        '''
        _guild = discord_commands.get_guild()
        tabulate_dict = {
            'name': [],
            'id': [],
            'animated': [],
            'managed': []
        }
        if sort is not None:
            _emojis = tuple(sorted(
                _guild.emojis, key=lambda emoji: emoji.name.lower()
            ))
        else:
            _emojis = _guild.emojis
        for emoji in _emojis:
            tabulate_dict['name'].append(emoji.name)
            tabulate_dict['id'].append(emoji.id)
            if emoji.animated:
                tabulate_dict['animated'].append('Ja')
            else:
                tabulate_dict['animated'].append('Nei')
            if emoji.managed:
                tabulate_dict['managed'].append('Ja')
            else:
                tabulate_dict['managed'].append('Nei')
        tabulated = tabulate(
            # TODO var msg i18n?
            tabulate_dict, headers=[
                'Navn', 'ID', 'Animert?', 'Auto-håndtert?'
            ]
        )
        paginated = paginate_tabulate(tabulated)
        for page in paginated:
            await ctx.reply(f'```{page}```')
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @role_list.group(name='reactions', aliases=['reac'])
    async def list_reactions(self, ctx, reaction_msg_name: str = None):
        '''
        List reactions

        If reaction_msg_name is not provided, list all messages

        Parameters
        ------------
        reaction_msg_name: str
            The names of the reaction message to list (default: None)
        '''
        if reaction_msg_name:
            db_reactions = await db_helper.get_combined_output(
                envs.roles_db_msgs_schema,
                envs.roles_db_roles_schema,
                key='msg_id',
                select=[
                    'name',
                    'content',
                    'channel',
                    'A.msg_id',
                    'role_name',
                    'emoji'
                ],
                where=[
                    ('A.name', reaction_msg_name)
                ]
            )
            if len(db_reactions) <= 0:
                await ctx.reply(f'Did not find `{reaction_msg_name}`')
                return
            tabulate_dict = {
                'role': [],
                'emoji': []
            }
            for reaction in db_reactions:
                tabulate_dict['role'].append(reaction[4])
                tabulate_dict['emoji'].append(reaction[5])
            # TODO i18n?
            await ctx.reply(
                'Navn: `{}`\nKanal: `{}`\nMeldings-ID: `{}`\n'
                'Tekst: `{}`\n\n```{}```'.format(
                    db_reactions[0][0],
                    db_reactions[0][1],
                    db_reactions[0][2],
                    db_reactions[0][3],
                    tabulate(tabulate_dict, headers=['Rolle', 'Emoji'])
                )
            )
        elif not reaction_msg_name:
            tabulate_dict = {
                'name': [],
                'channel': [],
                'order': [],
                'id': [],
                'content': [],
                'reactions': []
            }
            sorted_reacts = await db_helper.get_combined_output(
                template_info_1=envs.roles_db_msgs_schema,
                template_info_2=envs.roles_db_roles_schema,
                select=[
                    'name',
                    'channel',
                    'msg_order',
                    'A.msg_id',
                    'content'
                ],
                key='msg_id',
                group_by='A.msg_id',
                order_by=[
                    ('channel', 'DESC'),
                    ('msg_order', 'ASC')
                ]
            )
            if sorted_reacts is None:
                await ctx.reply('Ingen meldinger i databasen')
                return
            for _sort in sorted_reacts:
                tabulate_dict['name'].append(_sort[0])
                tabulate_dict['channel'].append(_sort[1])
                tabulate_dict['order'].append(_sort[2])
                tabulate_dict['id'].append(_sort[3])
                tabulate_dict['content'].append(
                    '{}…'.format(
                        str(_sort[4])[0:20]
                    )
                )
                tabulate_dict['reactions'].append(_sort[5])
            await ctx.reply(
                '```{}```'.format(
                    tabulate(
                        # TODO i18n?
                        tabulate_dict, headers=[
                            'Navn', 'Kanal', 'Rekkefølge', 'ID', 'Tekst',
                            'Ant. reaksj.'
                        ]
                    )
                )
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @guildroles.group(name='manage', aliases=['m'])
    async def role_manage(self, ctx):
        'Manage specific roles on the server'
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @role_manage.group(name='add', aliases=['a'])
    async def add_role(
        self, ctx, role_name: str, permissions: str,
        color: str, hoist: str, mentionable: str
    ):
        '''
        Add role to the server

        Parameters
        ------------
        role_name: str
            The names of the role to add (default: None)
        permissions: str
            Permissions to give this role
        color: str
            Set color for the role
        hoist: str (yes/no)
            Set if the role should be mentionable or not
        mentionable: str (yes/no)
            Set if the role should be mentionable or not
        '''
        if role_name is None:
            # todo var msg
            log.log('Role has no name')
            await ctx.message.reply('Role has no name')
            return
        # TODO i18n
        if str(permissions).lower() in ['ingen', 'none', 'no', '0']:
            permissions = discord.Permissions(permissions=0)
        if color.lower() in ['ingen', 'none', 'no']:
            color = discord.Color.random()
        else:
            color = discord.Color.from_str(color)
        _yes = ['yes', 'y']
        _no = ['no', 'n']
        if hoist in _yes:
            hoist = True
        elif hoist in _no:
            hoist = False
        else:
            await ctx.message.reply(
                'Parameter `hoist` needs a `yes` or a `no`'
            )
            return
        if mentionable in _yes:
            mentionable = True
        elif mentionable in _no:
            mentionable = False
        else:
            await ctx.message.reply(
                'Parameter `mentionable` needs a `yes` or a `no`'
            )
            return
        guild = discord_commands.get_guild()
        await guild.create_role(
            name=role_name,
            permissions=permissions,
            color=color,
            hoist=hoist,
            mentionable=mentionable,
        )
        await ctx.message.reply('Role is created')
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @role_manage.group(name='remove', aliases=['delete', 'r', 'd'])
    async def remove_role(self, ctx, role_name):
        '''
        Remove a role from the server

        Parameters
        ------------
        role_name: str
            The name of the role to remove (default: None)
        '''

        if role_name is None:
            # todo var msg
            log.log('Give a role name or ID')
            await ctx.message.reply('Give a role name or ID')
            return
        _guild = discord_commands.get_guild()
        _roles = _guild.roles
        for _role in _roles:
            log.debug(f'Sjekker `_role`: {_role}')
            if _role.name == role_name:
                log.debug(f'Fant {role_name}, sletter...')
                await _guild.get_role(int(_role.id)).delete()
                await ctx.message.reply('Role has been deleted')
                return
        log.log(f'Fant ikke `{role_name}`')
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @role_manage.group(name='edit', aliases=['e'])
    async def edit_role(
        self, ctx, role_name: str = None,
        setting: str = None,
        value: str = None
    ):
        '''
        Edit a role on the server

        Parameters
        ------------
        role_name: str
            The name of the role to edit (default: None)
        setting: str
            The setting to change (default: None)
            Available settings:
                name (str)
                color (hex)
                hoist (Bool)
                mentionable (Bool)
        value: str
            The new value (default: None)
        '''
        if role_name is not None and len(role_name) > 0:
            _guild = discord_commands.get_guild()
            _roles = _guild.roles
            _role_edit = None
            for _role in _roles:
                log.debug(f'role_name.lower(): {role_name.lower()}')
                log.debug(f'_role: {_role}')
                if role_name.lower() == str(_role).lower():
                    _role_edit = _guild.get_role(_role.id)
                    continue
            if _role_edit is None:
                # TODO var msg
                log.debug(f'role_name `{role_name}` is not found')
                return
            if setting == 'name':
                await _role_edit.edit(name=value)
                # TODO var msg
                log.debug('Changed name')
                await ctx.reply(
                    f'Changed name on role `{role_name}` -> `{value}`'
                )
                return
            elif setting == 'color':
                await _role_edit.edit(color=discord.Colour.from_str(value))
                # TODO var msg
                log.debug('Changed color')
                await ctx.reply(
                    f'Changed color on role `{role_name}` to `{value}`'
                )
                return
            elif setting == 'hoist':
                await _role_edit.edit(hoist=value)
                # TODO var msg
                log.debug('Changed hoist')
                await ctx.reply(
                    f'Set hoist on role `{role_name}` to `{value}`'
                )
                return
            elif setting == 'mentionable':
                await _role_edit.edit(mentionable=value)
                # TODO var msg
                log.debug('Changed hoist')
                await ctx.reply(
                    f'Set hoist on role `{role_name}` to `{value}`'
                )
                return
            else:
                # TODO var msg
                log.debug('`setting` not recognized')
                await ctx.reply(f'setting `{value}` not recognized')
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @guildroles.group(name='user')
    async def user_role(self, ctx):
        '''
        Manage a user\'s roles
        '''
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @user_role.group(name='add', aliases=['a'])
    async def user_add_role(self, ctx, user_name: str, *role_names):
        '''
        Add role(s) to a user

        Parameters
        ------------
        user_name: str
            Username to be given role(s)
        *role_names: str
            The names of the role to add (default: None)
        '''
        if role_names is None or user_name is None:
            # todo var msg
            var_msg = '`Role names` and `User name` is mandatory'
            log.log(var_msg)
            await ctx.message.reply(var_msg)
            return
        _guild = discord_commands.get_guild()
        _roles = _guild.roles
        log.debug(f'_roles: {_roles}')
        _var_roles = []
        _var_roles.extend([str(_role.name).lower() for _role in _roles])
        ok_roles = []
        similar_roles = []
        not_found_roles = []
        log.debug(f'_var_roles: {_var_roles}')
        for chosen_role in role_names:
            if chosen_role.lower() in _var_roles:
                ok_roles.append(chosen_role)
                log.debug('Found role')
            else:
                # Check for typos
                typo_check = file_io.check_similarity(
                    chosen_role, _var_roles, ratio_floor=0.8
                )
                if typo_check is False or typo_check is None:
                    not_found_roles.append(chosen_role)
                else:
                    not_found_roles.append(chosen_role)
                    similar_roles.append(typo_check)
        log.debug(f'ok_roles: {ok_roles}')
        log.debug(f'not_found_roles: {not_found_roles}')
        log.debug(f'similar_roles: {similar_roles}')
        out_msg = ''
        if len(ok_roles) > 0:
            # TODO var msg
            out_msg += 'Legger til {}'.format(', '.join(
                ['`{}`'.format(_role) for _role in ok_roles])
            )
            for _role in ok_roles:
                for __role in ctx.guild.roles:
                    if __role.name.lower() == _role.lower():
                        await _guild.get_member_named(user_name).add_roles(
                            __role
                        )
                        break
        if len(not_found_roles) > 0:
            # TODO var msg
            out_msg += ', men disse finnes ikke: {}'.format(', '.join(
                ['`{}`'.format(_role) for _role in not_found_roles])
            )
        if len(similar_roles) > 0:
            # TODO var msg
            out_msg += '\nMente du egentlig {}?'.format(', '.join(
                ['`{}`'.format(_role) for _role in similar_roles]
            ))
        await ctx.message.reply(out_msg)
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @user_role.group(name='remove', aliases=['delete', 'r', 'd'])
    async def user_remove_role(self, ctx, user_name, *role_names):
        '''
        Remove roles from a user

        Parameters
        ------------
        user_name: str
            Username to remove role(s) from
        *role_names: str
            The names of the role to remove (default: None)
        '''
        if role_names is None or user_name is None:
            # todo var msg
            var_msg = '`Role names` and `User name` is mandatory'
            log.log(var_msg)
            await ctx.message.reply(var_msg)
            return
        _guild = discord_commands.get_guild()
        _member = _guild.get_member_named(user_name)
        if _member is None:
            log.log(f'Could not find user {user_name}')
            return
        for _role in role_names:
            for __role in _member.roles:
                if __role.name.lower() == _role.lower():
                    await _member.remove_roles(__role)
        # TODO var msg
        var_msg = 'Fjernet `{}` fra følgende roller: {}'.format(
            user_name, ', '.join(role_names)
        )
        await ctx.message.reply(var_msg)
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @guildroles.group(name='reaction', aliases=['reac'])
    async def role_reaction(self, ctx):
        'Manage reaction roles and messages on the server'
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @role_reaction.group(name='add', aliases=['a'])
    async def add_reaction_item(self, ctx):
        '''
        Add a reaction message or a role to existing message
        '''
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @add_reaction_item.group(name='message', aliases=['msg', 'm'])
    async def add_reaction_message(
        self, ctx, msg_name: str = None, message_text: str = '',
        channel: str = None, order: int = None
    ):
        '''
        Add a reaction message

        Parameters
        ------------
        msg_name: str
            Name of the message for the reaction roles (default: None)
        message_text: str
            The text for the message (default: '')
        channel: str
            Channel to post reaction message to. If not specified, it will
            use the channel in settings
        order: int
            Set order for the message in the channel
        '''
        if channel is None:
            channel = config.ROLE_CHANNEL
        msg_db = await db_helper.get_output(
            envs.roles_db_msgs_schema,
            where=[
                ('name', msg_name)
            ],
            select=('name')
        )
        if len(msg_db) == 1:
            # TODO var msg
            await ctx.reply(
                f'Reaction message `{msg_name}` is already registered...'
            )
            return
        # TODO var msg
        _msg_addroles = 'Svar på denne meldingen innen 60 sekunder med '\
            'navnet på en rolle og navnet på en emoji:\n`rollenavn med '\
            'mellomrom;emojinavn`\nBruk shift + enter mellom hvert sett '\
            'for å legge til flere om gangen.'
        _msg_addroles_msg = await ctx.message.reply(_msg_addroles)
        _guild = discord_commands.get_guild()
        try:
            _msg = await config.bot.wait_for('message', timeout=60.0)
            desc_out = ''
            errors = []
            reactions = []
            _roles = _guild.roles
            _roles_list = []
            _roles_list.extend([role.name.lower() for role in _roles])
            log.verbose(f'_roles_list: {_roles_list}')
            _emojis = _guild.emojis
            _emojis_list = []
            _emojis_list.extend([emoji.name.lower() for emoji in _emojis])
            log.verbose(f'_emojis_list: {_emojis_list}')
            content_split = []
            content_split.extend(
                line for line in str(_msg.content).split('\n')
            )
            for line in content_split:
                role, emoji = line.strip().split(';')
                # Use this for reporting non-existing roles
                if role.lower() not in _roles_list:
                    log.debug(f'Could not find role `{role}`')
                    errors.append(f'{role} does not exist')
                    continue
                else:
                    for _role in _roles:
                        if role == _role.name:
                            _role_id = _role.id
                            break
                if len(desc_out) > 0:
                    desc_out += ''
                desc_out += '{} <@&{}>'.format(
                    emoji, _role_id
                )
                reactions.append((role, emoji))
            embed_json = {
                'description': desc_out
            }
        except TimeoutError:
            # TODO var msg
            await ctx.reply('Timed out')
            sleep(3)
            await _msg_addroles_msg.delete()
            await ctx.message.delete()
            return
        # Inform about role/emoji errors
        if errors:
            await ctx.reply(errors)
        # Post the reaction message
        reaction_msg = await discord_commands.post_to_channel(
            channel, content_in=message_text,
            content_embed_in=embed_json
        )
        # Save to DB
        reactions_in = []
        for reac in reactions:
            reactions_in.append(
                (reaction_msg.id, reac[0], reac[1])
            )
        # Add to messages DB
        await db_helper.insert_many_all(
            envs.roles_db_msgs_schema,
            inserts=[
                (
                    reaction_msg.id, channel, msg_name, message_text,
                    embed_json['description'], order
                )
            ]
        )
        await db_helper.insert_many_all(
            envs.roles_db_roles_schema,
            inserts=reactions_in
        )
        # TODO Gå over fra posting til reordering?
        for reaction in reactions_in:
            log.debug(f'Adding emoji {reaction[2]}')
            await reaction_msg.add_reaction(reaction[2])
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @add_reaction_item.group(name='role', aliases=['r'])
    async def add_reaction_role(
        self, ctx, msg_id_or_name=None, *role_emoji_combo
    ):
        '''
        Add a reaction role to an existing message

        Parameters
        ------------
        msg_id_or_name: int/str
            The message ID to look for, or name of the saved message
        role_emoji_combo: str
            Name of a role and an actual emoji, separated by a semicolon:
            `testrole;❓`
            Multiple sets can be added, using newline (shift-Enter).
        '''
        await ctx.message.add_reaction('✅')
        if not msg_id_or_name:
            ctx.reply('You need to reference a message ID or name')
            return
        if not role_emoji_combo:
            ctx.reply('You need to reference roles and emojis')
            return
        log.verbose(f'Got `role_emoji_combo:` {role_emoji_combo}', color='red')
        msg_info = await get_msg_id_and_name(msg_id_or_name)
        _roles = discord_commands.get_roles()
        reactions_db_in = await db_helper.get_output(
            template_info=envs.roles_db_roles_schema,
            where=(
                ('msg_id', msg_info['id'])
            ),
            select=('role_name', 'emoji')
        )
        log.verbose(f'Got `reactions_db_in:` {reactions_db_in}', color='red')
        reactions_out = []
        reaction_role_check = [reaction[0] for reaction in reactions_db_in]
        log.verbose(f'`reaction_role_check`: {reaction_role_check}')
        reaction_emoji_check = [reaction[1] for reaction in reactions_db_in]
        log.verbose(f'`reaction_emoji_check`: {reaction_emoji_check}')
        errors = []
        for combo in role_emoji_combo:
            log.debug(f'combo: {combo}')
            if ';' not in str(combo):
                _error_msg = f'{combo} has an error'
                log.debug(_error_msg)
                errors.append(_error_msg)
                continue
            role, emoji = str(combo).split(';')
            # Check roles
            if role in reaction_role_check:
                _error_msg = f'Role {role} has already been added'
                log.debug(_error_msg)
                errors.append(_error_msg)
            elif role.lower() not in _roles:
                _error_msg = f'Could not find `role` {role}'
                log.debug(_error_msg)
                errors.append(_error_msg)
            # Check emojis
            if emoji in reaction_emoji_check:
                _error_msg = f'Emoji {emoji} has already been added'
                log.debug(_error_msg)
                errors.append(_error_msg)
            elif emoji not in reaction_emoji_check:
                try:
                    reactions_out.append((msg_info['id'], role, emoji))
                    log.debug(f'Adding role {role}, emoji {emoji}')
                except Exception as e:
                    _error_msg = f'Error when getting emoji {emoji}: '\
                        f'{type(e)}: {e}'
                    log.debug(_error_msg)
                    errors.append(_error_msg)
        if len(reactions_out) <= 0:
            await ctx.reply(
                'No role-emoji-combos to add, check errors:\n{}'.format(
                    '\n'.join(f'- {error}' for error in errors)
                )
            )
            return
        else:
            await db_helper.insert_many_all(
                envs.roles_db_roles_schema,
                inserts=reactions_out
            )
        sync_errors = await sync_reaction_message_from_settings(msg_id_or_name)
        # Inform about role/emoji errors
        _error_msg = ''
        if sync_errors:
            _error_msg += sync_errors
            _error_msg += '\n\n'
        # TODO i18n
        if len(errors) > 0:
            await ctx.reply(_error_msg)
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @role_reaction.group(name='sync', aliases=['s'])
    async def sync_reaction_items(self, ctx, msg_id_or_name=None):
        '''
        Synchronize a reaction message with the settings file

        Parameters
        ------------
        msg_id_or_name: int/str
            The message ID to look for, or name of the saved message in
            settings file
        '''
        if not msg_id_or_name:
            # TODO var msg
            await ctx.reply(
                'Du må oppgi navn eller ID til en melding som skal synces'
            )
            return
        sync_errors = await sync_reaction_message_from_settings(msg_id_or_name)
        if sync_errors:
            await ctx.reply(sync_errors)
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @role_reaction.group(name='sort')
    async def sort_reaction_items(
        self, ctx, msg_id_or_name=None
    ):
        '''
        Sort items in a reaction message alphabetically

        Parameters
        ------------
        msg_id_or_name: int/str
            The message ID from Discord or name in the database
        '''
        await ctx.message.add_reaction('✅')
        if not msg_id_or_name:
            # TODO var msg
            ctx.reply('I need the ID or name of the reaction message')
            return
        msg_info = await get_msg_id_and_name(msg_id_or_name)
        # Get message object
        _msg = await get_message_obj(
            msg_info['id'], msg_info['channel']
        )
        if _msg is None:
            # TODO var msg
            await ctx.reply('Could not find reaction message')
            return
        sync_errors = await sync_reaction_message_from_settings(
            msg_id_or_name,
            sorting=[('B.role_name', 'ASC')]
        )
        if sync_errors:
            ctx.reply(sync_errors)
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @role_reaction.group(name='remove', aliases=['r', 'delete', 'del'])
    async def remove_reaction(self, ctx):
        '''
        Remove a reaction message or a role to existing message
        '''
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @remove_reaction.group(name='message', aliases=['msg', 'm'])
    async def remove_reaction_message(self, ctx, msg_id_or_name=None):
        '''
        Remove a reaction message

        Parameters
        ------------
        msg_id_or_name: int/str
            The message ID from Discord or name in the database
        '''
        await ctx.message.add_reaction('✅')
        if not msg_id_or_name:
            # TODO var msg
            ctx.reply('I need the ID or name of the reaction message')
            return
        msg_info = await get_msg_id_and_name(msg_id_or_name)
        # Get message object
        _msg = await get_message_obj(
            msg_info['id'], msg_info['channel']
        )
        if _msg is None:
            # TODO var msg
            await ctx.reply('Could not find reaction message')
            return
        # Remove reaction message from database
        await db_helper.del_row_by_AND_filter(
            template_info=envs.roles_db_msgs_schema,
            where=[
                ('msg_id', msg_info['id'])
            ]
        )
        # Remove message from guild
        await _msg.delete()
        # TODO var msg
        await ctx.reply('Reaction message removed')
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @remove_reaction.group(name='role', aliases=['r'])
    async def remove_reaction_from_message(
        self, ctx, msg_id_or_name: str = None, role_name: str = None
    ):
        '''
        Remove a reaction from reaction message

        Parameters
        ------------
        msg_id_or_name: int/str
            The message ID to look for, or name of the saved message in
            settings file
        role_name: str
            Name of a role that is connected to a reaction
            in the message
        '''
        await ctx.message.add_reaction('✅')
        if not msg_id_or_name:
            # TODO var msg
            ctx.reply('I need the ID or name of the reaction message')
            return
        msg_info = await get_msg_id_and_name(msg_id_or_name)
        # Get message object
        _msg = await get_message_obj(
            msg_info['id'], msg_info['channel']
        )
        if _msg is None:
            # TODO var msg
            await ctx.reply('Could not find reaction message')
            return
        # Delete reaction from db
        await db_helper.del_row_by_AND_filter(
            template_info=envs.roles_db_roles_schema,
            where=[
                ('msg_id', msg_info['id']),
                ('role_name', role_name)
            ]
        )
        # Sync settings and inform of any role/emoji errors
        sync_errors = await sync_reaction_message_from_settings(msg_id_or_name)
        if sync_errors:
            ctx.reply(sync_errors)
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @role_reaction.group(name='reorder')
    async def reorder_reaction_messages(
        self, ctx, channel: str = None
    ):
        '''
        Check reaction messages order in a discord channel, discover any
        errors, and recreate them based on settings

        Parameters
        ------------
        channel: str
            What channel to check (default: None)
        '''

        '''
        Hent alle db-meldinger i rekkefølge
        Hent alle discord-meldinger i rekkefølge
        Avsjekk at rekkefølge stemmer
        Hvis ikke stemmer, fjern alle meldinger for kanalen og lag nye
        '''
        if not channel:
            # TODO var msg
            await ctx.message.reply(
                'Du må oppgi kanalen som skal sorteres på nytt'
            )
            return
        # Get all reaction messages in order from database
        react_msgs = await db_helper.get_output(
            envs.roles_db_msgs_schema,
            where=('channel', channel),
            order_by=[
                ('msg_order', 'ASC')
            ]
        )
        log.debug(f'Got `react_msgs`: {react_msgs}')
        _guild = discord_commands.get_guild()
        _channels = discord_commands.get_text_channel_list()
        channel_object = _guild.get_channel(
            _channels[channel]
        )
        discord_msgs = [message async for message in channel_object.history(
            limit=20, oldest_first=True
        )]
        trigger_reordering = False
        # Check order of messages
        if len(discord_msgs) != len(react_msgs):
            # TODO var msg
            log.log(
                'Antall reaksjonsmeldinger i {} og database stemmer '
                'ikke overens ({} vs {})'.format(
                    channel, len(discord_msgs), len(react_msgs)
                )
            )
            trigger_reordering = True
        log.debug(f'`trigger_reordering`: {trigger_reordering}')
        if not trigger_reordering:
            for idx, d_msg in enumerate(discord_msgs):
                log.debug(
                    '`d_msg.id` ({})  -  `react_msgs`: {}'.format(
                        d_msg.id, react_msgs[idx][0]
                    )
                )
                if str(d_msg.id) != str(react_msgs[idx][0]):
                    trigger_reordering = True
                    break
        log.debug(f'`trigger_reordering`: {trigger_reordering}')
        if trigger_reordering:
            # Delete the old message and recreate messages
            for react_msg in react_msgs:
                log.verbose(f'Getting object for react_msg: {react_msg}')
                old_react_msg = await get_message_obj(
                    react_msg[0],
                    react_msg[1]
                )
                log.debug('Deleting old_react_msg')
                await old_react_msg.delete()
                new_reaction_msg = await discord_commands.post_to_channel(
                    react_msg[1],
                    content_in=react_msg[3],
                    content_embed_in={
                        'description': react_msg[4]
                    }
                )
                # Update msg id in both dbs
                await db_helper.update_fields(
                    envs.roles_db_msgs_schema,
                    updates=[
                        ('msg_id', new_reaction_msg.id)
                    ],
                    where=('msg_id', react_msg[0])
                )
                await db_helper.update_fields(
                    envs.roles_db_roles_schema,
                    updates=[
                        ('msg_id', new_reaction_msg.id)
                    ],
                    where=('msg_id', react_msg[0])
                )
                # Recreate reactions by syncing settings
                await sync_reaction_message_from_settings(
                    str(new_reaction_msg.id)
                )
        return


async def setup(bot):
    cog_name = 'roles'
    log.log(envs.COG_STARTING.format(cog_name))
    log.verbose('Checking db')
    # Convert json to sqlite db-files if exists
    roles_inserts = None
    roles_inserts_msg = None
    roles_inserts_reactions = None
    roles_inserts_settings = None
    if file_io.file_size(envs.roles_settings_file):
        log.verbose('Found old json file')
        roles_inserts = db_helper.json_to_db_inserts(cog_name)
        roles_inserts_msg = roles_inserts['msg_inserts']
        roles_inserts_reactions = roles_inserts['reactions_inserts']
        roles_inserts_settings = roles_inserts['settings_inserts']
    msgs_is_ok = await db_helper.prep_table(
        envs.roles_db_msgs_schema, roles_inserts_msg
    )
    reacts_is_ok = await db_helper.prep_table(
        envs.roles_db_roles_schema, roles_inserts_reactions
    )
    settings_is_ok = await db_helper.prep_table(
        envs.roles_db_settings_schema, roles_inserts_settings
    )
    if msgs_is_ok and reacts_is_ok and settings_is_ok:
        file_io.remove_file(envs.roles_settings_file)
    log.verbose('Registering cog to bot')
    await bot.add_cog(Autoroles(bot))


# Maintain reaction roles

# Add roles to users from reactions
@config.bot.event
async def on_raw_reaction_add(payload):
    # TODO var msg
    log.debug('Checking added reaction role')
    if str(payload.user_id) == str(config.BOT_ID):
        log.debug('Change made by bot, skip')
        return
    else:
        log.debug('Change made by user, checking it...')
    reaction_messages = await db_helper.get_output(
        envs.roles_db_msgs_schema,
        select=('msg_id')
    )
    log.verbose(f'`reaction_messages`: {reaction_messages}')
    _guild = discord_commands.get_guild()
    for reaction_message in reaction_messages:
        if str(payload.message_id) == reaction_message[0]:
            # TODO var msg
            log.debug('Found message, checking add reactions...')
            reactions = await db_helper.get_combined_output(
                envs.roles_db_roles_schema,
                envs.roles_db_msgs_schema,
                key='msg_id',
                select=[
                    'role_name',
                    'emoji'
                ],
                where=[
                    ('A.msg_id', reaction_message[0])
                ]
            )
            log.verbose(f'`reactions` in add: {reactions}')
            for reaction in reactions:
                incoming_emoji = payload.emoji.name
                log.debug(f'incoming_emoji: {incoming_emoji}')
                log.debug('reaction[1]: {}'.format(
                    reaction[1]
                ))
                if incoming_emoji in reaction[1]:
                    for _role in _guild.roles:
                        if _role.name.lower() == reaction[0].lower():
                            log.debug(
                                f'Adding role {reaction[0]} to user'
                            )
                            await _guild.get_member(
                                payload.user_id
                            ).add_roles(
                                _role,
                                reason='Added in accordance with  '
                                'reaction message '
                                f'{reaction_message}'
                            )
                            break
    return


# Remove roles from users from reactions
@config.bot.event
async def on_raw_reaction_remove(payload):
    # TODO var msg
    log.debug('Checking removed reaction role')
    if str(payload.user_id) == str(config.BOT_ID):
        log.debug('Change made by bot, skip')
        return
    else:
        log.debug('Change made by user, checking it...')
    reaction_messages = await db_helper.get_output(
        envs.roles_db_msgs_schema,
        select=('msg_id')
    )
    log.verbose(f'`reaction_messages`: {reaction_messages}')
    _guild = discord_commands.get_guild()
    for reaction_message in reaction_messages:
        if str(payload.message_id) == str(reaction_message[0]):
            # TODO var msg
            log.debug('Found message, checking remove reactions...')
            reactions = await db_helper.get_combined_output(
                envs.roles_db_roles_schema,
                envs.roles_db_msgs_schema,
                key='msg_id',
                select=[
                    'role_name',
                    'emoji'
                ],
                where=[
                    ('A.msg_id', reaction_message[0])
                ]
            )
            log.verbose(f'`reactions` in remove: {reactions}')
            for reaction in reactions:
                incoming_emoji = payload.emoji.name
                log.debug(f'incoming_emoji: {incoming_emoji}')
                log.debug('reaction[1]: {}'.format(
                    reaction[1]
                ))
                if incoming_emoji in reaction[1]:
                    for _role in _guild.roles:
                        if _role.name.lower() == reaction[0].lower():
                            log.debug(
                                f'Removing role {reaction[0]} from user'
                            )
                            await _guild.get_member(
                                payload.user_id
                            ).remove_roles(
                                _role,
                                reason='Removed in accordance with '
                                'reaction message '
                                f'{reaction_message}'
                            )
                            break
    return


# Maintain unique roles
@config.bot.event
async def on_member_update(before, after):
    '''
    If a role ID is set as `unique` in settings database, it will make
    sure that if a user has 0 roles (not accounting for the roles with
    setting `not_include_in_total`), it will automatically get the unique
    role.
    '''
    unique_role = await db_helper.get_output(
        envs.roles_db_settings_schema,
        select=('value'),
        where=('setting', 'unique'),
        single=True
    )
    if len(unique_role) <= 0:
        # TODO var msg
        log.log('No unique role provided or setting is not string')
    if isinstance(unique_role[0], str):
        # TODO var msg
        log.debug('Check for unique role')
        if str(before.id) == str(config.BOT_ID):
            log.debug('Change made by bot, skip')
            return
        _guild = discord_commands.get_guild()
        log.verbose(
            f'Before ({len(before.roles)}) vs after ({len(after.roles)})'
        )
        log.verbose('before.roles: {}'.format(
            ', '.join(role.name for role in before.roles)
        ))
        log.verbose('after.roles: {}'.format(
            ', '.join(role.name for role in after.roles)
        ))
        if len(after.roles) and all(
            unique_role[0] == role.id for role in after.roles
        ):
            log.debug('Only the unique role was added')
            return
        # Prepare numbers for evaluation (remove 1 for @everyone)
        _before = len(before.roles) - 1
        _after = len(after.roles) - 1
        not_include_in_total = await db_helper.get_output(
            envs.roles_db_settings_schema,
            select=('value'),
            where=('setting', 'not_include_in_total')
        )
        if len(not_include_in_total) > 0:
            # TODO var msg
            log.debug('Found roles not to include in total')
            _before -= len(not_include_in_total)
            _after -= len(not_include_in_total)
        if any(str(unique_role[0]) == role for role in before.roles):
            _before -= 1
        elif any(str(unique_role[0]) == role for role in after.roles):
            _after -= 1
        log.verbose('before and after, minus unique role:')
        log.verbose(f'_before: {_before}')
        log.verbose(f'_after: {_after}')
        if int(_after) == 0:
            # TODO var msg
            log.debug('Length of _after is 0, adding unique role')
            await after.add_roles(_guild.get_role(int(unique_role[0])))
        elif int(_after) > 1:
            # TODO var msg
            log.debug(
                'Length of after.roles is more than 1, removing unique role'
            )
            await after.remove_roles(_guild.get_role(int(unique_role[0])))
    return
