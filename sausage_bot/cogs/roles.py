#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands
import discord
from tabulate import tabulate
from asyncio import TimeoutError
from time import sleep
import re

from sausage_bot.util import config, envs, file_io, discord_commands
from sausage_bot.util.log import log

'''
Manual command tree:
!roles              guildroles
    info            guildroles.role_info
    manage          guildroles.role_manage
        add         guildroles.role_manage.add_role
        remove      guildroles.role_manage.remove_role
        edit        guildroles.role_manage.edit_role
    user            guildroles.user_role
        add         guildroles.user_role.user_add_role
        remove      guildroles.user_role.user_remove_role
    reaction        guildroles.role_reaction
        list        guildroles.role_reaction.list_reaction
        add         guildroles.role_reaction.add_reaction
            msg     guildroles.role_reaction.add_reaction.add_msg
            role    guildroles.role_reaction.add_reaction.add_role
        remove      guildroles.role_reaction.remove_reaction
            msg     guildroles.role_reaction.remove_reaction.remove_reaction_message
            role    guildroles.role_reaction.remove_reaction.remove_reaction_from_message
'''


def make_error_message(errors):
    '''
    Make a simple error message for reaction roles
    #autodoc skip#
    '''
    if len(errors['duplicate']) > 0 or len(errors['do_not_exist']) > 0:
        _error_msg_in = ''
        # TODO var msg
        _error_msg_in += '\nErrors:'
        if len(errors['duplicate']) > 0:
            _error_msg_in += '\nDuplicate:'
            for error_role in errors['duplicate']:
                _error_msg_in += f'\n- {error_role}'
        if len(errors['do_not_exist']) > 0:
            _error_msg_in += '\nDoes not exist:'
            for error_role in errors['do_not_exist']:
                _error_msg_in += f'\n- {error_role}'
        return _error_msg_in
    else:
        return None


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
                    # TODO How to i18n headers?
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
        If no `role_name` is given, return all users with no roles

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
                    # embed.description()     # string
                    # embed.set_thumbnail(url=_role.icon)
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
        elif role_name is None:
            # TODO var msg
            no_roles = []
            for member in _guild.members:
                if len(member.roles) == 1:
                    if member.roles[0].name == '@everyone':
                        no_roles.append(member.name)
            header = f'Brukere uten roller ({len(no_roles)}):'
            out = ''
            for _member in no_roles:
                if (len(out) + len(_member)) > 1800:
                    ctx.send(out)
                    out = ''
                if out == '':
                    out += header
                out += f'\n- {_member}'
            await ctx.send(out)
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
        if permissions.lower() == 'ingen':
            permissions = discord.Permissions(permissions=0)
        if color.lower() == 'ingen':
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
                new_name (str)
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
            if setting == 'new_name':
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
        # TODO lag samme settings som på stats
        return

    @role_reaction.group(name='list', aliases=['l'])
    async def list_reaction(self, ctx):
        'List available reaction messages'
        settings = file_io.read_json(envs.roles_settings_file)
        _msgs_in = settings['reaction_messages']
        if len(_msgs_in) <= 0:
            # TODO var msg
            await ctx.reply(
                'Ingen aktive reaction messages'
            )
            return
        _tabulate_msgs = {
            'name': [],
            'channel': [],
            'id': [],
            'content': [],
            'no_of_reactions': []
        }
        for _msg in _msgs_in:
            _tabulate_msgs['name'].append(_msg)
            _tabulate_msgs['channel'].append(_msgs_in[_msg]['channel'])
            _tabulate_msgs['id'].append(_msgs_in[_msg]['id'])
            _tabulate_msgs['content'].append(
                _msgs_in[_msg]['content']
            )
            _tabulate_msgs['no_of_reactions'].append(
                len(_msgs_in[_msg]['reactions'])
            )
        await ctx.reply(
            '```{}```'.format(
                tabulate(
                    # TODO var msg i18n?
                    _tabulate_msgs, headers=[
                        'Navn', 'Kanal', 'ID', 'Innhold', 'Reaksjoner'
                    ], maxcolwidths=[None, None, None, 20, None]
                )
            )
        )
        return

    @role_reaction.group(name='add', aliases=['a'])
    async def add_reaction(self, ctx):
        '''
        Add a reaction message or a role to existing message
        '''
        return

    @add_reaction.group(name='message', aliases=['msg', 'm'])
    async def add_msg(
        self, ctx, msg_name: str = None, message_text: str = '',
        channel: str = None
    ):
        '''
        Add a reaction message

        Parameters
        ------------
        msg_name: str
            Name of the message for the reaction roles
        message_text: str
            The text for the message (default: '')
        channel: strl
            Channel to post reaction message to. If not specified, it will
            use the channel in settings
        '''

        '''
        1. make message (in roles-channel defined in json-settings)
        2. ask for multiple roles to add with emojis (without :)
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
            _roles = discord_commands.get_roles()
            for line in str(_msg.content).split('\n'):
                role, emoji = line.split(';')
                # Use this for reporting non-existing roles
                if role.lower() not in _roles:
                    log.debug(f'Could not find role `role` {role}')
                    error_roles['do_not_exist'].append(role)
                    continue
                if len(desc_out) > 0:
                    desc_out += '\n'
                desc_out += '{} <@&{}>'.format(
                    emoji, _roles[role]['id']
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
        _error_msg = make_error_message(error_roles)
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

    @add_reaction.group(name='role', aliases=['r'])
    async def add_reaction_role(
        self, ctx, msg_id_or_name=None, *role_emoji_combo
    ):
        '''
        Add a reaction message

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
        # TODO Roles are not added to settings file
        roles_settings = file_io.read_json(envs.roles_settings_file)
        reaction_messages = roles_settings['reaction_messages']
        if isinstance(msg_id_or_name, str):
            # Get message ID first
            if msg_id_or_name in reaction_messages:
                msg_id = reaction_messages[msg_id_or_name]['id']
        elif isinstance(msg_id_or_name, int):
            msg_id = msg_id_or_name
        _channel = reaction_messages[msg_id_or_name]['channel']
        log.debug(f'using `msg_id`: {msg_id}')
        _guild = discord_commands.get_guild()
        _channels = discord_commands.get_text_channel_list()
        _channel = _guild.get_channel(
            _channels[_channel]
        )
        _msg = await _channel.fetch_message(msg_id)
        # Check if the bot is the author before continuing
        env_bot_id = config.env.int('BOT_ID')
        if _msg.author.id != env_bot_id:
            # TODO var msg
            await ctx.reply('Message is not created by me')
            return
        embed_desc = _msg.embeds[0].description
        _roles = discord_commands.get_roles()
        error_roles = {
            'duplicate': [],
            'do_not_exist': []
        }
        reactions = reaction_messages[msg_id_or_name]['reactions']
        for combo in role_emoji_combo:
            role, emoji = combo.split(';')
            if role.lower() not in _roles:
                log.debug(f'Could not find `role` {role}')
                error_roles['do_not_exist'].append(role)
                continue
            if emoji in embed_desc or role in reactions:
                log.debug(f'Emoji {role} has already been added')
                error_roles['duplicate'].append(role)
                continue
            embed_desc += '\n{} <@&{}>'.format(
                emoji, _roles[role]['id']
            )
            log.debug(f'Adding emoji {emoji}')
            await _msg.add_reaction(emoji)
            await ctx.message.add_reaction('✅')
            if '<:' in str(emoji):
                emoji = re.match(r'<:(.*):\d+>', emoji).group(1)
            reactions.append([role, emoji])
        file_io.write_json(envs.roles_settings_file, roles_settings)
        embed_json = {
            'description': embed_desc
        }
        # Inform about role/emoji errors
        _error_msg = make_error_message(error_roles)
        if _error_msg:
            await ctx.reply(_error_msg)
        await _msg.edit(embed=discord.Embed.from_dict(embed_json))
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
        self, ctx, msg_name: str = None, role_name: str = None
    ):
        '''
        Remove a reaction from reaction message

        Parameters
        ------------
        msg_name: str
            The message name of the saved message in settings file
        role_name: str
            Name of a role that is connected to a reaction in the message
        '''
        # Get message ID
        roles_settings = file_io.read_json(envs.roles_settings_file)
        reaction_messages = roles_settings['reaction_messages']
        if msg_name not in reaction_messages:
            await ctx.reply(f'Could not find {msg_name}')
            return
        # Fetch message
        msg_id = reaction_messages[msg_name]['id']
        channel = reaction_messages[msg_name]['channel']
        _guild = discord_commands.get_guild()
        _channels = discord_commands.get_text_channel_list()
        _channel = _guild.get_channel(_channels[channel])
        _msg = await _channel.fetch_message(msg_id)
        _roles = discord_commands.get_roles()
        # read msg embed
        embed_desc = _msg.embeds[0].description
        new_embed_desc = ''
        # identify role/emoji
        emoji = None
        reactions = reaction_messages[msg_name]['reactions']
        for reaction in reactions:
            if role_name.lower() == reaction[0].lower():
                emoji = reaction[1]
                log.debug(f'Got this emoji {emoji}')
        embed_desc_list = embed_desc.splitlines(keepends=True)
        for line in embed_desc_list:
            if emoji in line and str(_roles[role_name]['id']) in line:
                del embed_desc_list[embed_desc_list.index(line)]
        new_embed_desc = ''.join(item for item in embed_desc_list)
        embed_json = {
            'description': new_embed_desc
        }
        await _msg.edit(embed=discord.Embed.from_dict(embed_json))
        await _msg.clear_reaction(emoji=emoji)
        for reaction in reactions:
            if role_name == reaction[0]:
                del reactions[reactions.index(reaction)]
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
        roles_settings = file_io.read_json(envs.roles_settings_file)
        reaction_messages = roles_settings['reaction_messages']
        _guild = discord_commands.get_guild()
        for reaction_message in reaction_messages:
            if payload.message_id == reaction_messages[reaction_message]['id']:
                reactions = reaction_messages[reaction_message]['reactions']
                for reaction in reactions:
                    print(payload.emoji.name)
                    print(reaction[1])
                    if re.match(r'(<:)?{}(:\d+>)?'.format(
                                    reaction[1]
                            ), payload.emoji.name):
                        for _role in _guild.roles:
                            if _role.name.lower() == reaction[0].lower():
                                log.debug(f'Adding role {reaction[0]} to user')
                                await _guild.get_member(
                                    payload.user_id
                                ).add_roles(
                                    _role,
                                    reason='Added in accordance with reaction '
                                           f'message {reaction_message}'
                                )
                                continue
        return

    @config.bot.event
    async def on_raw_reaction_remove(payload):
        roles_settings = file_io.read_json(envs.roles_settings_file)
        reaction_messages = roles_settings['reaction_messages']
        _guild = discord_commands.get_guild()
        for reaction_message in reaction_messages:
            if payload.message_id == reaction_messages[reaction_message]['id']:
                reactions = reaction_messages[reaction_message]['reactions']
                for reaction in reactions:
                    print(payload.emoji.name)
                    print(reaction[1])
                    if re.match(r'(<:)?{}(:\d+>)?'.format(
                                    reaction[1]
                            ), payload.emoji.name):
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
                                continue
        return


# Maintain unique roles
_unique_role_settings = settings['unique_role']
if isinstance(_unique_role_settings['role'], str) and\
        len(_unique_role_settings['role']) > 0:
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
        if len(after.roles) > len(before.roles):
            # TODO var msg
            log.debug('Flere nye roller etter endring')
            _unique_role = _unique_role_settings['role']
            for _role in before.roles:
                if _role.id == _unique_role:
                    for __role in after.roles:
                        if __role.id == _unique_role:
                            log.debug('Unique role still in `after.roles`')
                            await after.remove_roles(
                                discord_commands.get_guild().get_role(
                                    _unique_role
                                )
                            )
                            return
                    log.debug('Unique role not in `after.roles`')
                    if len(after.roles) > len(before.roles):
                        log.debug('...and ')
        else:
            # TODO var msg
            log.debug('Færre nye roller etter endring')
            # Exclude roles in .env, as well as @everyone
            excluded_roles = len(
                _unique_role_settings['not_include_in_total']
            )+1
            if (len(after.roles) - excluded_roles) == 0:
                log.debug('Add unique role again')
                await after.add_roles(
                    discord_commands.get_guild().get_role(
                        _unique_role
                    )
                )
