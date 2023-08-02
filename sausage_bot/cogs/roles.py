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

    @commands.group(name='role')
    async def guildrole(self, ctx):
        'Control roles on the server'
        return

    @guildrole.group(name='info', aliases=['i'])
    async def info(
        self, ctx,
        role_name: str = commands.param(
            default=None,
            description="Role name"
        )
    ):
        'Get info about a role'
        _guild = discord_commands.get_guild()
        if role_name is not None and len(role_name)>0:
            _roles = _guild.roles
            for _role in _roles:
                log.debug(f'Sjekker `_role`: {_role}')
                if str(_role.name).lower() == role_name.lower():
                    log.debug(f'Fant `{role_name}`')
                    embed = discord.Embed(color=_role.color)
                    #embed.description()     # string
                    #embed.set_thumbnail(url=_role.icon)
                    embed.add_field(name="ID", value=_role.id, inline=True)
                    embed.add_field(name="Farge", value=_role.color, inline=True)
                    if _role.is_bot_managed() or _role.is_integration:
                        if _role.tags.bot_id:
                            _manager = _guild.get_member(_role.tags.bot_id).name
                        embed.add_field(
                            name="Autohåndteres", value=f"Ja, av '{_manager}'",
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
            header = 'Brukere uten roller:'
            out = ''
            for member in _guild.members:
                if len(member.roles) == 1:
                    if (len(out) + len(member.name)) > 1800:
                        ctx.send(out)
                        out = ''
                    if out == '':
                        out += header
                    out += f'\n- {member.name}'
            await ctx.send(out)
        return

    @guildrole.group(name='manage', aliases=['m'])
    async def manage(self, ctx):
        'Manage specific roles on the server'
        return

    @manage.group(name='add', aliases=['a'])
    async def add_role(
        self, ctx,
        role_name: str = commands.param(
            default=None,
            description="Role name"
        ),
        permissions: str = commands.param(
            default=discord.Permissions.none(),
            description="Set permissions for the role"
        ),
        color: str = commands.param(
            default='',
            description="Set color for the role"
        ),
        hoist: str = commands.param(
            default=False,
            description="Set if the role should be mentionable or not"
        ),
        mentionable: str = commands.param(
            default=False,
            description="Set if the role should be mentionable or not"
        )
    ):
        'Add role to the server'
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

    @manage.group(name='remove', aliases=['delete', 'r', 'd'])
    async def remove_role(
        self, ctx,
        role_name: str = commands.param(
            default=None,
            description="Role name"
        )
    ):
        'Remove a role from the server'
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

    @manage.group(name='edit', aliases=['e'])
    async def edit_role(
        self, ctx,
        role_name: str = commands.param(
            default=None,
            description="Role name"
        ),
        new_role_name: str = commands.param(
            default=None,
            description="Role name to change to"
        ),
        permissions: str = commands.param(
            default=discord.Permissions.none(),
            description="Set permissions for the role"
        ),
        color: str = commands.param(
            default='',
            description="Set color for the role"
        ),
        hoist: str = commands.param(
            default=False,
            description="Set if the role should be mentionable or not"
        ),
        mentionable: str = commands.param(
            default=False,
            description="Set if the role should be mentionable or not"
        )
    ):
        'Add role to the server'
        if role_name is None:
            # todo var msg
            log.log('Role has no name')
            await ctx.message.reply('Role has no name')
            return
        _guild = discord_commands.get_guild()
        _roles = _guild.roles
        for _role in _roles:
            log.debug(f'Sjekker `_role`: {_role}')
            if _role.name == role_name:
                log.debug(f'Fant {role_name}, sletter...')
                await _guild.get_role(int(_role.id)).edit(
                    role_name=new_role_name,
                    permissions=permissions,
                    color=color,
                    hoist=hoist,
                    mentionable=mentionable
                )
                await ctx.message.reply('Role has been changed')
                return
        log.log(f'Fant ikke `{role_name}`')
        return

    @guildrole.group(name='user')
    async def user(self, ctx):
        'Manage a user\'s roles'
        return

    @user.group(name='add', aliases=['a'])
    async def user_add(
        self, ctx,
        user_name: str = commands.param(
            default=None,
            description="User name"
        ),
        *role_names
    ):
        'Add role(s) to a user'
        if role_names is None or user_name is None:
            # todo var msg
            var_msg = '`Role names` and `User name` is mandatory'
            log.log(var_msg)
            await ctx.message.reply(var_msg)
            return
        _guild = discord_commands.get_guild()
        _roles = _guild.roles
        _temp_roles = []
        for _role in _roles:
            log.debug(f'Sjekker `_role`: {_role}')
            if _role.name in role_names:
                _temp_roles.append(_role)
        _member = _guild.get_member_named(user_name)
        if _member is None:
            log.log(f'Could not find user {user_name}')
            return
        for role in _temp_roles:
            await _member.add_roles(role)
        await ctx.message.reply(
            'User {} has been given these roles: {}'.format(
                user_name, ', '.join(role_names)
            )
        )
        return

    @user.group(name='remove', aliases=['delete', 'r', 'd'])
    async def user_remove(
        self, ctx,
        user_name: str = commands.param(
            default=None,
            description="User name"
        ),
        *role_names
    ):
        'Remove roles from a user'
        if role_names is None or user_name is None:
            # todo var msg
            var_msg = '`Role names` and `User name` is mandatory'
            log.log(var_msg)
            await ctx.message.reply(var_msg)
            return
        _guild = discord_commands.get_guild()
        _roles = _guild.roles
        _temp_roles = []
        for _role in _roles:
            log.debug(f'Sjekker `_role`: {_role}')
            if _role.name in role_names:
                _temp_roles.append(_role)
        _member = _guild.get_member_named(user_name)
        if _member is None:
            log.log(f'Could not find user {user_name}')
            return
        for role in _temp_roles:
            await _member.remove_roles(role)
        var_msg = 'User {} has been removed from these roles: {}'.format(
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
