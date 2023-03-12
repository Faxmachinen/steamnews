import discord
from discord.utils import escape_markdown as escape
from discord.ext import tasks
from bs4 import BeautifulSoup

def blurbify(markup):
    soup = BeautifulSoup(markup, features="html.parser")
    text = soup.get_text(' ')
    if len(text) > 400:
        text = text[:400] + '...'
    return text

def embed_from_feed_item(item, app_id, app_name, config):
    embed = discord.Embed(
        title=escape(item.title),
        description=escape(f"{app_name} (#{app_id})"),
        color=discord.Colour.fuchsia())
    embed.set_thumbnail(url=config['steam_app_icon_url'].format(id=app_id))
    embed.add_field(name=item.format_date(), value=escape(blurbify(item.description)), inline=False)
    embed.add_field(name='Read more', value=item.link, inline=False)
    return embed

async def send_button_message(ctx, message, options, callback, **args):
    class ButtonView(discord.ui.View):
        async def on_timeout(self):
            for child in self.children:
                child.disabled = True
    def make_button(index, option):
        @discord.ui.button(label=option, style=discord.ButtonStyle.primary, row=index//5)
        async def onclick(self, button, interaction):
            await callback(index, option, interaction)
        setattr(ButtonView, f'button_callback{index}', onclick)
    for index, option in enumerate(options[:25]):
        make_button(index, option)
    class ButtonView2(ButtonView):
        pass
    await ctx.respond(message, view=ButtonView2(timeout=120), **args)

def create_bot(program_state, steam_app_list, config, log):
    steamnewsgroup = discord.SlashCommandGroup(config['bot_name'].lower(), f"Commands for the {config['bot_name']} bot.")
    bot = discord.Bot()
    bot.add_application_command(steamnewsgroup)

    def _authorized(ctx):
        guild = ctx.guild
        if not guild:
            return True
        return guild.owner.id == ctx.user.id

    async def _do_add(ctx, response_func, appid, name):
        server = program_state.get_server(ctx, log)
        if not server:
            await ctx.respond("This is not a server!")
            return
        channel_was_set = server.add_feed(appid, ctx.channel_id)
        log.info(f'{server.name}#{server.id} added "{name}" (#{appid})')
        msg = f"Now posting news about *{escape(name)}* (#{appid})"
        if channel_was_set:
            msg += "\nPosting news in this channel."
        await response_func(msg)
        if appid not in program_state.timestamps:
            update_feeds.restart()

    @steamnewsgroup.command(description="Tell the bot to post here.")
    async def posthere(ctx):
        if not _authorized(ctx):
            ctx.respond("Only the server owner can use this command.")
            return
        server = program_state.get_server(ctx, log)
        if not server:
            await ctx.respond("This is not a server!")
            return
        server.channel = int(ctx.channel_id)
        log.info(f"{server.name}#{server.id} set channel to {ctx.channel}#{ctx.channel_id}")
        await ctx.respond("Now posting in this channel.")

    @steamnewsgroup.command(description="Stop posting to this server.")
    async def mute(ctx):
        if not _authorized(ctx):
            ctx.respond("Only the server owner can use this command.")
            return
        server = program_state.get_server(ctx, log)
        if not server:
            await ctx.respond("This is not a server!")
            return
        if server.channel is None:
            await ctx.respond("I was already not posting anywhere.", ephemeral=True)
            return
        log.info(f'{server.name}#{server.id} stopped posting')
        await ctx.respond("Ok, I've stopped posting.", ephemeral=True)
        await bot.get_channel(server.channel).send("No longer posting to this channel.")
        server.channel = None

    @steamnewsgroup.command(description="Add a Steam game to the news feed.")
    async def add(ctx, name: str):
        if not _authorized(ctx):
            ctx.respond("Only the server owner can use this command.")
            return
        matches = steam_app_list.search_names(name)
        if len(matches) == 0:
            await ctx.respond(f"Sorry, I couldn't find *{escape(name)}*!", ephemeral=True)
        elif len(matches) > 1:
            labels = [escape(m[1]) for m in matches]
            async def callback(index, label, interaction):
                appid, name = matches[index]
                await _do_add(ctx, interaction.response.send_message, appid, name)
            await send_button_message(ctx, "Is it one of these?", labels, callback, ephemeral=True)
        else:
            appid, name = matches[0]
            await _do_add(ctx, ctx.respond, appid, name)

    @steamnewsgroup.command(description="Add a Steam game by ID to the news feed.")
    async def addid(ctx, appid: int):
        if not _authorized(ctx):
            ctx.respond("Only the server owner can use this command.")
            return
        name = steam_app_list.name_from_id(appid)
        if not name:
            await ctx.respond(f"Sorry! I don't think #{appid} is valid.", ephemeral=True)
        else:
            log.debug(f"Found '{name}' for #{appid}")
            await _do_add(ctx, ctx.respond, appid, name)

    @steamnewsgroup.command(description="List all news feeds.")
    async def list(ctx):
        server = program_state.get_server(ctx, log)
        if not server:
            await ctx.respond("This is not a server!")
            return
        lines = ["These are the feeds you are subscribed to:"]
        for appid in server.subscribed:
            name = steam_app_list.name_from_id(appid) or '<Unnamed>'
            lines.append(f"  • *{escape(name)}* (#{appid})")
        if len(lines) == 1:
            await ctx.respond("You haven't subscribed to any feeds yet.", ephemeral=True)
        else:
            await ctx.respond('\n'.join(lines), ephemeral=True)

    @steamnewsgroup.command(description="Remove a news feed by #ID.")
    async def removeid(ctx, appid: int):
        if not _authorized(ctx):
            ctx.respond("Only the server owner can use this command.")
            return
        server = program_state.get_server(ctx, log)
        if not server:
            await ctx.respond("This is not a server!")
            return
        name = steam_app_list.name_from_id(appid) or '<Unnamed>'
        if appid in server.subscribed:
            server.subscribed.remove(appid)
            log.info(f"{server.name}#{server.id} removed {name} ({appid})")
            await ctx.respond(f"Ok! Won't post about *{escape(name)}* (#{appid}) any more.", ephemeral=True)
            if server.channel is not None:
                await bot.get_channel(server.channel).send("No longer posting about *{escape(name)}* (#{appid}) in this channel.")
        else:
            await ctx.respond(f"You're not subscribed to *{escape(name)}* (#{appid}).")

    @steamnewsgroup.command(description="Remove all news feeds.")
    async def purge(ctx):
        if not _authorized(ctx):
            ctx.respond("Only the server owner can use this command.")
            return
        server = program_state.get_server(ctx, log)
        if not server:
            await ctx.respond("This is not a server!")
            return
        server.subscribed.clear()
        await ctx.respond(f"Ok! All subscriptions are gone.", ephemeral=True)
        if server.channel is not None:
            await bot.get_channel(server.channel).send("No longer posting about anything in this channel.")

    @bot.event
    async def on_ready():
        save_state.start()
        update_feeds.start()
        log.info("Bot is running. Press Ctrl+C to exit.")

    @tasks.loop(seconds=config['seconds_between_updates'])
    async def update_feeds():
        servers_new_items = program_state.check_feeds(steam_app_list, config, log)
        if not servers_new_items:
            return
        log.info(f"Posting {len(servers_new_items)} new updates.")
        for servers, app_id, app_name, new_items in servers_new_items:
            embeds = [embed_from_feed_item(x, app_id, app_name, config) for x in new_items]
            for server in servers:
                channel = bot.get_channel(server.channel)
                for embed in embeds:
                    await channel.send(embed=embed)

    @tasks.loop(seconds=300)
    async def save_state():
        program_state.save(config, log)

    return bot
