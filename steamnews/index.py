import whoosh.index
import whoosh.fields
import whoosh.qparser
from pathlib import Path

def create_steamapp_index(config):
    indexdir = Path(config['steam_index_dir'])
    if indexdir.is_dir():
        return whoosh.index.open_dir(indexdir)
    else:
        indexdir.mkdir()
        schema = whoosh.fields.Schema(appid=whoosh.fields.NUMERIC(stored=True, unique=True), name=whoosh.fields.TEXT(stored=True))
        return whoosh.index.create_in(indexdir, schema)

class SteamApps:
    @classmethod
    def load(Cls, config, log):
        index = create_steamapp_index(config)
        log.info(f"Indexes loaded - {index.doc_count()} entries")
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
        parser = whoosh.qparser.QueryParser('name', schema=self.index.schema, group=whoosh.qparser.AndGroup)
        query = parser.parse(name)
        with self.index.searcher() as searcher:
            results = []
            for result in searcher.search(query):
                r_appid = result['appid']
                r_name = result['name']
                results.append((r_appid, r_name))
            return results

