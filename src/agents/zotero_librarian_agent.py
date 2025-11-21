"""
Zotero Librarian Agent using LangChain v1.0

An agentic assistant that helps users interact with their Zotero library.
Built following LangChain v1.0 best practices with proper tool definitions,
memory, structured outputs, and runtime context.
"""

import os
import sys
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import ToolRuntime, tool
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver

# Import our Zotero utility functions
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.Prompts.zotero_librarian_prompts import SYSTEM_PROMPT
from src.zotero.zotero_client import (
    get_item_count,
    get_items_by_collection_id,
    get_item_by_id,
    list_all_collections,
)

# Load environment variables
load_dotenv()

# Configure LangSmith tracing (optional but recommended for debugging)
os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING_V2", "false")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "ZoteroLibrarian")


# ===== Agent Class ====
@dataclass
class AgentConfig:
    model_name: str = "gpt-oss:latest"
    temperature: float = 0.0
    base_url: Optional[str] = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    use_structured_output: bool = True


# ===== Runtime Context Schema =====
@dataclass
class ZoteroContext:
    """
    Runtime context for Zotero operations.

    This context is injected into tools at runtime and provides
    user-specific configuration and preferences.
    """

    user_id: str
    # Add other user-specific settings as needed
    max_results: int = 10
    preferred_format: str = "markdown"


# ===== Structured Response Format =====


@dataclass
class ZoteroResponse:
    """
    Structured response schema for the Zotero Librarian agent.

    This ensures consistent, parseable responses from the agent.
    """

    # The main response to the user's query
    answer: str
    # List of referenced items (titles, IDs, or citations)
    referenced_items: list[str] | None = None
    # Suggested follow-up actions
    suggestions: list[str] | None = None
    # Any warnings or limitations
    warnings: str | None = None


# ===== Tool Definitions =====
# Tools can access runtime context via ToolRuntime parameter


@tool
def count_items() -> int:
    """
    Get the total number of items in the user's Zotero library.

    Returns:
        The count of all items in the library as an integer.

    Use this when the user asks about library size or total item count.
    """
    return get_item_count()


@tool
def list_collections() -> dict[str, str]:
    """
    List all collections in the Zotero library with their names and IDs.

    Returns:
        Dictionary mapping collection names (str) to collection IDs (str).

    Use this when the user wants to see available collections or browse their library organization.
    """
    return list_all_collections()


@tool
def get_items_in_collection(
        collection_id: str, runtime: ToolRuntime[ZoteroContext]
) -> dict[str, str]:
    """
    Get items from a specific Zotero collection, respecting user preferences.

    Args:
        collection_id: The unique ID of the collection to retrieve items from.
        runtime: Injected runtime context with user preferences.

    Returns:
        Dictionary mapping item titles (str) to item IDs (str), limited by max_results.

    Use this after getting collection IDs from list_collections() to see what items are in a collection.
    """
    items = get_items_by_collection_id(collection_id)
    max_results = runtime.context.max_results

    if len(items) > max_results:
        items = items[:max_results]

    item_dict = {item.get("title", ""): item.get("item_id", "") for _, item in items}
    return item_dict


@tool
def get_metadata(item_id: str) -> dict:
    """
    Get complete metadata for a specific item in the Zotero library.

    Args:
        item_id: The unique ID of the item to retrieve metadata for.

    Returns:
        Dictionary containing full metadata including title, authors, date, type,
        citation key, abstract, and other bibliographic information.

    Use this when the user needs detailed information about a specific paper or item.
    """
    item = get_item_by_id(item_id)
    return item[1]


@tool
def search_collections_by_topic(
        topic: str,
) -> dict[str, str]:
    """
    Search for collections related to a specific topic or keyword.

    Args:
        topic: The topic or keyword to search for in collection names.

    Returns:
        Dictionary mapping matching collection names to their IDs.

    Use this when the user asks about collections related to a specific research topic.
    """
    all_collections = list_all_collections()
    # Case-insensitive search
    matching = {
        name: cid
        for name, cid in all_collections.items()
        if topic.lower() in name.lower()
    }
    return matching


# ===== Agent Implementation =====
"""
A LangChain v1.0 agent with memory, structured outputs, and runtime context.

This agent follows the official LangChain quickstart pattern with:
- Conversational memory via checkpointer
- Structured response format for consistency
- Runtime context for user preferences
- Full tool-calling capabilities

Attributes:
    model: The language model instance
    tools: List of available Zotero interaction tools
    agent: The compiled agent graph with memory
    checkpointer: Memory storage for conversations
"""

AGENT_CONFIG = AgentConfig()
MODEL = ChatOllama(
    model=AGENT_CONFIG.model_name,
    temperature=AGENT_CONFIG.temperature,
    base_url=AGENT_CONFIG.base_url,
)

# Define available tools (including new search tool)
TOOLS = [
    count_items,
    list_collections,
    search_collections_by_topic,
    get_items_in_collection,
    get_metadata,
]

# Set up memory (in-memory for development, use persistent in production)
CHECKPOINTER = InMemorySaver()

# Create agent with all components
agent = create_agent(
    model=MODEL,
    system_prompt=SYSTEM_PROMPT,
    tools=TOOLS,
    context_schema=ZoteroContext,
    response_format=ZoteroResponse if AGENT_CONFIG.use_structured_output else None,
    checkpointer=CHECKPOINTER,
)
