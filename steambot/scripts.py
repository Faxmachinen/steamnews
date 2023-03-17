from pathlib import Path
import argparse
import requests

import steambot.config
import steambot.logconfig
import steambot.index
import steambot.feeds
import steambot.bot
import steambot.state

def configure(config_path, log_config_path):
    log = steambot.logconfig.init_logging(log_config_path)
    log.info("-------- Logging initialized --------")
    log.info("Getting configuration...")
    config = steambot.config.load_configuration(config_path, log)
    return config, log

def run_bot(config_path, log_config_path):
    config, log = configure(config_path, log_config_path)
    if config['bot_token'] == steambot.config.TOKEN_PLACEHOLDER:
        log.critical(f"Replace {steambot.config.TOKEN_PLACEHOLDER} in your config!")
        return 1
    log.info("Getting Steam apps...")
    steam_app_list = steambot.index.SteamApps.load(config, log)
    log.info("Getting state...")
    program_state = steambot.state.ProgramState.load(config, log)
    try:    
        bot = steambot.bot.create_bot(program_state, steam_app_list, config, log)
        log.info("Running bot...")
        bot.run(config['bot_token'])
    finally:
        log.info("Saving state before exit...")
        program_state.save(config, log)
    log.info("Shutdown complete.")
    return 0

def update_index(config_path, log_config_path):
    config, log = configure(config_path, log_config_path)
    index = steambot.index.create_steamapp_index(config)
    log.info("Getting app list...")
    r = requests.get(config['steam_app_list_url'])
    r.raise_for_status()
    log.info("Updating indexes... (may take a while!)")
    existing_appids = set([d['appid'] for d in index.searcher().documents()])
    writer = index.writer(limitmb=256, procs=4)
    new_count = 0
    for entry in r.json()["applist"]["apps"]:
        if entry['appid'] not in existing_appids:
            new_count += 1
            writer.update_document(appid=entry['appid'], name=entry['name'])
    writer.commit()
    log.info(f"Indexes updated - {new_count} new entries, {index.doc_count()} total")
    return 0

def main():
    parser = argparse.ArgumentParser(
        prog='steambot',
        description='A Discord bot for Steam news feeds.')
    parser.add_argument('action', choices=['bot', 'index'], help='bot: Run the bot; index: Update the Steam app index.')
    parser.add_argument('-c', '--config', help='The path to an application settings file.', default='appsettings.json')
    parser.add_argument('-l', '--logconfig', help='The path to a log configuration file.', default='logging.conf')
    args = parser.parse_args()
    config_path = Path(args.config)
    log_config_path = Path(args.logconfig)
    if args.action == 'bot':
        return steambot.scripts.run_bot(config_path, log_config_path)
    elif args.action == 'index':
        return steambot.scripts.update_index(config_path, log_config_path)
    else:
        raise Exception("First argument must be 'bot' or 'index'!")
