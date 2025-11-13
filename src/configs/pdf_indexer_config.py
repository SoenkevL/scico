import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Dict, List


class QueryType(StrEnum):
    """Types of queries supported for finding Zotero items."""

    ITEM_NAME = "item_name"
    ITEM_ID = "item_id"
    COLLECTION_NAME = "collection_name"
    COLLECTION_ID = "collection_id"
    ITEM_LIST = "item_list"


@dataclass
class IndexingResult:
    """Result of an indexing operation."""

    total_items: int
    successful: int
    failed: int
    failed_items: List[Dict[str, Any]]
    chunks_created: int


@dataclass
class IndexingConfig:
    """Configuration for the indexing process."""

    markdown_base_path: Path
    force_reindex: bool = False
    skip_existing_markdown: bool = True
    batch_size: int = 1
    chunk_size: int = 1000
    chunk_overlap: int = 200
    chunking_strategy: str = "markdown+recursive"
    vector_storage_path = os.getenv("VECTOR_STORAGE_PATH", "")
    collection_name = "Zotero"
    embedding_model = os.getenv("EMBEDDING_MODEL_NAME", "nomic-embed-text")
    api = os.getenv("EMBEDDING_MODEL_API", "ollama")

    def __post_init__(self):
        """Convert string paths to Path objects."""
        if isinstance(self.markdown_base_path, str):
            self.markdown_base_path = Path(self.markdown_base_path)
