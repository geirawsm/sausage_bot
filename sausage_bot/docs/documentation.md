# `__main__.py`

Set's up the bot, have a few generic commands and controls cogs


## ping (async Function)

Checks the bot latency


## delete (async Function) (amount)

Aliases: del, cls

*Permissions: is_owner, manage_messages=True*

Delete `amount` number of messages in the chat


## kick (async Function) (member, reason)

*Permissions: is_owner, kick_members=True*

Kick a member from the server

member	(discord.Member) Name of Discord user you want to kick
reason	(str) Reason for kicking user


## ban (async Function) (member, reason)

*Permissions: is_owner, ban_members=True*

Ban a member from the server

member	(discord.Member) Name of Discord user you want to ban
reason	(str) Reason for banning user


## say (async Function) (text)

*Permissions: is_owner, manage_messages=True*

Make the bot say something


## edit (async Function) (text)

*Permissions: is_owner, administrator=True*

Make the bot rephrase a previous message. Reply to it with `!edit [text]`


---

# `autoevent.py`

This cog can take links to soccer games on predefined sites, and make them
into an event for the server.


## AutoEvent (Class)

### autoevent (async Function)

Administer match events on the discord server based on a url from a
supported website.


### add (async Function) (url, channel, text)

*Permissions: is_owner, manage_events=True*

Add a scheduled event: `!autoevent add [url] [channel] [text]`

url    	(str) URL to match page from nifs.no
channel	(str) Voice channel to run event on
text   	(str) Additional text to the event's description


### remove (async Function) (event_id_in)

*Permissions: is_owner, manage_events=True*

Removes a scheduled event that has not started yet:
`!autoevent remove [event_id_in]`

event_id_in	(int) ID for the event to remove. Get ID's from `!autoevent list`


### list_events (async Function)

*Permissions: is_owner, manage_events=True*


### sync (async Function) (start_time, countdown)

*Permissions: is_owner, manage_events=True*

Create a timer in the active channel to make it easier for people attending an event to sync something that they're watching: `!autoevent timesync [start_time] [countdown]`

start_time	(str) A start time for the timer or a command for deleting the timer
countdown 	(int) How many seconds should it count down before hitting the `start_time`



---

# `dilemmas.py`

## Dilemmas (Class)

Post a random dilemma

### dilemmas (async Function)

#### prettify (Function) (dilemmas_in)

Enclosing `dilemmas_in` in quotation marks



### add (async Function) (dilemmas_in)

*Permissions: is_owner, administrator=True*

Add a dilemma: `!dilemmas add [dilemmas_in]`



---

# `quote.py`

## Quotes (Class)

Administer or post quotes

### quote (async Function) (number)

Post, add, edit, delete or count quotes
To post a specific quote: `!quote ([number])`

number	(int) Chose a number if you want a specific quote

#### pretty_quote (Function)

Returns: str


### add (async Function) (quote_text, quote_date)

*Permissions: is_owner, administrator=True*

Add a quote: `!quote add [quote_text] ([quote_date])`

quote_text	(str) The quote text (must be enclosed in quotation marks)
quote_date	(str) Set a custom date and time for the quote added (dd.mm.yyyy, HH:MM)


### edit (async Function) (quote_number, quote_in, custom_date)

*Permissions: is_owner, administrator=True*

Edit an existing quote:
`!quote edit [quote_number] [quote_in] [custom_date]`

quote_number	(int) The number of quote to edit
quote_in    	(str) The quote text (must be enclosed in quotation marks)
custom_date 	(str) Set a different date and time


### delete (async Function) (quote_number)

*Permissions: is_owner, administrator=True*

Delete an existing quote: `!quote delete [quote_number]`

quote_number	(int) The number of quote to edit

#### delete_logged_msgs (async Function)


#### check (Function)



### count (async Function)

Count the number of quotes available: `!quote count`



---

# `roles.py`

## Autoroles (Class)

Manage roles and settings

### guildrole (async Function)

Control roles on the server


### info (async Function) (role_name)

Get info about a role

role_name	(str) Role name


### manage (async Function)

