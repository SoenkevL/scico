import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class AgentModelConfig:
    api: str = os.getenv("AGENT_MODEL_API", "openai")
    name: str = os.getenv("AGENT_MODEL_NAME", "gpt-4-mini")
    temperature: float = float(os.getenv("AGENT_MODEL_TEMPERATURE", 0))


@dataclass
class EmbeddingModelConfig:
    api: str = os.getenv("EMBEDDING_MODEL_API", "openai")
    name: str = os.getenv("AGENT_MODEL_NAME", "gpt-4-mini")
