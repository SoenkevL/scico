from dataclasses import dataclass, field
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

from src.configs.Chroma_storage_config import ChromaStorageConfig
from src.storages.ChromaStorage import ChromaStorage

load_dotenv()





# ===== Runtime Context Schema =====
# Initialize vector storage at module level for LangGraph CLI
class RetrieverContext(BaseModel):
    """Runtime context for the retriever agent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    vector_storage_config: ChromaStorageConfig = ChromaStorageConfig()
    vector_storage: ChromaStorage = ChromaStorage(vector_storage_config)
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
