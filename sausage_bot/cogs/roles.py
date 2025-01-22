#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import discord
from discord.ext import commands
from discord.utils import get
from discord.app_commands import locale_str, describe
from tabulate import tabulate
import re
import typing

from sausage_bot.util import config, envs, file_io, discord_commands, db_helper
from sausage_bot.util.i18n import I18N
from sausage_bot.util.log import log


class DropdownPermissions(discord.ui.Select):
    def __init__(
            self, placeholder_in, options_out, options_in
    ):
        super().__init__(
            placeholder=placeholder_in,
            min_values=0,
            max_values=len(options_in),
            options=options_in
        )
        self.options_out = options_out
        self.options_in = options_in

    async def callback(
        self, interaction: discord.Interaction
    ):
        for opt in self.options_in:
            if opt.label in self.values:
                opt.default = True
            else:
                opt.default = False
        await interaction.response.edit_message(view=self.view)
        self.options_out += self.values


class ButtonConfirm(discord.ui.Button):
    def __init__(self, label):
        super().__init__(style=discord.ButtonStyle.green, label=label)

    async def callback(
        self, interaction: discord.Interaction
    ):
        self.disabled = True
        buttons = [x for x in self.view.children]
        for _btn in buttons:
            _btn.disabled = True
        await interaction.response.edit_message(view=self.view)
        self.view.stop()


class PermissionsView(discord.ui.View):
    def __init__(self, permissions_in=None):
        def prep_dropdown(perm_name, permissions_in: dict = None):
            list_out = []
            for perm in envs.SELECT_PERMISSIONS[perm_name]:
                _desc = envs.SELECT_PERMISSIONS[perm_name][perm]
                if len(_desc) >= 100:
                    _desc = f'{str(_desc):.90}...'
                if isinstance(permissions_in, (dict, list)) and\
                        perm in permissions_in:
                    list_out.append(
                        discord.SelectOption(
                            label=perm,
                            description=_desc,
                            value=perm,
                            default=True
                        )
                    )
                else:
                    list_out.append(
                        discord.SelectOption(
                            label=perm,
                            description=_desc,
                            value=perm
                        )
                    )
            return list_out

        super().__init__(timeout=120)
        self.permissions_out = []
        self.permissions_in = permissions_in

        general_perms = prep_dropdown(
            'general', self.permissions_in
        )
        text_perms = prep_dropdown(
            'text', self.permissions_in
        )
        voice_perms = prep_dropdown(
            'voice', self.permissions_in
        )

        general_dropdown = DropdownPermissions(
            I18N.t('roles.views.perms.drop_general'),
            self.permissions_out, general_perms
        )
        text_dropdown = DropdownPermissions(
            I18N.t('roles.views.perms.drop_text'),
            self.permissions_out, text_perms
        )
        voice_dropdown = DropdownPermissions(
            I18N.t('roles.views.perms.drop_voice'),
            self.permissions_out, voice_perms
        )

        self.add_item(general_dropdown)
        self.add_item(text_dropdown)
        self.add_item(voice_dropdown)
        button_ok = ButtonConfirm('OK')
        self.add_item(button_ok)


async def settings_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    settings_db = await db_helper.get_output(
        template_info=envs.roles_db_settings_schema,
        get_row_ids=True
    )
    print(f'SETTINGS_DB: {settings_db}')
    temp_settings = settings_db.copy()
    for setting in temp_settings:
        list_num = settings_db.index(setting)
        temp_settings[list_num]['name'] = get(
            discord_commands.get_guild().roles,
            id=int(setting['value'])
        ).name
    log.debug(f'`settings_db`: {settings_db}')
    return [
        discord.app_commands.Choice(
            name='{}. {} = {} ({})'.format(
                setting['rowid'], setting['setting'], setting['name'],
                setting['value']
            ),
            value=str(setting['rowid'])
        )
        for setting in temp_settings
        if current.lower() in '{}-{}-{}-{}'.format(
            setting['rowid'], setting['setting'], setting['name'],
            setting['value']
        ).lower()
    ]


async def get_msg_id_and_name(msg_id_or_name):
    '''
    Get msg id, channel and message name from database
    based on msg id or msg name
    '''
    msg_id_or_name = str(msg_id_or_name)
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
        select=('msg_id', 'channel', 'name'),
        single=True
    )
    log.verbose(f'db_message: {db_message}', color='yellow')
    return {
        'id': db_message['msg_id'],
        'channel': db_message['channel'],
        'name': db_message['name']
    }


async def strip_role_or_emoji(input):
    log.debug(f'Input is type {type(input)}')
    input_check = re.match(r'<.*\b(\d+)>', input)
    if input_check:
        return input_check.group(1)
    elif not input_check:
        return input


async def sync_reaction_message_from_settings(
        msg_id_or_name, sorting: bool = False
):
    # Assert that the reaction message exist on discord
    msg_info = await get_msg_id_and_name(msg_id_or_name)
    _guild = discord_commands.get_guild()
    log.debug('msg_info', pretty=msg_info)
    msg_id = msg_info['id']
    msg_channel = msg_info['channel']
    log.verbose(f'`msg_info` is {msg_info}')
    msg_obj = await discord_commands.get_message_obj(
        msg_id=msg_id,
        channel_id=msg_channel
    )
    log.verbose(f'`msg_obj` is {msg_obj}')
    if msg_obj is None:
        # If the message has been deleted, it needs to be recreated,
        # and msg_id in databases must be updated
        log.verbose('Creating a new message')
        db_message = await db_helper.get_output(
            template_info=envs.roles_db_msgs_schema,
            where=[
                ('msg_id', msg_id)
            ]
        )
        # Make a placeholder message
        msg_obj = await discord_commands.post_to_channel(
            msg_channel, content_in='placeholder'
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
        ],
        single=True
    )
    log.verbose(f'db_message: {db_message}')
    db_reactions = await db_helper.get_output(
        envs.roles_db_roles_schema,
        select=('role', 'emoji'),
        where=[
            ('msg_id', msg_id)
        ],
    )
    log.verbose(f'db_reactions: {db_reactions}')
    reactions_out = {}
    for react in db_reactions:
        log.debug('Processing `react`', pretty=react)
        role_name = get(
            _guild.roles, id=int(react['role'])
        ).name
        reactions_out[role_name] = {
            'role_id': react['role'],
            'emoji': react['emoji']
        }
    if sorting:
        reactions_out = dict(sorted(reactions_out.items()))
    log.verbose(f'reactions_out: {reactions_out}')
    # Recreate the embed
    new_embed_desc = ''
    new_embed_content = ''
    await msg_obj.clear_reactions()
    # Add header if in db
    new_embed_header = db_message['header']
    if new_embed_header:
        new_embed_content += f'## {new_embed_header}'
    for reaction in reactions_out:
        _emoji_id = reactions_out[reaction]['emoji']
        _role_id = reactions_out[reaction]['role_id']
        log.debug('Trying to add emoji: `{}`'.format(_emoji_id))
        if re.match(r'(\d+)', _emoji_id):
            emoji_out = get(_guild.emojis, id=int(_emoji_id))
        else:
            emoji_out = _emoji_id
        log.debug(f'`emoji_out` ({type(emoji_out)}) is `{emoji_out}`')
        await msg_obj.add_reaction(emoji_out)
        if len(new_embed_content) > 0:
            new_embed_content += '\n'
        new_embed_content += db_message['content']
        if len(new_embed_desc) > 0:
            new_embed_desc += '\n'
        new_embed_desc += '{} {}'.format(
            emoji_out,
            get(_guild.roles, id=int(_role_id))
        )
    embed_json = {
        'description': new_embed_desc,
        'content': new_embed_content
    }
    # Edit discord message
    await msg_obj.edit(
        content=db_message['content'],
        embed=discord.Embed.from_dict(embed_json)
    )
    return


