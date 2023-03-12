from pathlib import Path
import os
import logging
import logging.config

import steamnews.config
import steamnews.index
import steamnews.feeds
import steamnews.bot
import steamnews.state

def init_logging():
    logging.config.fileConfig('logging.conf')
    return logging.getLogger('root')

if __name__ == '__main__':
    os.chdir(Path(__file__).absolute().parent)
    print("Initializing logging...")
    log = init_logging()
    log.info("-------- Logging initialized --------")
    log.info("Getting configuration...")
    config_file = Path('./appsettings.json')
    config = steamnews.config.load_configuration(config_file, log)
    
    if config['bot_token'] == steamnews.config.TOKEN_PLACEHOLDER:
        log.critical(f"Replace {steamnews.config.TOKEN_PLACEHOLDER} in your config!")
        exit(1)
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
