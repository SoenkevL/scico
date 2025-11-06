"""
Zotero Retriever Agent using LangChain v1.0

An agentic assistant that performs retrieval-augmented generation (RAG) on Zotero documents.
Built following LangChain v1.0 best practices with proper tool definitions,
memory, structured outputs with sources, and runtime context.
"""
# At the very top of your main script (e.g., src/your_script.py)
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

# Import our VectorStorage
from VectorStorage import ChromaStorage

from src.configs.zotero_retriever_configs import VectorStorageConfig, RetrieverContext
from src.Tools.zotero_retriever_tools import semantic_search, search_by_item, get_item_context, list_indexed_items, \
    multi_query_search
from src.Tools.general_tools import final_answer, think
from src.Prompts.zotero_retriever_prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure LangSmith tracing (optional but recommended for debugging)
os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING_V2", "false")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "ZoteroRetriever")


class ZoteroRetriever:
    """
    A LangChain v1.0 RAG agent with memory, structured outputs, and guaranteed source attribution.
    
    This agent specializes in retrieval-augmented generation over Zotero documents,
    ensuring every answer is backed by specific source citations.
    
    Attributes:
        model: The language model instance
        tools: List of available retrieval tools
        agent: The compiled agent graph with memory
        checkpointer: Memory storage for conversations
        vector_storage: ChromaStorage instance for document retrieval
    """

    def __init__(
            self,
            vector_storage_config: VectorStorageConfig,
            model_name: str = "gpt-oss:latest",
            temperature: float = 0.0,
            base_url: Optional[str] = None
    ):
        """
        Initialize the Zotero Retriever agent with vector storage and memory.
        
        Args:
            model_name: Name of the Ollama model to use (default: "gpt-oss:latest")
            temperature: Temperature for LLM generation, 0.0 for deterministic (default: 0.0)
            base_url: Ollama API base URL (default: from env or http://localhost:11434)
        """
        # Store vector storage reference
        self.vector_storage = ChromaStorage(index_path=vector_storage_config.vector_storage_path,
                                            collection_name=vector_storage_config.collection_name,
                                            embedding_model=vector_storage_config.embedding_model)

        # Initialize LLM
        self.model = ChatOllama(
            model=model_name,
            temperature=temperature,
            base_url=base_url or os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        )

        # Define retrieval tools
        self.tools = [
            semantic_search,
            search_by_item,
            get_item_context,
            list_indexed_items,
            multi_query_search,
            final_answer,
            think
        ]

        self.model.bind_tools(self.tools, tool_choice='any')

        # Set up memory
        self.checkpointer = InMemorySaver()

        # Create agent with structured output (REQUIRED for source attribution)
        self.agent = create_agent(
            model=self.model,
            system_prompt=SYSTEM_PROMPT,
            tools=self.tools,
            context_schema=RetrieverContext,
            # response_format=RetrievalResponse,  # Always structured
            checkpointer=self.checkpointer
        )

    def invoke(
            self,
            query: str,
            thread_id: str = "default",
            user_id: str = "default_user",
            k_documents: int = 20,
            relevance_threshold: float = 1,
    ) -> dict:
        """
        Process a user query with retrieval-augmented generation.
        
        Args:
            query: User's question about the indexed documents
            thread_id: Unique identifier for this conversation (default: "default")
            user_id: User identifier for context (default: "default_user")
            k_documents: Number of documents to retrieve per search (default: 4)
            relevance_threshold: Maximum distance for considering a document relevant (default: 1.5)
        
        Returns:
            Agent's response dictionary with 'messages' and 'structured_response' (RetrievalResponse).
        """
        # Configuration for conversation threading
        config = {"configurable": {"thread_id": thread_id}}

        # Runtime context with vector storage and preferences
        context = RetrieverContext(
            user_id=user_id,
            vector_storage=self.vector_storage,
            k_documents=k_documents,
            relevance_threshold=relevance_threshold,
            preferred_format="markdown"
        )

        # Invoke agent with memory and context
        logger.info(f'invoking agent with query: {query}')
        result = self.agent.invoke(
            {"messages": [{"role": "user", "content": query}]},
            config=config,
            context=context,
            tool_choice="any"
        )

        return result

    def stream(
            self,
            query: str,
            thread_id: str = "default",
            user_id: str = "default_user",
            k_documents: int = 4,
            relevance_threshold: float = 1.5
    ):
        """
        Stream the agent's response with retrieval context.
        
        Args:
            query: User's question about the indexed documents
            thread_id: Unique identifier for this conversation
            user_id: User identifier for context
            k_documents: Number of documents to retrieve per search
            relevance_threshold: Maximum distance for relevance
        
        Yields:
            Response chunks as they are generated
        """
        config = {"configurable": {"thread_id": thread_id}}
        context = RetrieverContext(
            user_id=user_id,
            vector_storage=self.vector_storage,
            k_documents=k_documents,
            relevance_threshold=relevance_threshold,
            preferred_format="markdown"
        )

        for chunk in self.agent.stream(
                {"messages": [{"role": "user", "content": query}]},
                config=config,
                context=context
        ):
            yield chunk

    def get_response(self, result: dict) -> str:
        """
        Extract the answer text from an agent invocation result.

        Args:
            result: The dictionary returned by invoke()

        Returns:
            Plain text answer from the agent
        """
        # Get the last message from the agent
        messages = result.get('messages', [])
        if messages:
            last_message = messages[-1]
            answer_string = ""
            if hasattr(last_message, 'content'):
                return last_message.content
            elif hasattr(last_message, 'finalanswer'):
                return last_message.finalanswer
            else:
                return str(last_message)
        return ""


# ===== Usage Example =====

def main():
    """Demo the Zotero Retriever agent with RAG capabilities."""

    print("=" * 70)
    print("🔍 Zotero Retriever Agent Demo (RAG with Source Attribution)")
    print("=" * 70)

    # Initialize retriever agent
    retriever = ZoteroRetriever(
        vector_storage_config=VectorStorageConfig(),
        model_name="gpt-oss:latest",
        temperature=0.0
    )

    # bind final answer tool
    # Get collection stats
    stats = retriever.vector_storage.get_collection_stats()
    print(f"\n📊 Vector Storage Stats:")
    print(f"   Total chunks: {stats['total_elements']}")
    print(f"   Items indexed: {len(stats['items'])}")
    # Start a conversation
    thread_id = "rag-session-001"
    user_id = "researcher-bob"

    print(f"\n📝 Starting RAG session: {thread_id}")
    print(f"👤 User: {user_id}")
    print("-" * 70)

    # Example query
    query1 = "What is integrated information theory?"
    print(f"\n💬 Query: {query1}")

    result1 = retriever.invoke(
        query1,
        thread_id=thread_id,
        user_id=user_id,
        k_documents=10
    )

    response1: str = retriever.get_response(result1)

    print(f"\n📊 Answer:\n{response1}")

    # Follow-up query
    query2 = "Can you elaborate on differences to other theories of mind?"
    print(f"\n💬 Follow-up: {query2}")

    result2 = retriever.invoke(
        query2,
        thread_id=thread_id,
        user_id=user_id,
        k_documents=10
    )

    response2: str = retriever.get_response(result2)
    print(f"\n📊 Answer:\n{response2}")

    print("\n" + "=" * 70)
    print("✅ RAG session complete!")
    print("   Every answer included source attribution")
    print("=" * 70)


if __name__ == "__main__":
    main()
