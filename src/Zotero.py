"""File to set up Zotero MCP"""
from pyzotero import zotero
import os
from dotenv import load_dotenv
from fastmcp import FastMCP

# Setup
load_dotenv()
zot = zotero.Zotero(os.getenv("ZOTERO_ID"), "user", os.getenv("ZOTERO_API_KEY"))

# Tool functions
def get_item_count() -> int:
    """ Returns the number of items in the Zotero Library of the user"""
    return int(zot.count_items())

def list_all_collections() -> dict:
    """ Returns a dictionary of all collections in the Zotero Library with their name as the key and their ID as the value"""
    collections = zot.collections()
    collection_dict = {}
    for collection in collections:
        collection_dict[collection['data']['name']] = collection['data']['key']
    return collection_dict

def get_collection_items(collection_id:str, only_parent_items:bool = True)-> dict:
    """ Returns all items and their names from a zotero collection based on its ID"""
    item_dict = {}
    for item in zot.collection_items(collection_id):
        if not (item_data := item.get('data', None)):
            continue
        if only_parent_items and len(item_data.get('parentItem', '')) > 0:
            continue
        item_id = item.get('key')
        item_name = item.get('data', {}).get('title')
        item_dict[item_name] = item_id
    return item_dict

def get_item_metadata(item_id:str, metadata_parser=True) -> dict:
    """ Returns the metadata of a single item from the Zotero Library of the user using its ID"""
    item = zot.item(item_id)
    if metadata_parser:
        metadata = parse_item(item)
        return metadata
    return item

def get_fulltext_item(item_id:str) -> str:
    """ Returns the full text of a single item from the Zotero Library using the item ID"""
    fulltext = zot.fulltext_item(item_id)
    return fulltext.get('content', '')

def local_pdf_id_from_item_id(item_id: str) -> str:
    item = zot.item(item_id)
    links = item.get('links', {})
    attachment = links.get('attachment', {})
    if not attachment.get('attachmentType') == 'application/pdf':
        return ''
    href = attachment.get('href', '')
    local_id = href.split(os.sep)[-1]
    return local_id

def pdf_path_from_local_pdf_id(local_id: str) -> str:
    storage_path = os.path.join(os.getenv('LOCAL_ZOTERO_PATH'), 'storage', local_id)
    if not (files := os.listdir(storage_path)):
        return ''
    for file in files:
        if file.endswith('.pdf'):
            pdf_path = os.path.join(storage_path, file)
            return pdf_path
    return ''

def local_pdf_path_from_item_id(item_id: str) -> (str, str):
    """Find the local pdf based on the item_id"""
    local_id = local_pdf_id_from_item_id(item_id)
    return pdf_path_from_local_pdf_id(local_id)

#parsers for dicts
def parse_creators(creators:dict) -> str:
    authors = ''
    for author in creators:
        authors += f'{author.get("lastName")}, {author.get("firstName")}; '
    return authors.strip()

def parse_tags(tags:dict) -> str:
    tag_string = ''
    for tag in tags:
        tag_string += f'{tag.get("name")}; '
    return tag_string.strip()

def parse_extra_to_citation_key(extra:dict) -> str:
    citation_key = ''
    for line in extra.split('\n'):
        if line.startswith('Citation Key: '):
            citation_key = line.split('Citation Key: ')[1].strip()
            return citation_key
    return citation_key

def parse_links(links:dict) -> str:
    attachment = links.get('attachment', {})
    if not attachment.get('attachmentType') == 'application/pdf':
        return ''
    href = attachment.get('href', '')
    local_id = href.split(os.sep)[-1]
    return pdf_path_from_local_pdf_id(local_id)

def parse_item(item:dict) -> dict:
    mdata = item.get('data')
    parsed_dict = {
        'title': mdata.get('title'),
        'authors': parse_creators(mdata.get('creators', [])),
        'abstract': mdata.get('abstractNote'),
        'TAGS': parse_tags(mdata.get('TAGS', [])),
        'citation_key': parse_extra_to_citation_key(mdata.get('extra')),
        'doi': mdata.get('DOI'),
        'date': mdata.get('date'),
        'attachments': parse_links(item.get('links', {})),
    }
    return parsed_dict


if __name__ == "__main__":
    print('no main function implemented for Zotero')