#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"dev: Turn the bot owner's messages in a todo channel into GitHub issues"

import asyncio
import base64
import re
from pathlib import Path

import aiohttp
import discord
from discord.ext import commands
from discord.app_commands import locale_str, describe

from sausage_bot.util import config, envs, db_helper, discord_commands
from sausage_bot.util.l10n import _t

logger = config.logger

GITHUB_API = "https://api.github.com"
# GitHub rejects issue titles longer than this
TITLE_MAX = 256
# Discord's limits for a modal text input
BODY_MODAL_MAX = 4000
# Room left in a 2000 character message for the quote and the issue link
QUOTE_MAX = 1800
DRAFT_BODY_PREVIEW_MAX = 1400
# Messages the owner sends within this many seconds of each other become
# one draft - a forward and the text added to it arrive as two messages
DEBOUNCE_SECONDS = 5
# Where in the repo the images of an issue are saved. Discord's attachment
# links stop working after a while, so the images are moved here
IMAGE_DIR = "data/dev/github_imgs"
# The branch the images are committed to. The default branch can't be used:
# its rules require status checks, which a commit through the API can't pass.
# It is created from the default branch the first time an image is saved
IMAGE_BRANCH = "issue-images"


def local_image_dir() -> Path:
    "The folder in the bot's data dir that keeps a copy of every saved image"
    return envs.DATA_DIR / "dev" / "github_imgs"



DISCORD_IMAGE_REGEX = re.compile(
    r"!\[([^\]]*)\]\((https://(?:cdn|media)\.discordapp\.(?:com|net)/[^)\s]+)\)"
)
REPO_REGEX = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def in_admin_guild(guild_id) -> bool:
    "The dev cog only works in the guild that is set as admin guild"
    return guild_id is not None and str(guild_id) == str(config.ADMIN_GUILD_ID)


async def get_settings() -> dict:
    "Return the dev settings as `{setting: value}`"
    return await db_helper.get_output(
        envs.dev_settings_db_schema, as_settings_json=True
    )


async def set_setting(setting: str, value) -> None:
    "Replace one dev setting"
    await db_helper.del_row_by_AND_filter(
        envs.dev_settings_db_schema, where=[("setting", setting)]
    )
    await db_helper.insert_many_all(
        envs.dev_settings_db_schema, [(setting, str(value))]
    )


async def get_draft(message_id) -> dict | None:
    "Return the draft saved for the owner's message `message_id`, if any"
    draft = await db_helper.get_output(
        envs.dev_drafts_db_schema,
        where=("message_id", str(message_id)),
        single=True,
    )
    return draft or None


async def save_draft(
    message_id, channel_id, confirm_message_id, author_id, title, body
) -> None:
    """
    Save (or replace) a draft. Done as delete + insert, since the insert
    is parameterized and so safe for any title/body text.
    """
    await db_helper.del_row_by_AND_filter(
        envs.dev_drafts_db_schema, where=[("message_id", str(message_id))]
    )
    await db_helper.insert_many_all(
        envs.dev_drafts_db_schema,
        [
            (
                str(message_id),
                str(channel_id),
                str(confirm_message_id),
                str(author_id),
                title,
                body,
            )
        ],
    )


async def delete_draft(message_id) -> None:
    "Delete a draft and the list of messages it was made from"
    await db_helper.del_row_by_AND_filter(
        envs.dev_drafts_db_schema, where=[("message_id", str(message_id))]
    )
    await db_helper.del_row_by_AND_filter(
        envs.dev_draft_messages_db_schema, where=[("draft_id", str(message_id))]
    )


async def save_draft_message_ids(draft_id, message_ids) -> None:
    await db_helper.insert_many_all(
        envs.dev_draft_messages_db_schema,
        [(str(draft_id), str(message_id)) for message_id in message_ids],
    )


async def get_draft_message_ids(draft_id) -> list[int]:
    """
    Ids of all the owner's messages a draft was made from. Falls back to
    just `draft_id` for a draft saved before messages were collected.
    """
    rows = await db_helper.get_output(
        envs.dev_draft_messages_db_schema,
        where=("draft_id", str(draft_id)),
    )
    return [int(row["message_id"]) for row in rows] or [int(draft_id)]


def message_text_and_files(message) -> tuple[str, list]:
    """
    Get the text and the attachments of a message. A forwarded
    message has no content of its own to speak of: what was forwarded is
    in its `message_snapshots`, so that text comes after any text the
    sender added.
    """
    parts = [message.content]
    attachments = list(message.attachments)
    for snapshot in getattr(message, "message_snapshots", []):
        parts.append(snapshot.content)
        attachments.extend(snapshot.attachments)
    text = "\n\n".join(part.strip() for part in parts if part and part.strip())
    return text, attachments


