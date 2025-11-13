"""
Main PdfIndexer class that orchestrates the indexing pipeline for Zotero PDFs.

This class coordinates:
- Querying Zotero for items/collections
- Converting PDFs to Markdown
- Chunking Markdown into LangChain Documents
- Indexing chunks into vector storage
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.documents import Document

import src.zotero.zotero_client as zot
from src.configs.pdf_indexer_config import IndexingConfig, IndexingResult, QueryType
from src.document_processing.Chunker import chunk
from src.document_processing.PdfToMarkdown import convert_pdf_to_markdown
from src.storages.VectorStorage import ChromaStorage

logger = logging.getLogger(__name__)


class PdfIndexer:
    """
    Main orchestrator for indexing Zotero PDFs into a vector database.

    This class provides a high-level interface for:
    - Querying Zotero items by various criteria
    - Converting PDFs to Markdown
    - Chunking text into documents
    - Indexing into vector storage
    """

    def __init__(self, config: IndexingConfig):
        """
        Initialize the PdfIndexer with all required components.

        Args:
            config: Configuration for the indexing process
        """
        self.config = config
        self.zotero_client = zot
        self.vector_indexer = ChromaStorage(
            index_path=self.config.vector_storage_path,
            collection_name=self.config.collection_name,
            embedding_model=self.config.embedding_model,
            api=self.config.api,
        )

        # Ensure markdown base path exists
        self.config.markdown_base_path.mkdir(parents=True, exist_ok=True)
        self.config.markdown_base_path = self.config.markdown_base_path.resolve()

        logger.info(
            f"PdfIndexer initialized with markdown path: {self.config.markdown_base_path}"
        )

    def search(
            self, query: str, metadata_filter: dict = {}, n_results: int = 10
    ) -> List[Document]:
        """search the vector indexer with its own search method"""
        return self.vector_indexer.search(query, metadata_filter, n_results)

    def _index_by_item_name(self, item_name: str) -> IndexingResult:
        """
        Index PDFs by item name.

        Args:
            item_name: Name of the Zotero item to index

        Returns:
            IndexingResult with statistics about the operation
        """
        logger.info(f"Indexing by item name: {item_name}")
        items = self.zotero_client.get_items_by_name(item_name)
        return self._index_items(items)

    def _index_by_item_id(self, item_id: str) -> IndexingResult:
        """
        Index PDFs by item ID.

        Args:
            item_id: Zotero item ID to index

        Returns:
            IndexingResult with statistics about the operation
        """
        logger.info(f"Indexing by item ID: {item_id}")
        items = self.zotero_client.get_items_by_id(item_id)
        return self._index_items([items])

    def _index_by_collection_name(self, collection_name: str) -> IndexingResult:
        """
        Index all PDFs in a collection by name.

        Args:
            collection_name: Name of the Zotero collection to index

        Returns:
            IndexingResult with statistics about the operation
        """
        logger.info(f"Indexing by collection name: {collection_name}")
        items = self.zotero_client.get_items_by_collection_name(collection_name)
        return self._index_items(items)

    def _index_by_collection_id(self, collection_id: str) -> IndexingResult:
        """
        Index all PDFs in a collection by ID.

        Args:
            collection_id: Zotero collection ID to index

        Returns:
            IndexingResult with statistics about the operation
        """
        logger.info(f"Indexing by collection ID: {collection_id}")
        items = self.zotero_client.get_items_by_collection_id(collection_id)
        return self._index_items(items)

    def update_index(
            self,
            query_type: QueryType,
            query_value: str | List[Tuple[Path, Dict[str, Any]]],
            force: bool = False,
    ) -> IndexingResult:
        """
        Update the existing index by re-processing items.

        This will remove old chunks and re-index with fresh data.

        Args:
            query_type: Type of query (item/collection by name/id)
            query_value: Value to query for
            force: If True, force reindex even if content hasn't changed

        Returns:
            IndexingResult with statistics about the operation
        """
        force = force or self.config.force_reindex
        logger.info(f"Updating index for {query_type.value}")

        # Get items based on query type
        if query_type == QueryType.ITEM_NAME and isinstance(query_value, str):
            items = self.zotero_client.get_items_by_name(query_value)
        elif query_type == QueryType.ITEM_ID and isinstance(query_value, str):
            items = self.zotero_client.get_items_by_id(query_value)
        elif query_type == QueryType.COLLECTION_NAME and isinstance(query_value, str):
            items = self.zotero_client.get_items_by_collection_name(query_value)
        elif query_type == QueryType.COLLECTION_ID and isinstance(query_value, str):
            items = self.zotero_client.get_items_by_collection_id(query_value)
        elif query_type == QueryType.ITEM_LIST and isinstance(query_value, list):
            items = query_value
        else:
            raise ValueError(
                f"Unknown query type: {query_type} or missmatch in query type and value"
            )

        # Handle existing chunks
        remove_list = []
        for pdf_path, metadata in items:
            item_id = metadata.get("item_id") or metadata.get("key")
            if not item_id:
                continue
            uids = self.vector_indexer.uids_from_item_id(item_id)
            if len(uids) > 0:
                logger.info(f"Found {len(uids)} existing chunks for item: {item_id}")
                if force:
                    self.vector_indexer.delete_by_item_id(item_id)
                    logger.info(f"Deleted existing chunks for item: {item_id}")
                else:
                    remove_list.append((pdf_path, metadata))
                    logger.info(f"Skipping re-index for item: {item_id} (no changes)")
        if remove_list:
            for ritem in remove_list:
                items.remove(ritem)

        # Index
        logger.info(f"Indexing {len(items)} items")
        result = self._index_items(items)

        return result

    def _index_items(
            self,
            items: List[Tuple[Path, Dict[str, Any]]],
    ) -> IndexingResult:
        """
        Internal method to index a list of items.

        Args:
            items: List of tuples (pdf_path, metadata)

        Returns:
            IndexingResult with statistics about the operation
        """
        total_items = len(items)
        successful = 0
        failed = 0
        failed_items = []
        total_chunks = 0

        logger.info(f"Starting to index {total_items} items")

        for idx, (pdf_path, metadata) in enumerate(items, 1):
            try:
                logger.info(f"Processing item {idx}/{total_items}: {pdf_path}")
                # Step 1: Convert PDF to Markdown
                markdown_path: Path | None = self._convert_to_markdown(
                    pdf_path, metadata
                )

                if markdown_path is None:
                    logger.warning(
                        f"Skipping item {idx}: Markdown conversion failed or skipped"
                    )
                    failed += 1
                    failed_items.append(
                        {
                            "pdf_path": str(pdf_path),
                            "metadata": metadata,
                            "reason": "Markdown conversion failed",
                        }
                    )
                    continue

                # Step 2: Chunk the markdown
                chunks: list[Document] = self._chunk_markdown(markdown_path, metadata)

                if not chunks:
                    logger.warning(f"No chunks created for item {idx}")
                    failed += 1
                    failed_items.append(
                        {
                            "pdf_path": str(pdf_path),
                            "metadata": metadata,
                            "reason": "No chunks created",
                        }
                    )
                    continue

                # Step 3: Index chunks into vector storage
                self._index_chunks(chunks)

                total_chunks += len(chunks)
                successful += 1
                logger.info(
                    f"Successfully indexed item {idx}/{total_items} with {len(chunks)} chunks"
                )

            except Exception as e:
                logger.error(
                    f"Error processing item {idx}/{total_items}: {e}", exc_info=True
                )
                failed += 1
                failed_items.append(
                    {"pdf_path": str(pdf_path), "metadata": metadata, "reason": str(e)}
                )

        result = IndexingResult(
            total_items=total_items,
            successful=successful,
            failed=failed,
            failed_items=failed_items,
            chunks_created=total_chunks,
        )

        logger.info(f"Indexing complete: {successful}/{total_items} successful ")

        return result

    def _convert_to_markdown(
            self, pdf_path: Path, metadata: Dict[str, Any]
    ) -> Optional[Path]:
        """
        Convert a PDF to Markdown format.

        Args:
            pdf_path: Path to the PDF file
            metadata: Metadata associated with the PDF

        Returns:
            Path to the created Markdown file, or None if conversion failed/skipped
        """
        storage_key = metadata.get("storage_key") or metadata.get("key")
        if not storage_key:
            logger.error(f"No storage key found in metadata for {pdf_path}")
            return None

        # Build output path: {markdown_base}/{storage_key}/{pdf_name}.md
        output_dir = self.config.markdown_base_path / storage_key
        output_dir.mkdir(parents=True, exist_ok=True)

        markdown_filename = pdf_path.stem + ".md"
        markdown_path = output_dir / markdown_filename

        logger.info(f"Converting PDF to Markdown: {pdf_path} -> {markdown_path}")
        # Skip if already exists and not forcing reindex
        if markdown_path.exists() and self.config.skip_existing_markdown:
            logger.info(f"Markdown already exists, skipping: {markdown_path}")
            return markdown_path

        try:
            # Use the pdf_processor to convert
            success = convert_pdf_to_markdown(
                pdf_path=pdf_path,
                output_path=markdown_path,
            )
            if success:
                logger.info(f"Converted PDF to Markdown: {markdown_path}")
                return markdown_path
            else:
                logger.info(
                    f"Failed during conversion to convert PDF to Markdown: {markdown_path}"
                )
            return None

        except Exception as e:
            logger.error(
                f"Failed to convert PDF to Markdown outside of actual conversion: {e}"
            )
            return None

    def _chunk_markdown(
            self, markdown_path: Path, metadata: Dict[str, Any]
    ) -> list[Document]:
        """
        Chunk a Markdown file into LangChain Documents.

        Args:
            markdown_path: Path to the Markdown file
            metadata: Metadata to attach to each chunk

        Returns:
            List of LangChain Document objects
        """
        try:
            # Create chunks with metadata
            chunks = chunk(
                md_path=markdown_path,
                metadata=metadata,
            )

            logger.debug(f"Created {len(chunks)} chunks from {markdown_path}")
            return chunks

        except Exception as e:
            logger.error(f"Failed to chunk markdown {markdown_path}: {e}")
            return []

    def _index_chunks(
            self,
            chunks: List[Any],  # List[Document]
    ) -> None:
        """
        Index chunks into the vector storage.

        Args:
            chunks: List of LangChain Document objects
        """
        try:
            # Add chunks to vector storage
            self.vector_indexer.add_documents(
                documents=chunks,
            )
            logger.debug(f"Indexed {len(chunks)} chunks for item")

        except Exception as e:
            logger.error(f"Failed to index chunks: {e}")
            raise

    def get_indexing_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the current index.

        Returns:
            Dictionary with statistics (total chunks, items, etc.)
        """
        return self.vector_indexer.get_collection_stats()

    def clear_index(self, confirm: bool = False) -> bool:
        """
        Clear the entire vector index.

        Args:
            confirm: Must be True to actually clear the index (safety measure)

        Returns:
            True if cleared, False otherwise
        """
        if not confirm:
            logger.warning("Index clear requested but not confirmed")
            return False

        logger.warning("Clearing entire vector index")
        self.vector_indexer.clear()
        return True
