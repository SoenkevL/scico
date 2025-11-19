import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# ===== Vector Storage Configuration =====
@dataclass
class VectorStorageConfig:
    vector_storage_path: Path = Path(os.getenv("VECTOR_STORAGE_PATH", ""))
    collection_name: str = os.getenv("COLLECTION_NAME", "Zotero")
    embedding_model: str = os.getenv("EMBEDDING_MODEL_NAME", "")
    api: str = os.getenv("EMBEDDING_MODEL_API", "")
