"""
Zotero Librarian Agent using LangChain v1.0
An agentic assistant that helps users interact with their Zotero library
"""

import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain.agents import create_agent
from langchain.tools import tool

# Import our Zotero tools
from Zotero import (
    get_item_count,
    list_all_collections,
    get_collection_items,
    get_item_metadata,
    get_fulltext_item,
    local_pdf_path_from_item_id
)

load_dotenv()
# Tracing
os.environ["LANGCHAIN_PROJECT"] = "ZoteroLibrarian"

# ===== STEP 1: Convert Zotero functions to LangChain tools =====
@tool
def count_items() -> int:
    """Get the total number of items in the user's Zotero library"""
    return get_item_count()


@tool
def list_collections() -> dict:
    """List all collections in the Zotero library with their names and IDs"""
    return list_all_collections()


@tool
def get_items_in_collection(collection_id: str) -> dict:
    """
    Get all items from a specific Zotero collection.
    
    Args:
        collection_id: The ID of the collection to retrieve items from
    
    Returns:
        Dictionary with item names as keys and item IDs as values
    """
    return get_collection_items(collection_id)


@tool
def get_metadata(item_id: str) -> dict:
    """
    Get metadata for a specific item in the Zotero library.
    
    Args:
        item_id: The ID of the item to get metadata for
    
    Returns:
        Dictionary containing full metadata of the item
    """
    return get_item_metadata(item_id)


@tool
def get_item_fulltext(item_id: str) -> str:
    """
    Get the full text content of an item if available.
    
    Args:
        item_id: The ID of the item to get full text from
    
    Returns:
        String containing the full text content
    """
    return get_fulltext_item(item_id)


@tool
def get_pdf_path(item_id: str) -> str:
    """
    Get the local file path to the PDF attachment of an item.
    
    Args:
        item_id: The ID of the item to get PDF path for
    
    Returns:
        String containing the local file path to the PDF
    """
    return local_pdf_path_from_item_id(item_id)


# ===== STEP 2: Create the Agent with LangChain v1.0 =====
class ZoteroLibrarian:
    """
    A librarian agent that helps users interact with their Zotero library.
    Uses LangChain v1.0 create_agent for construction.
    """

    def __init__(self, model_name: str = "gpt-oss:latest", temperature: float = 0.0):
        """
        Initialize the Zotero Librarian agent.
        
        Args:
            model_name: Name of the Ollama model to use
            temperature: Temperature for LLM generation
        """
        # Initialize LLM
        self.llm = ChatOllama(
            model=model_name,
            temperature=temperature,
            base_url=os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        )

        # Define available tools
        self.tools = [
            count_items,
            list_collections,
            get_items_in_collection,
            get_metadata,
            get_item_fulltext,
            get_pdf_path
        ]

        # Create system prompt (renamed from 'prompt' to 'system_prompt' in v1.0)
        system_prompt = """You are a helpful Zotero librarian assistant. 
Your role is to help users navigate and understand their Zotero research library.

You have access to tools that allow you to:
- Count items in the library
- List collections
- Get items from specific collections
- Retrieve metadata for items
- Access full text of documents
- Find local PDF paths

When helping users:
1. First understand what they need
2. Use the appropriate tools to gather information
3. Present information clearly and concisely
4. Suggest next steps if relevant

Always be precise and helpful. If you cannot find information, say so clearly.
"""

        # Create agent using v1.0 API (replaces create_tool_calling_agent + AgentExecutor)
        self.agent = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=system_prompt
        )

    def invoke(self, query: str) -> dict:
        """
        Process a user query using the agent.
        
        Args:
            query: User's question or request
        
        Returns:
            Agent's response dictionary
        """
        result = self.agent.invoke(
            {
                "messages": [{"role":"user", "content":query}]
            },
        )
        return result

    def stream(self, query: str):
        """
        Stream the agent's response.
        
        Args:
            query: User's question or request
        
        Yields:
            Response chunks as they are generated
        """
        for chunk in self.agent.stream({
            "messages": [("user", query)]
        }):
            yield chunk


