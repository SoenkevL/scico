from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
from typing import List, Dict, Any
import os


class ChromaStorage:
    """LangChain-powered vector storage with Ollama embeddings."""
    
    def __init__(self, index_path: str, collection_name: str, embedding_model: str = "nomic-embed-text"):
        self.index_path = index_path
        self.collection_name = collection_name
        
        # Initialize LangChain Ollama embeddings
        self.embeddings = OllamaEmbeddings(
            model=embedding_model,
            base_url=os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        )
        
        # Initialize LangChain Chroma vector store
        self.vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=index_path
        )
    
    def add_documents(self, documents: list[Document]) -> List[str]:
        """
        Add documents to vector store using LangChain Document format.
        
        Args:
            chunks: List of dicts with 'page_content', 'metadata', 'split_uid'
            
        Returns:
            List of document IDs
        """
        return self.vectorstore.add_documents(documents)
    
    def query(self, query_texts: List[str], n_results: int = 5) -> Dict[str, Any]:
        """
        Query vector store using similarity search.
        
        Args:
            query_texts: List of query strings (typically one query)
            n_results: Number of results to return
            
        Returns:
            Dict with 'documents', 'metadatas', 'distances' keys for compatibility
        """
        # Use the first query text
        query = query_texts[0] if isinstance(query_texts, list) else query_texts
        
        # Perform similarity search with scores
        results = self.vectorstore.similarity_search_with_score(
            query=query,
            k=n_results
        )
        
        # Format results to match original API
        documents = [[doc.page_content for doc, _ in results]]
        metadatas = [[doc.metadata for doc, _ in results]]
        distances = [[score for _, score in results]]
        
        return {
            'documents': documents,
            'metadatas': metadatas,
            'distances': distances
        }
    
    def as_retriever(self, search_kwargs: Dict[str, Any] = None):
        """
        Return LangChain Retriever interface for RAG chains.
        
        This is the key method for integrating with LangChain RAG chains!
        """
        search_kwargs = search_kwargs or {'k': 5}
        return self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs=search_kwargs
        )
    
    @property
    def collection(self):
        """Backward compatibility: access underlying collection."""
        return self.vectorstore._collection
    
    @staticmethod
    def print_results(results: Dict[str, Any]):
        """Pretty print search results."""
        for i, (doc, meta, dist) in enumerate(zip(
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        ), 1):
            print(f'Result {i} (distance: {dist:.4f}):')
            print(f'Document: {doc[:200]}...')
            print(f'Metadata: {meta}')
            print('---')

    @staticmethod
    def add_additional_metadata_to_documents(metadata, splits=None):
        if not splits:
            raise Exception("No splits found. Please run chunk() first.")
        for split in splits:
            split.metadata = {**split.metadata, **metadata}
        return splits