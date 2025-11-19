from typing import TypedDict, List, Literal

from dotenv import load_dotenv
from langchain_core.documents import Document
# Assuming we are using OpenAI, though this can be swapped
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt

load_dotenv()

from src.Tools.zotero_retriever_tools import multi_query_search
from src.storages.ChromaStorage import ChromaStorage
from src.configs.Chroma_storage_config import VectorStorageConfig

VECTOR_STORAGE_CONFIG = VectorStorageConfig()
VECTOR_STORAGE = ChromaStorage(VECTOR_STORAGE_CONFIG)


# --- State Definition ---

class ZoteroState(TypedDict):
    """
    Represents the state of the research agent.
    """
    user_query: str
    search_queries: List[str]
    retrieved_docs: List[Document]
    information_string: str
    final_response: str

# Initialize LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0)


# --- Nodes ---
def check_for_user_query(state: ZoteroState) -> Command[Literal["generate_search_queries"]]:
    """
    Has the user provided a query? if not get one from him 
    """
    if not state.get("user_query"):
        user_input = interrupt({
            "msg": "Please provide a research query to search your Zotero library.",
        })

        # Update state with the provided query
        return Command(
            update={"user_query": user_input},
            goto="generate_search_queries"
        )

    # If query exists, continue to search query generation
    return Command(goto="generate_search_queries")


def generate_search_queries(state: ZoteroState) -> Command[Literal["retrieve_zotero_docs"]]:
    """
    Decomposes the user query into specific search terms for the vector DB.
    """
    original_query = state.get("user_query")

    # In a production app, use structured output (with_structured_output) for reliability
    prompt = (
        f"Generate 3 specific search queries to find information in a Zotero database "
        f"that answers this question: '{original_query}'. "
        f"Return them as a comma-separated list."
    )

    response = llm.invoke(prompt).content

    # Simple parsing logic for the demo
    queries = [q.strip() for q in response.split(",")]

    print(f"Generated queries: {queries}")

    return Command(
        update={"search_queries": queries},
        goto="retrieve_zotero_docs"
    )


def retrieve_zotero_docs(state: ZoteroState) -> Command[Literal["check_results"]]:
    """
    Executes the vector search using the generated queries.
    """
    queries = state.get("search_queries")

    # Call the existing function
    docs = multi_query_search(queries, VECTOR_STORAGE, k=5)

    print(f"Retrieved {len(docs)} documents.")

    return Command(
        update={"retrieved_docs": docs},
        goto="check_results"
    )


def check_results(state: ZoteroState) -> Command[Literal["synthesize_answer", "no_results"]]:
    """
    Routing node: Decides if we have enough info to answer.
    """
    if not state.get("retrieved_docs"):
        return Command(goto="no_results")

    return Command(goto="synthesize_answer")


def synthesize_answer(state: ZoteroState) -> Command[END]:
    """
    Synthesizes a final answer based on the retrieved documents.
    """
    docs = state.get("retrieved_docs")
    query = state.get("user_query")

    # Format context for the LLM
    context_str = "\n\n".join \
        ([f"Source: {d.metadata.get('source', 'Unknown')}\nContent: {d.page_content}" for d in docs])

    prompt = (
        f"Answer the user query based ONLY on the provided Zotero context.\n\n"
        f"User Query: {query}\n\n"
        f"Context:\n{context_str}"
    )

    response = llm.invoke(prompt).content

    return Command(
        update={"final_response": response},
        goto=END
    )


def no_results(state: ZoteroState) -> Command[Literal[END]]:
    """
    Handles cases where the vector search returned nothing.
    """
    msg = "I searched your Zotero library but couldn't find any relevant documents matching your query."

    return Command(
        update={"final_response": msg},
        goto=END
    )


# --- Graph Construction ---

workflow = StateGraph(ZoteroState)

# Add nodes
workflow.add_node("check_for_user_query", check_for_user_query)
workflow.add_node("generate_search_queries", generate_search_queries)
workflow.add_node("retrieve_zotero_docs", retrieve_zotero_docs)
workflow.add_node("check_results", check_results)
workflow.add_node("synthesize_answer", synthesize_answer)
workflow.add_node("no_results", no_results)

# Define edges
# Note: Conditional logic is handled inside the nodes via Command, 
# so we only need to define the entry point.
workflow.add_edge(START, 'check_for_user_query')

# Compile graph
app = workflow.compile()

# --- Example Usage ---
if __name__ == "__main__":
    initial_state = {"user_query": "What are the key factors in urban climate adaptation?"}

    # Run the graph
    result = app.invoke(initial_state)

    print("\n--- Final Result ---")
    print(result["final_response"])
