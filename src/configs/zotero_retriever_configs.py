import os
from dataclasses import dataclass, field
from typing import List, Optional

from dotenv import load_dotenv

from src.VectorStorage import ChromaStorage

load_dotenv()


# ===== Vector Storage Configuration =====
@dataclass
class VectorStorageConfig:
    vector_storage_path = os.getenv('VECTOR_STORAGE_PATH')
    collection_name = 'Zotero'
    embedding_model = 'nomic-embed-text'


# ===== Runtime Context Schema =====
@dataclass
class RetrieverContext:
    """
    Runtime context for retrieval operations.

    This context is injected into tools at runtime and provides
    user-specific configuration and preferences.
    """
    user_id: str
    vector_storage: ChromaStorage
    # Number of documents to retrieve per query
    k_documents: int = 10
    # Minimum relevance threshold (distance metric)
    relevance_threshold: float = 1
    preferred_format: str = "markdown"


# ===== Structured Response Format =====

@dataclass
class RetrievalResponse:
    """
    Structured response schema for the Zotero Retriever agent.

    This ensures that every response includes both an answer AND the sources,
    making it perfect for retrieval-augmented generation.
    """
    # The synthesized answer to the user's query
    answer: str
    # List of source documents that the answer is based on
    sources: List[dict] = field(default_factory=list)
    # Confidence level or relevance score
    confidence: str = "medium"  # low, medium, high
    # Any limitations or caveats about the answer
    limitations: Optional[str] = None