def tabulate_emoji(dict_in):
    content = {
        'emoji': {
            'length': 7,
            'header': 'Emoji'
        },
        'name': {
            'length': 0,
            'header': 'Navn'
        },
        'id': {
            'length': 20,
            'header': 'ID'
        },
        'animated': {
            'length': 11,
            'header': 'Animert?'
        },
        'managed': {
            'length': 17,
            'header': 'Auto-håndtert?'
        }
    }
    for dict_item in dict_in:
        for item in dict_in[dict_item]:
            if len(str(item)) > content[dict_item]['length']:
                content[dict_item]['length'] = len(str(item)) + 1
    header = '`    {:>{}} {:>{}} {:>{}} {:>{}}`'.format(
        content['name']['header'],
        content['name']['length'],
        content['id']['header'],
        content['id']['length'],
        content['animated']['header'],
        content['animated']['length'],
        content['managed']['header'],
        content['managed']['length'],
    )
    paginated = []
    temp_out = header
    counter = 0
    while counter < len(dict_in['name']):
        line_out = '{}  `{:>{}} {:>{}} {:>{}} {:>{}}`'.format(
            dict_in['emoji'][counter],
            dict_in['name'][counter],
            content['name']['length'],
            dict_in['id'][counter],
            content['id']['length'],
            dict_in['animated'][counter],
            content['animated']['length'],
            dict_in['managed'][counter],
            content['managed']['length'],
        )
        if len(temp_out) + len(line_out) > 1900:
            log.debug('Hit 1900 mark')
            paginated.append(temp_out)
            temp_out = header
            temp_out += f'\n{line_out}'
        else:
            temp_out += f'\n{line_out}'
        counter += 1
    paginated.append(temp_out)
    return paginated


def tabulate_roles(dict_in):
    content = {
        'emoji': {
            'length': 7,
            'header': I18N.t('roles.roles_headers.emoji')
        },
        'name': {
            'length': 0,
            'header': I18N.t('roles.roles_headers.name')
        },
        'id': {
            'length': 20,
            'header': I18N.t('roles.roles_headers.id')
        },
        'members': {
            'length': 8,
            'header': I18N.t('roles.roles_headers.members')
        },
        'managed': {
            'length': 17,
            'header': I18N.t('roles.roles_headers.managed')
        }
    }
    for dict_item in dict_in:
        for item in dict_in[dict_item]:
            if len(str(item)) > content[dict_item]['length']:
                content[dict_item]['length'] = len(str(item)) + 1
    header = '`    {:>{}} {:>{}} {:>{}} {:>{}}`'.format(
        content['name']['header'],
        content['name']['length'],
        content['id']['header'],
        content['id']['length'],
        content['members']['header'],
        content['members']['length'],
        content['managed']['header'],
        content['managed']['length'],
    )
    paginated = []
    temp_out = header
    counter = 0
    while counter < len(dict_in['name']):
        line_out = '{}  `{:>{}} {:>{}} {:>{}} {:>{}}`'.format(
            dict_in['emoji'][counter],
            dict_in['name'][counter],
            content['name']['length'],
            dict_in['id'][counter],
            content['id']['length'],
            dict_in['members'][counter],
            content['members']['length'],
            dict_in['managed'][counter],
            content['managed']['length'],
        )
        if len(temp_out) + len(line_out) > 1900:
            log.debug('Hit 1900 mark')
            paginated.append(temp_out)
            temp_out = header
            temp_out += f'\n{line_out}'
        else:
            temp_out += f'\n{line_out}'
        counter += 1
    paginated.append(temp_out)
    return paginated


def tabulate_emojis_and_roles(dict_in):
    content = {
        'emoji': {
            'length': 1,
        },
        'emoji_name': {
            'length': len(str(
                I18N.t('roles.tabulate_emojis_and_roles.emoji_name')
            )),
            'header': I18N.t('roles.tabulate_emojis_and_roles.emoji_name')
        },
        'emoji_id': {
            'length': 19,
            'header': str(I18N.t('roles.tabulate_emojis_and_roles.emoji_id'))
        },
        'role_name': {
            'length': len(str(
                I18N.t('roles.tabulate_emojis_and_roles.role_name')
            ))+1,
            'header': str(I18N.t('roles.tabulate_emojis_and_roles.role_name'))
        },
        'role_id': {
            'length': 19,
            'header': str(I18N.t('roles.tabulate_emojis_and_roles.role_id'))
        }
    }
    for dict_item in dict_in:
        log.debug(f'Processing: {dict_item}')
        for item in dict_in[dict_item]:
            if len(str(item)) > content[dict_item]['length']:
                content[dict_item]['length'] = len(str(item)) + 1
    header = '`   {:{}} {:{}} {:{}} {:{}}`'.format(
        content['emoji_name']['header'],
        content['emoji_name']['length'],
        content['emoji_id']['header'],
        content['emoji_id']['length'],
        content['role_name']['header'],
        content['role_name']['length'],
        content['role_id']['header'],
        content['role_id']['length']
    )
    paginated = []
    temp_out = header
    counter = 0
    while counter <= len(dict_in['emoji_id'])-1:
        line_out = '{} `{:{}} {:{}} {:{}} {:{}}`'.format(
            '<:{}:{}>'.format(
                dict_in['emoji_name'][counter],
                dict_in['emoji_id'][counter]
            ),
            dict_in['emoji_name'][counter], content['emoji_name']['length'],
            dict_in['emoji_id'][counter], content['emoji_id']['length'],
            dict_in['role_name'][counter], content['role_name']['length'],
            dict_in['role_id'][counter], content['role_id']['length']
        )
        if len(line_out) == 0:
            line_out = temp_out
        if (len(temp_out) + len(line_out)) > 1900:
            log.debug('Hit 1900 mark')
            paginated.append(temp_out)
            temp_out = header
            temp_out += f'\n{line_out}'
        else:
            temp_out += f'\n{line_out}'
        counter += 1
    paginated.append(temp_out)
    return paginated


def paginate_tabulate(tabulated):
    log.debug(f'Length of `tabulated` is {len(tabulated)}')
    paginated = []
    temp_out = ''
    if len(tabulated) >= 1900:
        tabulated_split = tabulated.splitlines(keepends=True)
        temp_out += tabulated_split[0]
        for line in tabulated_split[1:]:
            if len(temp_out) + len(line) > 1900:
                log.debug('Hit 1900 mark')
                paginated.append(temp_out)
                temp_out = ''
                temp_out += tabulated_split[0]
                temp_out += line
            else:
                temp_out += line
        paginated.append(temp_out)
    else:
        paginated.append(tabulated)
    return paginated


