"""
Zotero Client for PDF Indexing workflow.

This module wraps the pyzotero library and provides methods to query
Zotero items and collections, returning them in a format suitable for
the PDF indexing pipeline.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from dotenv import load_dotenv
from pyzotero import zotero

logger = logging.getLogger(__name__)
load_dotenv()


@dataclass
class ZoteroClientConfig:
    library_id: str = os.getenv("ZOTERO_ID", '')
    api_key: str = os.getenv("ZOTERO_API_KEY", '')
    local_storage_path: Path = Path(os.getenv("LOCAL_ZOTERO_PATH", ""))

    def __post__init__(self):
        if not self.library_id or not self.api_key:
            raise ValueError("ZOTERO_ID and ZOTERO_API_KEY must be provided or set in environment")

        if not self.local_storage_path or not self.local_storage_path.exists():
            raise ValueError(f"LOCAL_ZOTERO_PATH must be provided and exist: {self.local_storage_path}")


CONFIG = ZoteroClientConfig()
ZOT = zotero.Zotero(
    CONFIG.library_id, "user", CONFIG.api_key
)


def get_item_count() -> int:
    """Returns the number of items in the Zotero Library."""
    return int(ZOT.count_items())


def get_items_by_name(item_name: str) -> List[Tuple[Path, Dict[str, Any]]]:
    """
    Get items matching a name/title.

    Args:
        item_name: Name or title to search for (partial match)

    Returns:
        List of (pdf_path, metadata) tuples
    """
    logger.info(f"Searching for items with name: {item_name}")

    # Search for items by title
    items = ZOT.items(q=item_name, qmode='titleCreatorYear')

    results = []
    for item in items:
        if item_tuple := _process_item(item):
            results.append(item_tuple)

    logger.info(f"Found {len(results)} items matching '{item_name}'")
    return results


def get_items_by_id(item_id: str) -> Tuple[Path, Dict[str, Any]]:
    """
    Get a specific item by its ID.

    Args:
        item_id: Zotero item ID (key)

    Returns:
        List containing single (pdf_path, metadata) tuple if found
    """
    logger.info(f"Fetching item with ID: {item_id}")

    try:
        item = ZOT.item(item_id)
        if item_tuple := _process_item(item):
            return item_tuple
    except Exception as e:
        logger.error(f"Error fetching item {item_id}: {e}")

    return Path(""), {}


def get_items_by_collection_name(collection_name: str) -> List[Tuple[Path, Dict[str, Any]]]:
    """
    Get all items in a collection by its name.

    Args:
        collection_name: Name of the Zotero collection

    Returns:
        List of (pdf_path, metadata) tuples
    """
    logger.info(f"Fetching items from collection: {collection_name}")

    # Find collection ID by name
    collections = list_all_collections()
    collection_id = collections.get(collection_name)

    if not collection_id:
        logger.warning(f"Collection '{collection_name}' not found")
        return []

    return get_items_by_collection_id(collection_id)


def get_items_by_collection_id(collection_id: str) -> List[Tuple[Path, Dict[str, Any]]]:
    """
    Get all items in a collection by its ID.

    Args:
        collection_id: Zotero collection ID (key)

    Returns:
        List of (pdf_path, metadata) tuples
    """
    logger.info(f"Fetching items from collection ID: {collection_id}")

    try:
        items = ZOT.collection_items(collection_id)
    except Exception as e:
        logger.error(f"Error fetching collection {collection_id}: {e}")
        return []

    results = []
    if not isinstance(items, list):
        items = list(items)
    for item in items:
        # Skip child items (attachments, notes, etc.)
        if item.get('data', {}).get('parentItem'):
            continue

        if item_tuple := _process_item(item):
            results.append(item_tuple)

    logger.info(f"Found {len(results)} items in collection '{collection_id}'")
    return results


def list_all_collections() -> Dict[str, str]:
    """
    Returns a dictionary of all collections.

    Returns:
        Dictionary with collection names as keys and IDs as values
    """
    collections = ZOT.collections()
    collection_dict = {}
    for collection in collections:
        collection_dict[collection['data']['name']] = collection['data']['key']
    return collection_dict


def _process_item(item: Dict[str, Any]) -> Optional[Tuple[Path, Dict[str, Any]]]:
    """
    Process a Zotero item and extract PDF path and metadata.

    Args:
        item: Raw Zotero item from API

    Returns:
        Tuple of (pdf_path, metadata) or None if no PDF found
    """
    try:
        # Get item data
        item_data = item.get('data', {})
        item_id = item_data.get('key')

        if not item_id:
            logger.warning("Item has no key, skipping")
            return None

        # Get PDF path
        pdf_path = _get_pdf_path_for_item(item)

        if not pdf_path:
            logger.debug(f"No PDF found for item {item_id}")
            return None

        # Parse metadata
        metadata = _parse_item_metadata(item)
        metadata['item_id'] = item_id
        metadata['storage_key'] = _get_storage_key_from_item(item)

        return (pdf_path, metadata)

    except Exception as e:
        logger.error(f"Error processing item: {e}", exc_info=True)
        return None


def _get_pdf_path_for_item(item: Dict[str, Any]) -> Optional[Path]:
    """
    Get the local PDF path for a Zotero item.

    Args:
        item: Zotero item

    Returns:
        Path to PDF file or None if not found
    """
    # Check if item has attachment link
    links = item.get('links', {})
    attachment = links.get('attachment', {})

    if attachment.get('attachmentType') != 'application/pdf':
        # No direct PDF attachment, check for child attachments
        item_id = item.get('key')
        if item_id:
            children = ZOT.children(item_id)
            if not isinstance(children, list):
                children = list(children)
            for child in children:
                if not isinstance(child, dict):
                    continue
                if child.get('data', {}).get('contentType') == 'application/pdf':
                    return _get_pdf_path_from_child(child)
        return None

    # Get storage key from attachment link
    href = attachment.get('href', '')
    if not href:
        return None

    storage_key = href.split('/')[-1]
    return _get_pdf_from_storage_key(storage_key)


def _get_pdf_path_from_child(child_item: Dict[str, Any]) -> Optional[Path]:
    """Get PDF path from a child attachment item."""
    child_key = child_item.get('key')
    if not child_key:
        return None

    return _get_pdf_from_storage_key(child_key)


def _get_pdf_from_storage_key(storage_key: str) -> Optional[Path]:
    """
    Get PDF path from a storage key.

    Args:
        storage_key: Zotero storage key

    Returns:
        Path to PDF file or None
    """
    storage_path = CONFIG.local_storage_path / 'storage' / storage_key

    if not storage_path.exists():
        logger.debug(f"Storage path does not exist: {storage_path}")
        return None

    # Find PDF file in storage directory
    for file in storage_path.iterdir():
        if file.suffix.lower() == '.pdf':
            return file

    logger.debug(f"No PDF found in storage path: {storage_path}")
    return None


def _get_storage_key_from_item(item: Dict[str, Any]) -> str:
    """
    Extract storage key from item.

    Args:
        item: Zotero item

    Returns:
        Storage key string
    """
    # Try to get from attachment link
    links = item.get('links', {})
    attachment = links.get('attachment', {})
    href = attachment.get('href', '')

    if href:
        return href.split('/')[-1]

    # Check children for attachment
    item_id = item.get('key')
    if item_id:
        children = ZOT.children(item_id)
        if not isinstance(children, list):
            children = list(children)
        for child in children:
            if not isinstance(child, dict):
                continue
            if child.get('data', {}).get('contentType') == 'application/pdf':
                return child.get('key', '')

    # Fallback to item key
    return item.get('key', '')


def _parse_collections(collection: List[str]) -> str:
    all_collections = list_all_collections()
    all_collections = {item: key for key, item in all_collections.items()}
    collection_names = [all_collections[col] for col in collection]
    return ': '.join(collection_names)


def _parse_creators(creators: List[Dict[str, str]]) -> str:
    """Parse creators into a string."""
    author_list = []
    for creator in creators:
        last_name = creator.get('lastName', '')
        first_name = creator.get('firstName', '')
        if last_name or first_name:
            author_list.append(f"{last_name}, {first_name}".strip(', '))
    return '; '.join(author_list)


def _parse_tags(tags: List[Dict[str, str]]) -> str:
    """Parse tags into a string."""
    return '; '.join([tag.get('tag', '') for tag in tags])


def _parse_citation_key(extra: str) -> str:
    """Extract citation key from extra field."""
    for line in extra.split('\n'):
        if line.startswith('Citation Key: '):
            return line.split('Citation Key: ')[1].strip()
    return ''


def _parse_item_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse metadata from a Zotero item.

    Args:
        item: Raw Zotero item

    Returns:
        Dictionary with parsed metadata
    """
    item_data = item.get('data', {})

    metadata = {
        'title': item_data.get('title', ''),
        'authors': _parse_creators(item_data.get('creators', [])),
        'abstract': item_data.get('abstractNote', ''),
        'collections': _parse_collections(item_data.get('collections', [])),
        'tags': _parse_tags(item_data.get('tags', [])),
        'citation_key': item_data.get('citationKey') or _parse_citation_key(item_data.get('extra', '')),
        'doi': item_data.get('DOI', ''),
        'date': item_data.get('date', ''),
        'item_type': item_data.get('itemType', ''),
        'publication': item_data.get('publicationTitle', ''),
        'url': item_data.get('url', ''),
        'source': 'Zotero',
        'item_id': item_data.get('key'),
    }

    return metadata


if __name__ == "__main__":
    # Example usage
    print(f"Connected to Zotero library with {get_item_count()} items")

    # List collections
    collections = list_all_collections()
    print(f"\nFound {len(collections)} collections:")
    for name, id in list(collections.items())[:5]:
        print(f"  - {name}: {id}")