# ===== STEP 3: Create a simple chain-based workflow (deterministic alternative) =====
class ZoteroWorkflow:
    """
    A simpler, more deterministic workflow for common Zotero tasks.
    Uses LCEL chains without agentic behavior for predictable operations.
    """

    def __init__(self, model_name: str = "gpt-oss:latest", temperature: float = 0.0):
        self.llm = ChatOllama(
            model=model_name,
            temperature=temperature,
            base_url=os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        )
        self.output_parser = StrOutputParser()

    def summarize_collection(self, collection_id: str) -> str:
        """
        Generate a summary of a collection using a deterministic workflow.
        
        Args:
            collection_id: ID of the collection to summarize
        
        Returns:
            Summary of the collection
        """
        # Step 1: Get collection items
        items = get_collection_items(collection_id)

        # Step 2: Get metadata for each item
        items_info = []
        for title, item_id in list(items.items())[:10]:  # Limit to first 10
            metadata = get_item_metadata(item_id)
            items_info.append({
                'title': title,
                'type': metadata.get('data', {}).get('itemType', 'unknown'),
                'date': metadata.get('data', {}).get('date', 'unknown'),
                'citation_key': metadata.get('data', {}).get('citationKey', 'unknown'),
            })

        # Step 3: Create summarization chain
        prompt = ChatPromptTemplate.from_template(
            """Based on these items from a Zotero collection, provide a brief summary:

Items:
{items}

Provide a 2-3 sentence summary describing the main topics and timeframe of this collection."""
        )

        chain = (
                RunnableLambda(lambda x: {"items": str(x)})
                | prompt
                | self.llm
                | self.output_parser
        )

        return chain.invoke(items_info)

    def find_and_describe_item(self, search_term: str) -> str:
        """
        Search for an item and provide its description.
        
        Args:
            search_term: Term to search for in collection names
        
        Returns:
            Description of found item
        """
        # Get all collections
        collections = list_all_collections()

        # Simple search
        matching_collections = {
            name: cid for name, cid in collections.items()
            if search_term.lower() in name.lower()
        }

        if not matching_collections:
            return f"No collections found matching '{search_term}'"

        # Get items from first matching collection
        collection_name = list(matching_collections.keys())[0]
        collection_id = matching_collections[collection_name]

        return f"Found collection: {collection_name}\n" + \
            self.summarize_collection(collection_id)


# ===== STEP 4: Usage example =====
def main():
    """Demo the Zotero Librarian agent"""

    print("=" * 60)
    print("Zotero Librarian Agent Demo (LangChain v1.0)")
    print("=" * 60)

    # Initialize agent
    librarian = ZoteroLibrarian(model_name="gpt-oss:latest")

    # Example queries
    queries = [
        "How many items are in my library?",
        "What collections do I have?",
        "Which of my collections deal with the topic of eeg?",
        "What items are part of these collections?",
        "Retrieve 5 eeg related papers which also deal with meditation and summarize their abstracts"
    ]

    for query in queries:
        print(f"\n📚 Query: {query}")
        print("-" * 60)
        result = librarian.invoke(query)
        # In v1.0, result is a dict with 'messages' key
        if 'messages' in result:
            last_message = result['messages'][-1]
            print(f"Response: {last_message.content}\n")
        else:
            print(f"Response: {result}\n")

    # Demo workflow
    print("\n" + "=" * 60)
    print("Deterministic Workflow Demo")
    print("=" * 60)

    workflow = ZoteroWorkflow()
    collections = list_all_collections()

    if collections:
        first_collection_id = list(collections.values())[0]
        summary = workflow.summarize_collection(first_collection_id)
        print(f"\nCollection Summary:\n{summary}")


if __name__ == "__main__":
    main()