async def reaction_msgs_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    db_reactions = await db_helper.get_output(
        template_info=envs.roles_db_msgs_schema,
        select=('name', 'msg_id'),
        order_by=[
            ('name', 'ASC')
        ]
    )
    log.debug(f'db_reactions: {db_reactions}')
    return [
        discord.app_commands.Choice(
            name=str(reaction['name']), value=str(reaction['msg_id'])
        )
        for reaction in db_reactions if current.lower() in '{}-{}'.format(
            reaction['name'], reaction['msg_id']
        ).lower()
    ]


async def reaction_msgs_roles_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    db_reactions = await db_helper.get_output(
        template_info=envs.roles_db_msgs_schema,
        select=('name', 'msg_id'),
        order_by=[
            ('name', 'ASC')
        ]
    )
    reactions = []
    for reaction in db_reactions:
        reactions.append((reaction['name'], reaction['msg_id']))
    log.debug(f'reactions: {reactions}')
    return [
        discord.app_commands.Choice(
            name=str(reaction['name']), value=str(reaction['msg_id'])
        )
        for reaction in reactions if current.lower() in '{}-{}'.format(
            reaction['name'], reaction['msg_id']
        ).lower()
    ]


async def emojis_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    _guild = discord_commands.get_guild()
    _emojis = _guild.emojis
    _emojis_list = []
    for emoji in _emojis:
        _emojis_list.append((
            emoji.name, '<:{}:{}>'.format(
                emoji.name, emoji.id
            )
        ))
    log.debug(f'_emojis_list: {_emojis_list}')
    return [
        discord.app_commands.Choice(
            name=str(emoji[0]),
            value=str(emoji[1])
        )
        for emoji in _emojis_list if current.lower() in emoji[0].lower()
    ]


async def combine_roles_and_emojis(roles_in, emojis_in):
    '''Do splits of roles and emojis to make sure the lengths are identical'''
    log.debug(f'Got `roles_in`: {roles_in}')
    log.debug(f'Got `emojis_in`: {emojis_in}')
    emoji_split = []
    _roles = re.split(
        envs.input_split_regex, roles_in.replace(
            envs.roles_ensure_separator[0], envs.roles_ensure_separator[1]
        )
    )
    role_split = [await strip_role_or_emoji(_role) for _role in _roles]
    _emojis = re.split(
        envs.input_split_regex, emojis_in.replace(
            envs.roles_ensure_separator[0], envs.roles_ensure_separator[1]
        )
    )
    emoji_split = [await strip_role_or_emoji(_emoji) for _emoji in _emojis]
    if len(_roles) != len(_emojis):
        log.log(
            f'Number of roles ({len(_roles)}) and emojis ({len(_emojis)})'
            'are not the same'
        )
        return None
    # Process the splits
    return tuple(zip(role_split, emoji_split))


