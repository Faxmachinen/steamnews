from pathlib import Path
import pickle
from collections import defaultdict

import steamnews.feeds

class Server:
    def __init__(self, name, id_, channel=None, subscribed=None):
        self.name = name
        self.id = id_
        self.channel = channel
        self.subscribed = subscribed or set()
    @classmethod
    def from_context(Cls, ctx):
        name = str(ctx.guild)
        id_ = int(ctx.guild_id)
        return Cls(name, id_)
    def add_feed(self, steam_app_id, channel=None):
        self.subscribed.add(int(steam_app_id))
        if self.channel is None and channel is not None:
            self.channel = int(channel)
            return True
        else:
            return False
    def serialize(self):
        return (self.name, self.id, self.channel, self.subscribed)
    @classmethod
    def deserialize(Cls, version, data):
        (name, id_, channel, subscribed) = data
        return Cls(name, id_, channel, subscribed)

class ProgramState:
    def __init__(self, servers=None, timestamps=None):
        self.servers = servers or {}
        self.timestamps = timestamps or {}
        self.changed = False
    def save(self, config, log):
        if not self.changed:
            return
        state_file = Path(config['state_file']).absolute()
        with open(state_file, 'wb') as fh:
            pickle.dump((1, self.serialize()), fh)
        self.changed = False
        log.info("State saved to disk.")
    def get_server(self, ctx, log):
        guild_id = ctx.guild_id
        if not guild_id:
            return None
        if not guild_id in self.servers:
            self.servers[guild_id] = Server.from_context(ctx)
            self.changed = True
            log.info(f"Server {ctx.guild}#{guild_id} added. Total servers: {len(self.servers)}")
        return self.servers[guild_id]
    def get_active_server_feeds(self):
        feed_servers = defaultdict(list)
        for server in self.servers.values():
            if server.channel is not None:
                for server_feed in server.subscribed:
                    feed_servers[server_feed].append(server)
        return feed_servers
    def check_feeds(self, steamapps, config, log):
        feed_servers = self.get_active_server_feeds()
        log.info(f"Checking feeds ({len(feed_servers)})")
        result = []
        for app_id in feed_servers.keys():
            try:
                items = steamnews.feeds.load(app_id, config, log)
                if app_id not in self.timestamps:
                    # Feed not seen before, only get latest item.
                    new = items[-1:]
                else:
                    # Feed seen before, get new items.
                    new = steamnews.feeds.items_after(items, self.timestamps[app_id])
                if new:
                    app_name = steamapps.name_from_id(app_id) or '<Unknown>'
                    result.append((feed_servers[app_id], app_id, app_name, new))
                    self.timestamps[app_id] = new[-1].timestamp()
                    self.changed = True
            except Exception as ex:
                log.warning(f"Error getting feed #{app_id}: {ex}")
        return result
    def serialize(self):
        servers = [(k, v.serialize()) for k, v in self.servers.items()]
        timestamps = self.timestamps
        return (servers, timestamps)
    @classmethod
    def load(Cls, config, log):
        state_file = Path(config['state_file']).absolute()
        if not state_file.is_file():
            log.info("No state found, creating new...")
            return Cls()
        else:
            log.info("Loading previous state...")
            with open(state_file, 'rb') as fh:
                (version, data) = pickle.load(fh)
            instance = Cls.deserialize(version, data)
            log.info(f"State loaded: {len(instance.servers)} servers and {len(instance.timestamps)} feeds")
            return instance
    @classmethod
    def deserialize(Cls, version, data):
        (servers, timestamps) = data
        servers = dict([(k, Server.deserialize(version, v)) for k, v in servers])
        return Cls(servers, timestamps)