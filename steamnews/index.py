import whoosh.index
import whoosh.fields
from pathlib import Path

def create_steamapp_index(config):
    indexdir = Path(config['steam_index_dir'])
    if indexdir.is_dir():
        return whoosh.index.open_dir(indexdir)
    else:
        indexdir.mkdir(exist_ok)
        schema = whoosh.fields.Schema(appid=whoosh.fields.NUMERIC(stored=True, unique=True), name=whoosh.fields.TEXT(stored=True))
        return whoosh.index.create_in(indexdir, schema)
