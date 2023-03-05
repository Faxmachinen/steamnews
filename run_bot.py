import discord
from discord.utils import escape_markdown as escape
import pickle
from pathlib import Path
import functools
from collections import defaultdict

import whoosh.query
import whoosh.qparser
import xml.etree.ElementTree as ET
from discord.ext import tasks
import requests
from bs4 import BeautifulSoup

import steamnews.config
import steamnews.index

class SteamApps:
    @classmethod
    def load(Cls, config):
        index = steamnews.index.create_steamapp_index(config)
        print(f"Indexes loaded - {index.doc_count()} entries")
        return Cls(index)
    def __init__(self, index):
        self.index = index
    def name_from_id(self, appid):
        with self.index.searcher() as searcher:
            results = list(searcher.documents(appid=appid))
        if not results:
            return None
        return results[0]['name']
    def search_names(self, name):
        parser = whoosh.qparser.QueryParser('name', schema=self.index.schema)
        query = parser.parse(name)
        with self.index.searcher() as searcher:
            results = []
            for result in searcher.search(query):
                r_appid = result['appid']
                r_name = result['name']
                results.append((r_appid, r_name))
            return results

class Server:
    def __init__(self, context):
        self.name = str(context.guild)
        self.id = int(context.guild_id)
        self.channel = None
        self.subscribed = set()
    def add_feed(self, steam_app_id, channel=None):
        self.subscribed.add(int(steam_app_id))
        if self.channel is None and channel is not None:
            self.channel = int(channel)
            return True
        else:
            return False

class ProgramState:
    @classmethod
    def load(Cls, config):
        state_file = Path(config['state_file']).absolute()
        if not state_file.is_file():
            print("No state found, creating new...")
            return Cls()
        else:
            print("Loading previous state...")
            with open(state_file, 'rb') as fh:
                loaded = pickle.load(fh)
            print(f"State loaded: {len(loaded.servers)} servers and {len(loaded.last_guids)} feeds")
            return loaded
    def __init__(self):
        self.servers = {}
        self.last_guids = {}
    def save(self, config):
        state_file = Path(config['state_file']).absolute()
        with open(state_file, 'wb') as fh:
            pickle.dump(self, fh)
    def get_server(self, context):
        guild_id = context.guild_id
        if not guild_id:
            return None
        if not guild_id in self.servers:
            self.servers[guild_id] = Server(context)
            print(f"Server #{guild_id} added. Total servers: {len(self.servers)}")
        return self.servers[guild_id]
    def check_feeds(self, steamapps, config):
        print("Checking feeds...")
        feed_ids = defaultdict(list)
        result = []
        for server in self.servers.values():
            if server.channel is not None:
                for server_feed in server.subscribed:
                    feed_ids[server_feed].append(server)
        print(f"{len(feed_ids)} feeds to check.")
        for feed_id in feed_ids.keys():
            try:
                new = self.get_new_items(feed_id, steamapps, config)
                if new:
                    result.append((feed_ids[feed_id], new))
            except Exception as ex:
                print(f"Error getting feed #{feed_id}: {ex}")
        return result
    def get_new_items(self, feed_id, steamapps, config):
        last_guid = self.last_guids.get(feed_id, None)
        app_name = steamapps.name_from_id(feed_id)
        url = config['steam_feed_url'].format(id=feed_id)
        r = requests.get(url)
        if r.status_code != 200:
            print(f"Code {r.status_code} when fetching {url}")
            return None
        root = ET.fromstring(r.text)
        link_tag = root.find('channel/link')
        item_tags = root.findall('channel/item')
        if len(item_tags) == 0:
            return []
        if last_guid is None:
            item_tags = item_tags[:1]  # Only get the last one
        items = []
        for item_tag in item_tags:
            item = self.parse_item_tag(item_tag, feed_id, app_name, link_tag.text if link_tag else None)
            if item['guid'] == last_guid:
                break
            items.append(item)
        if items:
            self.last_guids[feed_id] = items[0]['guid']
        return items
    def parse_item_tag(self, item_tag, app_id, app_name, feed_link):
        return {
            'guid': item_tag.find('guid').text,
            'app_id': app_id,
            'app_name': app_name,
            'feed_link': feed_link,
            'item_title': item_tag.find('title').text,
            'item_link': item_tag.find('link').text,
            'item_date': item_tag.find('pubDate').text,
            'item_description': item_tag.find('description').text,
        }

def blurbify(markup, more_url):
    soup = BeautifulSoup(markup, features="html.parser")
    text = soup.get_text(' ')
    if len(text) > 400:
        text = text[:400] + '...'
    return text

def embed_from_feed_item(item, config):
    embed = discord.Embed(
        title=escape(item['item_title']),
        description=escape(f"{item['app_name']} (#{item['app_id']})"),
        color=discord.Colour.fuchsia())
    embed.set_thumbnail(url=config['steam_app_icon_url'].format(id=item['app_id']))
    embed.add_field(name=escape(item['item_date']), value=escape(blurbify(item['item_description'], item['item_link'])), inline=False)
    embed.add_field(name='Read more', value=item['item_link'], inline=False)
    return embed