def attachment_markdown(attachment) -> str:
    "Images are shown in the issue, other files are linked"
    name = attachment.filename
    if (attachment.content_type or "").startswith("image/"):
        return f"![{name}]({attachment.url})"
    return f"- [{name}]({attachment.url})"


def build_draft(text: str, attachments: list) -> tuple[str, str]:
    """
    Make an issue draft: the first line (cut to GitHub's limit) is the
    title and the whole text is the body, with the attachments last.
    """
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    title = first_line[:TITLE_MAX] or _t("dev.msg_untitled")
    body = text
    if attachments:
        files = "\n".join(attachment_markdown(a) for a in attachments)
        body = f"{body}\n\n**{_t('dev.attachments_heading')}**\n{files}".strip()
    return title, body


def quote_text(text: str, max_length: int = QUOTE_MAX) -> str:
    "Format `text` as a Discord blockquote, cut to `max_length`"
    if len(text) > max_length:
        text = text[: max_length - 1] + "…"
    return "\n".join(f"> {line}" for line in text.splitlines())


def draft_message(owner_id, repo, title, body) -> str:
    "The confirmation message that is posted for a draft"
    return _t(
        "dev.msg_draft",
        owner=f"<@{owner_id}>",
        repo=repo,
        title=title,
        body=quote_text(body, DRAFT_BODY_PREVIEW_MAX),
    )


def github_headers() -> dict:
    return {
        "Authorization": f"Bearer {config.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "sausage-bot",
    }


async def download_file(url: str) -> bytes | None:
    "Download `url`. Returns None when it fails, e.g. an expired Discord link"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status != 200:
                    logger.warning(f"Could not download {url}: {response.status}")
                    return None
                return await response.read()
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.warning(f"Could not download {url}: {e}")
        return None


async def ensure_image_branch(repo: str) -> str | None:
    """
    Make sure `IMAGE_BRANCH` exists in `repo`, creating it from the
    default branch if it doesn't. Returns None, or an error.
    """
    try:
        async with aiohttp.ClientSession() as session:
            timeout = aiohttp.ClientTimeout(total=30)

            async def request(method, path, **kwargs):
                async with session.request(
                    method,
                    f"{GITHUB_API}/repos/{repo}{path}",
                    headers=github_headers(),
                    timeout=timeout,
                    **kwargs,
                ) as response:
                    return response.status, await response.json()

            status, data = await request("GET", f"/git/ref/heads/{IMAGE_BRANCH}")
            if status == 200:
                return None
            if status != 404:
                return f"{status} {data.get('message', '')}".strip()
            status, data = await request("GET", "")
            if status != 200:
                return f"{status} {data.get('message', '')}".strip()
            status, data = await request(
                "GET", f"/git/ref/heads/{data['default_branch']}"
            )
            if status != 200:
                return f"{status} {data.get('message', '')}".strip()
            status, data = await request(
                "POST",
                "/git/refs",
                json={
                    "ref": f"refs/heads/{IMAGE_BRANCH}",
                    "sha": data["object"]["sha"],
                },
            )
            if status != 201:
                return f"{status} {data.get('message', '')}".strip()
            return None
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.error(f"Could not reach GitHub: {e}")
        return str(e) or type(e).__name__


async def upload_image(
    repo: str, path: str, content: bytes
) -> tuple[str | None, str | None]:
    """
    Commit `content` to `path` in `repo` (on `IMAGE_BRANCH`) through
    the GitHub contents API. Returns `(url, None)` with a link that shows
    the file, or `(None, error)`. A file that is already there from an
    earlier try is reused.
    """
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    payload = {
        "message": f"Add {path.rsplit('/', 1)[-1]}",
        "content": base64.b64encode(content).decode(),
        "branch": IMAGE_BRANCH,
    }
    try:
        async with aiohttp.ClientSession() as session:
            timeout = aiohttp.ClientTimeout(total=60)
            async with session.put(
                url, json=payload, headers=github_headers(), timeout=timeout
            ) as response:
                data = await response.json()
                if response.status in (200, 201):
                    return f"{data['content']['html_url']}?raw=true", None
                if response.status != 422:
                    message = data.get("message", "") if isinstance(data, dict) else ""
                    return None, f"{response.status} {message}".strip()
            # 422: the file exists already, so look up where it is
            async with session.get(
                url,
                params={"ref": IMAGE_BRANCH},
                headers=github_headers(),
                timeout=timeout,
            ) as response:
                data = await response.json()
                if response.status == 200:
                    return f"{data['html_url']}?raw=true", None
                message = data.get("message", "") if isinstance(data, dict) else ""
                return None, f"{response.status} {message}".strip()
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.error(f"Could not reach GitHub: {e}")
        return None, str(e) or type(e).__name__


