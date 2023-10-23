#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands
import discord
from tabulate import tabulate
from asyncio import TimeoutError
from time import sleep
from operator import itemgetter

from sausage_bot.util import config, envs, file_io, discord_commands
from sausage_bot.util.log import log


def make_error_message(errors, header):
    '''
    Make a simple error message for reaction roles
    #autodoc skip#
    '''
    if len(errors['duplicate']) > 0 or len(errors['do_not_exist']) > 0:
        _error_msg_in = ''
        if len(errors['duplicate']) > 0:
            _error_msg_in += f'\n{header} duplicate:'
            for _error in errors['duplicate']:
                _error_msg_in += f'\n- {_error}'
        if len(errors['do_not_exist']) > 0:
            _error_msg_in += f'\n{header} does not exist:'
            for _error in errors['do_not_exist']:
                _error_msg_in += f'\n- {_error}'
        return _error_msg_in
    else:
        return None


async def get_message_by_id_or_name_from_settings(
        msg_id_or_name, reaction_settings_in, channel: str = None
) -> dict:
    '''
    Get a message object and it's ID and name

    Parameters
    ------------
    msg_id_or_name: int/str
        The message ID to look for, or name of the saved message in
        settings file
    reaction_settings_in: dict
        The reaction settings from the settings file
    channel: str (optional)
        Channel to get message from (default: None)

    Returns
    ------------
    dict:
        msg:
            Discord message object
        id: str
            Discord message ID
        name: str
            Message name as used in the settings file
    '''

    msg_id = None
    msg_name = None
    if isinstance(msg_id_or_name, str):
        # Get message ID and name first
        if msg_id_or_name in reaction_settings_in:
            msg_id = reaction_settings_in[msg_id_or_name]['id']
            msg_name = msg_id_or_name
    elif isinstance(msg_id_or_name, int):
        msg_id = msg_id_or_name
        for reaction in reaction_settings_in:
            if reaction_settings_in[reaction]['id'] == msg_id_or_name:
                msg_name = reaction_settings_in[reaction]
    if msg_id is None and msg_name is None:
        # TODO var msg
        log.log('No message was found')
        return None
    log.debug(f'`msg_id_or_name` is `{msg_id_or_name}`')
    if channel:
        _channel = channel
    else:
        _channel = reaction_settings_in[msg_id_or_name]['channel']
    log.log_more(f'using `msg_id`: {msg_id}')
    log.log_more(f'using `msg_name`: {msg_name}')
    _guild = discord_commands.get_guild()
    _channels = discord_commands.get_text_channel_list()
    _channel = _guild.get_channel(
        _channels[_channel]
    )
    msg = await _channel.fetch_message(msg_id)
    return {
        'msg': msg,
        'id': msg_id,
        'name': msg_name
    }


