"""
Zotero Librarian Agent using LangChain v1.0

An agentic assistant that helps users interact with their Zotero library.
Built following LangChain v1.0 best practices with proper tool definitions,
memory, structured outputs, and runtime context.
"""

import os
from typing import Optional

from dotenv import load_dotenv
from dataclasses import dataclass
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
from langgraph.checkpoint.memory import InMemorySaver
import sys

# Import our Zotero utility functions
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Zotero import (
    get_item_count,
    list_all_collections,
    get_collection_items,
    get_item_metadata,
    get_fulltext_item,
)

# Load environment variables
load_dotenv()

# Configure LangSmith tracing (optional but recommended for debugging)
os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING_V2", "false")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "ZoteroLibrarian")


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
    collection_id: str,
    runtime: ToolRuntime[ZoteroContext]
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
    items = get_collection_items(collection_id)
    max_results = runtime.context.max_results
    
    # Limit results based on user preference
    if len(items) > max_results:
        items = dict(list(items.items())[:max_results])
    
    return items


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
    return get_item_metadata(item_id)


@tool
def get_item_fulltext(item_id: str) -> str:
    """
    Get the full text content of an item if available.
    
    Args:
        item_id: The unique ID of the item to get full text from.
    
    Returns:
        String containing the full text content, or empty string if not available.
    
    Use this when the user wants to read or search within the actual document content.
    """
    return get_fulltext_item(item_id)


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
        name: cid for name, cid in all_collections.items()
        if topic.lower() in name.lower()
    }
    
    return matching


# ===== System Prompt =====

SYSTEM_PROMPT = """You are an expert Zotero librarian assistant specializing in research library management.

Your role is to help researchers efficiently navigate, organize, and understand their Zotero library.

**Available Tools:**
- count_items: Get total library size
- list_collections: Browse all collection names and IDs
- search_collections_by_topic: Find collections related to specific topics
- get_items_in_collection: List items in a specific collection (respects user's max_results preference)
- get_metadata: Get detailed bibliographic information for an item
- get_item_fulltext: Access full document content
- get_pdf_path: Get local file paths to PDFs

**Best Practices:**
1. Always understand the user's intent before calling tools
2. Use search_collections_by_topic when users mention research topics
3. When listing items, respect the user's max_results preference (from context)
4. Present information clearly using markdown formatting
5. Cite item titles, authors, and dates when relevant
6. Suggest logical next steps based on what the user is researching
7. If you cannot find information, explain why and suggest alternatives

**Response Guidelines:**
- Be precise and factual
- Use markdown for readability (lists, bold, headers)
- Always include relevant item titles and authors in your answer
- Provide actionable suggestions for follow-up queries
- Warn users if results are truncated or incomplete

**Important:** 
- You have access to the user's preferences through runtime context
- Some tools automatically limit results based on user preferences
- Always acknowledge when you're showing partial results"""


# ===== Agent Implementation =====

