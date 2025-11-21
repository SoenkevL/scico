import os
import time
from logging import getLogger
from typing import List, Dict, Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings

from src.configs.Chroma_storage_config import VectorStorageConfig

logger = getLogger(__name__)


def _format_search_results(results: List[tuple]) -> List[Document]:
    """Format similarity search results into Document objects with distance metadata."""
    return [
        Document(
            page_content=doc.page_content,
            metadata=doc.metadata | {'distance': distance}
        )
        for doc, distance in results
    ]


def _convert_results_to_documents(results: Dict) -> List[Document]:
    """Convert raw collection results to Document objects."""
    documents = []
    if results['ids']:
        for i in range(len(results['ids'])):
            doc = Document(
                page_content=results['documents'][i],
                metadata=results['metadatas'][i]
            )
            documents.append(doc)
    return documents


class ChromaStorage:
    """LangChain-powered vector storage with Ollama embeddings."""

    def __init__(self, config: VectorStorageConfig):
        self.index_path = config.vector_storage_path
        self.embedding_model = config.embedding_model
        self.api = config.api
        self.collection_name = f'{config.collection_name}_{self.api}_{self.embedding_model}'

        # Initialize LangChain Ollama embeddings
        self.embeddings = self._init_embedding()

        # Initialize LangChain Chroma vector store
        logger.info(f"Initializing Chroma vector store with collection {self.collection_name}")
        self.vectorstore = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embeddings,
            persist_directory=str(config.vector_storage_path)
        )

    def _init_embedding(self):
        if self.api == 'openai':
            return OpenAIEmbeddings(model=self.embedding_model, )
        if self.api == 'ollama':
            return OllamaEmbeddings(model=self.embedding_model,
                                    base_url=os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434'))
        else:
            raise ValueError(f"Unsupported provider: {self.api}")

    def _get_collection(self):
        """Get the underlying Chroma collection."""
        return self.vectorstore._collection

    def _query(self, query: str, n_results: int = 5) -> List[Document]:
        """
        Query vector store using similarity search.
        Args:
            query:query string to run similarity search on
            n_results: Number of results to return
        Returns:
            Dict with 'documents', 'metadatas', 'distances' keys for compatibility
        """

        # Perform similarity search with scores
        results = self.vectorstore.similarity_search_with_score(
            query=query,
            k=n_results
        )

        return _format_search_results(results)

    def _query_with_metadata(
            self,
            query: str,
            metadata_filter: Dict[str, Any],
            n_results: int = 5
    ) -> List[Document]:
        """
        Query vector store using similarity search with metadata filtering.
        Args:
            query:
            metadata_filter: Dictionary of metadata key-value pairs to filter by
                           e.g., {'source': 'paper.pdf', 'page': 1}
            n_results: Number of results to return
        Returns:
            Dict with 'documents', 'metadatas', 'distances' keys
        """
        # Perform similarity search with metadata filter
        results = self.vectorstore.similarity_search_with_score(
            query=query,
            k=n_results,
            filter=metadata_filter
        )

        return _format_search_results(results)

    def _search_by_metadata(
            self,
            metadata_filter: Dict[str, Any],
            n_results: int = 5
    ) -> List[Document]:
        """
        Search documents by metadata only (no semantic search).
        Args:
            metadata_filter: Dictionary of metadata key-value pairs to filter by
                           e.g., {'source': 'paper.pdf', 'author': 'Smith'}
            n_results: Maximum number of results to return
        Returns:
            List of Document objects matching the metadata filter
        """
        collection = self._get_collection()

        # Query with metadata filter only
        results = collection.get(
            where=metadata_filter,
            limit=n_results
        )

        return _convert_results_to_documents(results)

    def add_documents(self, documents: list[Document]) -> List[str]:
        """
        Add documents to vector store using LangChain Document format.
        
        Args:
           documents: List of LangChain Document objects
            
        Returns:
            List of document IDs
        """
        current_timestamp = time.time()
        for doc in documents:
            doc.metadata['added_at'] = current_timestamp
        return self.vectorstore.add_documents(documents)

    def search(self, query: str = '', metadata: dict = None, n_results: int = 4) -> list[Document]:
        """ Unified function for searching the vector store."""
        if query:
            if metadata:
                return self._query_with_metadata(query, metadata, n_results)
            else:
                return self._query(query, n_results)
        elif metadata:
            return self._search_by_metadata(metadata, n_results)
        return []

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the collection.

        Returns:
            Dictionary containing:
                - total_elements: Total number of documents in the collection
                - items: Dictionary mapping item_id to their document count and titles
        """
        collection = self._get_collection()

        # Get all documents from the collection
        results = collection.get()

        total_elements = len(results['ids'])

        # Build item_id statistics
        items = {}
        if results['ids']:
            for i in range(len(results['ids'])):
                metadata = results['metadatas'][i]
                item_id = metadata.get('item_id', 'unknown')
                title = metadata.get('title', 'No title')
                storage_key = metadata.get('storage_key', 'unknown')
                citation_key = metadata.get('citation_key', 'unknown')

                if item_id not in items:
                    items[item_id] = {
                        'count': 0,
                        'title': title,
                        'storage_key': storage_key,
                        'citation_key': citation_key,
                    }

                items[item_id]['count'] += 1

        return {
            'total_elements': total_elements,
            'items': items
        }

    def delete_by_item_id(self, item_id: str) -> int:
        """
        Delete all documents associated with a specific item_id from metadata.
        Args:
            item_id: The item_id value to search for in metadata
        Returns:
            Number of documents deleted
        """
        collection = self._get_collection()
        uids = self.uids_from_item_id(item_id)

        # Check if any documents were found
        if len(uids) == 0:
            print(f"No documents found with item_id: {item_id}")
            return 0

        # Delete the documents by their IDs
        collection.delete(ids=uids)
        num_deleted = len(uids)
        print(f"Deleted {num_deleted} document(s) with item_id: {item_id}")
        return num_deleted

    def uids_from_item_id(self, item_id: str) -> List[str]:
        collection = self._get_collection()

        # Find all documents with matching item_id
        results = collection.get(
            where={'item_id': item_id}
        )

        if results:
            return results['ids']
        else:
            return []

    def clear(self):
        """
        Reset the vector store by deleting the collection and recreating it.
        Warning: This will delete all documents in the collection!
        """
        try:
            # Delete the collection
            self.vectorstore.delete_collection()
            # Reinitialize the vector store with the same settings
            self.vectorstore = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=self.index_path
            )
            print(f"Collection '{self.collection_name}' has been reset.")
        except Exception as e:
            print(f"Error resetting collection: {e}")
            raise
