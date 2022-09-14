# SausageBot

SausageBot - affectionately known as "pølsa" among its Norwegian users - is a Discord bot with some very specific functions.

## Usage

This code is intended to be selfhosted and run on a server you have access to.

## Installation

Ok, so you want to run a Discord bot?

### Register Discord bot
Read up on what you need to do to register a bot on Discord: https://discord.com/developers/docs/getting-started

### .env file
The .env file is essential to the bot. It contains all the important information that the bot uses, both for connecting to Discord and setting the correct stats channel, setting a custom "watching" info for the bot, and adding your API key if you want to use the Youtube-cog.
The first time running the script, it will fail, but it will also create a template .env file for you in the root folder.

### Actually running the bot
It is recommended to run the bot in a controlled environment, by using pipenv or similar services.
The bot is ran by the command `python -m sausage_bot` (or any other name you want to give the root folder).

If you run `python -m sausage_bot -h` you can also see all the arguments you can add.

## Functions

SausageBot has the following main functions:

### ping
`!ping` - Checks the bot latency

### delete

Permissions: is_owner, manage_messages=True

`!delete [amount]` - Delete [amount] messages in the channel you run the command.

### kick

Permissions: is_owner, kick_members=True

`!kick [member] ([reason])` - Kick a [member] from the server with an optional [reason]

### ban

Permissions: is_owner, ban_members=True

`!ban [member] ([reason])` - Ban a member from the server

### say

Permissions: is_owner, ban_members=True

`!say [something]` - Make the bot say [something] and delete the message with the command

---

## Cogs
Cogs are special commands for the bot. These can be enabled or disabled by using the `!cog` command:

`!cog list` - List all available cogs

`!cog [enable/disable] [cog name]` - Enable or disable an available cog

### autoevent

Administer match events on the discord server based on a url from a
supported website. Add, remove or list events.

#### add

Permissions: is_owner, manage_events=True

Add a scheduled event: `!autoevent add [url] [channel] [text]`

`channel` should be a voice channel for the event.

`url` should be a link to a specific match from an accepted site.
As of now only match links from nifs.no is parsed.

`text` is additional text that should be added to the description
of the event.

#### remove

Permissions: is_owner, manage_events=True

Removes a scheduled event that has not started yet: `!autoevent remove [event_id_in]`

You can get `event_id_in` by getting list of all events

#### list

Permissions: is_owner, manage_events=True

Lists all the planned events: `!autoevent list`

---

### dilemmas

Post a random dilemma: `!dilemmas`

Add a dilemma: `!dilemmas add [dilemmas_in]`

---

### quote
Permissions: is_owner, administrator=True

Post, add, edit, delete or count quotes

`!quote` posts a random quote

`!quote [number]` posts a specific quote

#### Add quote
Add a quote: `!quote add [quote_text] ([quote_date])`

`quote_text`:   The quote text. Must be enclosed in quotation marks.

`quote_date`:   Set a custom date and time for the quote added
(dd.mm.yyyy, HH:MM)

#### Edit quote
Edit an existing quote: `!quote edit [quote_number] [quote_in] [custom_date]`

`quote_number`: The number of quote to edit.

`quote_in`:     The quote text. Must be enclosed in quotation marks.

`custom_date`:  Set a different date and time.

#### Delete quote
Delete an existing quote: `!quote delete [quote_number]`

`quote_number`: The number of quote to edit.

#### Count quotes
Count the number of quotes available: `!quote count`

---

### rss
Administer RSS-feeds that will autopost to a given channel when published

Uses `add` and `remove` to administer RSS-feeds.

`list` returns a list over the feeds that are active as of now.

Examples:
```
!rss add [name for rss] [rss url] [rss posting channel]

!rss remove [name for rss]

!rss list

!rss list long
```

#### Add feed

Permissions: is_owner, administrator=True

Add an RSS feed to a specific channel

`feed_name`: The custom name for the feed

`feed_link`: The link to the RSS-/XML-feed

`channel`:   The channel to post from the feed

#### Remove feed

Permissions: is_owner, administrator=True

Remove a feed based on `feed_name`

#### Channel

Permissions: is_owner, administrator=True

Edit a feed's channel: `!rss channel [feed_name] [channel_in]`

`feed_name`:    The feed to change channel
`channel_in`:   New channel

#### List

'List all active rss feeds on the discord server'

---

### scrape_fcb_news

A hardcoded cog - get newsposts from https://www.fcbarcelona.com and post
them to specific team channels.

---

### stats

Update interesting stats in a channel post and write the info to ../json/stats_logs.json.
The channel is defined in the .env file (stats_channel).

---

### youtube

Autopost new videos from given Youtube channels

#### add

Permissions: is_owner, administrator=True

Add a Youtube feed to a specific channel: `!youtube add [feed_name] [yt_link] [channel]`

`feed_name`:    The custom name for the feed
`yt_link`:      The link for the youtube-channel
`channel`:      The Discord channel to post from the feed

#### remove

Permissions: is_owner, administrator=True

Remove a Youtube feed: `!youtube remove [feed_name]`

#### list

List all active Youtube feeds: `!youtube list`

---

## Want to contribute?

Here's how to help out:

- Report bugs in issues.

- Come up with awesome ideas (and submit them in issues)

- Make pull requests that solves a problem or an issue