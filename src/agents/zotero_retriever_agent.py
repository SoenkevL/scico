"""
Zotero Retriever Agent using LangChain v1.0

An agentic assistant that performs retrieval-augmented generation (RAG) on Zotero documents.
Built following LangChain v1.0 best practices with proper tool definitions,
memory, structured outputs with sources, and runtime context.
"""

# At the very top of your main script (e.g., src/your_script.py)
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import our VectorStorage
from src.configs.model_config import AgentModelConfig
from src.configs.zotero_retriever_configs import RetrieverContext
from src.Prompts.zotero_retriever_prompts import SYSTEM_PROMPT
from src.Tools.general_tools import final_answer, think
from src.Tools.zotero_retriever_tools import (
    list_indexed_items_tool,
    multi_query_search_tool,
    search_by_item_tool,
    semantic_search_tool,
)

logger = logging.getLogger(__name__)
load_dotenv()

# Configure LangSmith tracing (optional but recommended for debugging)
os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING_V2", "false")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "ZoteroRetriever")


def _choose_agent_model():
    if AGENT_MODEL_CONFIG.api == "ollama":
        return ChatOllama(
            model=AGENT_MODEL_CONFIG.name,
            temperature=AGENT_MODEL_CONFIG.temperature,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
    if AGENT_MODEL_CONFIG.api == "openai":
        return ChatOpenAI(
            model=AGENT_MODEL_CONFIG.name,
            temperature=AGENT_MODEL_CONFIG.temperature,
        )
    else:
        raise ValueError(f"Unsupported provider: {AGENT_MODEL_CONFIG.api}")


AGENT_MODEL_CONFIG = AgentModelConfig()
MODEL = _choose_agent_model()

# Define retrieval tools
TOOLS = [
    semantic_search_tool,
    search_by_item_tool,
    list_indexed_items_tool,
    multi_query_search_tool,
    final_answer,
    think,
]

# ignored by ollama
MODEL.bind_tools(TOOLS, tool_choice="any")

# Create agent
agent = create_agent(
    model=MODEL,
    system_prompt=SYSTEM_PROMPT,
    tools=TOOLS,
    middleware=[
        ModelCallLimitMiddleware(run_limit=10, thread_limit=15, exit_behavior="end")
    ],
    context_schema=RetrieverContext,
)
