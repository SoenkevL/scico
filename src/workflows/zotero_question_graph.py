"""
Main graph definition for the Zotero Research Assistant.
Handles query generation, iterative retrieval, summarization, and structured answering.
"""
# === import global packages ===
from typing import TypedDict, List, Literal, Optional

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

# === import local file dependencies ===
from src.Tools.zotero_retriever_tools import multi_query_search, list_of_documents_to_string
from src.configs.Chroma_storage_config import VectorStorageConfig
from src.storages.ChromaStorage import ChromaStorage

# === initialize global objects ===
load_dotenv()

VECTOR_STORAGE_CONFIG = VectorStorageConfig()
VECTOR_STORAGE = ChromaStorage(VECTOR_STORAGE_CONFIG)

# Initialize LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0)


# === define classes ===

class Queries(BaseModel):
    """Structured input for the research agent."""
    queries: List[str] = Field(description="The generated research queries.")


class ResearchResponse(BaseModel):
    """Structured output for the final answer."""
    sources: List[str] = Field(description="List of valid sources/citations used with a description of their content.")
    summary_of_sources: str = Field(
        description="A summary of the sources used to answer the question containing in line citations.")
    answer: str = Field(description="The direct answer to the user's question.")


class SourceRelevance(BaseModel):
    """Relevant information extracted from a single source."""
    source_citation_key: str = Field(description="The citation key from the source metadata.")
    relevant_content: str = Field(
        description="The relevant information extracted from the source, excluding references.")


class KnowledgeSynthesis(BaseModel):
    """Synthesis of knowledge across multiple sources."""
    relevant_sources: List[SourceRelevance] = Field(description="List of relevant information per source.")
    synthesis_text: str = Field(
        description="A synthesis of knowledge across the references with citations using the citation key.")


class JudgeDecision(BaseModel):
    """Structured output for the judging step."""
    is_sufficient: bool = Field(
        description="True if the provided context is enough to answer the query or if no progress is made in answering the question")
    new_search_queries: Optional[List[str]] = Field(
        description="New, optimized search queries if info is insufficient.", default=None)
    reasoning: str = Field(description="Reasoning for the decision.")

class ZoteroState(TypedDict):
    """
    Represents the state of the research agent.
    """
    user_query: str
    queries: List[str]
    past_queries: List[str]
    judgments: List[str]  # Added to track history
    added_sources: int
    retrieved_docs: List[Document]
    known_document_ids: List[str]
    synthesized_string: str
    loop_count: int
    final_response: dict  # Stores the dict representation of ResearchResponse


# === Nodes ===


def check_for_user_query(state: ZoteroState) -> Command[Literal["generate_initial_search_queries"]]:
    """
    Has the user provided a query? if not get one from him.
    Initializes loop count and past queries.
    """
    updates = {}
    if "loop_count" not in state:
        updates["loop_count"] = 0
    
    if not state.get("user_query"):
        user_input = interrupt({
            "msg": "Please provide a research query to search your Zotero library.",
        })
        updates["user_query"] = user_input

    # If we have updates, apply them, otherwise just transition
    if updates:
        return Command(update=updates, goto="generate_initial_search_queries")

    return Command(goto="generate_initial_search_queries")


def generate_initial_search_queries(state: ZoteroState) -> Command[Literal["retrieve_zotero_docs"]]:
    """
    Decomposes the user query into specific search terms for the vector DB.
    Only runs once at the beginning.
    """
    original_query = state.get("user_query")

    prompt = (
        f"Generate 3 specific search queries to find information in a Zotero database "
        f"that answers this question: '{original_query}'. "
        f"Return them as a comma-separated list."
    )

    structured_llm = llm.with_structured_output(Queries)
    queries: Queries = structured_llm.invoke(prompt)

    print(f"Generated initial queries: {queries.queries}")

    # Update both current search queries and add them to history
    return Command(
        update={
            "queries": queries.queries,
        },
        goto="retrieve_zotero_docs"
    )


def retrieve_zotero_docs(state: ZoteroState) -> Command[Literal["synthesize_knowledge"]]:
    """
    Executes the vector search using the current search queries in the state.
    Appends new docs to existing ones to build a comprehensive context.
    """
    queries = state.get("queries", [])
    current_docs = state.get("retrieved_docs", [])
    current_doc_ids = state.get("known_document_ids", [])

    # Search
    new_docs = multi_query_search(queries, VECTOR_STORAGE, k=10)

    # de duplication
    new_docs_dict = {f'{doc.metadata.get("item_id")}_{doc.metadata.get('split_id')}': doc for doc in new_docs}
    new_doc_ids = list(new_docs_dict.keys())
    if current_doc_ids:
        for doc_id in current_doc_ids:
            if doc_id in new_doc_ids:
                new_docs_dict.pop(doc_id)
        new_doc_ids = list(new_docs_dict.keys())
        new_docs = list(new_docs_dict.values())

    # updates
    current_length = len(current_docs)
    all_docs = current_docs + new_docs
    all_doc_ids = current_doc_ids + new_doc_ids
    added_length = len(all_docs) - current_length

    print(f"Retrieved {len(new_docs)} new documents. Total: {len(all_docs)}")

    return Command(
        update={"retrieved_docs": all_docs,
                "added_sources": added_length,
                "current_doc_ids": all_doc_ids,
                },
        goto="synthesize_knowledge"
    )


