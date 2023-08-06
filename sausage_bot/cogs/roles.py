#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands
import discord

from sausage_bot.util import config, envs, file_io, discord_commands
from sausage_bot.util.log import log

class Autoroles(commands.Cog):
    'Manage roles and settings'

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='roles')
    async def guildroles(self, ctx):
        'Control roles on the server'
        return

    @guildroles.group(name='info', aliases=['i'])
    async def role_info(self, ctx, role_name):
        '''
        Get info about a role

        Parameters
        ------------
        role_name: str
            The role name to get info about (default: None)
        '''

        _guild = discord_commands.get_guild()
        if role_name is not None and len(role_name) > 0:
            _roles = _guild.roles
            _var_roles = ';'.join([role.name for role in _roles])
            print(_var_roles)
            for _role in _roles:
                log.debug(f'Sjekker `_role`: {_role}')
                if str(_role.name).lower() == role_name.lower():
                    log.debug(f'Fant `{role_name}`')
                    embed = discord.Embed(color=_role.color)
                    #embed.description()     # string
                    #embed.set_thumbnail(url=_role.icon)
                    embed.add_field(name="ID", value=_role.id, inline=True)
                    embed.add_field(
                        name="Farge", value=_role.color, inline=True
                    )
                    if _role.is_bot_managed() or _role.is_integration:
                        _value = "Ja"
                        if _role.tags.bot_id:
                            _manager = _guild.get_member(
                                _role.tags.bot_id
                            ).name
                            _value += f', av {_manager}'
                        embed.add_field(
                            name="Autohåndteres", value=_value,
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
            log.debug(f'Fant ikke rollen `{role_name}`')
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
        color: str, hoist: bool, mentionable: bool
    ):
        '''
        Add role to the server

        Parameters
        ------------
        role_name: str
            The names of the role to add (default: None)
        color: str
            Set color for the role
        hoist: bool
            Set if the role should be mentionable or not
        mentionable: bool
            Set if the role should be mentionable or not
        '''

        if role_name is None:
            # todo var msg
            log.log('Role has no name')
            await ctx.message.reply('Role has no name')
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
    async def user(self, ctx):
        'Manage a user\'s roles'
        return

    @user.group(name='add', aliases=['a'])
    async def user_add(self, ctx, user_name: str, *role_names):
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
                    print(__role.name, _role)
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

    @user.group(name='remove', aliases=['delete', 'r', 'd'])
    async def user_remove(self, ctx, user_name, *role_names):
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


async def setup(bot):
    log.log(envs.COG_STARTING.format('autoroles'))
    log.log_more(envs.CREATING_FILES)
    check_and_create_files = [
        (envs.role_settings_file, {})
    ]
    file_io.create_necessary_files(check_and_create_files)
    await bot.add_cog(Autoroles(bot))


_unique_role = config.env.int('ROLES_UNIQUE', default=None)
if _unique_role is not None:
    # TODO var msg
    log.debug('`ROLES_UNIQUE` oppdaget i innstillinger')
    @config.bot.event
    async def on_member_update(before, after):
        '''
        If a role ID is set in `ROLES_UNIQUE` in the bot\'s .env file,
        it will make sure that if a user has 0 roles, it will automatically
        get the unique role.
        If roles are specified in the `ROLES_UNIQUE_NOT_INCLUDE_IN_TOTAL`
        in the .env file, these will not be counted in the total of a users
        role to make sure the total number will be correct
        '''
        if len(after.roles) > len(before.roles):
            # TODO var msg
            log.debug('Flere nye roller etter endring')
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
                config.env.list(
                    'ROLES_UNIQUE_NOT_INCLUDE_IN_TOTAL',
                    default=[]
                )
            )+1
            if (len(after.roles) - excluded_roles) == 0:
                log.debug('Add unique role again')
                await after.add_roles(
                    discord_commands.get_guild().get_role(
                        _unique_role
                    )
                )
