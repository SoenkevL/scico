"""
Main PdfIndexer class that orchestrates the indexing pipeline for Zotero PDFs.

This class coordinates:
- Querying Zotero for items/collections
- Converting PDFs to Markdown
- Chunking Markdown into LangChain Documents
- Indexing chunks into vector storage
"""

# === import global packages ===
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, Callable

from langchain_core.documents import Document

# === import local file dependencies ===
import src.zotero.zotero_client as zot
from src.configs.Chroma_storage_config import ChromaStorageConfig
from src.configs.pdf_indexer_config import IndexingConfig, IndexingResult, QueryType
from src.document_processing.Chunker import chunk
from src.document_processing.PdfToMarkdown import convert_pdf_to_markdown
from src.storages.ChromaStorage import ChromaStorage

# === initialize global objects ===
logger = logging.getLogger(__name__)


# === define helper functions ===
def _chunk_markdown(
        markdown_path: Path, metadata: zot.ZoteroMetadata
) -> List[Document]:
    """Chunk a Markdown file into LangChain Documents. Adds error handling."""
    try:
        chunks = chunk(md_path=markdown_path, metadata=dict(metadata))
        logger.debug(f"Created {len(chunks)} chunks from {markdown_path}")
        return chunks
    except Exception as e:
        logger.error(f"Failed to chunk markdown {markdown_path}: {e}")
        return []