def synthesize_knowledge(state: ZoteroState) -> Command[Literal["judge_information"]]:
    """
    Reduces the information string to a structured synthesis and per-source relevance.
    """
    # We re-construct a context with explicit metadata to ensure the LLM can find citation keys
    docs = state.get("retrieved_docs", [])
    user_query = state.get("user_query")
    docs_string = list_of_documents_to_string(docs)
    current_synthesis = state.get("synthesized_string", "")

    structured_llm = llm.with_structured_output(KnowledgeSynthesis)

    prompt = (
        f"Analyze the following zotero documents for the query: '{user_query}'.\n\n"
        f"Documents:\n{docs_string}\n\n"
        f"Provide a structured output containing:\n"
        f"1. Relevant information per source (excluding references).\n"
        f"2. A synthesis of knowledge across the references with citations using the citation key from the metadata."
    )

    result: KnowledgeSynthesis = structured_llm.invoke(prompt)

    # Format the structured output back into a string for the 'information_string' state variable
    # This ensures downstream nodes (Judge, Final Answer) get the refined info.
    formatted_output = f"## Knowledge Synthesis\n{result.synthesis_text}\n\n## Relevant Information by Source\n"
    for item in result.relevant_sources:
        formatted_output += f"### Source: {item.source_citation_key}\n{item.relevant_content}\n\n"

    return Command(
        update={"synthesized_string": formatted_output},
        goto="judge_information"
    )


def judge_information(state: ZoteroState) -> Command[Literal["retrieve_zotero_docs", "final_answer_tool"]]:
    """
    Decides if we have sufficient info. 
    If NO: Generates new queries (avoiding past ones) and loops back.
    If YES: Goes to final answer.
    """
    query = state.get("user_query")
    info_string = state.get("synthesized_string")
    loop_count = state.get("loop_count", 0)
    past_queries = state.get("past_queries", [])
    past_judgments = state.get("judgments", [])
    added_sources = state.get("added_sources", 0)

    # Safety break for infinite loops
    if added_sources < 2:
        print("Added sources less than 2. Ending loop.")
        return Command(goto="final_answer_tool")
    if loop_count >= 3:
        print("Max loops reached. Proceeding to answer with available info.")
        return Command(goto="final_answer_tool")

    structured_llm = llm.with_structured_output(JudgeDecision)
    
    prompt = (
        f"User Query: {query}\n\n"
        f"Available Information Summary:\n{info_string}\n\n"
        f"Past Search Queries (DO NOT REPEAT THESE): {past_queries}\n\n"
        f"Reasoning for updated search queries: {past_judgments}\n\n"
        f"Analyze if the available information is sufficient to provide a comprehensive answer. "
        f"If not, generate at most 2-3 NEW, different search queries to find the missing pieces. "
        f"If you cannot think of significantly different queries that might yield new info, mark as sufficient."
    )

    decision: JudgeDecision = structured_llm.invoke(prompt)
    updated_reasoning = past_judgments + [decision.reasoning]
    new_queries = decision.new_search_queries
    if decision.is_sufficient:
        print(f"Judge: Sufficient info (or exhausted options). Reason: {decision.reasoning}")
        return Command(
            update={
                "judgments": updated_reasoning,
            },
            goto="final_answer_tool"
        )
    # Verify we actually got new queries
    if not new_queries:
        print(f"Judge: Insufficient info but no new queries provided. Ending loop.")
        return Command(
            update={
                "judgments": updated_reasoning,
            },
            goto="final_answer_tool"
        )

    updated_history = past_queries + new_queries

    return Command(
        update={
            "search_queries": new_queries,
            "past_queries": updated_history,
            "judgments": updated_reasoning,
            "loop_count": loop_count + 1
        },
        goto="retrieve_zotero_docs"
    )


def final_answer_tool(state: ZoteroState) -> Command[Literal[END]]:
    """
    Constructs the final structured output using the gathered information.
    If info is missing, it explicitly states what was found and what is missing.
    """
    query = state.get("user_query")
    info_string = state.get("synthesized_string", "No information found.")
    judgments = state.get("judgments", [])

    structured_llm = llm.with_structured_output(ResearchResponse)

    prompt = (
        f"Based on the following context, answer the user's question.\n"
        f"User Query: {query}\n\n"
        f"Context:\n{info_string}\n\n"
        f"Validity of the context: {judgments}\n\n"
        f"Important: If the context is partial or incomplete, answer based on what you have, never make information up"
    )

    response: ResearchResponse = structured_llm.invoke(prompt)
    
    return Command(
        update={"final_response": response.model_dump()},
        goto=END
    )


# --- Graph Construction ---

workflow = StateGraph(ZoteroState)

# Add nodes
workflow.add_node("check_for_user_query", check_for_user_query)
workflow.add_node("generate_initial_search_queries", generate_initial_search_queries)
workflow.add_node("retrieve_zotero_docs", retrieve_zotero_docs)
workflow.add_node("synthesize_knowledge", synthesize_knowledge)
workflow.add_node("judge_information", judge_information)
workflow.add_node("final_answer_tool", final_answer_tool)

# Define edges
workflow.add_edge(START, 'check_for_user_query')

# Compile graph
app = workflow.compile()

# --- Example Usage ---
if __name__ == "__main__":
    initial_state = {"user_query": "What are the key factors in urban climate adaptation?"}

    # Run the graph
    result = app.invoke(initial_state)

    print("\n--- Final Result ---")
    # Pretty print the dict response
    final = result.get("final_response", {})
    print(f"Answer: {final.get('answer')}")
    print(f"Summary: {final.get('summary_of_sources')}")
    print(f"Sources: {final.get('sources')}")
