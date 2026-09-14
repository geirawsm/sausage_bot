#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for what happens when a feed corrects the link of an item that is
already posted.

A publisher fixes a typo in an url and the item comes back as new. The
url is new, but the text is the same, so this is the same post - and the
bot should edit the message it already sent instead of posting again.

    url in log                  -> skip
    url new, content hash known -> edit the old message, move the log row
    both new                    -> post and log

The hash has to be made from something that can be reproduced without
asking the web for it, so it is made from the feed item's own text.
"""

from types import SimpleNamespace

import discord
import pytest

from sausage_bot.util import (
    db_helper,
    discord_commands,
    envs,
    feeds_core,
    net_io,
)

GUILD_ID = 555555555555555555
UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
FEED_NAME = "kode24"
CHANNEL = "1022791150047858728"
DESC = "Mattilsynet skal bli mer risikovillige, sier utviklingssjefen."
MSG_ID = 1414141414141414141
TYPO_LINK = "https://www.kode24.no/artikkel/ny-utviklingsavdeling/7619499"
FIXED_LINK = "https://www.kode24.no/artikkel/ny-utviklingsavdeling/76194994"


@pytest.fixture
def guild(guild_db_root, monkeypatch):
    """
    A guild that collects what the bot posts and edits instead of
    talking to discord.
    """
    posted = []
    edited = []
    bot_channel = []

    async def _post(channel_in, content_in=None, embed_in=None, files_in=None,
                    view=None):
        posted.append((channel_in, content_in))
        return SimpleNamespace(id=MSG_ID, content=content_in)

    async def _replace(guild_in, replace_content, replace_with, channel_in,
                       msg_id=None):
        edited.append((replace_content, replace_with, msg_id))
        return True

    async def _log_to_bot(guild_in, content):
        bot_channel.append(content)

    monkeypatch.setattr(feeds_core.discord_commands, "post_to_channel", _post)
    monkeypatch.setattr(feeds_core.discord_commands, "replace_post", _replace)
    monkeypatch.setattr(feeds_core.discord_commands, "log_to_bot_channel", _log_to_bot)
    monkeypatch.setattr(feeds_core.args, "testmode", False)
    return SimpleNamespace(
        id=GUILD_ID,
        name="Dissonance",
        posted=posted,
        edited=edited,
        bot_channel=bot_channel,
        get_channel_or_thread=lambda _id: SimpleNamespace(id=_id),
    )


@pytest.fixture
def no_web(monkeypatch):
    """
    The whole point of the content hash is that no page is fetched to
    make it, so any call here is a test failure.
    """

    async def _boom(*args, **kwargs):
        raise AssertionError("the posting logic fetched a page to make a hash")

    monkeypatch.setattr(feeds_core.net_io, "get_page_hash", _boom)
    monkeypatch.setattr(feeds_core.net_io, "get_link", _boom)


async def _seed_log(url, hash_in, msg_id=None):
    await db_helper.prep_table(envs.rss_db_log_schema, guild_id=GUILD_ID)
    await feeds_core.log_link(
        envs.rss_db_log_schema,
        UUID,
        url,
        hash_in,
        SimpleNamespace(id=GUILD_ID),
        msg_id=msg_id,
    )


async def _read_log():
    return await db_helper.get_output(
        template_info=envs.rss_db_log_schema,
        select=("url", "hash", "msg_id"),
        where=[("uuid", UUID)],
        guild_id=GUILD_ID,
    )


def _item(link, description=DESC, title="Ny utviklingsavdeling"):
    return {
        "type": "rss",
        "title": title,
        "description": description,
        "hash": net_io.get_content_hash(description, title),
        "link": link,
        "img": "",
    }


async def _run(guild, items):
    await feeds_core.process_links_for_posting_or_editing(
        feed_name=FEED_NAME,
        feed_type="rss",
        uuid=UUID,
        FEED_POSTS=items,
        CHANNEL=CHANNEL,
        guild=guild,
    )


# The content hash


def test_hash_survives_a_fixed_link_in_the_text():
    # The typo sits in the url, and feeds like to repeat the url inside
    # the description, so urls are not part of what is hashed.
    typo = f"Les mer: {TYPO_LINK}"
    fixed = f"Les mer: {FIXED_LINK}"
    assert net_io.get_content_hash(typo) == net_io.get_content_hash(fixed)


def test_hash_ignores_markup():
    assert net_io.get_content_hash(f"<p>{DESC}</p>") == net_io.get_content_hash(DESC)


def test_hash_falls_back_to_the_title():
    assert net_io.get_content_hash(None, "Tittel") == net_io.get_content_hash("", "Tittel")
    assert net_io.get_content_hash(None, "Tittel") is not None


def test_hash_is_none_without_content():
    assert net_io.get_content_hash("", "") is None
    assert net_io.get_content_hash(None, None) is None


# The posting decision


async def test_a_known_link_is_left_alone(guild, no_web):
    item = _item(TYPO_LINK)
    await _seed_log(TYPO_LINK, item["hash"])
    await _run(guild, [item])
    assert guild.posted == []
    assert guild.edited == []
    assert len(await _read_log()) == 1


async def test_a_new_link_is_posted_and_logged(guild, no_web):
    item = _item(FIXED_LINK)
    await db_helper.prep_table(envs.rss_db_log_schema, guild_id=GUILD_ID)
    await _run(guild, [item])
    assert guild.posted == [(CHANNEL, FIXED_LINK)]
    log = await _read_log()
    assert len(log) == 1
    assert log[0]["url"] == FIXED_LINK
    assert log[0]["hash"] == item["hash"]


async def test_a_fixed_link_edits_the_old_post(guild, no_web):
    # Regression: this posted the item a second time.
    item = _item(FIXED_LINK)
    await _seed_log(TYPO_LINK, item["hash"])
    await _run(guild, [item])
    assert guild.posted == []
    assert guild.edited == [(TYPO_LINK, FIXED_LINK, None)]


async def test_a_fixed_link_moves_the_log_row(guild, no_web):
    # Without this the bot edits the same message over and over, once
    # per run, because the log still points at the old link.
    item = _item(FIXED_LINK)
    await _seed_log(TYPO_LINK, item["hash"])
    await _run(guild, [item])
    log = await _read_log()
    assert len(log) == 1
    assert log[0]["url"] == FIXED_LINK
    await _run(guild, [item])
    assert guild.edited == [(TYPO_LINK, FIXED_LINK, None)]


async def test_an_unfound_message_is_posted_as_new(guild, no_web, monkeypatch):
    # The original post can be older than the message history we look
    # through, or deleted. Then there is nothing to edit.
    async def _replace(guild_in, replace_content, replace_with, channel_in,
                       msg_id=None):
        guild.edited.append((replace_content, replace_with, msg_id))
        return False

    monkeypatch.setattr(feeds_core.discord_commands, "replace_post", _replace)
    item = _item(FIXED_LINK)
    await _seed_log(TYPO_LINK, item["hash"])
    await _run(guild, [item])
    assert guild.posted == [(CHANNEL, FIXED_LINK)]
    log = await _read_log()
    assert sorted(row["url"] for row in log) == sorted([TYPO_LINK, FIXED_LINK])


async def test_a_failed_post_is_not_logged(guild, no_web, monkeypatch):
    async def _post(channel_in, content_in=None, embed_in=None, files_in=None,
                    view=None):
        return None

    monkeypatch.setattr(feeds_core.discord_commands, "post_to_channel", _post)
    await db_helper.prep_table(envs.rss_db_log_schema, guild_id=GUILD_ID)
    await _run(guild, [_item(FIXED_LINK)])
    assert await _read_log() == []


async def test_a_new_post_records_its_message_id(guild, no_web):
    # The id is what lets a later fix edit that exact message instead
    # of digging through the channel history
    await db_helper.prep_table(envs.rss_db_log_schema, guild_id=GUILD_ID)
    await _run(guild, [_item(FIXED_LINK)])
    log = await _read_log()
    assert log[0]["msg_id"] == str(MSG_ID)


async def test_a_fixed_link_edits_by_message_id(guild, no_web):
    item = _item(FIXED_LINK)
    await _seed_log(TYPO_LINK, item["hash"], msg_id=MSG_ID)
    await _run(guild, [item])
    assert guild.edited == [(TYPO_LINK, FIXED_LINK, str(MSG_ID))]
    assert guild.posted == []


async def test_an_edited_post_keeps_its_message_id(guild, no_web):
    item = _item(FIXED_LINK)
    await _seed_log(TYPO_LINK, item["hash"], msg_id=MSG_ID)
    await _run(guild, [item])
    log = await _read_log()
    assert len(log) == 1
    assert log[0]["url"] == FIXED_LINK
    assert log[0]["msg_id"] == str(MSG_ID)


# Finding the message to edit


class FakeMsg:
    "A bot message that records what it was edited to"

    def __init__(self, content="", embeds=None, author_id="1"):
        self.content = content
        self.embeds = embeds or []
        self.author = SimpleNamespace(id=author_id)
        self.edits = []

    async def edit(self, content=None, embeds=None):
        self.edits.append({"content": content, "embeds": embeds})


def _channel(*messages):
    async def _history(limit=None):
        for msg in messages:
            yield msg

    return SimpleNamespace(history=_history)


@pytest.fixture
def bot_guild(monkeypatch):
    "A guild where the bot is author `1`"
    monkeypatch.setattr(discord_commands.config, "BOT_ID", "1")
    return monkeypatch


async def test_replace_post_edits_the_message_text(bot_guild):
    msg = FakeMsg(content=TYPO_LINK)
    guild = SimpleNamespace(get_channel=lambda _id: _channel(msg))
    assert await discord_commands.replace_post(
        guild, TYPO_LINK, FIXED_LINK, CHANNEL
    ) is True
    assert msg.edits[0]["content"] == FIXED_LINK


async def test_replace_post_edits_a_podcast_embed(bot_guild):
    # Podcast episodes are posted as embeds, so the link is not in
    # `msg.content` at all
    embed = discord.Embed(title="Episode", url=TYPO_LINK)
    embed.add_field(name="", value=f"[HØR PÅ EPISODEN]({TYPO_LINK})")
    msg = FakeMsg(embeds=[embed])
    guild = SimpleNamespace(get_channel=lambda _id: _channel(msg))
    assert await discord_commands.replace_post(
        guild, TYPO_LINK, FIXED_LINK, CHANNEL
    ) is True
    edited = msg.edits[0]["embeds"][0]
    assert edited.url == FIXED_LINK
    assert FIXED_LINK in edited.fields[0].value


async def test_replace_post_skips_other_authors(bot_guild):
    msg = FakeMsg(content=TYPO_LINK, author_id="999")
    guild = SimpleNamespace(get_channel=lambda _id: _channel(msg))
    assert await discord_commands.replace_post(
        guild, TYPO_LINK, FIXED_LINK, CHANNEL
    ) is False
    assert msg.edits == []


async def test_replace_post_reports_a_missing_message(bot_guild):
    guild = SimpleNamespace(get_channel=lambda _id: _channel(FakeMsg(content="hei")))
    assert await discord_commands.replace_post(
        guild, TYPO_LINK, FIXED_LINK, CHANNEL
    ) is False


async def test_replace_post_goes_straight_to_the_message(bot_guild):
    msg = FakeMsg(content=TYPO_LINK)

    def _history(limit=None):
        raise AssertionError("the channel history was searched anyway")

    async def _fetch(msg_id):
        assert msg_id == MSG_ID
        return msg

    channel = SimpleNamespace(history=_history, fetch_message=_fetch)
    guild = SimpleNamespace(get_channel=lambda _id: channel)
    assert await discord_commands.replace_post(
        guild, TYPO_LINK, FIXED_LINK, CHANNEL, msg_id=MSG_ID
    ) is True
    assert msg.edits[0]["content"] == FIXED_LINK


async def test_replace_post_falls_back_to_the_history(bot_guild):
    # Rows logged before the id column existed have no id, and a message
    # can be deleted after it was logged
    msg = FakeMsg(content=TYPO_LINK)

    async def _fetch(msg_id):
        raise discord.NotFound(
            SimpleNamespace(status=404, reason="Not Found"), "Unknown Message"
        )

    channel = _channel(msg)
    channel.fetch_message = _fetch
    guild = SimpleNamespace(get_channel=lambda _id: channel)
    assert await discord_commands.replace_post(
        guild, TYPO_LINK, FIXED_LINK, CHANNEL, msg_id=MSG_ID
    ) is True
    assert msg.edits[0]["content"] == FIXED_LINK


async def test_an_older_log_table_gets_the_id_column(guild_db_root):
    # Live log tables were made before `msg_id` existed, and the rss cog
    # brings them up to date on load
    old_schema = dict(envs.rss_db_log_schema)
    old_schema["items"] = [
        col for col in envs.rss_db_log_schema["items"] if col[0] != "msg_id"
    ]
    await db_helper.prep_table(old_schema, guild_id=GUILD_ID)
    await db_helper.add_missing_db_setup(
        envs.rss_db_log_schema, {}, guild_id=GUILD_ID
    )
    await feeds_core.log_link(
        envs.rss_db_log_schema,
        UUID,
        FIXED_LINK,
        "d41d8cd98f00b204e9800998ecf8427e",
        SimpleNamespace(id=GUILD_ID),
        msg_id=MSG_ID,
    )
    log = await _read_log()
    assert log[0]["msg_id"] == str(MSG_ID)
