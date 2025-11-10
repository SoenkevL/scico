import os
from dataclasses import dataclass, field
from typing import List, Optional, Any

from dotenv import load_dotenv
from openai import BaseModel

load_dotenv()


# ===== Vector Storage Configuration =====
@dataclass
class VectorStorageConfig:
    vector_storage_path = os.getenv('VECTOR_STORAGE_PATH')
    collection_name = 'Zotero'
    embedding_model = 'nomic-embed-text'


# ===== Runtime Context Schema =====
class RetrieverContext(BaseModel):
    """Runtime context for the retriever agent."""
    user_id: str = "default_user"
    vector_storage: Optional[Any] = None  # Will be set at module level
    k_documents: int = 4
    relevance_threshold: float = 1.5
    preferred_format: str = "markdown"

    # Accept additional config parameters that LangGraph may pass
    thread_id: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
        # Allow extra fields that LangGraph might inject
        extra = "allow"

    def model_post_init(self, __context):
        """Post-initialization to set vector_storage from module if not provided."""
        if self.vector_storage is None:
            # Import here to avoid circular imports
            from src.zotero_retriever_agent import _vector_storage
            self.vector_storage = _vector_storage


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
