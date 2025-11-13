import logging
from typing import Any, List

import pandas as pd
from langchain.tools import ToolRuntime, tool
from langchain_core.documents import Document

import src.configs.zotero_retriever_configs as config

logger = logging.getLogger(__name__)


# ===== Helper Functions =====


def _document_to_dict(doc: Document) -> dict:
    """Format a Document into a source dictionary for the response."""
    metadata = doc.metadata
    return {
        "title": metadata.get("title", "Unknown"),
        "date": metadata.get("date", "Unknown"),
        "authors": metadata.get("authors", "Unknown"),
        "citation_key": metadata.get("citation_key", "unknown"),
        "item_id": metadata.get("item_id", "unknown"),
        "split_id": metadata.get("split_id", None),
        "distance": metadata.get("distance", 0.0),
        "content": doc.page_content,
    }


def _list_of_documents_to_dataframe(documents: list[Document]) -> pd.DataFrame:
    """Convert a list of Document objects to a Pandas DataFrame for display."""
    doc_dicts = [_document_to_dict(doc) for doc in documents]
    return pd.DataFrame(doc_dicts)


def _metadata_string_from_df(df: pd.DataFrame) -> str:
    """Convert a DataFrame of metadata to a string for display."""
    return (
        "<metadata>\n"
        f"authors: {df['authors'].unique()[0]}\n"
        f"citation_key: {df['citation_key'].unique()[0]}\n"
        f"item_id: {df['item_id'].unique()[0]}\n"
        f"date_of_publication: {df['date'].unique()[0]}\n"
        "</metadata>"
    )


def _content_string_from_df(df: pd.DataFrame) -> str:
    """Convert a DataFrame of content to a string for display."""
    content_string = "<content>\n"
    for _, row in df.iterrows():
        content_string += f"{row['content']}\n"
    content_string += "</content>"
    return content_string


def _list_of_documents_to_string(documents: list[Document]) -> str:
    """Convert a list of Document objects to a string for display."""
    display_string = "<context from scientific literature>\n"
    df = _list_of_documents_to_dataframe(documents)
    for title, group in df.groupby("title"):
        group = group.sort_values("split_id")
        content_string = _content_string_from_df(group)
        metadata_string = _metadata_string_from_df(group)
        display_string += (
            f"<title>\n{title}\n</title>\n{content_string}\n{metadata_string}\n\n"
        )
    display_string += "</context from scientific literature>"
    return display_string


def _assess_relevance(documents: List[Document], threshold: float) -> str:
    """Assess the overall relevance quality of retrieved documents."""
    if not documents:
        return "low"

    avg_distance = sum(doc.metadata.get("distance", 1.0) for doc in documents) / len(
        documents
    )

    if avg_distance < threshold * 0.5:
        return "high"
    elif avg_distance < threshold:
        return "medium"
    else:
        return "low"


# ===== Tool Definitions =====


@tool(response_format="content_and_artifact")
def semantic_search(
        query: str, runtime: ToolRuntime[config.RetrieverContext]
) -> tuple[str, Any]:
    """
    Perform semantic search on the Zotero vector storage to find relevant document passages.

    Args:
        query: The search query or question to find relevant content for.
        runtime: Injected runtime context with vector storage and preferences.

    Returns:
        A structured string of relevant information using the following format:
        <title>\n<content>\n<metadata>\n\n...

    Use this as the PRIMARY tool for answering single and simple questions.
    """
    storage = runtime.context.vector_storage
    k = runtime.context.k_documents

    logger.debug(f"Performing semantic search for query: {query}")
    results = storage.search(query=query, n_results=k)
    logger.info(f"Found {len(results)}/{k} results for query: {query}")

    result_string = _list_of_documents_to_string(results)

    return result_string, results


@tool(response_format="content_and_artifact")
def multi_query_search(
        queries: List[str], runtime: ToolRuntime[config.RetrieverContext]
):
    """
    Perform multiple semantic searches and combine results.

    Args:
        queries: List of related search queries to execute.
        runtime: Injected runtime context with vector storage and preferences.

     Returns:
        A structured string of relevant information using the following format:
        <title>\n<content>\n<metadata>\n\n...

    Use this as the PRIMARY tool for complex questions that might need multiple perspectives and with optimized semantic searches,
    or to ensure comprehensive coverage of a topic.
    """
    storage = runtime.context.vector_storage
    k = runtime.context.k_documents

    all_results = []
    seen_ids = set()

    for query in queries:
        results = storage.search(query=query, n_results=k)
        for doc in results:
            # Use a hash of content + metadata to deduplicate
            doc_id = f"{doc.page_content[:100]}_{doc.metadata.get('item_id', '')}"
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                all_results.append(doc)

    # Sort by distance (lower is better)
    all_results.sort(key=lambda d: d.metadata.get("distance", 999.0))

    results = all_results[
        : k * 2
    ]  # Return up to 2x k_documents for comprehensive coverage
    result_string = _list_of_documents_to_string(results)

    return result_string, results


@tool(response_format="content_and_artifact")
def search_by_item(
        item_id: str, query: str, runtime: ToolRuntime[config.RetrieverContext]
):
    """
    Search for relevant content within a specific Zotero item.

    Args:
        item_id: The Zotero item ID to search within.
        query: The search query to find relevant passages in this item.
        runtime: Injected runtime context with vector storage and preferences.

    Returns:
        A structured string of relevant information using the following format:
        <title>\n<content>\n<metadata>\n\n...

    Use this when the user asks about a specific paper or item by name or ID.
    """
    storage = runtime.context.vector_storage
    k = runtime.context.k_documents

    results = storage.search(query=query, metadata={"item_id": item_id}, n_results=k)

    result_string = _list_of_documents_to_string(results)

    return result_string, results


@tool
def list_indexed_items(runtime: ToolRuntime[config.RetrieverContext]) -> dict:
    """
    Get statistics about what items are indexed in the vector storage.

    Args:
        runtime: Injected runtime context with vector storage.

    Returns:
        Dictionary with 'total_elements' and 'items' (mapping item_id to title and count).

    Use this to understand what documents are available for search,
    or when the user asks "what can I search" or "what's indexed".
    """
    storage = runtime.context.vector_storage
    return storage.get_collection_stats()