class ZoteroLibrarian:
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
    
    def __init__(
        self,
        model_name: str = "gpt-oss:latest",
        temperature: float = 0.0,
        base_url: Optional[str] = None,
        use_structured_output: bool = True
    ):
        """
        Initialize the Zotero Librarian agent with memory and structured outputs.
        
        Args:
            model_name: Name of the Ollama model to use (default: "llama3.2")
            temperature: Temperature for LLM generation, 0.0 for deterministic (default: 0.0)
            base_url: Ollama API base URL (default: from env or http://localhost:11434)
            use_structured_output: Whether to use structured response format (default: True)
        """
        # Initialize LLM using init_chat_model for better configuration
        self.model = ChatOllama(
            model=model_name,
            temperature=temperature,
            base_url=base_url or os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        )
        
        # Define available tools (including new search tool)
        self.tools = [
            count_items,
            list_collections,
            search_collections_by_topic,
            get_items_in_collection,
            get_metadata,
            get_item_fulltext,
        ]
        
        # Set up memory (in-memory for development, use persistent in production)
        self.checkpointer = InMemorySaver()
        
        # Create agent with all components
        self.agent = create_agent(
            model=self.model,
            system_prompt=SYSTEM_PROMPT,
            tools=self.tools,
            context_schema=ZoteroContext,
            response_format=ZoteroResponse if use_structured_output else None,
            checkpointer=self.checkpointer
        )
        
        self.use_structured_output = use_structured_output
    
    def invoke(
        self,
        query: str,
        thread_id: str = "default",
        user_id: str = "default_user",
        max_results: int = 10
    ) -> dict:
        """
        Process a user query with conversational memory.
        
        Args:
            query: User's question or request about their Zotero library
            thread_id: Unique identifier for this conversation (default: "default")
            user_id: User identifier for context (default: "default_user")
            max_results: Maximum results to return per query (default: 10)
        
        Returns:
            Agent's response dictionary with 'messages' and optionally 'structured_response'.
        """
        # Configuration for conversation threading
        config = {"configurable": {"thread_id": thread_id}}
        
        # Runtime context with user preferences
        context = ZoteroContext(
            user_id=user_id,
            max_results=max_results,
            preferred_format="markdown"
        )
        
        # Invoke agent with memory and context
        result = self.agent.invoke(
            {"messages": [{"role": "user", "content": query}]},
            config=config,
            context=context
        )
        
        return result
    
    def stream(
        self,
        query: str,
        thread_id: str = "default",
        user_id: str = "default_user",
        max_results: int = 10
    ):
        """
        Stream the agent's response with memory and context.
        
        Args:
            query: User's question or request
            thread_id: Unique identifier for this conversation
            user_id: User identifier for context
            max_results: Maximum results to return per query
        
        Yields:
            Response chunks as they are generated
        """
        config = {"configurable": {"thread_id": thread_id}}
        context = ZoteroContext(
            user_id=user_id,
            max_results=max_results,
            preferred_format="markdown"
        )
        
        for chunk in self.agent.stream(
            {"messages": [{"role": "user", "content": query}]},
            config=config,
            context=context
        ):
            yield chunk
    
    def get_response(self, result: dict) -> str | ZoteroResponse:
        """
        Extract the response from an agent invocation result.
        
        Args:
            result: The dictionary returned by invoke()
        
        Returns:
            Structured response if enabled, otherwise text content
        """
        if self.use_structured_output and 'structured_response' in result:
            return result['structured_response']
        elif 'messages' in result and result['messages']:
            return result['messages'][-1].content
        return str(result)
    
    def continue_conversation(
        self,
        query: str,
        thread_id: str,
        user_id: str = "default_user",
        max_results: int = 10
    ) -> dict:
        """
        Continue an existing conversation using the same thread_id.
        
        This is a convenience method that makes it clear you're continuing
        a conversation rather than starting a new one.
        
        Args:
            query: User's follow-up question
            thread_id: The thread_id from the original conversation
            user_id: User identifier
            max_results: Maximum results to return
        
        Returns:
            Agent's response dictionary
        """
        return self.invoke(query, thread_id, user_id, max_results)


# ===== Deterministic Workflow Alternative =====

