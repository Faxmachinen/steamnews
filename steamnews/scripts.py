from pathlib import Path
import logging
import logging.config
import argparse

import steamnews.config
import steamnews.index
import steamnews.feeds
import steamnews.bot
import steamnews.state

def configure(config_path, log_config_path):
    print("Initializing logging...")
    logging.config.fileConfig(log_config_path)
    log = logging.getLogger('root')
    log.info("-------- Logging initialized --------")
    log.info("Getting configuration...")
    config = steamnews.config.load_configuration(config_path, log)
    return config, log

def run_bot(config_path, log_config_path):
    config, log = configure(config_path, log_config_path)
    if config['bot_token'] == steamnews.config.TOKEN_PLACEHOLDER:
        log.critical(f"Replace {steamnews.config.TOKEN_PLACEHOLDER} in your config!")
        return 1
    log.info("Getting Steam apps...")
    steam_app_list = steamnews.index.SteamApps.load(config, log)
    log.info("Getting state...")
    program_state = steamnews.state.ProgramState.load(config, log)
    try:    
        bot = steamnews.bot.create_bot(program_state, steam_app_list, config, log)
        log.info("Running bot...")
        bot.run(config['bot_token'])
    finally:
        log.info("Saving state before exit...")
        program_state.save(config, log)
    log.info("Shutdown complete.")
    return 0

def update_index(config_path, log_config_path):
    config, log = configure(config_path, log_config_path)
    index = steamnews.index.create_steamapp_index(config)
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
        prog='steamnews',
        description='A Discord bot for Steam news feeds.')
    parser.add_argument('action', choices=['bot', 'index'], help='bot: Run the bot; index: Update the Steam app index.')
    parser.add_argument('-c', '--config', type=Path, help='The path to an application settings file.', default='appsettings.json')
    parser.add_argument('-l', '--logconfig', type=Path, help='The path to a log configuration file.', default='logging.conf')
    args = parser.parse_args()
    if args.action == 'bot':
        return steamnews.scripts.run_bot(args.config, args.logconfig)
    elif args.action == 'index':
        return steamnews.scripts.update_index(args.config, args.logconfig)
    else:
        raise Exception("First argument must be 'bot' or 'index'!")