Manage specific roles on the server


### add_role (async Function) (role_name, permissions, color, hoist, mentionable)

Add role to the server

role_name  	(str) Role name
permissions	(str) Set permissions for the role
color      	(str) Set color for the role
hoist      	(str) Set if the role should be mentionable or not
mentionable	(str) Set if the role should be mentionable or not


### remove_role (async Function) (role_name)

Remove a role from the server

role_name	(str) Role name


### edit_role (async Function) (role_name, new_role_name, permissions, color, hoist, mentionable)

Add role to the server

role_name    	(str) Role name
new_role_name	(str) Role name to change to
permissions  	(str) Set permissions for the role
color        	(str) Set color for the role
hoist        	(str) Set if the role should be mentionable or not
mentionable  	(str) Set if the role should be mentionable or not


### user (async Function)

Manage a user's roles


### user_add (async Function) (user_name)

Add role(s) to a user

user_name	(str) User name


### user_remove (async Function) (user_name)

Remove roles from a user

user_name	(str) User name



---

# `rss.py`

## RSSfeed (Class)

Administer RSS-feeds that will autopost to a given channel when published

### rss (async Function)

Administer RSS-feeds


### add (async Function) (feed_name, feed_link, channel)

*Permissions: is_owner, administrator=True*

Add RSS feed to a specific channel:
`!rss add [feed_name] [feed_link] [channel]`

feed_name	(str) Name of feed
feed_link	(str) Link to the RSS-/XML-feed
channel  	(str) The channel to post from the feed


### rss_edit (async Function)

*Permissions: is_owner, administrator=True*

Edit a feed listing. You can edit `channel`, `name` and `url`


### rss_edit_channel (async Function) (feed_name, channel)

*Permissions: is_owner, administrator=True*

Edit a feed's channel: `!rss edit channel [feed_name] [channel]`

feed_name	(str) Name of feed
channel  	(str) Name of channel


### rss_edit_name (async Function) (feed_name, new_feed_name)

*Permissions: is_owner, administrator=True*

Edit the name of a feed: `!rss edit name [feed_name] [new_feed_name]`

feed_name    	(str) Name of feed
new_feed_name	(str) New name of feed


### rss_edit_url (async Function) (feed_name, url)

*Permissions: is_owner, administrator=True*

Edit the url for a feed: `!rss edit url [feed_name] [url]`

feed_name	(str) Name of feed
url      	(str) New url for feed


### rss_filter (async Function) (feed_name, add_remove, allow_deny, filter_in)

*Permissions: is_owner, administrator=True*

Add/remove filter for feed (deny/allow): `!rss filter [feed name] [add/remove] [allow/deny] [filter]`

feed_name 	(str) Name of feed
add_remove	(str) `Add` or `remove`
allow_deny	(str) Specify if the filter should `allow` or `deny`
filter_in 	(str) What to filter a post by


### remove (async Function) (feed_name)

*Permissions: is_owner, administrator=True*

Remove a feed based on `feed_name`

feed_name	(str) Name of feed


### list_rss (async Function) (list_type)

List all active rss feeds on the discord server:
!rss list ([list_type])

list_type	(str) `long` or `filter`


### rss_parse (async Function)


### before_rss_parse (async Function)


### cog_unload (Function)

Cancel task if unloaded



---

# `scrape_fcb_news.py`

## scrape_and_post (Class)

A hardcoded cog - get newsposts from https://www.fcbarcelona.com and post
them to specific team channels

### post_fcb_news (async Function)

Post news from https://www.fcbarcelona.com to specific team channels

#### scrape_fcb_page (Function) (url)

Scrape https://www.fcbarcelona.com


#### scrape_fcb_news_links (Function)

Find links for specific team news and return it as a dict



### before_post_fcb_news (async Function)


### cog_unload (Function)

Cancel task if unloaded



---

# `stats.py`

## get_members (Function)

Get number of members and number of Patreon-members


## get_stats_codebase (Function)

Get statistics for the code base


## Stats (Class)

Get interesting stats for the discord server

### update_stats (async Function)