async def move_images_to_repo(
    repo: str, draft_id, body: str
) -> tuple[str | None, str | None]:
    """
    Save the Discord images in `body` in the repo and point the body at
    the saved copies instead. A copy of each image is also kept in
    `local_image_dir()`. An image that can't be downloaded any more
    keeps its Discord link. Returns `(body, None)` or `(None, error)` when
    saving an image to the repo fails.
    """
    branch_checked = False
    for index, match in enumerate(DISCORD_IMAGE_REGEX.finditer(body), start=1):
        name, url = match.groups()
        content = await download_file(url)
        if content is None:
            continue
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", name) or "image"
        file_name = f"{draft_id}-{index}-{safe_name}"
        local_dir = local_image_dir()
        await asyncio.to_thread(local_dir.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread((local_dir / file_name).write_bytes, content)
        path = f"{IMAGE_DIR}/{file_name}"
        if not branch_checked:
            error = await ensure_image_branch(repo)
            if error:
                return None, error
            branch_checked = True
        saved_url, error = await upload_image(repo, path, content)
        if saved_url is None:
            return None, error
        body = body.replace(url, saved_url)
    return body, None


async def create_issue(
    repo: str, title: str, body: str
) -> tuple[dict | None, str | None]:
    """
    Create an issue in `repo` through the GitHub REST API. Returns
    `(issue, None)` on success and `(None, error)` when it fails.
    """
    headers = github_headers()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{GITHUB_API}/repos/{repo}/issues",
                json={"title": title, "body": body},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                data = await response.json()
                if response.status == 201:
                    return data, None
                message = data.get("message", "") if isinstance(data, dict) else ""
                return None, f"{response.status} {message}".strip()
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.error(f"Could not reach GitHub: {e}")
        return None, str(e) or type(e).__name__


async def delete_message_quietly(message) -> None:
    try:
        await message.delete()
    except discord.HTTPException as e:
        logger.debug(f"Could not delete message: {e}")


class EditDraftModal(discord.ui.Modal):
    "Edit the title and body of a draft, prefilled with the current text"

    def __init__(self, message_id, title: str, body: str):
        super().__init__(title=_t("dev.modal.title"))
        self.message_id = message_id
        self.title_input = discord.ui.TextInput(
            label=_t("dev.modal.field_title"),
            default=title[:TITLE_MAX],
            max_length=TITLE_MAX,
        )
        self.body_input = discord.ui.TextInput(
            label=_t("dev.modal.field_body"),
            default=body[:BODY_MODAL_MAX],
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=BODY_MODAL_MAX,
        )
        self.add_item(self.title_input)
        self.add_item(self.body_input)

    async def on_submit(self, interaction: discord.Interaction):
        async with db_helper.guild_locale_context(interaction.guild_id):
            draft = await get_draft(self.message_id)
            if draft is None:
                await interaction.response.send_message(
                    _t("dev.msg_draft_missing"), ephemeral=True
                )
                return
            title = self.title_input.value.strip()
            body = self.body_input.value
            await save_draft(
                self.message_id,
                draft["channel_id"],
                draft["confirm_message_id"],
                draft["author_id"],
                title,
                body,
            )
            settings = await get_settings()
            await interaction.response.edit_message(
                content=draft_message(
                    draft["author_id"], settings.get("repo"), title, body
                ),
                view=DraftView(self.message_id),
            )


class DraftView(discord.ui.View):
    """
    Yes/Edit/Cancel buttons under a draft. Has no timeout and fixed
    `custom_id`s built from the owner's message id, so the buttons keep
    working after a restart (the cog registers a view for every draft
    that is still waiting, see `Dev.cog_load()`).
    """

    def __init__(self, message_id):
        super().__init__(timeout=None)
        self.message_id = message_id
        for key, style, callback in (
            ("yes", discord.ButtonStyle.success, self.yes),
            ("edit", discord.ButtonStyle.primary, self.edit),
            ("cancel", discord.ButtonStyle.danger, self.cancel),
        ):
            button = discord.ui.Button(
                label=_t(f"dev.buttons.{key}"),
                style=style,
                custom_id=f"dev:{key}:{message_id}",
            )
            button.callback = callback
            self.add_item(button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if await interaction.client.is_owner(interaction.user):
            return True
        async with db_helper.guild_locale_context(interaction.guild_id):
            await interaction.response.send_message(
                _t("common.msg_owner_only"), ephemeral=True
            )
        return False

    async def yes(self, interaction: discord.Interaction):
        async with db_helper.guild_locale_context(interaction.guild_id):
            await interaction.response.defer()
            draft = await get_draft(self.message_id)
            if draft is None:
                await interaction.followup.send(
                    _t("dev.msg_draft_missing"), ephemeral=True
                )
                await delete_message_quietly(interaction.message)
                return
            repo = (await get_settings()).get("repo")
            body, error = await move_images_to_repo(repo, self.message_id, draft["body"])
            if body is None:
                await interaction.followup.send(_t("dev.msg_issue_failed", error=error))
                return
            issue, error = await create_issue(repo, draft["title"], body)
            if issue is None:
                # Keep the draft and the original, so Yes can be tried again
                await interaction.followup.send(_t("dev.msg_issue_failed", error=error))
                return
            channel = interaction.channel
            originals = []
            for original_id in await get_draft_message_ids(self.message_id):
                try:
                    originals.append(await channel.fetch_message(original_id))
                except discord.HTTPException:
                    continue
            quoted = "\n\n".join(
                text for text in (message_text_and_files(m)[0] for m in originals) if text
            )
            await channel.send(
                quote_text(quoted or draft["body"])
                + "\n"
                + _t(
                    "dev.msg_issue_created",
                    number=issue["number"],
                    url=issue["html_url"],
                )
            )
            for original in originals:
                await delete_message_quietly(original)
            await delete_message_quietly(interaction.message)
            await delete_draft(self.message_id)

    async def edit(self, interaction: discord.Interaction):
        async with db_helper.guild_locale_context(interaction.guild_id):
            draft = await get_draft(self.message_id)
            if draft is None:
                await interaction.response.send_message(
                    _t("dev.msg_draft_missing"), ephemeral=True
                )
                return
            await interaction.response.send_modal(
                EditDraftModal(self.message_id, draft["title"], draft["body"])
            )

    async def cancel(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await delete_message_quietly(interaction.message)
        await delete_draft(self.message_id)


class Dev(commands.Cog):
    "Turn the bot owner's messages in a todo channel into GitHub issues"

    def __init__(self, bot):
        self.bot = bot
        # Owner messages waiting to become one draft, per channel id:
        # `{"messages": [...], "task": asyncio.Task}`
        self._pending = {}
        super().__init__()

    async def _warn_missing_token(self):
        "Tell the bot channel of the admin guild once that GITHUB_TOKEN is not set"
        await self.bot.wait_until_ready()
        if not config.ADMIN_GUILD_ID:
            return
        guild = self.bot.get_guild(int(config.ADMIN_GUILD_ID))
        if guild is None:
            return
        async with db_helper.guild_locale_context(guild.id):
            await discord_commands.log_to_bot_channel(
                guild, _t("dev.msg_no_token")
            )

    async def cog_load(self):
        "Give the buttons of drafts that are still waiting their callbacks back"
        if not config.GITHUB_TOKEN:
            logger.warning("GITHUB_TOKEN is not set, dev cannot create issues")
            self._token_warning = asyncio.create_task(self._warn_missing_token())
        drafts = await db_helper.get_output(envs.dev_drafts_db_schema)
        if not drafts:
            return
        if config.ADMIN_GUILD_ID:
            async with db_helper.guild_locale_context(config.ADMIN_GUILD_ID):
                views = [DraftView(row["message_id"]) for row in drafts]
        else:
            views = [DraftView(row["message_id"]) for row in drafts]
        for row, view in zip(drafts, views):
            self.bot.add_view(view, message_id=int(row["confirm_message_id"]))
        logger.debug(f"Restored {len(views)} waiting issue drafts")

    group = discord.app_commands.Group(
        name="dev", description=locale_str(_t("dev.group.cmd"))
    )

    @discord_commands.is_owner()
    @group.command(
        name="channel", description=locale_str(_t("dev.commands.channel.cmd"))
    )
    @describe(channel=_t("dev.commands.channel.desc.channel"))
    async def dev_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not in_admin_guild(interaction.guild_id):
            await interaction.followup.send(
                _t("dev.msg_not_admin_guild"), ephemeral=True
            )
            return
        await set_setting("channel", channel.id)
        await interaction.followup.send(
            _t("dev.commands.channel.msg_confirm", channel=channel.mention),
            ephemeral=True,
        )

    @discord_commands.is_owner()
    @group.command(name="repo", description=locale_str(_t("dev.commands.repo.cmd")))
    @describe(repo=_t("dev.commands.repo.desc.repo"))
    async def dev_repo(self, interaction: discord.Interaction, repo: str) -> None:
        await interaction.response.defer(ephemeral=True)
        if not in_admin_guild(interaction.guild_id):
            await interaction.followup.send(
                _t("dev.msg_not_admin_guild"), ephemeral=True
            )
            return
        repo = repo.strip()
        if not REPO_REGEX.match(repo):
            await interaction.followup.send(
                _t("dev.commands.repo.msg_invalid"), ephemeral=True
            )
            return
        await set_setting("repo", repo)
        await interaction.followup.send(
            _t("dev.commands.repo.msg_confirm", repo=repo), ephemeral=True
        )

    @discord_commands.is_owner()
    @group.command(
        name="settings", description=locale_str(_t("dev.commands.settings.cmd"))
    )
    async def dev_settings(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not in_admin_guild(interaction.guild_id):
            await interaction.followup.send(
                _t("dev.msg_not_admin_guild"), ephemeral=True
            )
            return
        settings = await get_settings()
        not_set = _t("dev.commands.settings.not_set")
        channel_id = settings.get("channel")
        token = (
            _t("dev.commands.settings.token_set")
            if config.GITHUB_TOKEN
            else _t("dev.commands.settings.token_missing")
        )
        await interaction.followup.send(
            _t(
                "dev.commands.settings.msg_settings",
                channel=f"<#{channel_id}>" if channel_id else not_set,
                repo=settings.get("repo") or not_set,
                token=token,
            ),
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return
        if not in_admin_guild(message.guild.id):
            return
        if message.type not in (discord.MessageType.default, discord.MessageType.reply):
            return
        settings = await get_settings()
        if str(message.channel.id) != str(settings.get("channel")):
            return
        if not await self.bot.is_owner(message.author):
            return
        if not config.GITHUB_TOKEN:
            async with db_helper.guild_locale_context(message.guild.id):
                await message.reply(_t("dev.msg_no_token"))
            return
        pending = self._pending.setdefault(
            message.channel.id, {"messages": [], "task": None}
        )
        pending["messages"].append(message)
        # Every new message restarts the wait, so a batch is only made
        # into a draft once the owner has stopped sending
        if pending["task"]:
            pending["task"].cancel()
        pending["task"] = asyncio.create_task(self._flush_later(message.channel.id))

    async def _flush_later(self, channel_id):
        await asyncio.sleep(DEBOUNCE_SECONDS)
        await self.flush(channel_id)

    async def flush(self, channel_id):
        "Make one draft of the messages collected in `channel_id`"
        pending = self._pending.pop(channel_id, None)
        if not pending or not pending["messages"]:
            return
        messages = pending["messages"]
        first = messages[0]
        async with db_helper.guild_locale_context(first.guild.id):
            repo = (await get_settings()).get("repo")
            if not repo or not config.GITHUB_TOKEN:
                await first.reply(_t("dev.msg_not_configured"))
                return
            texts, attachments = [], []
            for message in messages:
                message_text, message_attachments = message_text_and_files(message)
                if message_text:
                    texts.append(message_text)
                attachments.extend(message_attachments)
            text = "\n\n".join(texts)
            if not text and not attachments:
                return
            title, body = build_draft(text, attachments)
            confirm = await first.reply(
                draft_message(first.author.id, repo, title, body),
                view=DraftView(first.id),
            )
            await save_draft(
                first.id,
                first.channel.id,
                confirm.id,
                first.author.id,
                title,
                body,
            )
            await save_draft_message_ids(first.id, [m.id for m in messages])


async def setup(bot):
    cog_name = "dev"
    logger.info(envs.COG_STARTING.format(cog_name))
    logger.debug("Checking db")
    await db_helper.prep_table(envs.dev_settings_db_schema)
    await db_helper.prep_table(envs.dev_drafts_db_schema)
    await db_helper.prep_table(envs.dev_draft_messages_db_schema)
    logger.debug("Registering cog to bot")
    await bot.add_cog(Dev(bot))
    logger.info(envs.COG_STARTED.format(cog_name))