class Autoroles(commands.Cog):
    'Manage roles and settings'

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    roles_group = discord.app_commands.Group(
        name="roles", description=locale_str(
            I18N.t('roles.commands.roles.cmd')
        )
    )

    roles_reaction_group = discord.app_commands.Group(
        name="reaction", description=locale_str(I18N.t(
            'roles.commands.reaction.cmd'
        )),
        parent=roles_group
    )

    roles_reaction_add_group = discord.app_commands.Group(
        name="reaction_add", description=locale_str(I18N.t(
            'roles.commands.reaction_add.cmd'
        )),
        parent=roles_group
    )

    roles_reaction_remove_group = discord.app_commands.Group(
        name="reaction_remove",
        description=locale_str(I18N.t('roles.commands.reaction_remove.cmd')),
        parent=roles_group
    )

    roles_settings_group = discord.app_commands.Group(
        name="settings", description=locale_str(I18N.t(
            'roles.commands.settings_group'
        )),
        parent=roles_group
    )

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_group.command(
        name='info',
        description=locale_str(I18N.t('roles.commands.info.cmd'))
    )
    @describe(
        public=I18N.t('roles.commands.info.desc.public'),
        role_in=I18N.t('roles.commands.info.desc.role_in')
    )
    async def role_info(
        self, interaction: discord.Interaction,
        public: typing.Literal[
            I18N.t('common.literal_yes_no.yes'),
            I18N.t('common.literal_yes_no.no')
        ],
        role_in: discord.Role
    ):
        '''
        Get info about a specific role (`role_in`)

        Parameters
        ------------
        role_name: str
            The role name to get info about (default: None)
        '''
        if public == I18N.t('common.literal_yes_no.yes'):
            _ephemeral = False
        elif public == I18N.t('common.literal_yes_no.no'):
            _ephemeral = True
        await interaction.response.defer(ephemeral=_ephemeral)
        embed = discord.Embed(color=role_in.color)
        embed.set_thumbnail(url=role_in.icon)
        embed.add_field(name="ID", value=role_in.id, inline=True)
        embed.add_field(
            name="Farge", value=role_in.color, inline=True
        )
        if role_in.is_bot_managed():
            embed.add_field(
                name="Autohåndteres",
                value='Ja, av {}'.format(role_in.name),
                inline=True
            )
        elif role_in.is_integration():
            embed.add_field(
                name="Autohåndteres",
                value='Ja, av {}'.format(
                    role_in.tags.integration_id
                ),
                inline=True
            )
        else:
            embed.add_field(
                name="Autohåndteres", value="Nei", inline=True
            )
        embed.add_field(
            name="Spesielt synlig",
            value='Ja' if role_in.hoist else 'Nei',
            inline=True
        )
        embed.add_field(
            name="Brukere med rollen",
            value=len(role_in.members), inline=True
        )
        permissions = ", ".join(
            [permission for permission, value in
                iter(role_in.permissions) if value is True]
        )
        embed.add_field(
            name="Tillatelser",
            value=permissions if permissions else 'Ingen',
            inline=False
        )
        await interaction.followup.send(
            embed=embed, ephemeral=_ephemeral
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_group.command(
        name='list', description='List roles or emojis'
    )
    @describe(
        public=I18N.t('roles.commands.list.desc.public'),
        type=I18N.t('roles.commands.list.desc.type'),
        sort=I18N.t('roles.commands.list.desc.sort')
    )
    async def roles_list(
        self, interaction: discord.Interaction,
        public: typing.Literal[
            I18N.t('common.literal_yes_no.yes'),
            I18N.t('common.literal_yes_no.no')
        ],
        type: typing.Literal[
            I18N.t('roles.commands.list.literal.type.roles'),
            I18N.t('roles.commands.list.literal.type.emojis')
        ],
        sort: typing.Literal[
            I18N.t('roles.commands.list.literal.sort.name'),
            I18N.t('roles.commands.list.literal.sort.id')
        ]
    ):
        async def roles_list_roles():
            _guild = discord_commands.get_guild()
            tabulate_dict = {
                'emoji': [],
                'name': [],
                'id': [],
                'members': [],
                'managed': []
            }
            if sort == I18N.t('roles.commands.list.literal.sort.name'):
                _roles = tuple(sorted(
                    _guild.roles, key=lambda role: role.name.lower()
                ))
            elif sort == I18N.t('roles.commands.list.literal.sort.id'):
                _roles = tuple(sorted(
                    _guild.roles, key=lambda role: role.id
                ))
            for role in _roles:
                tabulate_dict['emoji'].append(role.display_icon)
                tabulate_dict['name'].append(role.name)
                tabulate_dict['id'].append(role.id)
                tabulate_dict['members'].append(len(role.members))
                if role.managed:
                    tabulate_dict['managed'].append(
                        I18N.t('common.literal_yes_no.yes')
                    )
                elif not role.managed:
                    tabulate_dict['managed'].append(
                        I18N.t('common.literal_yes_no.no')
                    )
            return tabulate_roles(tabulate_dict)

        async def roles_list_emojis():
            _guild = discord_commands.get_guild()
            tabulate_dict = {
                'emoji': [],
                'name': [],
                'id': [],
                'animated': [],
                'managed': []
            }
            if sort == I18N.t('roles.commands.list.literal.sort.name'):
                _emojis = tuple(sorted(
                    _guild.emojis, key=lambda emoji: emoji.name.lower()
                ))
            elif sort == I18N.t('roles.commands.list.literal.sort.id'):
                _emojis = tuple(sorted(
                    _guild.emojis, key=lambda emoji: emoji.id
                ))
            for emoji in _emojis:
                tabulate_dict['emoji'].append(
                    f'<:{emoji.name}:{emoji.id}>'
                )
                tabulate_dict['name'].append(emoji.name)
                tabulate_dict['id'].append(emoji.id)
                if emoji.animated:
                    tabulate_dict['animated'].append(
                        I18N.t('common.literal_yes_no.yes')
                    )
                else:
                    tabulate_dict['animated'].append(
                        I18N.t('common.literal_yes_no.no')
                    )
                if emoji.managed:
                    tabulate_dict['managed'].append(
                        I18N.t('common.literal_yes_no.yes')
                    )
                else:
                    tabulate_dict['managed'].append(
                        I18N.t('common.literal_yes_no.no')
                    )
            # Returning pagination
            return tabulate_emoji(
                type_in='roles_list_emoji',
                dict_in=tabulate_dict
            )

        if public == I18N.t('common.literal_yes_no.yes'):
            _ephemeral = False
        elif public == I18N.t('common.literal_yes_no.no'):
            _ephemeral = True
        await interaction.response.defer(ephemeral=_ephemeral)
        if type == I18N.t('roles.commands.list.literal.type.roles'):
            pages = await roles_list_roles()
        elif type == I18N.t('roles.commands.list.literal.type.emojis'):
            pages = await roles_list_emojis()
        for page in pages:
            log.verbose(f'{page}')
            await interaction.followup.send(
                f'{page}',
                ephemeral=_ephemeral
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_group.command(
        name='add', description=locale_str(I18N.t('roles.commands.add.cmd'))
    )
    @describe(
        role_name=I18N.t('roles.commands.add.desc.role_name'),
        hoist=I18N.t('roles.commands.add.desc.hoist'),
        mentionable=I18N.t('roles.commands.add.desc.mentionable'),
        color=I18N.t('roles.commands.add.desc.color'),
        display_icon=I18N.t('roles.commands.add.desc.display_icon')
    )
    async def add_role(
        self, interaction: discord.Interaction, role_name: str,
        hoist: bool, mentionable: bool, color: str = None,
        display_icon: discord.Attachment = None
    ):
        await interaction.response.defer(ephemeral=True)
        if not color:
            color = discord.Color.random()
        else:
            color = discord.Color.from_str(color)
        if display_icon:
            display_icon = await display_icon.read()
        perm_view = PermissionsView()
        await interaction.followup.send(
            I18N.t('roles.commands.add.set_perms'), view=perm_view
        )
        await perm_view.wait()
        # Get new permissions and add to role
        perms = perm_view.permissions_out
        perms_in = ''
        if len(perms) > 0:
            perms_in = ', '.join(f'{perm}=True' for perm in perms)
        # Create role in guild
        guild = discord_commands.get_guild()
        try:
            await guild.create_role(
                name=role_name,
                permissions=eval(f'discord.Permissions({perms_in})'),
                color=color,
                hoist=hoist,
                mentionable=mentionable,
                display_icon=display_icon
            )
            await interaction.followup.send(
                I18N.t('roles.commands.add.msg_confirm')
            )
        except discord.errors.Forbidden as e:
            await interaction.followup.send(
                I18N.t('roles.commands.add.msg_error', _error=e.text)
            )
            return
        except ValueError as e:
            await interaction.followup.send(
                I18N.t('roles.commands.add.msg_error', _error=e)
            )
            return
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_group.command(
        name='remove', description=locale_str(I18N.t(
            'roles.commands.remove.cmd'
        ))
    )
    @describe(
        role_name=I18N.t('roles.commands.remove.desc.role_name')
    )
    async def remove_role(
        self, interaction: discord.Interaction, role_name: discord.Role
    ):
        await interaction.response.defer(ephemeral=True)
        _guild = discord_commands.get_guild()
        rolename = role_name.name
        await _guild.get_role(int(role_name.id)).delete()
        await interaction.followup.send(
            I18N.t('roles.commands.remove.msg_confirm', rolename=rolename)
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_group.command(
        name='edit', description=locale_str(I18N.t('roles.commands.edit.cmd'))
    )
    @describe(
        role_name=I18N.t('roles.commands.edit.desc.role_name'),
        new_name=I18N.t('roles.commands.edit.desc.new_name'),
        color=I18N.t('roles.commands.edit.desc.color'),
        hoist=I18N.t('roles.commands.edit.desc.hoist'),
        permissions=I18N.t('roles.commands.edit.desc.permissions')
    )
    async def edit_role(
        self, interaction: discord.Interaction, role_name: discord.Role,
        permissions: bool, new_name: str = None, color: str = None,
        hoist: bool = None
    ):
        await interaction.response.defer(ephemeral=True)
        changes = []
        if new_name:
            log.debug('Changed name')
            i18n_name = I18N.t('roles.commands.edit.changelist_name')
            changes.append(f'\n- {i18n_name}: `{role_name}` -> `{new_name}`')
            await role_name.edit(
                name=new_name
            )
        if color:
            log.debug('Changed color')
            i18n_color = I18N.t('roles.commands.edit.changelist_color')
            changes.append(
                f'\n- {i18n_color}: `{role_name.color}` -> `{color}`'
            )
            await role_name.edit(
                color=discord.Color.from_str(color)
            )
        if hoist:
            log.debug('Changed hoist setting')
            i18n_hoist = I18N.t('roles.commands.edit.changelist_hoist')
            changes.append(
                f'\n- {i18n_hoist}: `{role_name.hoist}` -> `{hoist}`'
            )
            await role_name.edit(
                hoist=hoist
            )
        if permissions:
            perms_in = []
            log.debug(f'`role_name.permissions`: {role_name.permissions}')
            for perm in role_name.permissions:
                if perm[1] is True:
                    perms_in.append(perm[0])
            log.debug(f'`perms_in`: {perms_in}')
            perm_view = PermissionsView(
                permissions_in=perms_in
            )
            await interaction.followup.send(
                I18N.t("roles.commands.edit.change_perms"), view=perm_view
            )
            await perm_view.wait()
            perms_out = perm_view.permissions_out
            log.debug(
                f'`perm_view.permissions_out`: {perm_view.permissions_out}'
            )
            new_perms = ''
            if len(perms_out) > 0:
                new_perms = ', '.join(f'{perm}=True' for perm in perms_out)
            # Edit role in guild
            await role_name.edit(
                permissions=eval(f'discord.Permissions({new_perms})')
            )
            log.debug('Changed permissions')
            perms_in_text = ', '.join(perm for perm in perms_in)
            perms_out_text = ', '.join(perm for perm in perms_out)
            i18n_perms = I18N.t('roles.commands.edit.change_perms')
            changes.append(
                f'\n- {i18n_perms}: `{perms_in_text}` -> `{perms_out_text}`'
            )
        if len(changes) > 0:
            changes_out = '{}:'.format(
                I18N.t(
                    'roles.commands.edit.changes_out',
                    role_name=role_name.name
                )
            )
            for change in changes:
                changes_out += change
            await interaction.followup.send(
                changes_out
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @describe(
        reaction_msg=I18N.t('roles.commands.react_list.desc.reaction_msg')
    )
    @discord.app_commands.autocomplete(reaction_msg=reaction_msgs_autocomplete)
    @roles_reaction_group.command(
        name='list', description=locale_str(I18N.t(
            'roles.commands.react_list.cmd'
        ))
    )
    async def list_reactions(
        self, interaction: discord.Interaction,
        reaction_msg: str = None
    ):
        await interaction.response.defer(ephemeral=True)
        if reaction_msg:
            db_reactions = await db_helper.get_combined_output(
                envs.roles_db_msgs_schema,
                envs.roles_db_roles_schema,
                key='msg_id',
                select=[
                    'name',
                    'content',
                    'channel',
                    'A.msg_id',
                    'role',
                    'emoji'
                ],
                where=[
                    ('A.msg_id', reaction_msg)
                ]
            )
            log.verbose('db_reactions: ', pretty=db_reactions)
            if len(db_reactions) <= 0 or db_reactions is None:
                await interaction.followup.send(
                    I18N.t(
                        'roles.commands.react_list.msg_error',
                        reaction_msg=reaction_msg
                    )
                )
                return
            tabulate_dict = {
                'emoji_id': [],
                'emoji_name': [],
                'role_id': [],
                'role_name': []
            }
            for reaction in db_reactions:
                if re.match(r'\d{19,22}', reaction['role']):
                    role = get(
                        discord_commands.get_guild().roles,
                        id=int(reaction['role'])
                    )
                    role_name = role.name
                    role_id = role.id
                else:
                    role_name = I18N.t('roles.commands.react_list.role_error')
                    role_id = reaction['role']
                if re.match(r'\d{19,22}', reaction['emoji']):
                    emoji = get(
                        discord_commands.get_guild().emojis,
                        id=int(reaction['emoji'])
                    )
                    emoji_name = emoji.name
                    emoji_id = emoji.id
                else:
                    emoji_name = I18N.t(
                        'roles.commands.react_list.emoji_error')
                    emoji_id = reaction['emoji']
                tabulate_dict['emoji_id'].append(emoji_id)
                tabulate_dict['emoji_name'].append(emoji_name)
                tabulate_dict['role_id'].append(role_id)
                tabulate_dict['role_name'].append(role_name)
            tabulated_reactions = tabulate_emojis_and_roles(tabulate_dict)
            await interaction.followup.send(
                '{}: `{}`\n{}: `{}`\n{}: `{}`\n'
                '{}: `{}`\n\n{}'.format(
                    I18N.t('common.name'), db_reactions[0]['name'],
                    I18N.t('common.channel'), db_reactions[0]['channel'],
                    I18N.t('common.message_id'), db_reactions[0]['msg_id'],
                    I18N.t('common.text'), db_reactions[0]['content'],
                    '\n'.join(tabulated_reactions)
                )
            )
        elif not reaction_msg:
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
            log.debug(f'`sorted_reacts` is {sorted_reacts}')
            if sorted_reacts is None:
                await interaction.followup.send(
                    'Ingen meldinger i databasen'
                )
                return
            for _sort in sorted_reacts:
                tabulate_dict['name'].append(_sort['name'])
                tabulate_dict['channel'].append(_sort['channel'])
                tabulate_dict['order'].append(_sort['msg_order'])
                tabulate_dict['id'].append(_sort['msg_id'])
                tabulate_dict['content'].append(
                    '{}…'.format(
                        str(_sort['content'])[0:30]
                    )
                )
                tabulate_dict['reactions'].append(_sort['COUNT(*)'])
            await interaction.followup.send(
                '```{}```'.format(
                    tabulate(
                        tabulate_dict, headers=[
                            I18N.t('common.name'),
                            I18N.t('common.channel'),
                            I18N.t('common.order'),
                            I18N.t('common.id'),
                            I18N.t('common.text'),
                            I18N.t('common.num_reactions')
                        ]
                    )
                )
            )
        return

    @roles_reaction_add_group.command(
        name='message', description=locale_str(I18N.t(
            'roles.commands.add_reaction_msg.cmd'
        ))
    )
    @describe(
        msg_name=I18N.t('roles.commands.add_reaction_msg.desc.msg_name'),
        message_text=I18N.t('roles.commands.add_reaction_msg.desc.msg_text'),
        order=I18N.t('roles.commands.add_reaction_msg.desc.order'),
        channel=I18N.t('roles.commands.add_reaction_msg.desc.channel'),
        roles=I18N.t('roles.splits.roles'),
        emojis=I18N.t('roles.splits.emojis'),
        header=I18N.t('roles.commands.add_reaction_msg.desc.header')
    )
    async def add_reaction_message(
        self, interaction: discord.Interaction,
        msg_name: str, message_text: str, order: int,
        channel: discord.TextChannel, roles: str, emojis: str,
        header: str = None
    ):
        '''
        Add a reaction message
        '''
        await interaction.response.defer(ephemeral=True)
        msg_db_orders = await db_helper.get_output(
            envs.roles_db_msgs_schema,
            where=('channel', channel),
            select=('msg_order', 'name')
        )
        if order in [msg_order['msg_order'] for msg_order in msg_db_orders]:
            await interaction.followup.send(
                I18N.t(
                    'roles.commands.add_reaction_msg.msg_order_exist',
                    channel=channel,
                    num=len(msg_db_orders) + 1
                )
            )
            return
        msg_db = await db_helper.get_output(
            envs.roles_db_msgs_schema,
            where=[
                ('name', msg_name)
            ],
            select=('name')
        )
        if len(msg_db) == 1:
            await interaction.followup.send(
                I18N.t(
                    'roles.commands.add_reaction_msg.'
                    'msg_reaction_already_exist',
                    msg_name=msg_name
                )
            )
            return
        desc_out = ''
        reactions = []
        merged_roles_emojis = await combine_roles_and_emojis(roles, emojis)
        log.debug(
            '`merged_roles_emojis` is done (role, emoji): ',
            pretty=merged_roles_emojis
        )
        if merged_roles_emojis is None:
            await interaction.followup.send(
                I18N.t(
                    'roles.commands.add_reaction_msg.msg_roles_emojis_error'
                )
            )
            return
        for combo in merged_roles_emojis:
            log.debug(f'Checking combo `{combo}`')
            log.debug(f'Combo[0] `{combo[0]}`')
            log.debug(f'Combo[1] `{combo[1]}`')
            role_out = get(
                discord_commands.get_guild().roles, id=int(combo[0])
            )
            if re.match(r'<.*\b(\d+)>', combo[1]):
                emoji_out = combo[1]
            elif re.match(r'(\d+)', combo[1]):
                emoji_out = get(
                    discord_commands.get_guild().emojis, id=int(combo[1])
                )
            else:
                emoji_out = combo[1]
            if len(desc_out) > 0:
                desc_out += ''
            desc_out += '\n{} {}'.format(emoji_out, role_out)
            reactions.append([combo[0], combo[1]])
        log.debug(f'`reactions` is done: {reactions}')
        if desc_out == '':
            embed_json = None
        else:
            embed_json = discord.Embed.from_dict(
                {
                    'description': desc_out
                }
            )
        if header:
            content = f'## {header}\n{message_text}'
        else:
            content = message_text
        # Post the reaction message
        reaction_msg = await channel.send(
            content=content,
            embed=embed_json
        )
        # Save to DB
        reactions_in = []
        for reac in reactions:
            log.debug(f'Checking reac {reac}')
            reactions_in.append(
                (
                    reaction_msg.id, reac[0], reac[1]
                )
            )
            log.debug(f'Adding emoji {reac[1]}')
            if re.match(r'^(\d+)$', reac[1]):
                log.debug('Adding emoji as id')
                await reaction_msg.add_reaction(
                    get(discord_commands.get_guild().emojis, id=int(reac[1]))
                )
            else:
                log.debug('Adding emoji as name')
                await reaction_msg.add_reaction(reac[1])
        await db_helper.insert_many_all(
            envs.roles_db_roles_schema,
            inserts=reactions_in
        )
        # Add to messages DB
        await db_helper.insert_many_all(
            envs.roles_db_msgs_schema,
            inserts=[
                (
                    reaction_msg.id, channel.name, msg_name, header,
                    message_text, desc_out, order
                )
            ]
        )
        await interaction.followup.send(
            I18N.t('roles.commands.add_reaction_msg.msg_confirm'),
            ephemeral=True
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_reaction_add_group.command(
        name='role', description=locale_str(I18N.t(
            'roles.commands.add_reaction_role.cmd'
        ))
    )
    @describe(
        msg_name=I18N.t('roles.commands.add_reaction_role.desc.msg_name'),
        roles=I18N.t('roles.splits.roles'),
        emojis=I18N.t('roles.splits.emojis')
    )
    @discord.app_commands.autocomplete(
        msg_name=reaction_msgs_autocomplete
    )
    async def add_reaction_role(
        self, interaction: discord.Interaction, msg_name: str,
        roles: str, emojis: str
    ):
        '''
        Add reaction roles to an existing message
        '''
        await interaction.response.defer(ephemeral=True)
        msg_info = await get_msg_id_and_name(msg_name)
        # TODO Denne skal sørge for at den ikke legger inn duplikater
        # reactions_db_in = await db_helper.get_output(
        #    template_info=envs.roles_db_roles_schema,
        #    where=(
        #        ('msg_id', msg_info['id'])
        #    ),
        #    select=('role_name', 'emoji')
        # )
        # log.verbose(f'Got `reactions_db_in:` {reactions_db_in}')

        merged_roles_emojis = await combine_roles_and_emojis(roles, emojis)
        new_inserts = []
        for item in merged_roles_emojis:
            temp_item = [msg_info['id']]
            for unit in item:
                temp_item.append(unit)
            new_inserts.append(temp_item)
        await db_helper.insert_many_all(
            envs.roles_db_roles_schema,
            inserts=new_inserts
        )
        await sync_reaction_message_from_settings(msg_name)
        await interaction.followup.send(
            I18N.t('roles.commands.add_reaction_role.msg_confirm'),
            ephemeral=True
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @discord.app_commands.autocomplete(reaction_msg=reaction_msgs_autocomplete)
    @describe(
        reaction_msg=I18N.t('roles.commands.sync.desc.reaction_msg')
    )
    @roles_reaction_group.command(
        name='sync', description=locale_str(I18N.t(
            'roles.commands.sync.cmd'
        ))
    )
    async def sync_reaction_items(
        self, interaction: discord.Interaction, reaction_msg: str
    ):
        '''
        Synchronize a reaction message with the database
        '''
        await interaction.response.defer(ephemeral=True)
        sync_errors = await sync_reaction_message_from_settings(reaction_msg)
        if sync_errors:
            await interaction.followup.send(
                sync_errors, ephemeral=True
            )
        else:
            await interaction.followup.send(
                I18N.t('roles.commands.sync.confirm_sync'),
                ephemeral=True
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @discord.app_commands.autocomplete(reaction_msg=reaction_msgs_autocomplete)
    @describe(
        reaction_msg=I18N.t('roles.commands.sort.desc.reaction_msg')
    )
    @roles_reaction_group.command(name='sort')
    async def sort_reaction_items(
        self, interaction: discord.Interaction, reaction_msg: str
    ):
        '''
        Sort items in a reaction message alphabetically
        '''
        await interaction.response.defer(ephemeral=True)
        # Get message object
        msg_info = await get_msg_id_and_name(reaction_msg)
        _msg = await discord_commands.get_message_obj(
            msg_info['id'], msg_info['channel']
        )
        if _msg is None:
            await interaction.followup.send(
                I18N.t(
                    'roles.commands.sort.msg_error',
                    reaction_msg=reaction_msg
                )
            )
            return
        sync_errors = await sync_reaction_message_from_settings(
            reaction_msg, sorting=True
        )
        if sync_errors:
            await interaction.followup.send(
                sync_errors, ephemeral=True
            )
        else:
            await interaction.followup.send(
                I18N.t('roles.commands.sort.msg_confirm'),
                ephemeral=True
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_reaction_remove_group.command(
        name='message', description='Remove a reaction message'
    )
    @discord.app_commands.autocomplete(reaction_msg=reaction_msgs_autocomplete)
    async def remove_reaction_message(
        self, interaction: discord.Interaction, reaction_msg: str
    ):
        '''
        Remove a reaction message

        Parameters
        ------------
        reaction_msg: int/str
            The message ID from Discord or name in the database
        '''
        await interaction.response.defer(ephemeral=True)
        # Get message object
        msg_info = await get_msg_id_and_name(reaction_msg)
        _msg = await discord_commands.get_message_obj(
            msg_info['id'], msg_info['channel']
        )
        if _msg is None:
            await interaction.followup.send(
                I18N.t(
                    'roles.commands.remove_msg.msg_error',
                    reaction_msg=reaction_msg
                )
            )
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
        await interaction.followup.send(
            I18N.t('roles.commands.remove_msg.msg_confirm')
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_reaction_remove_group.command(
        name='role', description=locale_str(I18N.t(
            'roles.commands.remove_role.cmd'
        ))
    )
    @describe(
        reaction_msg=I18N.t('roles.commands.remove_role.desc.reaction_msg'),
        role_name=I18N.t('roles.commands.remove_role.desc.role_name')
    )
    @discord.app_commands.autocomplete(
        reaction_msg=reaction_msgs_autocomplete
    )
    async def remove_reaction_role(
        self, interaction: discord.Interaction, reaction_msg: str,
        role_name: discord.Role
    ):
        '''
        Remove a reaction from reaction message
        '''
        await interaction.response.defer(ephemeral=True)
        # Get message object
        msg_info = await get_msg_id_and_name(reaction_msg)
        ###
        from pprint import pprint
        pprint(msg_info)
        ###
        # Delete reaction from db
        role_name_out = f'<@&{role_name.id}>'
        await db_helper.del_row_by_AND_filter(
            template_info=envs.roles_db_roles_schema,
            where=[
                ('msg_id', str(msg_info['id'])),
                ('role', str(role_name.id))
            ]
        )
        # Sync settings
        await sync_reaction_message_from_settings(reaction_msg)
        await interaction.followup.send(
            I18N.t(
                'roles.commands.remove_role.msg_confirm',
                rolename=role_name.name
            ),
            ephemeral=True
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_reaction_group.command(
        name='reorder', description=locale_str(I18N.t(
            'roles.commands.reorder.cmd'
        ))
    )
    @describe(
        channel=I18N.t('roles.commands.reorder.desc.channel')
    )
    async def reorder_reaction_messages(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        '''
        Check reaction messages order in a discord channel and recreate them
        based on settings
        '''
        async def update_msg_id(old_msg, new_msg):
            # Update msg id in both dbs
            await db_helper.update_fields(
                envs.roles_db_msgs_schema,
                updates=[
                    ('msg_id', new_msg)
                ],
                where=('msg_id', old_msg)
            )
            await db_helper.update_fields(
                envs.roles_db_roles_schema,
                updates=[
                    ('msg_id', new_msg)
                ],
                where=('msg_id', old_msg)
            )

        await interaction.response.defer(ephemeral=True)
        # Get all reaction messages in order from database
        # TODO Test reordering etter endring i GET_OUTPUT
        react_msgs = await db_helper.get_output(
            envs.roles_db_msgs_schema,
            where=('channel', channel.name),
            order_by=[
                ('msg_order', 'ASC')
            ]
        )
        log.debug(f'Got `react_msgs`: {react_msgs}')
        discord_msgs = [message async for message in channel.history(
            limit=20, oldest_first=True
        )]
        trigger_reordering = False

        # Check order of messages
        if len(discord_msgs) != len(react_msgs):
            log.log(
                'Number of reaction messages in {} and database are not'
                'the same nubmer ({} vs {})'.format(
                    channel, len(discord_msgs), len(react_msgs)
                )
            )
            trigger_reordering = True
        log.debug(f'`trigger_reordering`: {trigger_reordering}')
        if not trigger_reordering:
            for idx, d_msg in enumerate(discord_msgs):
                log.debug(
                    '`d_msg.id` ({})  -  `react_msgs`: {}'.format(
                        d_msg.id, react_msgs[idx]['msg_id']
                    )
                )
                if str(d_msg.id) != str(react_msgs[idx]['msg_id']):
                    trigger_reordering = True
                    break
        log.debug(f'`trigger_reordering`: {trigger_reordering}')
        if trigger_reordering:
            # Delete the old message and recreate messages
            for react_msg in react_msgs:
                log.debug('Deleting old_react_msg')
                new_reaction_msg = await discord_commands.post_to_channel(
                    react_msg['channel'],
                    content_in=react_msg['header'],
                    embed_in={
                        'description': react_msg['content']
                    }
                )
                # Update msg id in both dbs
                await update_msg_id(
                    old_msg=react_msg['msg_id'],
                    new_msg=new_reaction_msg.id
                )
                # Recreate reactions by syncing settings
                await sync_reaction_message_from_settings(
                    str(new_reaction_msg.id)
                )
            await interaction.followup.send(
                I18N.t('roles.commands.reorder.msg_confirm')
            )
        else:
            await interaction.followup.send(
                I18N.t('roles.commands.reorder.msg_already_sorted')
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_settings_group.command(
        name='add', description=locale_str(I18N.t(
            'roles.commands.settings_add.cmd'
        ))
    )
    @describe(
        setting=I18N.t('roles.commands.settings_add.desc.setting'),
        role_in=I18N.t('roles.commands.settings_add.desc.role_in')
    )
    async def add_settings(
        self, interaction: discord.Interaction,
        setting: typing.Literal[
            I18N.t(
                'roles.commands.settings_add.literal.setting.unique'
            ),
            I18N.t(
                'roles.commands.settings_add.literal.setting'
                '.not_include_in_total'
            )
        ],
        role_in: discord.Role
    ):
        '''
        Add a setting for roles on the server
        '''
        await interaction.response.defer(ephemeral=True)
        if setting == I18N.t(
            'roles.commands.settings_add.literal.setting.unique'
        ):
            _setting = 'unique'
            unique = await db_helper.get_output(
                template_info=envs.roles_db_settings_schema,
                select=('value'),
                where=('setting', 'unique'),
                single=True
            )
            if unique['value']:
                await interaction.followup.send(
                    I18N.t('roles.commands.settings_add.role_already_set')
                )
                return
        elif setting == I18N.t(
            'roles.commands.settings_add.literal.setting.not_include_in_total'
        ):
            _setting = 'not_include_in_total'
        await db_helper.insert_many_all(
            template_info=envs.roles_db_settings_schema,
            inserts=[
                (_setting, str(role_in.id))
            ]
        )
        await interaction.followup.send(
            I18N.t('roles.commands.settings_add.msg_confirm')
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @discord.app_commands.autocomplete(setting=settings_autocomplete)
    @roles_settings_group.command(
        name='remove', description=locale_str(I18N.t(
            'roles.commands.settings_remove.cmd'
        ))
    )
    @describe(
        setting=I18N.t('roles.commands.settings_remove.desc.setting')
    )
    async def remove_settings(
        self, interaction: discord.Interaction,
        setting: str
    ):
        '''
        Remove a setting for roles on the server
        '''
        await interaction.response.defer(ephemeral=True)
        log.debug(f'Got row_id `{setting}`')
        await db_helper.del_row_id(
            template_info=envs.roles_db_settings_schema,
            numbers=setting
        )
        await interaction.followup.send(
            I18N.t('roles.commands.settings_remove.msg_confirm'),
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_settings_group.command(
        name='list', description=locale_str(I18N.t(
            'roles.commands.settings_list.cmd'
        ))
    )
    async def list_settings(
        self, interaction: discord.Interaction
    ):
        '''
        List settings for roles on the server
        '''
        await interaction.response.defer(ephemeral=True)

        settings_db = await db_helper.get_output(
            template_info=envs.roles_db_settings_schema
        )
        temp_settings_db = settings_db.copy()
        log.verbose('temp_settings_db', pretty=temp_settings_db)
        for setting in temp_settings_db:
            _role = get(
                discord_commands.get_guild().roles,
                id=int(setting['value'])
            )
            setting['role'] = _role
        log.verbose(f'temp_settings_db: {temp_settings_db}')
        _settings = tabulate(
            temp_settings_db, headers={
                'setting': I18N.t(
                    'roles.commands.settings_list.headers.setting'
                ),
                'role': I18N.t('roles.commands.settings_list.headers.role'),
                'value': I18N.t('roles.commands.settings_list.headers.value')
            }
        )
        await interaction.followup.send(f'```{_settings}```')
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @discord.app_commands.autocomplete(setting=settings_autocomplete)
    @roles_settings_group.command(
        name='edit', description=locale_str(I18N.t(
            'roles.commands.settings_edit.cmd'
        ))
    )
    @describe(
        setting=I18N.t('roles.commands.settings_edit.desc.setting'),
        role_in=I18N.t('roles.commands.settings_edit.desc.role_in')
    )
    async def edit_settings(
        self, interaction: discord.Interaction,
        setting: str, role_in: discord.Role
    ):
        '''
        Edit a setting for roles on the server
        '''
        await interaction.response.defer(ephemeral=True)
        await db_helper.update_fields(
            template_info=envs.roles_db_settings_schema,
            where=('setting', setting),
            updates=('value', str(role_in.id))
        )
        await interaction.followup.send(
            I18N.t(
                'roles.commands.settings_edit.confirm_msg',
                setting=setting, role_in=role_in.id
            )
        )
        return

# TODO Only for test
#    @roles_group.command(
#        name='test',
#        description='TEST'
#    )
#    async def role_test(
#        self, interaction: discord.Interaction
#    ):
#        #await interaction.response.defer(ephemeral=True)
#        await sync_reaction_message_from_settings(1295750251164074047)
#        return


async def setup(bot):
    # Create necessary databases before starting
    cog_name = 'roles'
    log.log(envs.COG_STARTING.format(cog_name))
    log.verbose('Checking db')

    # Convert json to sqlite db-files if exists
    # Define inserts
    roles_inserts = None
    roles_inserts_msg = None
    roles_inserts_reactions = None
    roles_inserts_settings = None
    msgs_is_ok = False
    reacts_is_ok = False
    settings_is_ok = False

    # Populate the inserts
    roles_inserts = None
    roles_inserts_msg = None
    roles_inserts_reactions = None
    roles_inserts_settings = None
    # Convert the inserts from json if file exist
    if not file_io.file_exist(envs.roles_db_roles_schema['db_file']):
        if file_io.file_exist(envs.roles_settings_file):
            log.verbose('Found old json file')
            roles_inserts = await db_helper.json_to_db_inserts(cog_name)
            roles_inserts_msg = roles_inserts['msg_inserts']
            roles_inserts_reactions = roles_inserts['reactions_inserts']
            roles_inserts_settings = roles_inserts['settings_inserts']
        log.debug(f'`roles_inserts_msg` is {roles_inserts_msg}')
        log.debug(f'`roles_inserts_reactions` is {roles_inserts_reactions}')
        log.debug(f'`roles_inserts_settings` is {roles_inserts_settings}')
        msgs_is_ok = await db_helper.prep_table(
            table_in=envs.roles_db_msgs_schema,
            inserts=roles_inserts_msg
        )
        log.verbose(f'`msgs_is_ok` is {msgs_is_ok}')
        reacts_is_ok = await db_helper.prep_table(
            table_in=envs.roles_db_roles_schema,
            inserts=roles_inserts_reactions
        )
        log.verbose(f'`reacts_is_ok` is {reacts_is_ok}')
        settings_is_ok = await db_helper.prep_table(
            table_in=envs.roles_db_settings_schema,
            inserts=roles_inserts_settings
        )
        log.verbose(f'`settings_is_ok` is {settings_is_ok}')

    # Delete old json files if they exist
    if msgs_is_ok and reacts_is_ok and settings_is_ok:
        file_io.remove_file(envs.roles_settings_file)

    log.verbose('Registering cog to bot')
    await bot.add_cog(Autoroles(bot))


# Maintain reaction roles

# Add roles to users from reactions
@config.bot.event
async def on_raw_reaction_add(payload):
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
    _guild = discord_commands.get_guild()
    for reaction_message in reaction_messages:
        if str(payload.message_id) == str(reaction_message['msg_id']):
            log.debug('Found message, checking add reactions...')
            reactions = await db_helper.get_combined_output(
                envs.roles_db_roles_schema,
                envs.roles_db_msgs_schema,
                key='msg_id',
                select=[
                    'emoji',
                    'role'
                ],
                where=[
                    ('A.msg_id', payload.message_id)
                ]
            )
            log.debug(f'reactions is {reactions}')
            if payload.emoji.id is not None:
                incoming_emoji = str(payload.emoji.id)
            elif payload.emoji.name is not None:
                incoming_emoji = str(payload.emoji.name)
            else:
                log.error('Could not find emoji')
                return
            for reaction in reactions:
                log.debug(f'`reaction` is {reaction}')
                log.debug(
                    'Comparing emoji from payload ({}) '
                    'with emoji from db ({})'.format(
                        incoming_emoji, reaction['emoji']
                    )
                )
                if str(incoming_emoji) == str(reaction['emoji']):
                    await _guild.get_member(
                        payload.user_id
                    ).add_roles(
                        get(
                            discord_commands.get_guild().roles,
                            id=int(reaction['role'])
                        ),
                        reason=I18N.t(
                            'roles.cogs.on_raw_reaction_add.'
                            'channel_log_confirm'
                        )
                    )
                    break
            else:
                log.error('Could not find emoji')
    return


# Remove roles from users from reactions
@config.bot.event
async def on_raw_reaction_remove(payload):
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
    log.verbose(f'reaction_messages: {reaction_messages}')
    _guild = discord_commands.get_guild()
    for reaction_message in reaction_messages:
        if str(payload.message_id) == str(reaction_message['msg_id']):
            log.debug('Found message, checking remove reactions...')
            reactions = await db_helper.get_combined_output(
                envs.roles_db_roles_schema,
                envs.roles_db_msgs_schema,
                key='msg_id',
                select=[
                    'role',
                    'emoji'
                ],
                where=[
                    ('A.msg_id', reaction_message['msg_id'])
                ]
            )
            log.verbose(f'`reactions`: {reactions}')
            if payload.emoji.id is not None:
                incoming_emoji = str(payload.emoji.id)
            elif payload.emoji.name is not None:
                incoming_emoji = str(payload.emoji.name)
            else:
                log.error('Could not find emoji')
                return
            for reaction in reactions:
                log.debug(f'`reaction` is {reaction}')
                if str(payload.emoji.id) == reaction['emoji']:
                    incoming_emoji = str(payload.emoji.id)
                elif str(payload.emoji.name) == reaction['emoji']:
                    incoming_emoji = str(payload.emoji.name)
                log.debug(
                    'Comparing emoji from payload ({}) '
                    'with emoji from db ({})'.format(
                        incoming_emoji, reaction['emoji']
                    )
                )
                if str(incoming_emoji) == str(reaction['emoji']):
                    for _role in _guild.roles:
                        if str(_role.id) in reaction['role'].lower():
                            log.debug(
                                'Removing role {} from user'.format(
                                    reaction['role']
                                )
                            )
                            await _guild.get_member(
                                payload.user_id
                            ).remove_roles(
                                _role,
                                reason=I18N.t(
                                    'roles.cogs.on_raw_reaction_remove.'
                                    'channel_log_confirm'
                                )
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
    unique_role = unique_role['value']
    log.debug(f'Got `unique_role`: {unique_role}')
    if not unique_role or unique_role == '':
        log.log('No unique role provided or setting is not string')
        return
    if unique_role:
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
            unique_role == role.id for role in after.roles
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
            log.debug('Found roles not to include in total')
            _before -= len(not_include_in_total)
            _after -= len(not_include_in_total)
        if any(str(unique_role) == role for role in before.roles):
            _before -= 1
        elif any(str(unique_role) == role for role in after.roles):
            _after -= 1
        log.verbose('before and after, minus unique role:')
        log.verbose(f'_before: {_before}')
        log.verbose(f'_after: {_after}')
        if int(_after) <= 0:
            log.debug('Length of _after is 0, adding unique role')
            await after.add_roles(
                get(_guild.roles, id=int(unique_role))
            )
        elif int(_after) > 1:
            log.debug(
                'Length of after.roles is more than 1, removing unique role'
            )
            await after.remove_roles(
                get(_guild.roles, id=int(unique_role))
            )
    return