Update interesting stats in a channel post and write the info to
`mod_vars.stats_logs_file`.
The channel is defined in the .env file (stats_channel).

#### tabify (Function) (dict_in, _key, _item, prefix, suffix, split, filter_away)

dict_in    	(dict) 
_key       	(str) 
_item      	(str) 
filter_away	(bool) 



### before_update_stats (async Function)


### cog_unload (Function)

Cancel task if unloaded



---

# `youtube.py`

## Youtube (Class)

Autopost new videos from given Youtube channels

### youtube (async Function)

Administer what Youtube channels to post


### add (async Function) (feed_name, yt_link, channel)

*Permissions: is_owner, administrator=True*

Add a Youtube feed to a specific channel: `!youtube add [feed_name] [yt_link] [channel]`

feed_name	(str) Name of feed
yt_link  	(str) The link for the youtube-channel
channel  	(str) The Discord channel to post from the feed


### remove (async Function) (feed_name)

*Permissions: is_owner, administrator=True*

Remove a Youtube feed: `!youtube remove [feed_name]`

feed_name	(str) Name of feed


### list_youtube (async Function) (list_type)

List all active Youtube feeds: !youtube list ([list_type])

list_type	(str) `added` or `filter`


### get_yt_info (async Function) (url)

Use yt-dlp to get info about a channel


### process_links_for_posting_or_editing (async Function) (name, videos, feed_info, feed_log_file)


### post_videos (async Function)


### before_post_new_videos (async Function)


### cog_unload (Function)

Cancel task if unloaded



---

# `args.py`

Arguments to use for running the bot in the terminal

---

# `cogs.py`

## loading (Class)

### change_cog_status (async Function)


### load_cog (async Function)


### unload_cog (async Function)


### reload_cog (async Function)


### load_and_clean_cogs (async Function)


### reload_all_cogs (async Function)



## cog (async Function) (cmd_in)

*Permissions: is_owner, administrator=True*

Enable, disable, reload or list cogs for this bot

cmd_in      "enable"/"e" or "disable"/"d"
cog_names   Name(s) of wanted cog, or "all"

### action_on_cog (async Function)



## get_cogs_list (Function)


---

# `config.py`

Get env values and initiate the Discord bot object


## config (Function)


---

# `datetime_handling.py`

## make_dt (Function) (date_in)

Make a datetime-object from string input

Handles the following input:
- 17.05.22
- 17.05.20 22
- 17.05.2022 1122
- 17.05.2022, 11.22
- 17.05.2022, 1122
- 17.05.20 22, 11.22
- 2022-05-17T11:22:00Z
- 2023-08-05T10:00:00+02:00


## get_dt (Function) (format, sep, dt)

Get a datetime object in preferred dateformat.

dt              Uses `pendulum.now()` as datetime-object if nothing
                else is given
sep             Use dots as separator if nothing else is given
format          Returns the dt-object in epoch/linux time-format if
                nothing else is given
```
Formats:
(Example date: May 17th 2014; time: 14:23:39; timezone: GMT)
`date`:             17.05.2014
`datetext`:         17 May 2014
`datetextfull`:     17 May 2014, 14.23
`revdate`:          2014.05.17
`datetime`:         17.05.2014 14.23
`datetimefull`:     17.05.2014 14.23.39
`revdatetimefull`:  2014.05.17 14.23.39
`time`:             14.23
`timefull`:         14.23.39
`week`:             20
`year`:             2014
`month`:            05
`day`:              17
`epoch`:            1400336619
```


## change_dt (Function) (pendulum_object_in, change, count, unit)

Take a pendulum datetime object and change it relatively

`pendulum_object_in`: The object to change

`change`: Accepts `add` or `remove`

`count`: How many `units` to change

`unit`: Unit to change. Accepted units are `years`, `months`, `days`,
    `hours`, `minutes` and `seconds`


---

# `discord_commands.py`

## get_guild (Function)


## get_text_channel_list (Function)


## channel_exist (Function)


## get_voice_channel_list (Function)


## get_scheduled_events (Function)


## get_sorted_scheduled_events (Function)


## get_roles (Function)