class ZoteroWorkflow:
    """
    Deterministic LCEL-based workflow for common Zotero tasks.
    
    This class provides predictable, workflow-based operations without agentic
    behavior. Use this for simple, reproducible tasks where determinism is preferred.
    """
    
    def __init__(
        self,
        model_name: str = "llama3.2",
        temperature: float = 0.0,
        base_url: Optional[str] = None
    ):
        """Initialize the workflow."""
        self.llm = ChatOllama(
            model=model_name,
            temperature=temperature,
            base_url=base_url or os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        )
        self.output_parser = StrOutputParser()
    
    def summarize_collection(self, collection_id: str, max_items: int = 10) -> str:
        """
        Generate a summary of a collection using a deterministic LCEL workflow.
        
        Args:
            collection_id: ID of the collection to summarize
            max_items: Maximum number of items to include (default: 10)
        
        Returns:
            A concise summary of the collection's research focus
        """
        # Get collection items
        items = get_collection_items(collection_id)
        
        # Get metadata for items
        items_info = []
        for title, item_id in list(items.items())[:max_items]:
            metadata = get_item_metadata(item_id)
            data = metadata.get('data', {})
            items_info.append({
                'title': title,
                'type': data.get('itemType', 'unknown'),
                'date': data.get('date', 'unknown'),
                'authors': ', '.join([
                    f"{c.get('firstName', '')} {c.get('lastName', '')}".strip()
                    for c in data.get('creators', [])
                ])
            })
        
        # Create LCEL chain
        prompt = ChatPromptTemplate.from_template(
            """Based on these items from a Zotero collection, provide a brief summary:

Items:
{items}

Provide a 2-3 sentence summary describing the main research topics, methodologies, and timeframe of this collection."""
        )
        
        chain = (
            RunnableLambda(lambda x: {"items": self._format_items(x)})
            | prompt
            | self.llm
            | self.output_parser
        )
        
        return chain.invoke(items_info)
    
    @staticmethod
    def _format_items(items: list[dict]) -> str:
        """Format items for readability."""
        formatted = []
        for i, item in enumerate(items, 1):
            formatted.append(
                f"{i}. {item['title']} ({item['date']})\n"
                f"   Authors: {item['authors']}\n"
                f"   Type: {item['type']}"
            )
        return "\n\n".join(formatted)


# ===== Usage Example =====

def main():
    """Demo the Zotero Librarian agent with memory and structured outputs."""
    
    print("=" * 70)
    print("🤖 Zotero Librarian Agent Demo (with Memory & Structured Output)")
    print("=" * 70)
    
    # Initialize agent with structured output
    librarian = ZoteroLibrarian(
        model_name="gpt-oss:latest",
        use_structured_output=True
    )
    
    # Start a conversation with a unique thread_id
    thread_id = "research-session-001"
    user_id = "researcher-alice"
    
    print(f"\n📝 Starting conversation: {thread_id}")
    print(f"👤 User: {user_id}")
    print("-" * 70)
    
    # First query
    query1 = "How many items are in my library?"
    print(f"\n💬 Query 1: {query1}")
    result1 = librarian.invoke(query1, thread_id=thread_id, user_id=user_id)
    response1 = librarian.get_response(result1)
    
    if isinstance(response1, ZoteroResponse):
        print(f"📊 Answer: {response1.answer}")
        if response1.suggestions:
            print(f"💡 Suggestions: {response1.suggestions}")
    else:
        print(f"📊 Response: {response1}")
    
    # Continue conversation (agent remembers context)
    query2 = "What collections do I have related to EEG?"
    print(f"\n💬 Query 2: {query2}")
    result2 = librarian.continue_conversation(
        query2,
        thread_id=thread_id,
        user_id=user_id,
        max_results=5  # Limit to 5 results
    )
    response2 = librarian.get_response(result2)
    
    if isinstance(response2, ZoteroResponse):
        print(f"📊 Answer: {response2.answer}")
        if response2.referenced_items:
            print(f"📚 Referenced: {response2.referenced_items}")
        if response2.suggestions:
            print(f"💡 Suggestions: {response2.suggestions}")
    else:
        print(f"📊 Response: {response2}")
    
    # Follow-up that uses memory
    query3 = "Show me some items from the first collection you mentioned"
    print(f"\n💬 Query 3 (using memory): {query3}")
    result3 = librarian.continue_conversation(
        query3,
        thread_id=thread_id,
        user_id=user_id
    )
    response3 = librarian.get_response(result3)
    
    if isinstance(response3, ZoteroResponse):
        print(f"📊 Answer: {response3.answer}")
        if response3.referenced_items:
            print(f"📚 Items: {response3.referenced_items}")
    else:
        print(f"📊 Response: {response3}")
    
    print("\n" + "=" * 70)
    print("✅ Conversation complete!")
    print(f"   The agent remembered context across {3} queries")
    print("=" * 70)


if __name__ == "__main__":
    main()
