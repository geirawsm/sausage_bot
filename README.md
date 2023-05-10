# SausageBot

SausageBot - affectionately known as "pølsa" among its Norwegian users - is a Discord bot with some very specific functions.

## Usage

This code is intended to be selfhosted and run on a server you have access to.

## Installation

Ok, so you want to run a Discord bot?

### Register Discord bot
Follow the instructions on this page on *Creating a Discord Bot Account*: https://www.pythondiscord.com/pages/guides/python-guides/discordpy/#creating-a-discord-bot-account
- Navigate to https://discord.com/developers/applications and log in.
- Click on New Application.
- Enter the application's name.
- Click on Bot on the left side settings menu.
- Click "Add Bot" and confirm with "Yes, do it!".
- Give your bot a cool name and a nice icon.
- Activate all the intents under "Bot" -> "Privileged Gateway Intents" and click "Save Changes".


### Running through Docker

`docker build .`

`docker run sausage_bot:latest -v [host path to a data folder]:/data`


### Running locally

#### Setup the python environment
It is recommended to run the bot in a controlled environment, by using `pipenv` or similar services.

- Using the terminal, navigate to the folder where you want to install the bot
- Run `git clone https://github.com/geirawsm/sausage_bot.git`
- `cd` into sausage_bot
- Install `pipenv` if you haven't already
- Run `pipenv shell` to create the python environment and start the shell
- Run `pipenv install` to install dependencies
- Run the bot once to get the `.env` file: `python -m sausage_bot`
- Open `sausage_bot/sausage_bot/data/.env` and add as a minimum these values under the `basic` key:
    - `DISCORD_TOKEN`   Get the token from the [Discord Developer portal](https://discord.com/developers/applications) under "Bot", "Build-A-Bot", "TOKEN"
    - `DISCORD_GUILD`   The name of the discord server you want to connect to
    - `BOT_ID`          Also found in the [Discord Developer portal](https://discord.com/developers/applications), under "OAuth2", "General", "Client information", "CLIENT ID"
- Invite the bot to your discord server:
    - Again, go back to the [Discord Developer portal](https://discord.com/developers/applications), "OAuth2", "URL Generator".
    - Chose the scope "bot"
    - Chose the minimum needed permission for the bot. Only chose "Administrator" if you're absolutely sure.
    - Click "Copy" on "Generated url", visit that link in a browser.
    - Make sure that the information looks correct, select the server you want it to join, and click "Continue" and confirm the permissions by clicking "Authorize". Your bot should now join the channel in a disconnected state.
- Start the bot
    - Go back to the terminal and run `python -m sausage_bot` again. The bot will now be online.

If you run `python -m sausage_bot -h` you can also see all the arguments you can add.

### yt-dlp requires PhantomJS and keeps nagging about it

Yep.

Use the `install_phantomjs.sh` script included.


## Functions

To be updated

---

## Want to contribute?

Here's how to help out:

- Report bugs in issues.

- Come up with awesome ideas (and submit them in issues)

- Make pull requests that solves a problem or an issue