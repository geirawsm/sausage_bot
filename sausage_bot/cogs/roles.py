#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from discord.ext import commands
from discord.utils import get
import discord
from tabulate import tabulate
import re
import typing

from sausage_bot.util import config, envs, file_io, discord_commands, db_helper
from sausage_bot.util.log import log


class DropdownPermissions(discord.ui.Select):
    def __init__(
            self, placeholder_in, options_out, options_in
    ):
        super().__init__(
            placeholder=placeholder_in, min_values=0,
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
        self.value = False

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
        def prep_dropdown(perm_name, permissions_in):
            list_out = []
            for perm in envs.SELECT_PERMISSIONS[perm_name]:
                _desc = envs.SELECT_PERMISSIONS[perm_name][perm]
                if len(_desc) >= 100:
                    _desc = f'{str(_desc):.90}...'
                if perm in permissions_in:
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
            'Select general permissions', self.permissions_out, general_perms
        )
        text_dropdown = DropdownPermissions(
            'Select text permissions', self.permissions_out, text_perms
        )
        voice_dropdown = DropdownPermissions(
            'Select voice permissions', self.permissions_out, voice_perms
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
    settings = [setting for setting in await db_helper.get_output(
            template_info=envs.roles_db_settings_schema,
            select=('setting', 'value'),
            get_row_ids=True
        )
    ]
    print(f'SETTINGS: {settings}')
    return [
        discord.app_commands.Choice(
            name='{}. {} = {}'.format(
                setting[0], setting[1], setting[2]
            ),
            value=str(setting[0])
        )
        for setting in settings if current.lower() in str(setting).lower()
    ]


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


async def strip_role_or_emoji(input):
    input_check = re.match(r'<.*\b(\d+)>', input)
    if input_check:
        return input_check.group(1)
    elif not input_check:
        return None


async def sync_reaction_message_from_settings(
        msg_id_or_name, sorting: list = None
):
    # Assert that the reaction message exist on discord
    msg_info = await get_msg_id_and_name(msg_id_or_name)
    msg_id = msg_info['id']
    msg_channel = msg_info['channel']
    log.verbose(f'`msg_info` is {msg_info}')
    msg_obj = await discord_commands.get_message_obj(
        msg_id=msg_id,
        channel=msg_channel
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
    new_embed_desc = ''
    new_embed_content = ''
    await msg_obj.clear_reactions()
    for reaction in db_reactions:
        try:
            await msg_obj.add_reaction(reaction[1])
        except Exception as e:
            log.error(f'Could not add reaction to message: {e}')
            continue
        new_embed_content = db_message[0][3]
        if len(new_embed_desc) > 0:
            new_embed_desc += '\n'
        new_embed_desc += '{} {}'.format(
            reaction[1], reaction[0]
        )
        continue
    embed_json = {
        'description': new_embed_desc,
        'content': new_embed_content
    }
    # Edit discord message if it exist
    await msg_obj.edit(
        content=db_message[0][3],
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
        'members': {
            'length': 8,
            'header': 'Members'
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
    reactions = []
    for reaction in db_reactions:
        reactions.append((reaction[0], reaction[1]))
    log.debug(f'reactions: {reactions}')
    return [
        discord.app_commands.Choice(
            name=str(reaction[0]), value=str(reaction[1])
        )
        for reaction in reactions if current.lower() in reaction[0].lower()
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
    # Do splits of roles and emojis to make sure the lengths are identical
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
        name="roles", description='Control roles on the server'
    )

    roles_reaction_group = discord.app_commands.Group(
        name="reaction", description='Control reaction messages on the server',
        parent=roles_group
    )

    roles_reaction_add_group = discord.app_commands.Group(
        name="reaction_add", description='Add reaction message to the server',
        parent=roles_group
    )

    roles_reaction_remove_group = discord.app_commands.Group(
        name="reaction_remove",
        description='Remove reaction message from the server',
        parent=roles_group
    )

    roles_settings_group = discord.app_commands.Group(
        name="settings", description='Control settings on the server',
        parent=roles_group
    )

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_group.command(
        name='info', description='Get info about a specific role'
    )
    async def role_info(
        self, interaction: discord.Interaction,
        public: typing.Literal['Yes', 'No'], role_in: discord.Role
    ):
        '''
        Get info about a specific role (`role_in`)

        Parameters
        ------------
        role_name: str
            The role name to get info about (default: None)
        '''
        if public.lower() == 'yes':
            _ephemeral = False
        elif public.lower() == 'no':
            _ephemeral = True
        await interaction.response.defer(ephemeral=_ephemeral)
        _guild = discord_commands.get_guild()
        embed = discord.Embed(color=role_in.color)
        embed.set_thumbnail(url=role_in.icon)
        embed.add_field(name="ID", value=role_in.id, inline=True)
        embed.add_field(
            name="Farge", value=role_in.color, inline=True
        )
        if role_in.is_bot_managed():
            embed.add_field(
                name="Autohåndteres",
                value='Ja, av {}'.format(
                    _guild.get_member(
                        role_in.tags.integration_id
                    ).name
                ),
                inline=True
            )
        elif role_in.is_integration():
            embed.add_field(
                name="Autohåndteres",
                value='Ja, av {}'.format(
                    _guild.get_member(role_in.tags.bot_id).name
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
    async def roles_list(
        self, interaction: discord.Interaction,
        public: typing.Literal['Yes', 'No'],
        type: typing.Literal['Roles', 'Emojis'],
        sort: typing.Literal['By name', 'By ID']
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
            if sort.lower() == 'by name':
                _roles = tuple(sorted(
                    _guild.roles, key=lambda role: role.name.lower()
                ))
            elif sort.lower() == 'by id':
                _roles = tuple(sorted(
                    _guild.roles, key=lambda role: role.id
                ))
            for role in _roles:
                tabulate_dict['emoji'].append(role.display_icon)
                tabulate_dict['name'].append(role.name)
                tabulate_dict['id'].append(role.id)
                tabulate_dict['members'].append(len(role.members))
                if role.managed:
                    # TODO i18n?
                    tabulate_dict['managed'].append('Ja')
                elif not role.managed:
                    # TODO i18n?
                    tabulate_dict['managed'].append('Nei')
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
            if sort.lower() == 'by name':
                _emojis = tuple(sorted(
                    _guild.emojis, key=lambda emoji: emoji.name.lower()
                ))
            elif sort.lower() == 'by id':
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
                    tabulate_dict['animated'].append('Ja')
                else:
                    tabulate_dict['animated'].append('Nei')
                if emoji.managed:
                    tabulate_dict['managed'].append('Ja')
                else:
                    tabulate_dict['managed'].append('Nei')
            # Returning pagination
            return tabulate_emoji(tabulate_dict)

        if public.lower() == 'yes':
            _ephemeral = False
        elif public.lower() == 'no':
            _ephemeral = True
        await interaction.response.defer(ephemeral=_ephemeral)
        if type.lower() == 'roles':
            pages = await roles_list_roles()
        elif type.lower() == 'emojis':
            pages = await roles_list_emojis()
        for page in pages:
            log.verbose(f'{page}')
            await interaction.followup.send(f'{page}')
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_group.command(
        name='add', description='Add a role'
    )
    async def add_role(
        self, interaction: discord.Interaction, role_name: str,
        hoist: bool, mentionable: bool, color: str = None,
        display_icon: discord.Attachment = None
    ):
        '''
        Add role to the server

        Parameters
        ------------
        role_name: str
            The names of the role to add
        color: str
            Set color for the role (accepts `0x<hex>`, `#<hex>`, `0x#<hex>`,
            or `rgb(<number>, <number>, <number>)`)
        hoist: str (yes/no)
            Set if the role should be mentionable or not
        mentionable: str (yes/no)
            Set if the role should be mentionable or not
        display_icon: discord.Attachment
            Set a display icon for the role. Only possible if the guild
            has enough boosts
        '''
        await interaction.response.defer(ephemeral=True)
        # TODO i18n
        if not color:
            color = discord.Color.random()
        else:
            color = discord.Color.from_str(color)
        if display_icon:
            display_icon = await display_icon.read()
        perm_view = PermissionsView()
        await interaction.followup.send(
            "Set permissions", view=perm_view
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
                'Role is created'
            )
        except discord.errors.Forbidden as e:
            await interaction.followup.send(
                f'Error when creating role: {e.text}'
            )
            return
        except ValueError as e:
            await interaction.followup.send(
                f'Error when creating role: {e}'
            )
            return
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_group.command(
        name='remove', description='Remove a role from the server'
    )
    async def remove_role(
        self, interaction: discord.Interaction, role_name: discord.Role
    ):
        '''
        Remove a role from the server

        Parameters
        ------------
        role_name: discord.Role
            The name of the role to remove
        '''
        await interaction.response.defer(ephemeral=True)
        _guild = discord_commands.get_guild()
        _rolename = role_name.name
        await _guild.get_role(int(role_name.id)).delete()
        await interaction.followup.send(
            f'Role `{_rolename}` has been deleted'
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_group.command(
        name='edit', description='Edit a role on the server'
    )
    async def edit_role(
        self, interaction: discord.Interaction, role_name: discord.Role,
        permissions: bool, new_name: str = None, color: str = None,
        hoist: bool = None
    ):
        '''
        Edit a role on the server

        Parameters
        ------------
        role_name: str
            The name of the role to edit
        new_name: str
            Name for the role (default: None)
        color: str
            Color for the role. Accepts 0x<hex>, #<hex>, 0x#<hex>,
            rgb(<number>, <number>, <number>)
        hoist: bool
            Indicates if the role will be displayed separately from other
            members.
        permissions: bool
            Indicate if the permissions also should be edited
        '''
        await interaction.response.defer(ephemeral=True)
        changes = []
        if new_name:
            log.debug('Changed name')
            changes.append(f'\n- Name: `{role_name}` -> `{new_name}`')
            await role_name.edit(
                name=new_name
            )
        if color:
            log.debug('Changed color')
            changes.append(f'\n- Color: `{role_name.color}` -> `{color}`')
            await role_name.edit(
                color=discord.Color.from_str(color)
            )
        if hoist:
            log.debug('Changed hoist setting')
            changes.append(f'\n- Hoist: `{role_name.hoist}` -> `{hoist}`')
            await role_name.edit(
                hoist=hoist
            )
        if permissions:
            perms_in = []
            for perm in role_name.permissions:
                if perm[1] is True:
                    perms_in.append(perm[0])
            perm_view = PermissionsView(
                permissions_in=perms_in
            )
            await interaction.followup.send(
                "Change permissions", view=perm_view
            )
            await perm_view.wait()
            perms_out = perm_view.permissions_out
            perms_added = [item for item in perms_in if item not in perms_out]
            perms_removed = [
                item for item in perms_out if item not in perms_in
            ]
            if permissions:
                if len(perms_added) > 0:
                    changes.append('\n- Permissions added: {}'.format(
                        ', '.join(perms_added)
                    ))
                if len(perms_removed) > 0:
                    changes.append('\n- Permissions removed: {}'.format(
                        ', '.join(perms_removed)
                    ))
        if len(changes) > 0:
            changes_out = f'Did following changes on role `{role_name.name}`:'
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
    @discord.app_commands.autocomplete(reaction_msg=reaction_msgs_autocomplete)
    @roles_reaction_group.command(
        name='list', description='List all reactions'
    )
    async def list_reactions(
        self, interaction: discord.Interaction,
        reaction_msg: str = None
    ):
        '''
        List reactions

        Parameters
        ------------
        reaction_msg_name: str
            The names of the reaction message to list (default: None)
        '''
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
                    'role_name',
                    'emoji'
                ],
                where=[
                    ('A.msg_id', reaction_msg)
                ]
            )
            if len(db_reactions) <= 0:
                await interaction.followup.send(
                    f'Did not find `{reaction_msg}`'
                )
                return
            tabulate_dict = {
                'role': [],
                'emoji': []
            }
            for reaction in db_reactions:
                tabulate_dict['role'].append(reaction[4])
                tabulate_dict['emoji'].append(reaction[5])
            # TODO i18n?
            await interaction.followup.send(
                'Navn: `{}`\nKanal: `{}`\nMeldings-ID: `{}`\n'
                'Tekst: `{}`\n\n```{}```'.format(
                    db_reactions[0][0],
                    db_reactions[0][1],
                    db_reactions[0][2],
                    db_reactions[0][3],
                    tabulate(tabulate_dict, headers=['Rolle', 'Emoji'])
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
            if sorted_reacts is None:
                await interaction.followup.send(
                    'Ingen meldinger i databasen'
                )
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
            await interaction.followup.send(
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

    @roles_reaction_add_group.command(
        name='message', description='Add reaction message'
    )
    async def add_reaction_message(
        self, interaction: discord.Interaction,
        msg_name: str, message_text: str, order: int,
        channel: discord.TextChannel, roles: str, emojis: str,
    ):
        '''
        Add a reaction message

        Parameters
        ------------
        msg_name: str
            Name of the message for the reaction roles
        message_text: str
            The text for the message
        channel: discord.TextChannel
            Channel to post reaction message to
        order: int
            Set order for the message in the channel
        roles: str
            Tagged roles separated by any of the following characers:
            " .,;-_\\/"
        emojis: str
            Tagged emojis separated by any of the following characers:
            " .,;-_\\/"
        '''
        await interaction.response.defer(ephemeral=True)
        msg_db_orders = await db_helper.get_output(
            envs.roles_db_msgs_schema,
            where=('channel', channel),
            select=('msg_order', 'name')
        )
        if order in [msg_order[0] for msg_order in msg_db_orders]:
            # TODO var msg
            await interaction.followup.send(
                f'That order number already exist for {channel}, '
                f'try {len(msg_db_orders)+1}'
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
            # TODO var msg
            await interaction.followup.send(
                f'Reaction message `{msg_name}` is already registered...'
            )
            return
        desc_out = ''
        reactions = []
        merged_roles_emojis = await combine_roles_and_emojis(roles, emojis)
        log.debug(
            '`merged_roles_emojis` is done (role, emoji): ', pretty=merged_roles_emojis
        )
        for combo in merged_roles_emojis:
            log.debug(f'Checking combo `{combo}`')
            log.debug(f'Combo[0] `{combo[0]}`') 
            log.debug(f'Combo[1] `{combo[1]}`') 
            role_out = get(discord_commands.get_guild().roles, id=int(combo[0]))
            emoji_out = get(discord_commands.get_guild().emojis, id=int(combo[1]))
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
        # Post the reaction message
        reaction_msg = await channel.send(
            content=message_text,
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
            log.debug(f'Adding emoji {reac}')
            await reaction_msg.add_reaction(
                get(discord_commands.get_guild().emojis, id=int(reac[1]))
            )
        await db_helper.insert_many_all(
            envs.roles_db_roles_schema,
            inserts=reactions_in
        )
        # Add to messages DB
        await db_helper.insert_many_all(
            envs.roles_db_msgs_schema,
            inserts=[
                (
                    reaction_msg.id, channel.name, msg_name, message_text,
                    desc_out, order
                )
            ]
        )
        await interaction.followup.send(
            'Message added', ephemeral=True
        )
        return
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_reaction_add_group.command(
        name='role', description='Add roles to a reaction message')
    @discord.app_commands.autocomplete(
        msg_name=reaction_msgs_autocomplete
    )
    async def add_reaction_role(
        self, interaction: discord.Interaction, msg_name: str,
        roles: str, emojis: str
    ):
        '''
        Add reaction roles to an existing message

        Parameters
        ------------
        msg_name: int/str
            Name of the saved message
        roles: str
            The roles to add
        emojis: str
            The emojis to add
        '''
        await interaction.response.defer(ephemeral=True)
        msg_info = await get_msg_id_and_name(msg_name)
        reactions_db_in = await db_helper.get_output(
            template_info=envs.roles_db_roles_schema,
            where=(
                ('msg_id', msg_info['id'])
            ),
            select=('role_name', 'emoji')
        )
        log.verbose(f'Got `reactions_db_in:` {reactions_db_in}', color='red')

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
            'Roles added', ephemeral=True
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @discord.app_commands.autocomplete(reaction_msg=reaction_msgs_autocomplete)
    @roles_reaction_group.command(
        name='sync', description='Synchronize reactions messages with database'
    )
    async def sync_reaction_items(
        self, interaction: discord.Interaction, reaction_msg: str
    ):
        '''
        Synchronize a reaction message with the settings file

        Parameters
        ------------
        reaction_msg: int/str
            The message ID to look for, or name of the saved message in
            settings file
        '''
        await interaction.response.defer(ephemeral=True)
        sync_errors = await sync_reaction_message_from_settings(reaction_msg)
        if sync_errors:
            await interaction.followup.send(
                sync_errors, ephemeral=True
            )
        else:
            await interaction.followup.send(
                'Reaction message synced', ephemeral=True
            )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @discord.app_commands.autocomplete(reaction_msg=reaction_msgs_autocomplete)
    @roles_reaction_group.command(name='sort')
    async def sort_reaction_items(
        self, interaction: discord.Interaction, reaction_msg: str
    ):
        '''
        Sort items in a reaction message alphabetically

        Parameters
        ------------
        reaction_msg: str
            The message ID from database
        '''
        await interaction.response.defer(ephemeral=True)
        # Get message object
        msg_info = await get_msg_id_and_name(reaction_msg)
        _msg = await discord_commands.get_message_obj(
            msg_info['id'], msg_info['channel']
        )
        if _msg is None:
            # TODO var msg
            await interaction.followup.send(
                'Could not find reaction message'
            )
            return
        sync_errors = await sync_reaction_message_from_settings(
            reaction_msg,
            sorting=[('B.role_name', 'ASC')]
        )
        if sync_errors:
            await interaction.followup.send(
                sync_errors, ephemeral=True
            )
        else:
            await interaction.followup.send(
                'Roles sorted', ephemeral=True
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
w            The message ID from Discord or name in the database
        '''
        await interaction.response.defer(ephemeral=True)
        # Get message object
        msg_info = await get_msg_id_and_name(reaction_msg)
        _msg = await discord_commands.get_message_obj(
            msg_info['id'], msg_info['channel']
        )
        if _msg is None:
            # TODO var msg
            await interaction.followup.send(
                'Could not find reaction message'
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
        # TODO var msg
        await interaction.followup.send(
            'Reaction message removed'
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_reaction_remove_group.command(
        name='role', description='Remove a reaction from reaction message'
    )
    @discord.app_commands.autocomplete(reaction_msg=reaction_msgs_autocomplete)
    async def remove_reaction_role(
        self, interaction: discord.Interaction, reaction_msg: str,
        role_name: discord.Role
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
        await interaction.response.defer(ephemeral=True)
        # Get message object
        msg_info = await get_msg_id_and_name(reaction_msg)
        # Delete reaction from db
        role_name = f'<@&{role_name.id}>'
        await db_helper.del_row_by_AND_filter(
            template_info=envs.roles_db_roles_schema,
            where=[
                ('msg_id', msg_info['id']),
                ('role_name', role_name)
            ]
        )
        # Sync settings
        await sync_reaction_message_from_settings(reaction_msg)
        await interaction.followup.send(
            'Role removed', ephemeral=True
        )
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_reaction_group.command(
        name='reorder', description='Check reaction messages order in a '
        'discord channel and recreate them based on settings'
    )
    async def reorder_reaction_messages(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        '''
        Check reaction messages order in a discord channel and recreate them
        based on settings

        Parameters
        ------------
        channel: str
            What channel to check
        '''

        '''
        Hent alle db-meldinger i rekkefølge
        Hent alle discord-meldinger i rekkefølge
        Avsjekk at rekkefølge stemmer
        Hvis ikke stemmer, fjern alle meldinger for kanalen og lag nye
        '''
        await interaction.response.defer(ephemeral=True)
        # Get all reaction messages in order from database
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
                old_react_msg = await discord_commands.get_message_obj(
                    react_msg[0],
                    react_msg[1]
                )
                log.debug('Deleting old_react_msg')
                await old_react_msg.delete()
                new_reaction_msg = await discord_commands.post_to_channel(
                    react_msg[1],
                    content_in=react_msg[3],
                    embed_in={
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
            await interaction.followup.send("Reaction messages reordered")
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_settings_group.command(
        name='add', description='Add a setting for roles on the server'
    )
    async def add_settings(
        self, interaction: discord.Interaction,
        setting: typing.Literal['Unique role', 'Not include in total'],
        role_in: discord.Role
    ):
        '''
        Add a setting for roles on the server

        Parameters
        ------------
        setting: typing.Literal
            The setting to add
        role_in: discord.Role
            The role to add to the setting
        '''
        await interaction.response.defer(ephemeral=True)
        if setting == 'Unique role':
            _setting = 'unique'
            # TODO Add a check, unique should only appear once
            unique = await db_helper.get_output(
                template_info=envs.roles_db_settings_schema,
                select=('value'),
                where=('setting', 'unique'),
                single=True
            )
            if unique:
                await interaction.followup.send(
                    # TODO i18n
                    'Unique role already set, remove or edit it'
                )
                return
        elif setting == 'Not include in total':
            _setting = 'not_include_in_total'
        await db_helper.insert_many_all(
            template_info=envs.roles_db_settings_schema,
            inserts=[
                (_setting, str(role_in.id))
            ]
        )
        # TODO i18n
        await interaction.followup.send(f'Added setting')
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @discord.app_commands.autocomplete(setting=settings_autocomplete)
    @roles_settings_group.command(
        name='remove', description='Remove a setting for roles on the server'
    )
    async def remove_settings(
        self, interaction: discord.Interaction,
        setting: str
    ):
        '''
        Remove a setting for roles on the server

        Parameters
        ------------
        setting: str
            The setting to remove
        '''
        await interaction.response.defer(ephemeral=True)
        await db_helper.del_row_id(
            template_info=envs.roles_db_settings_schema,
            numbers=setting
        )
        # TODO i18n
        await interaction.followup.send(f'Removed setting')
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @roles_settings_group.command(
        name='list', description='List settings for roles on the server' 
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
        _settings_db_expanded = []
        for setting in settings_db:
            _role = get(
                discord_commands.get_guild().roles,
                id=int(setting[1])
            )
            _settings_db_expanded.append(
                (setting[0], _role, setting[1])
            )
        _settings = tabulate(_settings_db_expanded, headers=['Setting', 'Role', 'Value'])
        # TODO i18n
        await interaction.followup.send(f'```{_settings}```')
        return

    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_roles=True)
    )
    @discord.app_commands.autocomplete(setting=settings_autocomplete)
    @roles_settings_group.command(
        name='edit', description='Edit a setting for roles on the server'
    )
    async def edit_settings(
        self, interaction: discord.Interaction,
        setting: str, role_in: discord.Role
    ):
        '''
        Edit a setting for roles on the server

        Parameters
        ------------
        setting: str
            The setting to edit
        role_in: discord.Role
            The role to add to the setting
        '''
        await interaction.response.defer(ephemeral=True)
        await db_helper.update_fields(
            template_info=envs.roles_db_settings_schema,
            where=('setting', setting),
            updates=('value', str(role_in.id))
        )
        # TODO i18n
        await interaction.followup.send(
            f'Edited setting ({setting} = {role_in.id})'
        )
        return


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
            roles_inserts = db_helper.json_to_db_inserts(cog_name)
            roles_inserts_msg = roles_inserts['msg_inserts']
            roles_inserts_reactions = roles_inserts['reactions_inserts']
            roles_inserts_settings = roles_inserts['settings_inserts']
        log.debug(f'`roles_inserts_msg` is {roles_inserts_msg}')
        log.debug(f'`roles_inserts_reactions` is {roles_inserts_reactions}')
        log.debug(f'`roles_inserts_settings` is {roles_inserts_settings}')
        msgs_is_ok = await db_helper.prep_table(
            table_in=envs.roles_db_msgs_schema,
            old_inserts=roles_inserts_msg
        )
        log.verbose(f'`msgs_is_ok` is {msgs_is_ok}')
        reacts_is_ok = await db_helper.prep_table(
            table_in=envs.roles_db_roles_schema,
            old_inserts=roles_inserts_reactions
        )
        log.verbose(f'`reacts_is_ok` is {reacts_is_ok}')
        settings_is_ok = await db_helper.prep_table(
            table_in=envs.roles_db_settings_schema,
            old_inserts=roles_inserts_settings
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
    _guild = discord_commands.get_guild()
    for reaction_message in reaction_messages:
        if str(payload.message_id) == str(reaction_message[0]):
            # TODO var msg
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
            for reaction in reactions:
                log.debug(f'`reaction` is {reaction}')
                log.debug(
                    f'Comparing emoji id from payload ({payload.emoji.id}) '
                    f'with emoji id from db ({reaction[0]})'
                )
                if str(payload.emoji.id) in reaction[0]:
                    await _guild.get_member(
                        payload.user_id
                    ).add_roles(
                        get(
                            discord_commands.get_guild().roles,
                            id=int(reaction[1])
                        ),
                        reason='Added in accordance with  '
                        'reaction messages'
                    )

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
                    'role',
                    'emoji'
                ],
                where=[
                    ('A.msg_id', reaction_message[0])
                ]
            )
            log.verbose(f'`reactions` in remove: {reactions}')
            for reaction in reactions:
                log.debug(f'`reaction` is {reaction}')
                incoming_emoji = payload.emoji.id
                log.debug(f'incoming_emoji: {incoming_emoji}')
                log.debug('reaction[1]: {}'.format(reaction[1]))
                if str(incoming_emoji) == str(reaction[1]):
                    for _role in _guild.roles:
                        if str(_role.id) in reaction[0].lower():
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
    log.debug(f'Got `unique_role`: {unique_role}')
    if not unique_role or unique_role == '':
        # TODO var msg
        log.log('No unique role provided or setting is not string')
        return
    if unique_role:
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
            # TODO var msg
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
        if int(_after) == 0:
            # TODO var msg
            log.debug('Length of _after is 0, adding unique role')
            await after.add_roles(
                get(_guild.roles, id=int(unique_role))
            )
        elif int(_after) > 1:
            # TODO var msg
            log.debug(
                'Length of after.roles is more than 1, removing unique role'
            )
            await after.remove_roles(
                get(_guild.roles, id=int(unique_role))
            )
    return
