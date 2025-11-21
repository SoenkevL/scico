import logging
from typing import Any, List

import pandas as pd
from langchain.tools import ToolRuntime, tool
from langchain_core.documents import Document

import src.configs.zotero_retriever_configs as config
from src.storages.ChromaStorage import ChromaStorage

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
        "### metadata\n"
        f"- authors: {df['authors'].unique()[0]}\n"
        f"- citation_key: {df['citation_key'].unique()[0]}\n"
        f"- item_id: {df['item_id'].unique()[0]}\n"
        f"- date_of_publication: {df['date'].unique()[0]}\n"
    )


def _content_string_from_df(df: pd.DataFrame) -> str:
    """Convert a DataFrame of content to a string for display."""
    content_string = "### content\n"
    for _, row in df.iterrows():
        content_string += f"- {row['content']}\n"
    return content_string


# === public functions ===
def list_of_documents_to_string(documents: list[Document]) -> str:
    """Convert a list of Document objects to a string for display.
    # Context from scientific literature
    ## title
    ### metadata
    ### content
    """
    display_string = "# Context from scientific literature\n\n"
    df = _list_of_documents_to_dataframe(documents)
    for title, group in df.groupby("title"):
        group = group.sort_values("split_id")
        content_string = _content_string_from_df(group)
        metadata_string = _metadata_string_from_df(group)
        display_string += (
            f"## {title}\n"
            f"{metadata_string}\n\n"
            f"{content_string}\n\n"
        )
    display_string += "--- \n\n"
    return display_string


def semantic_search(
        query: str, storage: ChromaStorage, k: int
) -> list[Document]:
    """
    Perform semantic search on the Zotero vector storage to find relevant document passages.
    """
    logger.debug(f"Performing semantic search for query: {query}")
    results = storage.search(query=query, n_results=k)
    logger.info(f"Found {len(results)}/{k} results for query: {query}")

    return results


def multi_query_search(
        queries: List[str],
        storage: ChromaStorage,
        k: int,
        metadata_filter: dict[str, Any] | None = None,
) -> list[Document]:
    """
    Perform multiple semantic searches and combine results.

    Args:
        queries: List of related search queries to execute.
        storage: vector storage to call search function on
        k: number of results to return
        metadata_filter: Optional dictionary of metadata to filter results by

     Returns:
        A structured string of relevant information using the following format:
        <title>\n<content>\n<metadata>\n\n...
    """
    all_results = []
    seen_ids = set()

    for query in queries:
        results = storage.search(query=query, metadata=metadata_filter, n_results=k)
        for doc in results:
            # Use a hash of content + metadata to deduplicate
            doc_id = f"{doc.page_content[:100]}_{doc.metadata.get('item_id', '')}"
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                all_results.append(doc)

    # Sort by distance (lower is better)
    all_results.sort(key=lambda d: d.metadata.get("distance", 999.0))

    results = all_results[:k]  # Return up to 2x k_documents for comprehensive coverage

    return results


def search_by_item(
        item_id: str, query: str, storage: ChromaStorage, k: int
) -> list[Document]:
    """
    Search for relevant content within a specific Zotero item.

    Args:
        item_id: The Zotero item ID to search within.
        query: The search query to find relevant passages in this item.
        storage: vector storage to call search function on
        k: number of results to return

    Returns:
        A structured string of relevant information using the following format:
        <title>\n<content>\n<metadata>\n\n...
    """
    results = storage.search(query=query, metadata={"item_id": item_id}, n_results=k)

    return results


def list_indexed_items(storage: ChromaStorage) -> dict[str, Any]:
    """
    Get statistics about what items are indexed in the vector storage.

    Args:
        storage: vector storage to call get_collection_stats function on

    Returns:
        Dictionary with 'total_elements' and 'items' (mapping item_id to title and count).
    """
    return storage.get_collection_stats()


# ===== Tool Definitions =====
@tool(response_format="content_and_artifact")
def semantic_search_tool(
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
    results = semantic_search(query, runtime.context.vector_storage, runtime.context.k_documents)
    return list_of_documents_to_string(results), results


@tool(response_format="content_and_artifact")
def multi_query_search_tool(
        queries: List[str], runtime: ToolRuntime[config.RetrieverContext]
):
    """
    Perform multiple semantic searches and combine results.

    Args:
        queries: List of related search queries to execute.
        runtime: Injected runtime context with vector storage and preferences.

     Returns:
        A structured string of relevant information in markdown format


    Use this as the PRIMARY tool for complex questions that might need multiple perspectives and with optimized semantic searches,
    or to ensure comprehensive coverage of a topic.
    """
    results = multi_query_search(queries, runtime.context.vector_storage, runtime.context.k_documents)
    return list_of_documents_to_string(results), results


@tool(response_format="content_and_artifact")
def search_by_item_tool(
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
    results = search_by_item(item_id, query, runtime.context.vector_storage, runtime.context.k_documents)
    return list_of_documents_to_string(results), results


@tool
def list_indexed_items_tool(runtime: ToolRuntime[config.RetrieverContext]) -> dict[str, Any]:
    """
    Get statistics about what items are indexed in the vector storage.

    Args:
        runtime: Injected runtime context with vector storage.

    Returns:
        Dictionary with 'total_elements' and 'items' (mapping item_id to title and count).

    Use this to understand what documents are available for search,
    or when the user asks "what can I search" or "what's indexed".
    """
    return list_indexed_items(storage=runtime.context.vector_storage)
