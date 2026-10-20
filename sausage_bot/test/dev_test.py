#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Covers the dev cog: turning the bot owner's messages in the todo channel
into issue drafts, and the settings commands that point the cog at a
channel and a repo.

GitHub is never called - `create_issue` is the only place that talks to
it - and `guild_db_root` (see conftest.py) keeps every write in a
throwaway directory.
"""

from types import SimpleNamespace
from unittest import mock

import discord

from sausage_bot.cogs import dev
from sausage_bot.util import config, envs, db_helper

ADMIN_GUILD = 111111111111111111
OTHER_GUILD = 222222222222222222
TODO_CHANNEL = 333333333333333333


def _make_interaction(guild_id=ADMIN_GUILD):
    return SimpleNamespace(
        response=SimpleNamespace(defer=mock.AsyncMock()),
        followup=SimpleNamespace(send=mock.AsyncMock()),
        guild_id=guild_id,
    )


def _make_message(content, author_is_bot=False, guild_id=ADMIN_GUILD, id=555):
    return SimpleNamespace(
        id=id,
        content=content,
        attachments=[],
        message_snapshots=[],
        author=SimpleNamespace(id=42, bot=author_is_bot),
        guild=SimpleNamespace(id=guild_id),
        channel=SimpleNamespace(id=TODO_CHANNEL),
        type=discord.MessageType.default,
        reply=mock.AsyncMock(return_value=SimpleNamespace(id=999)),
    )


def _make_cog(owner_is_author=True):
    bot = SimpleNamespace(is_owner=mock.AsyncMock(return_value=owner_is_author))
    return dev.Dev(bot)


async def _send_and_flush(cog, *messages):
    "Let the owner send `messages`, then skip the wait and make the draft"
    for message in messages:
        await cog.on_message(message)
    for pending in cog._pending.values():
        pending["task"].cancel()
    await cog.flush(TODO_CHANNEL)


async def _prep_dev(monkeypatch, repo="geirawsm/sausage_bot"):
    "The admin guild, its todo channel, a repo and a token are all set"
    monkeypatch.setattr(config, "ADMIN_GUILD_ID", str(ADMIN_GUILD))
    monkeypatch.setattr(config, "GITHUB_TOKEN", "token")
    await db_helper.prep_table(envs.dev_settings_db_schema)
    await db_helper.prep_table(envs.dev_drafts_db_schema)
    await dev.set_setting("channel", TODO_CHANNEL)
    await dev.set_setting("repo", repo)


def test_build_draft_uses_the_first_line_as_title_and_everything_as_body():
    title, body = dev.build_draft("Fix the ping\nIt answers twice", [])

    assert title == "Fix the ping"
    assert body == "Fix the ping\nIt answers twice"


def test_build_draft_cuts_a_long_first_line_to_githubs_title_limit():
    title, _ = dev.build_draft("x" * 300, [])

    assert title == "x" * 256


def _attachment(filename, content_type):
    return SimpleNamespace(
        url=f"https://cdn/{filename}", filename=filename, content_type=content_type
    )


def test_build_draft_shows_images_and_links_other_files_last():
    attachments = [
        _attachment("a.png", "image/png"),
        _attachment("log.txt", "text/plain"),
    ]

    _, body = dev.build_draft("See image", attachments)

    assert body == (
        "See image\n\n**Attachments**\n"
        "![a.png](https://cdn/a.png)\n"
        "- [log.txt](https://cdn/log.txt)"
    )


def test_message_text_puts_forwarded_text_after_the_senders_own():
    snapshot = SimpleNamespace(
        content="forwarded text",
        attachments=[_attachment("fwd.png", "image/png")],
    )
    message = SimpleNamespace(
        content="Please look at this",
        attachments=[],
        message_snapshots=[snapshot],
    )

    text, attachments = dev.message_text_and_files(message)

    assert text == "Please look at this\n\nforwarded text"
    assert [a.url for a in attachments] == ["https://cdn/fwd.png"]


def test_quote_text_quotes_every_line():
    assert dev.quote_text("one\ntwo") == "> one\n> two"


def test_in_admin_guild_is_false_for_other_guilds(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_GUILD_ID", str(ADMIN_GUILD))

    assert dev.in_admin_guild(ADMIN_GUILD) is True
    assert dev.in_admin_guild(OTHER_GUILD) is False


async def test_repo_command_stores_a_valid_repo(guild_db_root, monkeypatch):
    await _prep_dev(monkeypatch, repo="old/repo")

    await dev.Dev.dev_repo.callback(
        _make_cog(), _make_interaction(), "geirawsm/sausage_bot"
    )

    assert (await dev.get_settings())["repo"] == "geirawsm/sausage_bot"


async def test_repo_command_rejects_something_that_is_not_owner_slash_name(
    guild_db_root, monkeypatch
):
    await _prep_dev(monkeypatch, repo="old/repo")

    await dev.Dev.dev_repo.callback(_make_cog(), _make_interaction(), "no-slash")

    assert (await dev.get_settings())["repo"] == "old/repo"


async def test_repo_command_does_nothing_outside_the_admin_guild(
    guild_db_root, monkeypatch
):
    await _prep_dev(monkeypatch, repo="old/repo")

    await dev.Dev.dev_repo.callback(
        _make_cog(), _make_interaction(OTHER_GUILD), "new/repo"
    )

    assert (await dev.get_settings())["repo"] == "old/repo"


async def test_message_from_the_owner_gets_a_draft_saved(guild_db_root, monkeypatch):
    await _prep_dev(monkeypatch)
    message = _make_message("Fix the ping\nIt answers twice")

    await _send_and_flush(_make_cog(), message)

    draft = await dev.get_draft(555)
    assert (draft["title"], draft["confirm_message_id"]) == ("Fix the ping", "999")
    message.reply.assert_awaited_once()


async def test_messages_sent_close_together_become_one_draft(
    guild_db_root, monkeypatch
):
    await _prep_dev(monkeypatch)
    await db_helper.prep_table(envs.dev_draft_messages_db_schema)
    forward = _make_message("", id=555)
    forward.message_snapshots = [
        SimpleNamespace(content="Forwarded bug report", attachments=[])
    ]
    comment = _make_message("Please fix this", id=556)

    await _send_and_flush(_make_cog(), forward, comment)

    draft = await dev.get_draft(555)
    assert draft["body"] == "Forwarded bug report\n\nPlease fix this"
    assert await dev.get_draft(556) is None
    assert await dev.get_draft_message_ids(555) == [555, 556]
    forward.reply.assert_awaited_once()
    comment.reply.assert_not_awaited()


async def test_message_from_someone_else_than_the_owner_is_ignored(
    guild_db_root, monkeypatch
):
    await _prep_dev(monkeypatch)
    message = _make_message("Fix the ping")

    await _send_and_flush(_make_cog(owner_is_author=False), message)

    assert await dev.get_draft(555) is None
    message.reply.assert_not_awaited()


async def test_message_in_another_guild_is_ignored(guild_db_root, monkeypatch):
    await _prep_dev(monkeypatch)
    message = _make_message("Fix the ping", guild_id=OTHER_GUILD)

    await _send_and_flush(_make_cog(), message)

    assert await dev.get_draft(555) is None
    message.reply.assert_not_awaited()


async def test_message_without_a_token_asks_for_setup_instead_of_a_draft(
    guild_db_root, monkeypatch
):
    await _prep_dev(monkeypatch)
    monkeypatch.setattr(config, "GITHUB_TOKEN", "")
    message = _make_message("Fix the ping")

    await _send_and_flush(_make_cog(), message)

    assert await dev.get_draft(555) is None
    message.reply.assert_awaited_once_with(
        "Set the todo channel and repo with `/dev channel` and `/dev repo`, "
        "and add GITHUB_TOKEN to .env, before I can create issues"
    )


async def test_saving_a_draft_twice_keeps_one_row_with_the_new_text(guild_db_root):
    await db_helper.prep_table(envs.dev_drafts_db_schema)

    await dev.save_draft(555, 1, 999, 42, "Old title", "Old body")
    await dev.save_draft(555, 1, 999, 42, "It's new", "New body")

    draft = await dev.get_draft(555)
    assert (draft["title"], draft["body"]) == ("It's new", "New body")


async def test_images_are_saved_locally_and_in_the_repo_and_linked_from_there(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(envs, "DATA_DIR", tmp_path)
    body = "See\n\n![a.png](https://cdn.discordapp.com/attachments/1/a.png?ex=1)"
    with (
        mock.patch.object(dev, "download_file", mock.AsyncMock(return_value=b"img")),
        mock.patch.object(dev, "ensure_image_branch", mock.AsyncMock(return_value=None)),
        mock.patch.object(
            dev,
            "upload_image",
            mock.AsyncMock(return_value=("https://github.com/o/r/blob/main/a?raw=true", None)),
        ) as upload,
    ):
        new_body, error = await dev.move_images_to_repo("o/r", 555, body)

    upload.assert_awaited_once_with("o/r", "data/dev/github_imgs/555-1-a.png", b"img")
    assert (tmp_path / "dev" / "github_imgs" / "555-1-a.png").read_bytes() == b"img"
    assert (new_body, error) == (
        "See\n\n![a.png](https://github.com/o/r/blob/main/a?raw=true)",
        None,
    )


async def test_an_image_that_cannot_be_downloaded_keeps_its_discord_link():
    body = "![a.png](https://cdn.discordapp.com/attachments/1/a.png?ex=1)"
    with (
        mock.patch.object(dev, "download_file", mock.AsyncMock(return_value=None)),
        mock.patch.object(dev, "upload_image", mock.AsyncMock()) as upload,
    ):
        new_body, error = await dev.move_images_to_repo("o/r", 555, body)

    upload.assert_not_awaited()
    assert (new_body, error) == (body, None)


async def test_a_failed_upload_gives_an_error_and_no_body():
    body = "![a.png](https://cdn.discordapp.com/attachments/1/a.png?ex=1)"
    with (
        mock.patch.object(dev, "download_file", mock.AsyncMock(return_value=b"img")),
        mock.patch.object(dev, "ensure_image_branch", mock.AsyncMock(return_value=None)),
        mock.patch.object(
            dev, "upload_image", mock.AsyncMock(return_value=(None, "403 Forbidden"))
        ),
    ):
        new_body, error = await dev.move_images_to_repo("o/r", 555, body)

    assert (new_body, error) == (None, "403 Forbidden")


async def test_a_failed_branch_creation_stops_before_any_upload():
    body = "![a.png](https://cdn.discordapp.com/attachments/1/a.png?ex=1)"
    with (
        mock.patch.object(dev, "download_file", mock.AsyncMock(return_value=b"img")),
        mock.patch.object(
            dev, "ensure_image_branch", mock.AsyncMock(return_value="403 Forbidden")
        ),
        mock.patch.object(dev, "upload_image", mock.AsyncMock()) as upload,
    ):
        new_body, error = await dev.move_images_to_repo("o/r", 555, body)

    upload.assert_not_awaited()
    assert (new_body, error) == (None, "403 Forbidden")
