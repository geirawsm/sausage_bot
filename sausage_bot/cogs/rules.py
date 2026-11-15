#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
rules: Set and administer rules for a discord server
"""

import discord
from discord.ext import commands
from discord.app_commands import locale_str, describe
import uuid

from sausage_bot.util import envs, config
from sausage_bot.util import discord_commands, db_helper, datetime_handling
from sausage_bot.util.l10n import _t

logger = config.logger

# Autocomplete choices pack more than one field into a single value. A uuid
# holds `-` itself, so the fields are joined by something a uuid never holds.
AUTOCOMPLETE_SEP = ";"


async def ruleset_db_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    rulesets_in_db = await db_helper.get_output(
        template_info=envs.rules_db_rulesets_schema,
        select=("ruleset_uuid", "name", "channel_id"),
        guild_id=interaction.guild.id,
    )
    return [
        discord.app_commands.Choice(
            name="{name} (#{channel_name})".format(
                name=ruleset["name"],
                channel_name=discord_commands.get_channel_name(
                    interaction.guild, ruleset["channel_id"]
                ),
            ),
            value="{}{sep}{}".format(
                ruleset["ruleset_uuid"], ruleset["name"], sep=AUTOCOMPLETE_SEP
            ),
        )
        for ruleset in rulesets_in_db
        if current.lower()
        in "{}{sep}{}".format(
            ruleset["name"],
            discord_commands.get_channel_name(interaction.guild, ruleset["channel_id"]),
            sep=AUTOCOMPLETE_SEP,
        ).lower()
    ][:25]


async def rule_db_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[discord.app_commands.Choice[str]]:
    rules_and_sets_in_db = await db_helper.get_combined_output(
        template_info_1=envs.rules_db_rulesets_schema,
        template_info_2=envs.rules_db_rules_schema,
        key="ruleset_uuid",
        select=[
            "rule_uuid",
            "rule_number",
            "rule_text",
            "A.ruleset_uuid",
            "name",
            "channel_id",
        ],
        guild_id=interaction.guild.id,
    )
    return [
        discord.app_commands.Choice(
            name="{rule_number}. {rule_text} (#{channel_name} - {rule_set_name})".format(
                rule_number=ruleset["rule_number"],
                rule_text=ruleset["rule_text"],
                channel_name=discord_commands.get_channel_name(
                    interaction.guild, ruleset["channel_id"]
                ),
                rule_set_name=ruleset["name"],
            ),
            value="{set_uuid}{sep}{rule_uuid}".format(
                set_uuid=ruleset["ruleset_uuid"],
                sep=AUTOCOMPLETE_SEP,
                rule_uuid=ruleset["rule_uuid"],
            ),
        )
        for ruleset in rules_and_sets_in_db
        if current.lower()
        in "{}{sep}{}".format(
            ruleset["name"],
            discord_commands.get_channel_name(interaction.guild, ruleset["channel_id"]),
            sep=AUTOCOMPLETE_SEP,
        ).lower()
    ][:25]


class ModalRuleRemove(discord.ui.Modal):
    def prep_dropdown(self, rules_in: list[str]) -> list[discord.SelectOption] | None:
        "Prepare dropdown selections"
        list_out = []
        if len(rules_in) == 0:
            return None
        for _rule in rules_in:
            oneliner = "{}: {}".format(_rule["rule_number"], _rule["rule_text"])
            logger.debug(f"Checking rule: {oneliner}")
            if len(str(oneliner)) >= 100:
                oneliner = f"{str(oneliner):.90}..."
            list_out.append(
                discord.SelectOption(
                    label=oneliner, value=str(_rule["rule_uuid"]), default=False
                )
            )
        return list_out

    def __init__(
        self,
        rules_in: list = [],
        title_in: str = "Dummy title",
        row_ids: int = 0,
    ) -> None:
        super().__init__(title=title_in)

        self.rules_in = rules_in
        self.rules_out = []
        self.row_ids = row_ids
        # Overrides the "quote saved" reply, e.g. for suggestions that are
        # not saved until a moderator approves them
        logger.debug(f"self.rules_in: {self.rules_in}")

        self.rules_prep = self.prep_dropdown(rules_in)
        logger.debug(
            f"self.rules_prep ({len(self.rules_prep)}: {str(self.rules_prep)[0:500]}"
        )
        self.rules_dropdown = discord.ui.Select(
            placeholder=_t("rules.modals.remove.placeholder"),
            options=self.rules_prep,
            max_values=int(len(self.rules_prep) if self.rules_prep else 25),
            required=True,
        )
        self.add_item(
            discord.ui.Label(
                text=_t("rules.modals.remove.label"), component=self.rules_dropdown
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not self.rules_dropdown.values:
            await interaction.response.send_message(
                _t("rules.modals.remove.msg_no_values"),
                ephemeral=True,
            )
        else:
            self.rules_out = self.rules_dropdown.values
            msg_rules_deleted = []
            for rule in self.rules_in:
                if rule["rule_uuid"] in self.rules_out:
                    msg_rules_deleted.append(
                        "`{}. {}`".format(rule["rule_number"], rule["rule_text"])
                    )
            await interaction.response.send_message(
                content="{}\n{}".format(
                    _t("rules.modals.remove.msg_removed"),
                    "\n".join(msg_rules_deleted),
                ),
                ephemeral=True,
            )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.response.send_message(
            _t("rules.modals.remove.error"),
            ephemeral=True,
        )


async def sync_rule_msg(
    interaction: discord.interaction, rule_set: list, renumber: bool = False
):
    logger.debug("Running rule syncing...")
    ruleset_info = await db_helper.get_output(
        template_info=envs.rules_db_rulesets_schema,
        where=[("ruleset_uuid", rule_set[0])],
        guild_id=interaction.guild.id,
        single=True,
    )
    complete_rules = await db_helper.get_output(
        template_info=envs.rules_db_rules_schema,
        where=[("ruleset_uuid", rule_set[0])],
        select=("rule_number", "rule_text"),
        order_by=[("rule_number", "ASC")],
        guild_id=interaction.guild.id,
    )
    logger.debug("Loaded databases:")
    logger.debug(f"ruleset_info: {ruleset_info}")
    logger.debug(f"complete_rules: {complete_rules}")
    if renumber:
        for i, rule in enumerate(complete_rules, start=1):
            rule["rule_number"] = i
        await db_helper.renumber_rows_in_table(
            template_info=envs.rules_db_rules_schema, guild_id=interaction.guild.id
        )
    # create new rule message
    msg_out = ""
    if ruleset_info["header"] not in ["", None]:
        msg_out += "## {}".format(ruleset_info["header"])
    logger.debug("Added header: {}".format(ruleset_info["header"]))
    if ruleset_info["text_pre_rules"] not in ["", None]:
        if msg_out != "":
            msg_out += "\n"
        msg_out += "{}\n".format(ruleset_info["text_pre_rules"])
    logger.debug("Added text_pre_rules: {}".format(ruleset_info["text_pre_rules"]))
    if msg_out != "":
        msg_out += "\n"
    for rule in complete_rules:
        if rule != complete_rules[0]:
            msg_out += "\n"
        msg_out += "1. {}".format(rule["rule_text"])
    if ruleset_info["text_post_rules"] not in ["", None]:
        if msg_out != "":
            msg_out += "\n\n"
        msg_out += "{}\n".format(ruleset_info["text_post_rules"])
    logger.debug("Added text_post_rules: {}".format(ruleset_info["text_post_rules"]))
    logger.debug(f"New rule message created:\n{msg_out}")
    # Assert existence of db message
    msg_id = ruleset_info["msg_id"]
    if msg_id == "":
        logger.info("Message is not set in database, creating new")
        msg_id = await discord_commands.post_to_channel(
            channel_id=ruleset_info["channel_id"], content_in=msg_out
        )
        await db_helper.update_fields(
            template_info=envs.rules_db_rulesets_schema,
            where=[("ruleset_uuid", rule_set[0])],
            updates=[("msg_id", int(msg_id.id))],
            guild_id=interaction.guild.id,
        )
    else:
        msg_id = await discord_commands.get_message_obj(
            guild=interaction.guild,
            channel_id=ruleset_info["channel_id"],
            msg_id=ruleset_info["msg_id"],
        )
        if msg_id is None:
            logger.info("Message is not found, creating new")
            msg_id = await discord_commands.post_to_channel(
                channel_id=ruleset_info["channel_id"], content_in=msg_out
            )
            await db_helper.update_fields(
                template_info=envs.rules_db_rulesets_schema,
                where=[("ruleset_uuid", rule_set[0])],
                updates=[("msg_id", int(msg_id.id))],
                guild_id=interaction.guild.id,
            )
    # Edit message
    await msg_id.edit(content=msg_out)
    logger.debug("Rule syncing done!")


class Rules(commands.Cog):
    "Set and administer rules"

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    rules_group = discord.app_commands.Group(
        name="rules",
        description=locale_str(_t("rules.commands.groups.rules")),
    )

    rules_set_group = discord.app_commands.Group(
        name="set",
        description=locale_str(_t("rules.commands.groups.set")),
        parent=rules_group,
    )

    rules_rule_group = discord.app_commands.Group(
        name="rule",
        description=locale_str(_t("rules.commands.groups.rule")),
        parent=rules_group,
    )

    @discord_commands.is_owner_or_manage_guild()
    @rules_set_group.command(
        name="add",
        description=locale_str(_t("rules.commands.set.add.command")),
    )
    @describe(
        rule_set_name=_t("rules.commands.desc.rule_set_name"),
        header=_t("rules.commands.desc.header"),
        text_pre_rules=_t("rules.commands.desc.text_pre_rules"),
        text_post_rules=_t("rules.commands.desc.text_post_rules"),
        channel=_t("rules.commands.desc.channel"),
    )
    async def add_rule_set(
        self,
        interaction: discord.Interaction,
        rule_set_name: str,
        header: str | None,
        text_pre_rules: str | None,
        text_post_rules: str | None,
        channel: discord.TextChannel,
    ):
        """
        Add a ruleset
        """
        await interaction.response.defer(ephemeral=True)
        existing_rulesets = await db_helper.get_output(
            template_info=envs.rules_db_rulesets_schema,
            select=("name"),
            guild_id=interaction.guild.id,
            single_col_results=True,
        )
        if rule_set_name in existing_rulesets:
            await interaction.followup.send(
                content=_t(
                    "rules.commands.set.add.msg_already_exists", name=rule_set_name
                ),
                ephemeral=True,
            )
            return
        else:
            _uuid = str(uuid.uuid4())
            await db_helper.insert_many_all(
                template_info=envs.rules_db_rulesets_schema,
                inserts=[
                    (
                        _uuid,
                        rule_set_name,
                        header,
                        text_pre_rules,
                        text_post_rules,
                        channel.id,
                        "",
                        "",
                    )
                ],
                guild_id=interaction.guild.id,
            )
            await discord_commands.log_to_bot_channel(
                guild=interaction.guild,
                content_in=_t(
                    "rules.commands.set.add.log_added",
                    user=interaction.user.name,
                    name=rule_set_name,
                ),
            )
            await sync_rule_msg(
                interaction=interaction, rule_set=[_uuid, rule_set_name]
            )
            await interaction.followup.send(
                content=_t("rules.commands.set.add.msg_confirm", name=rule_set_name),
                ephemeral=True,
            )

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(rule_set=ruleset_db_autocomplete)
    @rules_set_group.command(
        name="remove",
        description=locale_str(_t("rules.commands.set.remove.command")),
    )
    @describe(
        rule_set=_t("rules.commands.desc.rule_set"),
    )
    async def remove_rule_set(
        self,
        interaction: discord.Interaction,
        rule_set: str,
    ):
        """
        Remove a ruleset
        """
        await interaction.response.defer(ephemeral=True)
        rule_set = rule_set.split(AUTOCOMPLETE_SEP)
        msg_info = await db_helper.get_output(
            template_info=envs.rules_db_rulesets_schema,
            where=[("ruleset_uuid", rule_set[0])],
            select=("channel_id", "msg_id"),
            guild_id=interaction.guild.id,
            single=True,
        )
        logger.debug(f"Got msg_info: {msg_info}")
        if msg_info["channel_id"] != "" or msg_info["msg_id"] != "":
            ruleset_msg = await discord_commands.get_message_obj(
                guild=interaction.guild,
                channel_id=msg_info["channel_id"],
                msg_id=msg_info["msg_id"],
            )
            await ruleset_msg.delete()
        await db_helper.del_row_by_OR_filter(
            template_info=envs.rules_db_rulesets_schema,
            where=[("ruleset_uuid", rule_set[0])],
            guild_id=interaction.guild.id,
        )
        await db_helper.del_row_by_OR_filter(
            template_info=envs.rules_db_rules_schema,
            where=[("ruleset_uuid", rule_set[0])],
            guild_id=interaction.guild.id,
        )
        await discord_commands.log_to_bot_channel(
            guild=interaction.guild,
            content_in=_t(
                "rules.commands.set.remove.log_removed",
                user=interaction.user.name,
                name=rule_set[1],
            ),
        )
        await interaction.followup.send(
            content=_t("rules.commands.set.remove.msg_confirm", name=rule_set[1]),
            ephemeral=True,
        )

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(rule_set=ruleset_db_autocomplete)
    @rules_set_group.command(
        name="edit",
        description=locale_str(_t("rules.commands.set.edit.command")),
    )
    @describe(
        rule_set=_t("rules.commands.desc.rule_set"),
        new_rule_set_name=_t("rules.commands.desc.new_rule_set_name"),
        header=_t("rules.commands.desc.header"),
        text_pre_rules=_t("rules.commands.desc.text_pre_rules"),
        text_post_rules=_t("rules.commands.desc.text_post_rules"),
        channel=_t("rules.commands.desc.channel"),
        message_id=_t("rules.commands.desc.message_id"),
    )
    async def edit_rule_set(
        self,
        interaction: discord.Interaction,
        rule_set: str,
        new_rule_set_name: str | None,
        header: str | None,
        text_pre_rules: str | None,
        text_post_rules: str | None,
        channel: discord.TextChannel | None,
        message_id: str | None,
    ):
        """
        Edit a ruleset
        """
        await interaction.response.defer(ephemeral=True)
        rule_set = rule_set.split(AUTOCOMPLETE_SEP)
        ruleset_info = await db_helper.get_output(
            template_info=envs.rules_db_rulesets_schema,
            where=[("ruleset_uuid", rule_set[0])],
            guild_id=interaction.guild.id,
            single=True,
        )
        pending_changes = []
        changes_out = []
        if new_rule_set_name:
            pending_changes.append(("name", str(new_rule_set_name)))
            changes_out.append(
                "\n- "
                + _t(
                    "rules.commands.set.edit.change_name",
                    old=ruleset_info["name"],
                    new=new_rule_set_name,
                )
            )
        if header:
            pending_changes.append(("header", str(header)))
            changes_out.append(
                "\n- "
                + _t(
                    "rules.commands.set.edit.change_header",
                    old=ruleset_info["header"],
                    new=header,
                )
            )
        if text_pre_rules:
            pending_changes.append(("text_pre_rules", str(text_pre_rules)))
            changes_out.append(
                "\n- "
                + _t(
                    "rules.commands.set.edit.change_text_pre_rules",
                    old=ruleset_info["text_pre_rules"],
                    new=text_pre_rules,
                )
            )
        if text_post_rules:
            pending_changes.append(("text_post_rules", str(text_post_rules)))
            changes_out.append(
                "\n- "
                + _t(
                    "rules.commands.set.edit.change_text_post_rules",
                    old=ruleset_info["text_post_rules"],
                    new=text_post_rules,
                )
            )
        if channel:
            pending_changes.append(("channel_id", int(channel.id)))
            changes_out.append(
                "\n- "
                + _t(
                    "rules.commands.set.edit.change_channel",
                    old=interaction.guild.get_channel_or_thread(
                        ruleset_info["channel_id"]
                    ),
                    new=str(channel.name),
                )
            )
        if message_id:
            pending_changes.append(("msg_id", int(message_id)))
            changes_out.append(
                "\n- "
                + _t(
                    "rules.commands.set.edit.change_message_id",
                    old=ruleset_info["msg_id"],
                    new=message_id,
                )
            )
        if len(pending_changes) > 0:
            await db_helper.update_fields(
                template_info=envs.rules_db_rulesets_schema,
                where=[
                    ("ruleset_uuid", rule_set[0]),
                ],
                updates=pending_changes,
                guild_id=interaction.guild.id,
            )
        await sync_rule_msg(interaction, rule_set)
        msg_out = _t("rules.commands.set.edit.msg_header")
        for change in changes_out:
            msg_out += change
        log_msg = _t(
            "rules.commands.set.edit.log_edited",
            user=interaction.user.name,
            name=rule_set[1],
        )
        for change in changes_out:
            log_msg += change
        await discord_commands.log_to_bot_channel(
            guild=interaction.guild,
            content_in=log_msg,
        )
        await interaction.followup.send(
            content=msg_out,
            ephemeral=True,
        )

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(rule_set=ruleset_db_autocomplete)
    @rules_set_group.command(
        name="sync",
        description=locale_str(_t("rules.commands.set.sync.command")),
    )
    @describe(
        rule_set=_t("rules.commands.desc.rule_set"),
        renumber=_t("rules.commands.desc.renumber"),
    )
    async def sync_rule_set(
        self, interaction: discord.Interaction, rule_set: str, renumber: bool = False
    ):
        """
        Sync a ruleset
        """
        await interaction.response.defer(ephemeral=True)
        rule_set = rule_set.split(AUTOCOMPLETE_SEP)
        await sync_rule_msg(interaction, rule_set, renumber)
        # Update sync time
        await db_helper.update_fields(
            template_info=envs.rules_db_rulesets_schema,
            where=[("ruleset_uuid", str(rule_set[0]))],
            updates=[
                (
                    "last_synced_datetime",
                    await datetime_handling.get_dt(format="ISO8601"),
                )
            ],
            guild_id=interaction.guild.id,
        )
        await interaction.followup.send(
            content=_t("rules.commands.set.sync.msg_confirm", name=rule_set[1]),
            ephemeral=True,
        )

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(rule_set=ruleset_db_autocomplete)
    @rules_rule_group.command(
        name="add",
        description=locale_str(_t("rules.commands.rule.add.command")),
    )
    @describe(
        rule_set=_t("rules.commands.desc.rule_set"),
        rule_number=_t("rules.commands.desc.rule_number"),
        rule_text=_t("rules.commands.desc.rule_text"),
        auto_update=_t("rules.commands.desc.auto_update"),
    )
    async def add_ruleset_rule(
        self,
        interaction: discord.Interaction,
        rule_set: str,
        rule_number: int,
        rule_text: str,
        auto_update: bool = False,
    ):
        """
        Add a rule to a ruleset
        """
        await interaction.response.defer(ephemeral=True)
        rule_set = rule_set.split(AUTOCOMPLETE_SEP)
        _uuid = str(uuid.uuid4())
        await db_helper.insert_many_all(
            template_info=envs.rules_db_rules_schema,
            inserts=[(rule_set[0], _uuid, rule_number, rule_text)],
            guild_id=interaction.guild.id,
        )
        if auto_update:
            logger.debug("auto_update activated")
            await sync_rule_msg(interaction, rule_set)
        await discord_commands.log_to_bot_channel(
            guild=interaction.guild,
            content_in=_t(
                "rules.commands.rule.add.log_added",
                user=interaction.user.name,
                number=rule_number,
                text=rule_text,
            ),
        )
        await interaction.followup.send(
            content=_t(
                "rules.commands.rule.add.msg_confirm",
                name=rule_set[1],
                number=rule_number,
                text=rule_text,
            ),
            ephemeral=True,
        )

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(rule_set=ruleset_db_autocomplete)
    @rules_rule_group.command(
        name="add_multiple",
        description=locale_str(_t("rules.commands.rule.add_multiple.command")),
    )
    @describe(
        rule_set=_t("rules.commands.desc.rule_set"),
        multiple_rules=_t("rules.commands.desc.multiple_rules"),
        auto_update=_t("rules.commands.desc.auto_update"),
    )
    async def add_multiple_ruleset_rules(
        self,
        interaction: discord.Interaction,
        rule_set: str,
        multiple_rules: str,
        auto_update: bool = False,
    ):
        """
        Add multiple rules to a ruleset

        Rules will be split by line change
        """
        await interaction.response.defer(ephemeral=True)
        rule_set = rule_set.split(AUTOCOMPLETE_SEP)
        complete_rules = await db_helper.get_output(
            template_info=envs.rules_db_rules_schema,
            where=[("ruleset_uuid", rule_set[0])],
            select=("rule_number"),
            order_by=[("rule_number", "ASC")],
            guild_id=interaction.guild.id,
        )
        if len(complete_rules) == 0:
            last_rule_number = 0
        else:
            last_rule_number = complete_rules[-1]["rule_number"]
        rules_in = multiple_rules.split("\n")
        rules_msg = _t("rules.commands.rule.add_multiple.msg_header")
        log_msg = _t(
            "rules.commands.rule.add_multiple.log_added",
            user=interaction.user.name,
            name=rule_set[1],
        )
        process_rules = []
        for rule_in in rules_in:
            last_rule_number += 1
            rules_msg += "\n- `{}. {}`".format(last_rule_number, rule_in)
            log_msg += "\n- `{}. {}`".format(last_rule_number, rule_in)
            process_rules.append(
                (
                    rule_set[0],
                    str(uuid.uuid4()),
                    last_rule_number,
                    rule_in,
                )
            )
        await db_helper.insert_many_all(
            template_info=envs.rules_db_rules_schema,
            inserts=process_rules,
            guild_id=interaction.guild.id,
        )
        if auto_update:
            logger.debug("auto_update activated")
            await sync_rule_msg(interaction, rule_set)
        await discord_commands.log_to_bot_channel(
            guild=interaction.guild, content_in=log_msg
        )
        await interaction.followup.send(
            content=rules_msg,
            ephemeral=True,
        )

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(rule_set=ruleset_db_autocomplete)
    @rules_rule_group.command(
        name="remove",
        description=locale_str(_t("rules.commands.rule.remove.command")),
    )
    @describe(
        rule_set=_t("rules.commands.desc.rule_set"),
        renumber=_t("rules.commands.desc.renumber"),
    )
    async def remove_ruleset_rule(
        self, interaction: discord.Interaction, rule_set: str, renumber: bool = False
    ):
        """
        Remove rules from a ruleset
        """
        rule_set = rule_set.split(AUTOCOMPLETE_SEP)
        existing_rules = await db_helper.get_output(
            template_info=envs.rules_db_rules_schema,
            select=("rule_uuid", "rule_number", "rule_text"),
            where=[("ruleset_uuid", rule_set[0])],
            guild_id=interaction.guild.id,
        )
        remove_rules_view = ModalRuleRemove(
            title_in=_t("rules.modals.remove.title"),
            rules_in=existing_rules,
        )
        await interaction.response.send_modal(remove_rules_view)
        await remove_rules_view.wait()
        await db_helper.del_row_by_OR_filter(
            template_info=envs.rules_db_rules_schema,
            where=[("rule_uuid", _uuid) for _uuid in remove_rules_view.rules_out],
            guild_id=interaction.guild.id,
        )
        await sync_rule_msg(
            interaction=interaction, rule_set=rule_set, renumber=renumber
        )

    @discord_commands.is_owner_or_manage_guild()
    @discord.app_commands.autocomplete(rule_in=rule_db_autocomplete)
    @rules_rule_group.command(
        name="edit",
        description=locale_str(_t("rules.commands.rule.edit.command")),
    )
    @describe(
        rule_in=_t("rules.commands.desc.rule_in"),
        new_rule_number=_t("rules.commands.desc.new_rule_number"),
        new_rule_text=_t("rules.commands.desc.new_rule_text"),
        auto_update=_t("rules.commands.desc.auto_update"),
    )
    async def edit_rule(
        self,
        interaction: discord.Interaction,
        rule_in: str,
        new_rule_number: int | None,
        new_rule_text: str | None,
        auto_update: bool = False,
    ):
        """
        Edit a rule
        """
        await interaction.response.defer(ephemeral=True)
        rule_in = rule_in.split(AUTOCOMPLETE_SEP)
        rules_in_db = await db_helper.get_output(
            template_info=envs.rules_db_rules_schema,
            select=("rule_number", "rule_text"),
            where=[("rule_uuid", rule_in[1])],
            guild_id=interaction.guild.id,
        )
        pending_changes = []
        changes_out = []
        if new_rule_number is not None:
            pending_changes.append(("rule_number", str(new_rule_number)))
            changes_out.append(
                "\n- "
                + _t(
                    "rules.commands.rule.edit.change_number",
                    old=rules_in_db[0]["rule_number"],
                    new=new_rule_number,
                )
            )
        if new_rule_text is not None:
            pending_changes.append(("rule_text", str(new_rule_text)))
            changes_out.append(
                "\n- "
                + _t(
                    "rules.commands.rule.edit.change_text",
                    old=rules_in_db[0]["rule_text"],
                    new=new_rule_text,
                )
            )
        if len(pending_changes) > 0:
            await db_helper.update_fields(
                template_info=envs.rules_db_rules_schema,
                where=[
                    ("rule_uuid", rule_in[1]),
                ],
                updates=pending_changes,
                guild_id=interaction.guild.id,
            )
        await sync_rule_msg(interaction, rule_in)
        msg_out = _t("rules.commands.rule.edit.msg_header")
        for change in changes_out:
            msg_out += change
        await interaction.followup.send(
            content=msg_out,
            ephemeral=True,
        )


async def ensure_guild_rules_tables(guild):
    """
    Prep this guild's rules tables, and fix up any legacy channel-name
    data. Safe to call repeatedly (idempotent).
    """
    await db_helper.prep_table(
        table_in=envs.rules_db_rulesets_schema, guild_id=guild.id
    )
    await db_helper.prep_table(table_in=envs.rules_db_rules_schema, guild_id=guild.id)


async def setup(bot):
    cog_name = "rules"
    logger.info(envs.COG_STARTING.format(cog_name))
    logger.debug("Checking db")

    approved_guilds = await db_helper.get_output(
        envs.guilds_db_schema, where=("status", "approved")
    )
    for guild_row in approved_guilds:
        guild = config.bot.get_guild(int(guild_row["guild_id"]))
        if guild is None:
            continue
        await ensure_guild_rules_tables(guild)

    logger.debug("Registering cog to bot")
    await bot.add_cog(Rules(bot))
