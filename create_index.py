from pathlib import Path
import requests

import steamnews.config
import steamnews.index

if __name__ == '__main__':
	config_file = Path(__file__).absolute().parent / 'appsettings.json'
	config = steamnews.config.load_configuration(config_file)
	index = steamnews.index.create_steamapp_index(config)
	print("Getting app list...")
	r = requests.get(config['steam_app_list_url'])
	r.raise_for_status()
	print("Updating indexes...")
	writer = index.writer(limitmb=256, procs=4)
	for entry in r.json()["applist"]["apps"]:
		writer.update_document(appid=entry['appid'], name=entry['name'])
	writer.commit()
	print(f"Indexes updated - {index.doc_count()} entries")
