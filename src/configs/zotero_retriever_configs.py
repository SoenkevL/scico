import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

from src.storages.VectorStorage import ChromaStorage

load_dotenv()


# ===== Vector Storage Configuration =====
@dataclass
class VectorStorageConfig:
    vector_storage_path: Path = Path(os.getenv("VECTOR_STORAGE_PATH", ""))
    collection_name: str = os.getenv("COLLECTION_NAME", "Zotero")
    embedding_model: str = os.getenv("EMBEDDING_MODEL_NAME", "")
    api: str = os.getenv("EMBEDDING_MODEL_API", "")


# ===== Runtime Context Schema =====
# Initialize vector storage at module level for LangGraph CLI
VECTOR_STORAGE_CONFIG = VectorStorageConfig()
VECTOR_STORAGE = ChromaStorage(
    index_path=str(VECTOR_STORAGE_CONFIG.vector_storage_path),
    collection_name=VECTOR_STORAGE_CONFIG.collection_name,
    embedding_model=VECTOR_STORAGE_CONFIG.embedding_model,
    api=VECTOR_STORAGE_CONFIG.api,
)

class RetrieverContext(BaseModel):
    """Runtime context for the retriever agent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    vector_storage: ChromaStorage = VECTOR_STORAGE
    thread_id: Optional[str] = None
    user_id: str = "default_user"
    k_documents: int = 4
    relevance_threshold: float = 1.5
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
