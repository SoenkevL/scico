"""File to set up Zotero MCP"""
import os

from dotenv import load_dotenv
from fastmcp import FastMCP
from pyzotero import zotero

mcp = FastMCP(
    name="Zotero",
    instructions="Fetch information from the Zotero reference manager of the user"
)

# Setup
load_dotenv()
zot = zotero.Zotero(os.getenv("ZOTERO_ID"), "user", os.getenv("ZOTERO_API_KEY"))


# Tool functions
@mcp.tool
def get_item_count() -> int:
    """ Returns the number of items in the Zotero Library of the user"""
    return int(zot.count_items())


@mcp.tool
def list_all_collections() -> dict:
    """ Returns a dictionary of all collections in the Zotero Library with their name as the key and their ID as the value"""
    collections = zot.collections()
    collection_dict = {}
    for collection in collections:
        collection_dict[collection['data']['name']] = collection['data']['key']
    return collection_dict


@mcp.tool
def get_collection_items(collection_id: str) -> dict:
    """ Returns all items and their names from a zotero collection based on its ID"""
    item_dict = {}
    for item in zot.collection_items(collection_id):
        item_id = item.get('key')
        item_name = item.get('data', {}).get('title')
        item_dict[item_name] = item_id
    return item_dict


@mcp.tool
def get_item_metadata(item_id: str) -> dict:
    """ Returns the metadata of a single item from the Zotero Library of the user using its ID"""
    item = zot.item(item_id)
    return item


@mcp.tool
def get_fulltext_item(item_id: str) -> str:
    """ Returns the full text of a single item from the Zotero Library using the item ID"""
    fulltext = zot.fulltext_item(item_id)
    return fulltext.get('content', '')


if __name__ == "__main__":
    mcp.run(transport="sse", host="127.0.0.1", port=8000)
