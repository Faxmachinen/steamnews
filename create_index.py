from pathlib import Path
import requests
import os
import logging
import logging.config

import steamnews.config
import steamnews.index

def init_logging():
    logging.config.fileConfig('logging.conf')
    return logging.getLogger('root')

if __name__ == '__main__':
	os.chdir(Path(__file__).absolute().parent)
	log = init_logging()
	config_file = Path('appsettings.json')
	config = steamnews.config.load_configuration(config_file, log)
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
