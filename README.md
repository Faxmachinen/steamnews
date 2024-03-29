# SteamBot

## Description

Steam provides RSS feeds for all the apps in its database, and you could use a generic RSS bot to post them to Discord.
But I was not happy with the awkward format of the feeds, often producing large walls of text and titles like "1234 RSS Feed".

By making SteamBot specifically for Steam, it affords some features:
- Search for apps by name in the Steam database.
- Show the app's name and image in every post.
- Include a link to the web version of the news feed.
- Limit the text to a few hundred characters to avoid the wall of text effect.

## Installation

### On Windows
```
py -m pip install steambot
```

### On Linux
```
pip3 install steambot
```

## Quick start

### Running the bot
1. Make a folder for SteamBot and `cd` into it.
1. Run `steambot index`
1. While that is doing it's thing, open another console and run `steambot bot`
   Since this is the first time it's run, it creates `appsettings.json`, tells you to replace YOUR_DISCORD_BOT_TOKEN_HERE in that file, and then exits.
1. Log in to the [Discord developer portal](https://discord.com/developers) and create an application with a bot (you may want to follow a guide).
1. Copy the bot's token into `appsettings.json`
1. Now run `steambot bot` again. This time it should print *"Bot is running. Press Ctrl+C to exit."*
1. Check that `steambot index` has finished. The command to search by name will not work until it has.

### Generating the invitation link
1. Go back to your bot on the Discord developer portal, and find the "URL Generator" under OAuth2.
1. Under scopes, check "bot".
1. Under bot permissions, check "Send Messages".
1. At the bottom, copy the generated URL. This is the URL you and others can use to invite the bot to your server.

### Start adding some feeds
After you've invited the bot to your server, you can start giving the bot commands:
1. Go to the channel on your server where you want the bot to post.
1. Type `/steambot add Half-Life` (or any other game that exists on Steam).
1. If there are multiple games with similar names, the bot will ask you. Click on the one you want.

## Commands

All commands except `/steambot list` can only be run by the server owner.

- `/steambot posthere`: The bot will start posting in this channel (instead of where it was posting before).
- `/steambot mute`: The bot will stop posting, but keeps the list of apps that were added.
- `/steambot add <Name>`: Adds an app by name, and starts posting to this channel if it wasn't posting anywhere.
- `/steambot addid <ID>`: Like `add`, but adds an app by ID instead.
- `/steambot list`: List the apps that have been added, and their IDs. Any server member can use this command.
- `/steambot removeid <ID>`: Removes the app with the given ID. Use `list` to find the ID.
- `/steambot purge`: Removes all apps that have been added.

## More information

You can see more options by running `steambot --help`, such as changing where the configuration files are read from.

### steambot index

This command downloads the list of apps from the Steam database, indexes the names, then exits.
You need to run this at least once for the bot to be able to find games by their names.
If you're running your bot as a public service, you may want to run it on a daily schedule to keep it in sync with Steam's database.
You can run it while the bot is running.

The indexes are stored on disk in the `./steamapps_index` folder.

### steambot bot

This script runs the bot, making it show as "Online" in Discord, and keeps running until you press Ctrl+C.
Commands sent to the bot in Discord are processed by this script.

If you need to stop the bot, you should do so with Ctrl+C (in theory, sending SIGINT would also work).
When you do so, it stores its state (servers, added apps, feed timestamps) in `state.picle` and exits cleanly.
Otherwise, the bot also stores its state every five minutes, so maybe you didn't lose too much (or anything at all).

You can check `./log.txt` to see when the state was last saved.
Note that state does not get saved unless it actually changed.