## post_to_channel (async Function) (channel_in, content_in, content_embed_in)

Post `content_in` in plain text or `content_embed_in` to channel `channel_in`


## replace_post (async Function)


## update_stats_post (async Function)


---

# `envs.py`

Set variables for the module like folder, files and botlines

---

# `feeds_core.py`

## check_feed_validity (async Function) (url)

Make sure that `url` is a valid link


## add_to_feed_file (async Function) (name, feed_link, channel, user_add, feeds_filename, yt_id)

Add a an item to the feed-json.

`name`:         The identifiable name of the added feed
`feed_link`:    The link for the feed
`channel`       The discord channel to post the feed to
`user_add`      The user who added the feed


## remove_feed_from_file (Function) (name, feed_file)

Remove a feed from `feed file` based on `name`


## update_feed (async Function) (feed_name, feeds_file_in, actions, items, values_in)

Update the fields for a feed in `feeds_file`

`feed_name`:        Identifiable name for the feed
`feeds_file_in`:    The file in where to update feed
`actions`:          What actions to perform on the item:
                    Command     Alternatives
                    'add'
                    'edit'      'change'
                    'increment'
                    'remove'    'delete'

`items`:            What items you want to change: name, channel, url,
                    status_url, status_url_counter or status_channel
`values_in`:        Value to change/replace `item`


## get_feed_links (async Function) (feed_name, url, filter_allow, filter_deny, cog_mode, include_shorts, filter_priority)

Get the links from a RSS-feeds `url`

### filter_link (Function) (link, filter_allow, filter_deny, filter_priority)

Filter incoming links based on active filters and settings in
`env.json`

#### post_based_on_filter (Function) (filter_priority, filter_allow, filter_deny, title_in, desc_in)



### get_items_from_rss (async Function) (req, url, include_shorts)



## get_feed_list (async Function) (feeds_file, feeds_vars, list_type)

Get a prettified list of feeds from `feeds_file`.

feeds_file  The file containing feeds or other things to list
feeds_vars  The titles and lengths of the fields to be used
list_type   If specified, should show that specific list_type,
            as specified in the feeds_vars 'list_type' field

feeds_vars	(dict) 
list_type 	(str) 

### split_lengthy_lists (Function) (feeds_file_in, feeds_vars, list_type)

#### wanted_fields (Function) (feeds_vars, list_type)


#### make_table (Function) (feeds_in, want_fields)


#### make_pretty_header (Function) (header, max_len)




## review_feeds_status (async Function) (feeds_file)

Get a status for a feed from `feeds` and update it in source file


## link_is_in_log (Function) (link, feed_name, feed_log)

Checks if `link` is in the `feed_log`

link     	(str) 
feed_name	(str) 
feed_log 	(list) 

Returns: bool

## link_similar_to_logged_post (Function) (link, feed_log)

Checks if `link` is similar to any other logged link in `feed_log`.
If similiar, return the similar link from log.
If no links are found to be similar, return None.

link    	(str) 
feed_log	(list) 


## process_links_for_posting_or_editing (async Function) (feed, FEED_POSTS, feed_log_file, CHANNEL)

Compare `FEED_POSTS` to posts belonging to `feed` in `feed_log_file`
to see if they already have been posted or not.
- If not posted, post to `CHANNEL`
- If posted, make a similarity check just to make sure we are not posting
duplicate links because someone's aggregation systems can't handle
editing urls with spelling mistakes. If it is simliar, but not identical,
replace the logged link and edit the previous post with the new link.

`feed`:             Name of the feed to process
`FEED_POSTS`:       The newly received feed posts
`feed_log_file`:    File containing the logs of posts
`CHANNEL`:          Discord channel to post/edit


---

# `file_io.py`

## write_file (Function) (filename, content_to_write, append)

Write `content_to_write` to the file `filename`
Appends instead if set to True


## import_file_as_list (Function) (file_in)

Open `file_in`, import it as a list and return ut.
If this fails, return None.


## add_to_list (Function) (list_file_in, item_add)

Add `item_add` to a list in file `list_file_in`


