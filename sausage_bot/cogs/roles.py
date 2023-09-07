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
        msg_id_or_name, reaction_settings_in
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
    reaction_template = reaction_msgs[_msg['name']]
    log.debug(f'reaction_template: {reaction_template}')
    # By using settingsfile, recreate the embed
    _roles = discord_commands.get_roles()
    new_embed_desc = ''
    await _msg['msg'].clear_reactions()
    _errors_out = ''
    for idx, reaction in enumerate(reaction_template['reactions'][:]):
        try:
            await _msg['msg'].add_reaction(reaction[1])
        except Exception as e:
            log.debug(f'Could not add reaction to message: {e}')
            if len(_errors_out) > 0:
                _errors_out += '\n'
            _errors_out += 'Could not add reaction {} to message'.format(
                reaction[1]
            )
            reaction_template['reactions'].remove(reaction)
            continue
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
            reaction_template['reactions'].remove(reaction)
            continue
    file_io.write_json(envs.roles_settings_file, roles_settings)
    embed_json = {
        'description': new_embed_desc
    }
    # Edit discord message
    await _msg['msg'].edit(
        content=reaction_template['content'],
        embed=discord.Embed.from_dict(embed_json)
    )


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
                log.debug(f'Sjekker `_role`: {_role}')
                if str(_role.name).lower() == role_name.lower():
                    log.debug(f'Fant `{role_name}`')
                    embed = discord.Embed(color=_role.color)
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
                            inline=False
                        )
                    elif _role.is_integration():
                        embed.add_field(
                            name="Autohåndteres",
                            value='Ja, av {}'.format(
                                _guild.get_member(_role.tags.bot_id).name
                            ),
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="Autohåndteres", value="Nei", inline=True
                        )
                    permissions = ", ".join(
                        [permission for permission, value in
                            iter(_role.permissions) if value is True]
                    )
                    if permissions:
                        embed.add_field(
                            name="Tillatelser", value=permissions,
                            inline=True
                        )
                    else:
                        embed.add_field(
                            name="Tillatelser", value='Ingen',
                            inline=True
                        )
                    if _role.hoist:
                        embed.add_field(
                            name="Spesielt synlig",
                            value='Ja'
                        )
                    else:
                        embed.add_field(
                            name="Spesielt synlig",
                            value='Nei'
                        )
                    embed.add_field(
                        name="Brukere med rollen",
                        value=len(_role.members), inline=False
                    )
                    await ctx.reply(embed=embed)
                    return
            # TODO var msg
            _var_msg = f'Fant ikke rollen `{role_name}`'
            log.debug(_var_msg)
            await ctx.reply(_var_msg)
        return

    @guildroles.group(name='list', aliases=['l'])
    async def role_list(self, ctx):
        'List roles, emojis or reactions'
        return

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
                'id': [],
                'content': [],
                'reactions': []
            }
            for msg in reaction_messages:
                tabulate_dict['name'].append(msg)
                tabulate_dict['channel'].append(reaction_messages[msg]['channel'])
                tabulate_dict['id'].append(reaction_messages[msg]['id'])
                tabulate_dict['content'].append(
                    reaction_messages[msg]['content'][0:20]
                )
                tabulate_dict['reactions'].append(
                    len(reaction_messages[msg]['reactions'])
                )
                await ctx.reply(
                    '```{}```'.format(
                        tabulate(
                            # TODO i18n?
                            tabulate_dict, headers=[
                                'Navn', 'Kanal', 'ID', 'Innhold', 'Ant. reaksj.'
                            ]
                        )
                    )
                )
        return

    @guildroles.group(name='manage', aliases=['m'])
    async def role_manage(self, ctx):
        'Manage specific roles on the server'
        return

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
        if permissions.lower() in ['ingen', 'none', 'no']:
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

    @guildroles.group(name='user')
    async def user_role(self, ctx):
        '''
        Manage a user\'s roles
        '''
        return

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

    @guildroles.group(name='reaction', aliases=['reac'])
    async def role_reaction(self, ctx):
        'Manage reaction roles and messages on the server'
        return

    @role_reaction.group(name='add', aliases=['a'])
    async def add_reaction_item(self, ctx):
        '''
        Add a reaction message or a role to existing message
        '''
        return

    @add_reaction_item.group(name='message', aliases=['msg', 'm'])
    async def add_msg(
        self, ctx, msg_name: str = None, message_text: str = '',
        channel: str = None
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
        try:
            _msg = await config.bot.wait_for('message', timeout=60.0)
            desc_out = ''
            error_roles = {
                'duplicate': [],
                'do_not_exist': []
            }
            reactions = []
            _guild = discord_commands.get_guild()
            _roles = _guild.roles
            _roles_list = []
            _roles_list.extend([role.name.lower() for role in _roles])
            log.log_more(f'_roles_list: {_roles_list}')
            _emojis = _guild.emojis
            _emojis_list = []
            _emojis_list.extend([emoji.name.lower() for emoji in _emojis])
            log.log_more(f'_emojis_list: {_emojis_list}')
            #
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
        # Inform about role/emoji errors
        _error_msg = make_error_message(error_roles, 'Roles')
        if _error_msg:
            await ctx.reply(_error_msg)
        # Post the reaction message
        reaction_msg = await discord_commands.post_to_channel(
            channel, content_in=message_text,
            content_embed_in=embed_json
        )
        for reaction in reactions:
            log.debug(f'Adding emoji {reaction[1]}')
            await reaction_msg.add_reaction(reaction[1])
        # Save to the settings file
        reaction_messages[msg_name] = {
            'channel': channel,
            'id': reaction_msg.id,
            'content': message_text,
            'description': embed_json['description'],
            'reactions': reactions
        }
        file_io.write_json(envs.roles_settings_file, roles_settings)
        return

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
        reactions = reaction_messages[_msg['name']]['reactions']
        for combo in role_emoji_combo:
            role, emoji = str(combo).split(';')
            if role.lower() not in _roles:
                log.debug(f'Could not find `role` {role}')
                error_roles['do_not_exist'].append(role)
            elif role in reactions:
                log.debug(f'Emoji {role} has already been added')
                error_roles['duplicate'].append(role)
            else:
                reactions.append([role, emoji])
                log.debug(f'Adding emoji {emoji}')
        file_io.write_json(envs.roles_settings_file, roles_settings)
        await sync_reaction_message_from_settings(msg_id_or_name)
        # Inform about role/emoji errors
        _error_msg = make_error_message(error_roles)
        if _error_msg:
            await ctx.reply(_error_msg)
        return

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
        await sync_reaction_message_from_settings(msg_id_or_name)
        return

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
        if not msg_id_or_name:
            # TODO var msg
            ctx.reply('I need the ID or name of the reaction message')
            return
        roles_settings = file_io.read_json(envs.roles_settings_file)
        reaction_messages = roles_settings['reaction_messages']
        _msg = await get_message_by_id_or_name_from_settings(
            msg_id_or_name, reaction_messages
        )
        reaction_messages[_msg['name']]['reactions'] = sorted(
            reaction_messages[_msg['name']]['reactions'],
            key=itemgetter(0)
        )
        file_io.write_json(envs.roles_settings_file, roles_settings)
        await sync_reaction_message_from_settings(msg_id_or_name)
        return

    @role_reaction.group(name='remove', aliases=['r', 'delete', 'del'])
    async def remove_reaction(self, ctx):
        '''
        Remove a reaction message or a role to existing message
        '''
        return

    @remove_reaction.group(name='message', aliases=['msg', 'm'])
    async def remove_reaction_message(self, ctx, msg_name: str = None):
        '''
        Remove a reaction message

        Parameters
        ------------
        msg_name: str
            The names of the reaction message to remove (default: None)
        '''
        roles_settings = file_io.read_json(envs.roles_settings_file)
        reaction_messages = roles_settings['reaction_messages']
        if msg_name not in reaction_messages:
            ctx.reply(f'Could not find {msg_name}')
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
        return

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
        reactions = reaction_messages[_msg['name']]['reactions']
        log.log_more(f'role_names: {role_names}')
        for role_name in role_names:
            if role_name.lower() not in _roles:
                log.debug(f'Could not find `role_name` {role_name}')
                error_roles['do_not_exist'].append(role_name)
            else:
                # Remove reaction from settings file
                for reaction in reactions:
                    if role_name == reaction[0]:
                        del reactions[reactions.index(reaction)]
        file_io.write_json(envs.roles_settings_file, roles_settings)
        await sync_reaction_message_from_settings(msg_id_or_name)
        # Inform about role/emoji errors
        _error_msg = make_error_message(error_roles)
        if _error_msg:
            await ctx.reply(_error_msg)
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
if isinstance(_unique_role_settings['role'], int):
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