async def send_button_message(ctx, message, options, callback):
    class ButtonView(discord.ui.View):
        async def on_timeout(self):
            for child in self.children:
                child.disabled = True
    def make_button(index, option):
        @discord.ui.button(label=option, style=discord.ButtonStyle.primary, row=index//5)
        async def onclick(self, button, interaction):
            button.disabled = True
            await callback(index, option, interaction)
        setattr(ButtonView, f'button_callback{index}', onclick)
    for index, option in enumerate(options[:25]):
        make_button(index, option)
    class ButtonView2(ButtonView):
        pass
    await ctx.respond(message, view=ButtonView2(timeout=120))

def create_bot(config, program_state, steam_app_list):
    steamnewsgroup = discord.SlashCommandGroup(config['bot_name'].lower(), f"Commands for the {config['bot_name']} bot.")
    bot = discord.Bot()
    bot.add_application_command(steamnewsgroup)

    async def _do_add(ctx, response_func, appid, name):
        server = program_state.get_server(ctx)
        channel_was_set = server.add_feed(appid, ctx.channel_id)
        print(f'[{server.name}#{server.id}] Added "{name}" (#{appid})')
        msg = f"Ok! I'll give you news about *{escape(name)}* (#{appid})"
        if channel_was_set:
            msg += "\nI'll post in this channel."
        await response_func(msg)
        if appid not in program_state.last_guids:
            update_feeds.restart()

    @steamnewsgroup.command(description="Tell the bot to post here.")
    async def posthere(ctx):
        server = program_state.get_server(ctx)
        if not server:
            await ctx.respond("I can't post here! Ask me in a channel on your server.")
            return
        server.channel = int(ctx.channel_id)
        print(f"[{server.name}#{server.id}] Setting channel to {ctx.channel} ({ctx.channel_id})")
        await ctx.respond("Ok, I will post here!")

    @steamnewsgroup.command(description="Stop posting to this server.")
    async def mute(ctx):
        server = program_state.get_server(ctx)
        if not server:
            await ctx.respond("This is not a server!")
            return
        print(f'[{server.name}#{server.id}] Stopping')
        await ctx.respond("Ok! I'll stop posting.")
        server.channel = None

    @steamnewsgroup.command(description="Add a Steam game to the news feed.")
    async def add(ctx, name: str):
        matches = steam_app_list.search_names(name)
        if len(matches) == 0:
            await ctx.respond(f"Sorry, I couldn't find *{escape(name)}*!")
        elif len(matches) > 1:
            labels = [escape(m[1]) for m in matches]
            async def callback(index, label, interaction):
                appid, name = matches[index]
                await _do_add(ctx, interaction.response.send_message, appid, name)
            await send_button_message(ctx, "Is it one of these?", labels, callback)
        else:
            appid, name = matches[0]
            await _do_add(ctx, ctx.respond, appid, name)

    @steamnewsgroup.command(description="Add a Steam game by ID to the news feed.")
    async def addid(ctx, appid: int):
        name = steam_app_list.name_from_id(appid)
        if not name:
            print("Not found.")
            await ctx.respond(f"Sorry! I don't think #{appid} is valid.")
        else:
            print(f"Found '{name}' for #{appid}")
            await _do_add(ctx, ctx.respond, appid, name)

    @steamnewsgroup.command(description="List all news feeds.")
    async def list(ctx):
        server = program_state.get_server(ctx)
        lines = ["These are the feeds you are subscribed to:"]
        for appid in server.subscribed:
            name = steam_app_list.name_from_id(appid) or '<Unnamed>'
            lines.append(f"  • *{escape(name)}* (#{appid})")
        if len(lines) == 1:
            await ctx.respond("You haven't subscribed to any feeds yet.")
        else:
            await ctx.respond('\n'.join(lines))

    @steamnewsgroup.command(description="Remove a news feed by #ID.")
    async def removeid(ctx, appid: int):
        name = steam_app_list.name_from_id(appid) or '<Unnamed>'
        if appid in server.subscribed:
            server.subscribed.remove(appid)
            print(f"[{server.name}#{server.id}] Removed {name} ({appid})")
            await ctx.respond(f"Ok! Won't post about *{escape(name)}* (#{appid}) any more.")
        else:
            await ctx.respond(f"You're not subscribed to *{escape(name)}* (#{appid}).")

    @steamnewsgroup.command(description="Remove all news feeds.")
    async def purge(ctx):
        server = program_state.get_server(ctx)
        server.subscribed.clear()
        await ctx.respond(f"Ok! All subscriptions are gone.")

    @bot.event
    async def on_ready():
        print("Bot is ready.")
        update_feeds.start()

    @tasks.loop(seconds=config['seconds_between_updates'])
    async def update_feeds():
        servers_new = program_state.check_feeds(steam_app_list, config)
        new_count = len(servers_new)
        print(f"{len(servers_new)} updates to post.")
        for servers, new in servers_new:
            embeds = [embed_from_feed_item(x, config) for x in new]
            for server in servers:
                channel = bot.get_channel(server.channel)
                for embed in embeds:
                    await channel.send(embed=embed)
    return bot

if __name__ == '__main__':
    print("Getting configuration...")
    config_file = Path(__file__).absolute().parent / 'appsettings.json'
    config = steamnews.config.load_configuration(config_file)
    if config['bot_token'] == steamnews.config.TOKEN_PLACEHOLDER:
        print(f"Replace {steamnews.config.TOKEN_PLACEHOLDER} in your config!")
        exit(1)
    print("Getting state...")
    program_state = ProgramState.load(config)
    print("Getting Steam apps...")
    steam_app_list = SteamApps.load(config)
    bot = create_bot(config, program_state, steam_app_list)

    print("Running bot...")
    bot.run(config['bot_token'])
    
    print("Saving state before exit...")
    program_state.save(config)
    print("Accepting my fate.")