# === define classes ===
class PdfIndexer:
    """
    Main orchestrator for indexing Zotero PDFs into a vector database.

    This class provides a high-level interface for:
    - Querying Zotero items by various criteria
    - Converting PDFs to Markdown
    - Chunking text into documents
    - Indexing into vector storage
    """

    def __init__(self, config: IndexingConfig, storage_config: ChromaStorageConfig):
        """
        Initialize the PdfIndexer with all required components.

        Args:
            config: Configuration for the indexing process
            storage_config: Configuration for the vector storage
        """
        self.config = config
        self.storage_config = storage_config
        self.zotero_client = zot
        self.vector_indexer = ChromaStorage(storage_config)

        # Ensure markdown base path exists
        self.config.markdown_base_path.mkdir(parents=True, exist_ok=True)
        self.config.markdown_base_path = self.config.markdown_base_path.resolve()

        logger.info(
            f"PdfIndexer initialized with markdown path: {self.config.markdown_base_path}"
        )

    # === define protected functions ===

    def _fetch_items_by_query(
            self,
            query_type: QueryType,
            query_value: Union[str, List[Tuple[Path, zot.ZoteroMetadata]]]
    ) -> List[Tuple[Path, zot.ZoteroMetadata]]:
        """
        Helper to fetch items from Zotero based on the query type.
        
        Returns:
            List of tuples containing (pdf_path, metadata)
        """
        if query_type == QueryType.ITEM_NAME and isinstance(query_value, str):
            return self.zotero_client.get_items_by_name(query_value)

        if query_type == QueryType.ITEM_ID and isinstance(query_value, str):
            # Normalize single item return to list
            item = self.zotero_client.get_item_by_id(query_value)
            return [item] if item else []

        if query_type == QueryType.COLLECTION_NAME and isinstance(query_value, str):
            return self.zotero_client.get_items_by_collection_name(query_value)

        if query_type == QueryType.COLLECTION_ID and isinstance(query_value, str):
            return self.zotero_client.get_items_by_collection_id(query_value)

        if query_type == QueryType.ITEM_LIST and isinstance(query_value, list):
            return query_value

        raise ValueError(
            f"Unknown query type: {query_type} or mismatch in query type and value"
        )

    def _convert_to_markdown(
            self, pdf_path: Path, metadata: zot.ZoteroMetadata
    ) -> Optional[Path]:
        """
        Convert a PDF to Markdown format.
        
        Returns:
            Path to the created Markdown file, or None if failed/skipped.
        """
        storage_key = metadata.get("storage_key")
        if not storage_key:
            logger.error(f"No storage key found in metadata for {pdf_path}")
            return None

        # Build output path: {markdown_base}/{storage_key}/{pdf_name}.md
        output_dir = self.config.markdown_base_path / storage_key
        output_dir.mkdir(parents=True, exist_ok=True)

        markdown_path = output_dir / (pdf_path.stem + ".md")

        # Skip if already exists and not forcing reindex
        if markdown_path.exists() and self.config.skip_existing_markdown:
            logger.info(f"Markdown already exists, skipping: {markdown_path}")
            return markdown_path

        try:
            logger.info(f"Converting PDF to Markdown: {pdf_path} -> {markdown_path}")
            success = convert_pdf_to_markdown(
                pdf_path=pdf_path,
                output_path=markdown_path,
            )

            if not success:
                logger.info(f"Failed during conversion: {markdown_path}")
                return None

            return markdown_path

        except Exception as e:
            logger.error(
                f"Failed to convert PDF to Markdown (exception): {e}", exc_info=True
            )
            return None

    def _index_chunks(self, chunks: List[Document]) -> None:
        """Index chunks into the vector storage."""
        if not chunks:
            return
        try:
            self.vector_indexer.add_documents(documents=chunks)
            logger.debug(f"Indexed {len(chunks)} chunks for item")
        except Exception as e:
            logger.error(f"Failed to index chunks: {e}")
            raise

    def _process_markdown_and_index(
            self, markdown_path: Path, metadata: zot.ZoteroMetadata
    ) -> Tuple[bool, int, Optional[str]]:
        """
        Process an existing markdown file: Chunk -> Index.
        
        Returns:
            Tuple of (success: bool, chunks_count: int, failure_reason: str | None)
        """
        # Step 1: Chunk the markdown
        chunks = _chunk_markdown(markdown_path, metadata)
        if not chunks:
            return False, 0, "No chunks created"

        # Step 2: Index chunks
        try:
            self._index_chunks(chunks)
            return True, len(chunks), None
        except Exception as e:
            return False, 0, str(e)

    def _process_single_item(
            self, pdf_path: Path, metadata: zot.ZoteroMetadata
    ) -> Tuple[bool, int, Optional[str]]:
        """
        Process a single Zotero item through the full pipeline: Convert -> Chunk -> Index.
        """
        # Step 1: Convert PDF to Markdown
        markdown_path = self._convert_to_markdown(pdf_path, metadata)
        if not markdown_path:
            return False, 0, "Markdown conversion failed"

        # Step 2 & 3: Chunk and Index
        return self._process_markdown_and_index(markdown_path, metadata)

    def _index_items_batch(
            self,
            items: List[Tuple[Path, zot.ZoteroMetadata]],
            progress_callback: Optional[Callable[[float], None]] = None,
    ) -> IndexingResult:
        """
        Internal method to process a batch of items.
        """
        total_items = len(items)
        successful = 0
        failed = 0
        failed_items = []
        total_chunks = 0

        logger.info(f"Starting to index {total_items} items")

        for idx, (pdf_path, metadata) in enumerate(items, 1):
            if progress_callback:
                progress_callback(idx / total_items)

            logger.info(f"Processing item {idx}/{total_items}: {pdf_path}")

            success, count, reason = self._process_single_item(pdf_path, metadata)

            if success:
                successful += 1
                total_chunks += count
                logger.info(f"Successfully indexed item {idx}/{total_items} ({count} chunks)")
            else:
                failed += 1
                failed_items.append({
                    "pdf_path": str(pdf_path),
                    "metadata": metadata,
                    "reason": reason
                })
                logger.warning(f"Failed item {idx}: {reason}")

        result = IndexingResult(
            total_items=total_items,
            successful=successful,
            failed=failed,
            failed_items=failed_items,
            chunks_created=total_chunks,
        )

        logger.info(f"Indexing complete: {successful}/{total_items} successful")
        return result

    def _index_by_item_name(self, item_name: str) -> IndexingResult:
        """Index PDFs by item name."""
        logger.info(f"Indexing by item name: {item_name}")
        items = self.zotero_client.get_items_by_name(item_name)
        return self._index_items_batch(items)

    def _index_by_item_id(self, item_id: str) -> IndexingResult:
        """Index PDFs by item ID."""
        logger.info(f"Indexing by item ID: {item_id}")
        item = self.zotero_client.get_item_by_id(item_id)
        # Wrap single item in list
        return self._index_items_batch([item] if item else [])

    def _index_by_collection_name(self, collection_name: str) -> IndexingResult:
        """Index all PDFs in a collection by name."""
        logger.info(f"Indexing by collection name: {collection_name}")
        items = self.zotero_client.get_items_by_collection_name(collection_name)
        return self._index_items_batch(items)

    def _index_by_collection_id(self, collection_id: str) -> IndexingResult:
        """Index all PDFs in a collection by ID."""
        logger.info(f"Indexing by collection ID: {collection_id}")
        items = self.zotero_client.get_items_by_collection_id(collection_id)
        return self._index_items_batch(items)

    # === define public functions ===

    def search(
            self, query: str, metadata_filter: Optional[Dict] = None, n_results: int = 10
    ) -> List[Document]:
        """Search the vector indexer with its own search method."""
        return self.vector_indexer.search(query, metadata_filter or {}, n_results)

    def index_all_markdown_files(
            self,
            progress_callback: Optional[Callable[[float], None]] = None
    ) -> IndexingResult:
        """
        Scan the configured markdown directory and index all found markdown files.
    
        This is useful for:
        1. Re-indexing existing content without querying Zotero.
        2. Ensuring manually added markdown files are indexed.
        3. Recovery if the indexing step failed but conversion succeeded.

        Returns:
            IndexingResult with statistics.
        """
        markdown_files = list(self.config.markdown_base_path.rglob("*.md"))
        total_items = len(markdown_files)

        logger.info(f"Found {total_items} existing markdown files in {self.config.markdown_base_path}")

        successful = 0
        failed = 0
        failed_items = []
        total_chunks = 0

        # get all items currently in the index
        indexing_stats = self.get_indexing_stats()
        indexed_items = indexing_stats.get("items", {})
        indexed_storage_keys = set([value.get('storage_key') for value in indexed_items.values()])


        for idx, md_path in enumerate(markdown_files, 1):
            if progress_callback:
                progress_callback(idx / total_items)

            try:
                # Attempt to reconstruct minimal metadata from path structure
                # Structure is expected to be: .../storage_key/filename.md
                storage_key = md_path.parent.name

                # continue to next one if allready indexed
                if storage_key in indexed_storage_keys and not self.config.force_reindex:
                    continue

                # get the metadata for the item
                item_id = zot.get_item_id_from_storage_key(storage_key)
                if not item_id:
                    logger.warning(f"No item id found for storage key: {storage_key}")
                    continue
                _, metadata = zot.get_item_by_id(item_id)
                logger.info(f"Processing local markdown {idx}/{total_items}: {md_path}")

                success, count, reason = self._process_markdown_and_index(md_path, metadata)

                if success:
                    successful += 1
                    total_chunks += count
                else:
                    failed += 1
                    failed_items.append({
                        "pdf_path": str(md_path),  # Using md_path here
                        "metadata": metadata,
                        "reason": reason
                    })
                    logger.warning(f"Failed local file {idx}: {reason}")

            except Exception as e:
                failed += 1
                failed_items.append({
                    "pdf_path": str(md_path),
                    "metadata": {},
                    "reason": str(e)
                })
                logger.error(f"Error processing local file {md_path}: {e}")

        result = IndexingResult(
            total_items=total_items,
            successful=successful,
            failed=failed,
            failed_items=failed_items,
            chunks_created=total_chunks
        )

        logger.info(f"Local markdown indexing complete: {successful}/{total_items} successful")
        return result

    def update_index(
            self,
            query_type: QueryType,
            query_value: Union[str, List[Tuple[Path, Dict[str, Any]]]],
            force: bool = False,
            progress_callback: Optional[Callable[[float], None]] = None,
    ) -> IndexingResult:
        """
        Update the existing index by re-processing items.

        This will remove old chunks and re-index with fresh data.

        Args:
            query_type: Type of query (item/collection by name/id)
            query_value: Value to query for
            force: If True, force reindex even if content hasn't changed
        """
        force = force or self.config.force_reindex
        logger.info(f"Updating index for {query_type.value}")

        # 1. Fetch Items
        items = self._fetch_items_by_query(query_type, query_value)

        # 2. Filter Existing Items
        items_to_process = []

        for pdf_path, metadata in items:
            item_id = metadata.get("item_id") or metadata.get("key")
            if not item_id:
                continue

            existing_uids = self.vector_indexer.uids_from_item_id(item_id)
            has_existing = len(existing_uids) > 0

            if has_existing:
                if force:
                    self.vector_indexer.delete_by_item_id(item_id)
                    logger.info(f"Deleted existing chunks for item: {item_id}")
                    items_to_process.append((pdf_path, metadata))
                else:
                    logger.info(f"Skipping re-index for item: {item_id} (no changes)")
            else:
                items_to_process.append((pdf_path, metadata))

        # 3. Index Filtered Items
        logger.info(f"Indexing {len(items_to_process)} items")
        return self._index_items_batch(items_to_process, progress_callback=progress_callback)

    def get_indexing_stats(self) -> Dict[str, Any]:
        """Get statistics about the current index."""
        return self.vector_indexer.get_collection_stats()

    def clear_index(self, confirm: bool = False) -> bool:
        """
        Clear the entire vector index.
        
        Args:
            confirm: Must be True to actually clear the index (safety measure)
        """
        if not confirm:
            logger.warning("Index clear requested but not confirmed")
            return False

        logger.warning("Clearing entire vector index")
        self.vector_indexer.clear()
        return True