async def sync_reaction_message_from_settings(msg_id_or_name):
    # Read settings file
    roles_settings = file_io.read_json(envs.roles_settings_file)
    reaction_msgs = roles_settings['reaction_messages']
    _msg = await get_message_by_id_or_name_from_settings(
        msg_id_or_name, reaction_msgs
    )
    if _msg is None:
        return None
    reaction_settings = reaction_msgs[_msg['name']]
    log.debug(f'reaction_settings: {reaction_settings}')
    # By using settingsfile, recreate the embed
    _roles = discord_commands.get_roles()
    new_embed_desc = ''
    new_embed_content = ''
    await _msg['msg'].clear_reactions()
    _errors_out = ''
    for idx, reaction in enumerate(reaction_settings['reactions'][:]):
        try:
            await _msg['msg'].add_reaction(reaction[1])
        except Exception as e:
            log.debug(f'Could not add reaction to message: {e}')
            if len(_errors_out) > 0:
                _errors_out += '\n'
            _errors_out += 'Could not add reaction {} to message'.format(
                reaction[1]
            )
            reaction_settings['reactions'].remove(reaction)
            continue
        new_embed_content = reaction_settings['content']
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
            reaction_settings['reactions'].remove(reaction)
            continue
    embed_json = {
        'description': new_embed_desc,
        'content': new_embed_content
    }
    file_io.write_json(envs.roles_settings_file, roles_settings)
    # Edit discord message
    await _msg['msg'].edit(
        content=reaction_settings['content'],
        embed=discord.Embed.from_dict(embed_json)
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
                log.log_more(f'Sjekker `_role`: {_role}')
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
            log.log_more(f'`{page}`')
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
    async def list_reactions(self, ctx, reaction_name: str = None):
        '''
        List reactions

        If reaction_name is not provided, list all messages

        Parameters
        ------------
        reaction_name: str
            The names of the reaction message to list (default: None)
        '''
        reaction_messages = file_io.read_json(
            envs.roles_settings_file
        )['reaction_messages']
        if reaction_name:
            if reaction_name not in reaction_messages:
                await ctx.reply(f'Did not find `{reaction_name}`')
                return
            reactions = reaction_messages[reaction_name]['reactions']
            tabulate_dict = {
                'role': [],
                'emoji': []
            }
            for reaction in reactions:
                tabulate_dict['role'].append(reaction[0])
                tabulate_dict['emoji'].append(reaction[1])
            # TODO i18n?
            await ctx.reply('```{}```'.format(
                tabulate(tabulate_dict, headers=['Rolle', 'Emoji'])
            ))
        elif not reaction_name:
            tabulate_dict = {
                'name': [],
                'channel': [],
                'order': [],
                'id': [],
                'content': [],
                'reactions': []
            }
            sorted_reacts = sorted(
                reaction_messages, key=lambda x: (
                    reaction_messages[x]['channel'],
                    reaction_messages[x]['order'])
            )
            for msg_name in sorted_reacts:
                tabulate_dict['name'].append(msg_name)
                tabulate_dict['channel'].append(
                    reaction_messages[msg_name]['channel']
                )
                tabulate_dict['order'].append(
                    reaction_messages[msg_name]['order']
                )
                tabulate_dict['id'].append(reaction_messages[msg_name]['id'])
                tabulate_dict['content'].append(
                    reaction_messages[msg_name]['content'][0:20]
                )
                tabulate_dict['reactions'].append(
                    len(reaction_messages[msg_name]['reactions'])
                )
            await ctx.reply(
                '```{}```'.format(
                    tabulate(
                        # TODO i18n?
                        tabulate_dict, headers=[
                            'Navn', 'Kanal', 'Rekkefølge', 'ID',
                            'Innhold', 'Ant. reaksj.'
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
        roles_settings = file_io.read_json(envs.roles_settings_file)
        if channel is None:
            if roles_settings['channel']:
                channel = roles_settings['channel']
            else:
                channel = 'roles'
        reaction_messages = roles_settings['reaction_messages']
        if msg_name in reaction_messages:
            # TODO var msg
            await ctx.reply(
                f'Reaction message `{msg_name}` is already in '
                '`roles settings`: `{}...`'.format(
                    reaction_messages[msg_name]['content'][0:20]
                )
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
            error_roles = {
                'duplicate': [],
                'do_not_exist': []
            }
            reactions = []
            _roles = _guild.roles
            _roles_list = []
            _roles_list.extend([role.name.lower() for role in _roles])
            log.log_more(f'_roles_list: {_roles_list}')
            _emojis = _guild.emojis
            _emojis_list = []
            _emojis_list.extend([emoji.name.lower() for emoji in _emojis])
            log.log_more(f'_emojis_list: {_emojis_list}')
            content_split = []
            content_split.extend(
                line for line in str(_msg.content).split('\n')
            )
            for line in content_split:
                role, emoji = line.strip().split(';')
                # Use this for reporting non-existing roles
                if role.lower() not in _roles_list:
                    log.debug(f'Could not find role `{role}`')
                    error_roles['do_not_exist'].append(role)
                    continue
                else:
                    for _role in _roles:
                        if role == _role.name:
                            _role_id = _role.id
                            break
                if len(desc_out) > 0:
                    desc_out += '\n'
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
        _error_msg = make_error_message(error_roles, 'Roles')
        if _error_msg:
            await ctx.reply(_error_msg)
        # Post the reaction message
        reaction_msg = await discord_commands.post_to_channel(
            channel, content_in=message_text,
            content_embed_in=embed_json
        )
        # Save to the settings file
        reaction_messages[msg_name] = {
            'channel': channel,
            'order': order,
            'id': reaction_msg.id,
            'content': message_text,
            'description': embed_json['description'],
            'reactions': reactions
        }
        file_io.write_json(envs.roles_settings_file, roles_settings)
        # TODO Gå over fra posting til reordering?
        for reaction in reactions:
            log.debug(f'Adding emoji {reaction[1]}')
            await reaction_msg.add_reaction(reaction[1])
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
            The message ID to look for, or name of the saved message in
            settings file
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
        temp_out = ''
        combos = []
        for combo in role_emoji_combo:
            if ';' not in combo:
                temp_out += f'{combo} '
            if ';' in combo:
                temp_out += combo
                combos.append(temp_out)
                temp_out = ''
        # Update settings file
        roles_settings = file_io.read_json(envs.roles_settings_file)
        reaction_messages = roles_settings['reaction_messages']
        _roles = discord_commands.get_roles()
        error_roles = {
            'duplicate': [],
            'do_not_exist': []
        }
        error_emojis = {
            'duplicate': [],
            'do_not_exist': []
        }
        _msg = await get_message_by_id_or_name_from_settings(
            msg_id_or_name, reaction_messages
        )
        if _msg is None:
            # TODO var msg
            await ctx.reply('Could not find reaction message')
            return
        reactions = reaction_messages[_msg['name']]['reactions']
        reaction_role_check = []
        reaction_role_check.extend(reaction[0] for reaction in reactions)
        reaction_emoji_check = []
        reaction_emoji_check.extend(reaction[1] for reaction in reactions)
        _role_error = False
        _emoji_error = False
        for combo in combos:
            log.debug(f'combo: {combo}')
            role, emoji = str(combo).split(';')
            # Check roles
            if role in reaction_role_check:
                log.debug(f'Role {role} has already been added')
                error_roles['duplicate'].append(role)
                _role_error = True
            elif role.lower() not in _roles:
                log.debug(f'Could not find `role` {role}')
                error_roles['do_not_exist'].append(role)
                _role_error = True
            # Check emojis
            if emoji in reaction_emoji_check:
                log.debug(f'Emoji {emoji} has already been added')
                error_emojis['duplicate'].append(emoji)
                _emoji_error = True
            elif emoji not in reaction_emoji_check:
                if not _role_error and not _emoji_error:
                    try:
                        reactions.append([role, emoji])
                        log.debug(f'Adding role {role}, emoji {emoji}')
                    except Exception as e:
                        log.debug(
                            f'Error when getting emoji {emoji}: {type(e)}: {e}'
                        )
                        error_emojis['do_not_exist'].append(emoji)
                        _emoji_error = True
        file_io.write_json(envs.roles_settings_file, roles_settings)
        sync_errors = await sync_reaction_message_from_settings(msg_id_or_name)
        # Inform about role/emoji errors
        _error_msg = ''
        if sync_errors:
            _error_msg += sync_errors
            _error_msg += '\n\n'
        # TODO i18n
        _msg_error_roles = make_error_message(error_roles, 'Roles')
        _msg_error_emojis = make_error_message(error_emojis, 'Emojis')
        if _msg_error_roles:
            _error_msg += _msg_error_roles
        if _msg_error_emojis:
            if len(_error_msg) > 0:
                _error_msg += '\n\n'
            _error_msg += _msg_error_emojis
        if len(_error_msg) > 0:
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
            The message ID to look for, or name of the saved message in
            settings file
        '''
        await ctx.message.add_reaction('✅')
        if not msg_id_or_name:
            # TODO var msg
            ctx.reply('I need the ID or name of the reaction message')
            return
        roles_settings = file_io.read_json(envs.roles_settings_file)
        reaction_messages = roles_settings['reaction_messages']
        _msg = await get_message_by_id_or_name_from_settings(
            msg_id_or_name, reaction_messages
        )
        if _msg is None:
            # TODO var msg
            await ctx.reply('Could not find reaction message')
            return
        reaction_messages[_msg['name']]['reactions'] = sorted(
            reaction_messages[_msg['name']]['reactions'],
            key=itemgetter(0)
        )
        file_io.write_json(envs.roles_settings_file, roles_settings)
        sync_errors = await sync_reaction_message_from_settings(msg_id_or_name)
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
    async def remove_reaction_message(self, ctx, msg_name: str = None):
        '''
        Remove a reaction message

        Parameters
        ------------
        msg_name: str
            The names of the reaction message to remove (default: None)
        '''
        await ctx.message.add_reaction('✅')
        roles_settings = file_io.read_json(envs.roles_settings_file)
        reaction_messages = roles_settings['reaction_messages']
        if msg_name not in reaction_messages:
            await ctx.reply(f'Could not find {msg_name}')
            return
        # Remove reaction message from guild
        channel = reaction_messages[msg_name]['channel']
        _guild = discord_commands.get_guild()
        _channels = discord_commands.get_text_channel_list()
        _channel = _guild.get_channel(
            _channels[channel]
        )
        _msg = await _channel.fetch_message(
            reaction_messages[msg_name]['id']
        )
        log.debug(f'Found message {_msg}')
        await _msg.delete()
        # Remove reaction message from settings file
        del reaction_messages[msg_name]
        file_io.write_json(envs.roles_settings_file, roles_settings)
        # TODO var msg
        await ctx.reply('Reaction message removed')
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @remove_reaction.group(name='role', aliases=['r'])
    async def remove_reaction_from_message(
        self, ctx, msg_id_or_name: str = None, *role_names
    ):
        '''
        Remove a reaction from reaction message

        Parameters
        ------------
        msg_id_or_name: int/str
            The message ID to look for, or name of the saved message in
            settings file
        role_names: str
            Name of one or several roles that is connected to a reaction
            in the message
        '''
        # Update settings file
        roles_settings = file_io.read_json(envs.roles_settings_file)
        reaction_messages = roles_settings['reaction_messages']
        _roles = discord_commands.get_roles()
        error_roles = {
            'duplicate': [],
            'do_not_exist': []
        }
        _msg = await get_message_by_id_or_name_from_settings(
            msg_id_or_name, reaction_messages
        )
        if _msg is None:
            # TODO var msg
            await ctx.reply('Could not find reaction message')
            return
        reactions = reaction_messages[_msg['name']]['reactions']
        _reaction_roles_list = []
        _reaction_roles_list.extend([role[0].lower() for role in reactions])
        log.log_more(f'role_names: {role_names}')
        for role_name in role_names:
            if role_name.lower() not in _roles:
                log.debug(f'Could not find `role_name` {role_name}')
                error_roles['do_not_exist'].append(role_name)
            elif role_name.lower() in _reaction_roles_list:
                _index = _reaction_roles_list.index(role_name.lower())
                # Remove reaction from settings file
                del reactions[_index]
                break
            else:
                log.debug(f'Could not find `{role_name}` in reactions')
                error_roles['do_not_exist'].append(role_name)
        file_io.write_json(envs.roles_settings_file, roles_settings)
        sync_errors = await sync_reaction_message_from_settings(msg_id_or_name)
        if sync_errors:
            ctx.reply(sync_errors)
        # Inform about role/emoji errors
        _error_msg = make_error_message(error_roles, 'Roles')
        if _error_msg:
            await ctx.reply(_error_msg)
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
        Check reaction messages placing in discord, discover any errors,
        and recreate them based on settings

        Parameters
        ------------
        channel: str
            What channel to check (default: None)
        '''
        if not channel:
            # TODO var msg
            await ctx.message.reply(
                'Du må oppgi kanalen som skal sorteres på nytt'
            )
            return
        roles_settings = file_io.read_json(envs.roles_settings_file)
        react_msgs = roles_settings['reaction_messages']
        order_compare = {
            'settings': {},
            'discord': {}
        }
        channel_compare = {}
        for msg in react_msgs:
            order_compare['settings'][react_msgs[msg]['order']] = \
                react_msgs[msg]['id']
            channel_compare[react_msgs[msg]['id']] = \
                react_msgs[msg]['channel']
        log.debug(
            f'This is the `channel_compare`: {channel_compare}',
            color='yellow'
        )
        order_compare['settings'] = dict(
            sorted(order_compare['settings'].items(), key=lambda x: x[0])
        )
        _guild = discord_commands.get_guild()
        _channels = discord_commands.get_text_channel_list()
        channel_object = _guild.get_channel(
            _channels[channel]
        )
        discord_msgs = [message async for message in channel_object.history(
            limit=20, oldest_first=True
        )]
        discord_order_comp = []
        discord_order_comp.extend(
            [(idx+1, message.id) for idx, message in enumerate(discord_msgs)]
        )
        for msg in discord_order_comp:
            order_compare['discord'][msg[0]] = msg[1]
        order_compare = dict(sorted(order_compare.items()))
        log.debug(
            f'This is the `order_compare`: {order_compare}',
            color='yellow'
        )
        trigger_reordering = None
        # Check order of messages
        if len(order_compare['discord']) != len(order_compare['settings']):
            # TODO var msg
            log.log(
                'Antall reaksjonsmeldinger i {} og innstillinger stemmer '
                'ikke overens ({} vs {})'.format(
                    channel, len(order_compare['settings']),
                    len(order_compare['discord'])
                )
            )
            # Delete the old message
            set1 = set(order_compare['settings'].items())
            set2 = set(order_compare['discord'].items())
            missing_msgs = list(set1 ^ set2)
            for msg in missing_msgs:
                msg_search = await discord_commands.search_for_message_id(
                    msg[1]
                )
                if msg_search is not None:
                    msg = await _guild.get_channel(
                        _channels[msg_search['channel']]
                    ).fetch_message(msg_search['msg_id'])
                    log.debug('Deleting msg')
                    await msg.delete()
                else:
                    # TODO var msg
                    log.debug('Message not found')
            trigger_reordering = True
        elif len(order_compare['discord']) == len(order_compare['settings']):
            len_reacts = len(order_compare['settings'])
            i = 1
            while i <= len_reacts:
                if order_compare['settings'][i] != order_compare['discord'][i]:
                    # TODO var msg
                    log.debug(
                        'Feil rekkefølge oppdaget!'
                    )
                    trigger_reordering = True
                    break
                else:
                    # TODO var msg
                    log.log('No errors in order')
                i += 1
        for msg_id in channel_compare:
            try:
                _msg = await get_message_by_id_or_name_from_settings(
                    msg_id, react_msgs, channel_compare[msg_id]
                )
                log.debug('Found message {}'.format(
                    _msg['id']
                ))
            except discord.errors.NotFound:
                # Trigger recreate
                trigger_reordering = True
            except Exception as e:
                print(f'Got error: ({type(e)}): {e}')
        if trigger_reordering:
            # Get and delete messages
            _channels = discord_commands.get_text_channel_list()
            for id in order_compare['discord']:
                msg = await _guild.get_channel(
                    _channels[channel]
                ).fetch_message(
                    order_compare['discord'][id]
                )
                log.debug(f'Found message {msg}')
                await msg.delete()
            # Recreate messages
            react_msgs_sorted = sorted(
                react_msgs, key=lambda x: (
                    react_msgs[x]['channel'],
                    react_msgs[x]['order'])
            )
            for msg in react_msgs_sorted:
                embed_json = {
                    'description': react_msgs[msg]['description']
                }
                reaction_msg = await discord_commands.post_to_channel(
                    react_msgs[msg]['channel'],
                    content_in=react_msgs[msg]['content'],
                    content_embed_in=embed_json
                )
                for reaction in react_msgs[msg]['reactions']:
                    log.debug(f'Adding emoji {reaction[1]}')
                    await reaction_msg.add_reaction(reaction[1])
                # Update the message id in settings file
                react_msgs[msg]['id'] = reaction_msg.id
            file_io.write_json(envs.roles_settings_file, roles_settings)
        return


async def setup(bot):
    log.log(envs.COG_STARTING.format('autoroles'))
    log.log_more(envs.CREATING_FILES)
    check_and_create_files = [
        (envs.roles_settings_file, envs.roles_template)
    ]
    file_io.create_necessary_files(check_and_create_files)
    await bot.add_cog(Autoroles(bot))


settings = file_io.read_json(envs.roles_settings_file)

# Maintain reaction roles
_reaction_roles = settings['reaction_messages']
if len(_reaction_roles) > 0:
    # TODO var msg
    log.debug('Checking reaction roles')

    @config.bot.event
    async def on_raw_reaction_add(payload):
        if int(payload.member.id) == int(config.BOT_ID):
            log.debug('Change made by bot, skip')
            return
        roles_settings = file_io.read_json(envs.roles_settings_file)
        reaction_messages = roles_settings['reaction_messages']
        _guild = discord_commands.get_guild()
        for reaction_message in reaction_messages:
            if payload.message_id == reaction_messages[reaction_message]['id']:
                # TODO var msg
                log.debug('Found message, checking reactions...')
                reactions = reaction_messages[reaction_message]['reactions']
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

    @config.bot.event
    async def on_raw_reaction_remove(payload):
        roles_settings = file_io.read_json(envs.roles_settings_file)
        reaction_messages = roles_settings['reaction_messages']
        _guild = discord_commands.get_guild()
        for reaction_message in reaction_messages:
            if payload.message_id == reaction_messages[reaction_message]['id']:
                # TODO var msg
                log.debug('Found message, checking reactions...')
                reactions = reaction_messages[reaction_message]['reactions']
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
_unique_role_settings = settings['unique_role']
if 'role' not in _unique_role_settings or\
        not isinstance(_unique_role_settings['role'], int):
    # TODO var msg
    log.log('No unique role provided or setting is not string')
elif 'role' in _unique_role_settings and\
        isinstance(_unique_role_settings['role'], int):
    # TODO var msg
    log.debug('Check for unique role')

    @config.bot.event
    async def on_member_update(before, after):
        '''
        If a role ID is set in `roles_settings.json['unique_role']['role]`,
        it will make sure that if a user has 0 roles, it will automatically
        get the unique role.
        If roles are specified in the
        `roles_settings.json['unique_role']['not_include_in_total]`,
        these will not be counted in the total of a users role to make
        sure the total number will be correct
        '''
        if int(before.id) == int(config.BOT_ID):
            log.debug('Change made by bot, skip')
            return
        _guild = discord_commands.get_guild()
        _unique_role = _unique_role_settings['role']
        log.log_more(
            f'Before ({len(before.roles)}) vs after ({len(after.roles)})'
        )
        log.log_more('before.roles: {}'.format(
            ', '.join(role.name for role in before.roles)
        ))
        log.log_more('after.roles: {}'.format(
            ', '.join(role.name for role in after.roles)
        ))
        if len(after.roles) and all(
            _unique_role == role.id for role in after.roles
        ):
            log.debug('Only the unique role was added')
            return
        # Prepare numbers for evaluation (remove 1 for @everyone)
        _before = len(before.roles) - 1
        _after = len(after.roles) - 1
        if len(_unique_role_settings['not_include_in_total']) > 0:
            # TODO var msg
            log.debug('Found roles not to include in total')
            _before -= len(_unique_role_settings['not_include_in_total'])
            _after -= len(_unique_role_settings['not_include_in_total'])
        if any(str(_unique_role) == role for role in before.roles):
            _before -= 1
        elif any(str(_unique_role) == role for role in after.roles):
            _after -= 1
        log.log_more('before and after, minus unique role:')
        log.log_more(f'_before: {_before}')
        log.log_more(f'_after: {_after}')
        if int(_after) == 0:
            # TODO var msg
            log.debug('Length of _after is 0, adding unique role')
            await after.add_roles(_guild.get_role(_unique_role))
            return
        elif int(_after) > 1:
            # TODO var msg
            log.debug(
                'Length of after.roles is more than 1, removing unique role'
            )
            await after.remove_roles(_guild.get_role(_unique_role))
        else:
            log.log('Something happened')