## read_json (Function) (json_file)

Open `json_file` as a JSON and convert to as a dict.
Returns _file as a dict or an empty dict.


## write_json (Function) (json_file, json_out)

Write `json_out` to `json file`


## file_size (Function) (filename)

Checks the file size of a file. If it can't find the file it will
return False


## ensure_folder (Function) (folder_path)

Create folders in `folder_path` if it doesn't exist

folder_path	(str) 


## ensure_file (Function) (file_path_in, file_template)

Create file `file_path_in` if it doesn't exist and include the
`file_template` if provided.

file_path_in 	(str) 


## get_max_item_lengths (Function) (headers, dict_in)

Get the maximum lengths for keys in dicts `headers` and `dict_in`


## check_similarity (Function) (text1, text2)

Check how similar `text1` and `text2` is. If it resembles eachother by
between 95 % to 99.999999999999999999999999995 %, it is considered
"similar" and will return True. Otherwise, return False.
If neither `text1` nor `text2` is a string, it will return None.

text1	(str) 
text2	(str) 

Returns: bool

## create_necessary_files (Function) (file_list)

Get `file_list` (list) and create necessary files before running code


---

# `net_io.py`

## get_link (async Function) (url)

Get contents of requests object from a `url`


## make_event_start_stop (Function) (date, time)

Make datetime objects for the event based on the start date and time.
The event will start 30 minutes prior to the match, and it will end 2
hours and 30 minutes after

`date`: The match date or a datetime-object
`time`: The match start time (optional)


## parse (async Function) (url)

Parse `url` to get info about a football match.

Returns a dict with information about the match given.

url	(str) 

### parse_nifs (Function) (json_in)

Parse match ID from matchpage from nifs.no, then use that in an
api call


### parse_vglive (Function) (json_in)

Parse match ID from matchpage from vglive.no, then use that in an
api call



---

# `log.py`

Custom logging for the module


## log_function (Function) (log_in, color, extra_info, extra_color, pretty, sameline)

Include the name of the function in logging.

log_in          The text/input to log
color           Specify the color for highlighting the function name:
                black, red, green, yellow, blue, magenta, cyan, white.
                If `color` is not specified, it will highlight in green.
extra_info      Used to specify extra information in the logging (default: None)
extra_color     Color for the `extra_info` (default: green)
pretty          Prettify the output. Works on dict and list

log_in     	(str) 
color      	(str) 
extra_info 	(str) 
extra_color	(str) 
pretty     	(bool) 
sameline   	(bool) 


## log (Function) (log_in, color, pretty, sameline)

Log the input `log_in`

log_in          The text/input to log
color           Specify the color for highlighting the function name:
                black, red, green, yellow, blue, magenta, cyan, white.
                If `color` is not specified, it will highlight in green.
pretty          Prettify the output. Works on dict and list

log_in  	(str) 
color   	(str) 
pretty  	(bool) 
sameline	(bool) 


## log_more (Function) (log_in, color, pretty, sameline)

Log the input `log_in`. Used as more verbose than `log`

log_in          The text/input to log
color           Specify the color for highlighting the function name:
                black, red, green, yellow, blue, magenta, cyan, white.
                If `color` is not specified, it will highlight in green.
pretty          Prettify the output. Works on dict and list

log_in  	(str) 
color   	(str) 
pretty  	(bool) 
sameline	(bool) 


## debug (Function) (log_in, color, extra_info, extra_color, pretty, sameline)

Log the input `log_in` as debug messages

color           Specify the color for highlighting the function name:
                black, red, green, yellow, blue, magenta, cyan, white.
                If `color` is not specified, it will highlight in gre
extra_info      Used to specify extra information in the logging
extra_color     Color for the `extra_info`
pretty          Prettify the output. Works on dict and list

log_in     	(str) 
color      	(str) 
extra_info 	(str) 
extra_color	(str) 
pretty     	(bool) 
sameline   	(bool) 


## log_func_name (Function)

Get the function name that the `log`-function is used within

Returns: str

## log_to_bot_channel (async Function) (text_in)

Messages you want to send directly to a specific channel


---

