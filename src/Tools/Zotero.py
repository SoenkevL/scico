from dotenv import load_dotenv
from pyzotero import zotero
import os
from pprint import pprint, pformat

class Zotero:
    def __init__(self):
        load_dotenv()
        self.zot = zotero.Zotero(os.getenv("ZOTERO_ID"), "user", os.getenv("ZOTERO_API_KEY"))

    def get_item_count(self) -> int:
        """ Returns the number of items in the Zotero Library of the user"""
        return int(self.zot.count_items())

    def get_all_collections(self) -> dict:
        """ Returns a dictionary of all collections in the Zotero Library with their name as the key and their ID as the value"""
        collections = self.zot.collections()
        collection_dict = {}
        for collection in collections:
            collection_dict[collection['data']['name']] = collection['data']['key']
        return collection_dict