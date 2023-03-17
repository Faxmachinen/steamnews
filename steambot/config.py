from pathlib import Path
import json

TOKEN_PLACEHOLDER = 'YOUR_DISCORD_BOT_TOKEN_HERE'
DEFAULT_CONFIG = {
    'version': 1,
    'bot_name': 'SteamBot',
    'bot_token': TOKEN_PLACEHOLDER,
    'state_file': './state.pickle',
    'steam_app_list_url': 'https://api.steampowered.com/ISteamApps/GetAppList/v2/',
    'steam_feed_url': 'https://store.steampowered.com/feeds/news/app/{id}',
    'steam_app_icon_url': 'https://cdn.cloudflare.steamstatic.com/steam/apps/{id}/header.jpg',
    'steam_index_dir': './steamapps_index',
    'seconds_between_updates': 600,
}

def load_configuration(config_file, log):
    log.info(f"Loading config from {config_file}")
    if not config_file.is_file():
        with open(config_file, 'w') as fh:
            log.info("... doesn't exist, so create it.")
            json.dump(DEFAULT_CONFIG, fh, indent='\t')
    with open(config_file, 'r') as fh:
        config = json.load(fh)
    return config
