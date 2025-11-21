"""
Streamlit interface for ZoteroPdfIndexer.

This interface provides an easy-to-use GUI for:
- Browsing Zotero collections
- Selecting items from collections
- Indexing selected PDFs into vector storage
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
from langchain_core.documents import Document

# Add project root to path to allow imports
project_root: Path = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import src.zotero.zotero_client as zot
from src.zotero.ZoteroPdfIndexer import (
    IndexingConfig,
    ChromaStorageConfig,
    IndexingResult,
    PdfIndexer,
    QueryType,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(page_title="Zotero PDF Indexer", page_icon="📚", layout="wide")


def initialize_session_state():
    """Initialize session state variables."""
    if "zotero_client" not in st.session_state:
        st.session_state.zotero_client = None
    if "indexer" not in st.session_state:
        st.session_state.indexer = None
    if "collections" not in st.session_state:
        st.session_state.collections = {}
    if "selected_collection" not in st.session_state:
        st.session_state.selected_collection = None
    if "collection_items" not in st.session_state:
        st.session_state.collection_items = []
    if "selected_items" not in st.session_state:
        st.session_state.selected_items = []
    if "indexing_results" not in st.session_state:
        st.session_state.indexing_results: Optional[IndexingResult] = None
    if "last_loaded_collection" not in st.session_state:
        st.session_state.last_loaded_collection: Optional[str] = None


def initialize_clients() -> bool:
    """Initialize Zotero client and PdfIndexer."""
    try:
        if st.session_state.zotero_client is None:
            st.session_state.zotero_client = zot

        if st.session_state.indexer is None:
            markdown_path: str = os.getenv("MARKDOWN_FOLDER_PATH", "./markdown_output")
            config: IndexingConfig = IndexingConfig(
                markdown_base_path=Path(markdown_path),
                force_reindex=False,
                skip_existing_markdown=True,
                chunk_size=1000,
                chunk_overlap=200,
                chunking_strategy="markdown+recursive",
            )
            storage_config: ChromaStorageConfig = ChromaStorageConfig()
            st.session_state.indexer = PdfIndexer(config=config, storage_config=storage_config)
            logger.info(
                f"Initialized PdfIndexer with config: {config} and storage config: {storage_config}"
            )

        return True
    except Exception as e:
        st.error(f"Failed to initialize clients: {e}")
        logger.error(f"Initialization error: {e}", exc_info=True)
        return False


def load_collections() -> Dict[str, str]:
    """Load all Zotero collections.

    Returns:
        Dictionary mapping collection names to collection IDs
    """
    try:
        # Returns Dict[str, str] - collection_name: collection_id
        collections: Dict[str, str] = (
            st.session_state.zotero_client.list_all_collections()
        )
        st.session_state.collections = collections
        return collections
    except Exception as e:
        st.error(f"Failed to load collections: {e}")
        logger.error(f"Collection loading error: {e}", exc_info=True)
        return {}


def load_collection_items(collection_id: str) -> List[Tuple[Path, Dict[str, Any]]]:
    """Load items from a selected collection.

    Args:
        collection_id: Zotero collection ID to load items from

    Returns:
        List of tuples containing (pdf_path, metadata)
    """
    try:
        items: List[Tuple[Path, Dict[str, Any]]] = (
            st.session_state.zotero_client.get_items_by_collection_id(collection_id)
        )
        st.session_state.collection_items = items
        return items
    except Exception as e:
        st.error(f"Failed to load collection items: {e}")
        logger.error(f"Item loading error: {e}", exc_info=True)
        return []


def format_item_display(item_data: Tuple[Path, Dict[str, Any]]) -> str:
    """Format item for display in multiselect.

    Args:
        item_data: Tuple of (pdf_path, metadata)

    Returns:
        Formatted string for display
    """
    pdf_path: Path
    metadata: Dict[str, Any]
    pdf_path, metadata = item_data

    title: str = metadata.get("title", "Untitled")
    author_str: str = metadata.get("authors", "")

    # Get first author if multiple
    authors: List[str] = author_str.split("; ")
    if len(authors) > 1:
        author_str = authors[0] + " et al."

    display: str = f"{title}"
    if author_str:
        display += f" — {author_str}"

    return display


def main() -> None:
    """Main Streamlit application."""
    initialize_session_state()

    # Header
    st.title("📚 Zotero PDF Indexer")
    st.markdown("Index your Zotero PDFs into a vector database for semantic search.")

    # Initialize clients
    with st.spinner("Initializing Zotero connection..."):
        if not initialize_clients():
            st.stop()

    st.success("✓ Connected to Zotero")

    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Configuration options
        force_reindex: bool = st.checkbox(
            "Force reindex", value=False, help="Reindex even if files already exist"
        )

        skip_existing_markdown: bool = st.checkbox(
            "Skip existing Markdown",
            value=True,
            help="Skip PDF-to-Markdown conversion if MD file exists",
        )

        # Update config
        if st.session_state.indexer:
            st.session_state.indexer.config.force_reindex = force_reindex
            st.session_state.indexer.config.skip_existing_markdown = (
                skip_existing_markdown
            )

        st.divider()

        # Maintenance Section
        st.header("🛠️ Maintenance")

        if st.button("📂 Index Local Markdown", help="Index all files in markdown directory"):
            if st.session_state.indexer:
                progress_bar = st.sidebar.progress(0)
                with st.spinner("Indexing local files..."):
                    def update_progress_local(p: float):
                        progress_bar.progress(p)

                    result = st.session_state.indexer.index_all_markdown_files(
                        progress_callback=update_progress_local
                    )
                    st.session_state.indexing_results = result
                    progress_bar.empty()
                    st.success(f"Completed: {result.successful} indexed")

        with st.expander("Danger Zone"):
            st.warning("This will permanently delete the vector index.")
            confirm_clear = st.checkbox("I confirm I want to clear the index")

            if st.button("🗑️ Clear Entire Index", type="primary", disabled=not confirm_clear):
                if st.session_state.indexer:
                    with st.spinner("Clearing index..."):
                        if st.session_state.indexer.clear_index(confirm=True):
                            st.success("Index cleared successfully.")
                            st.session_state.indexing_results = None
                            st.rerun()
                        else:
                            st.error("Failed to clear index.")

        st.divider()

        # Display stats
        st.header("📊 Index Statistics")
        if st.button("Refresh Stats"):
            try:
                stats: Dict[str, Any] = st.session_state.indexer.get_indexing_stats()
                st.json(stats)
            except Exception as e:
                st.error(f"Failed to load stats: {e}")

    # Add search interface section at the top
    st.header("🔍 Search Index")

    search_col1, search_col2 = st.columns([2, 1])

    with search_col1:
        search_query = st.text_input(
            "Search Query",
            placeholder="Enter semantic search query (optional)",
            help="Leave empty to search by metadata only",
        )

    with search_col2:
        num_results = st.number_input(
            "Number of Results", min_value=1, max_value=50, value=5
        )

    # Metadata filter inputs
    metadata_col1, metadata_col2, metadata_col3 = st.columns(3)

    with metadata_col1:
        filter_item_id = st.text_input(
            "Item ID Filter", placeholder="Filter by item_id (optional)"
        )

    with metadata_col2:
        filter_title = st.text_input(
            "Title Filter", placeholder="Filter by title (optional)"
        )

    with metadata_col3:
        filter_author = st.text_input(
            "Author Filter", placeholder="Filter by author (optional)"
        )

    # Build metadata filter
    metadata_filter = {}
    if filter_item_id:
        metadata_filter["item_id"] = filter_item_id
    if filter_title:
        metadata_filter["title"] = filter_title
    if filter_author:
        metadata_filter["authors"] = filter_author

    # Search button
    if st.button("🔎 Search", type="primary", use_container_width=True):
        if not search_query and not metadata_filter:
            st.warning("⚠️ Please provide either a search query or metadata filters")
        else:
            try:
                with st.spinner("Searching..."):
                    results: List[Document] = st.session_state.indexer.search(
                        query=search_query,
                        metadata_filter=metadata_filter if metadata_filter else None,
                        n_results=num_results,
                    )

                if results:
                    st.success(f"✅ Found {len(results)} results")

                    # Display results
                    for idx, doc in enumerate(results, 1):
                        with st.expander(
                                f"Result {idx}: {doc.metadata.get('title', 'Untitled')}"
                        ):
                            # Metadata
                            st.markdown("**Metadata:**")
                            metadata_display = {
                                "Title": doc.metadata.get("title", "N/A"),
                                "Authors": doc.metadata.get("authors", "N/A"),
                                "Item ID": doc.metadata.get("item_id", "N/A"),
                            }
                            if "distance" in doc.metadata:
                                metadata_display["Distance"] = (
                                    f"{doc.metadata['distance']:.4f}"
                                )

                            for key, value in metadata_display.items():
                                st.text(f"{key}: {value}")

                            st.divider()

                            # Content
                            st.markdown("**Content:**")
                            st.markdown(doc.page_content)
                else:
                    st.info("No results found")

            except Exception as e:
                st.error(f"❌ Search failed: {e}")
                logger.error(f"Search error: {e}", exc_info=True)

    st.divider()

    # Main content area
    col1, col2 = st.columns([1, 1])

    with col1:
        st.header("1️⃣ Select Collection")

        # Load collections button
        if st.button("🔄 Load Collections", use_container_width=True):
            with st.spinner("Loading collections..."):
                load_collections()

        # Collection dropdown
        if st.session_state.collections:
            # collections is Dict[str, str] with name: id mapping
            collection_names: List[str] = list(st.session_state.collections.keys())

            selected_collection_name: str = st.selectbox(
                "Choose a collection",
                options=[""] + collection_names,
                key="collection_selector",
            )

            if selected_collection_name:
                # Get collection ID from the dictionary
                collection_id: str = st.session_state.collections[
                    selected_collection_name
                ]

                # Only load items if collection has changed
                if st.session_state.last_loaded_collection != collection_id:
                    st.session_state.selected_collection = collection_id
                    st.session_state.last_loaded_collection = collection_id

                    # Load items for the new collection
                    with st.spinner("Loading collection items..."):
                        load_collection_items(collection_id)

                    # Apply selection if "Select All" is active
                    if st.session_state.get("select_all", False):
                        items = st.session_state.collection_items
                        st.session_state.item_selector = [
                            format_item_display(item) for item in items
                        ]
                    else:
                        st.session_state.item_selector = []

                    st.success(
                        f"✓ Loaded {len(st.session_state.collection_items)} items"
                    )
                else:
                    # Collection hasn't changed, just show the count
                    if st.session_state.collection_items:
                        st.info(
                            f"📄 {len(st.session_state.collection_items)} items in collection"
                        )
        else:
            st.info("Click 'Load Collections' to get started")

    with col2:
        st.header("2️⃣ Select Items")

        if st.session_state.collection_items:
            # Create item display mapping
            item_display_map: Dict[str, Tuple[Path, Dict[str, Any]]] = {}
            for item in st.session_state.collection_items:
                display_name: str = format_item_display(item)
                item_display_map[display_name] = item

            item_names: List[str] = list(item_display_map.keys())

            # Callback for select all
            def on_select_all():
                if st.session_state.select_all:
                    st.session_state.item_selector = item_names
                else:
                    st.session_state.item_selector = []

            # Select all checkbox
            st.checkbox("Select All Items", key="select_all", on_change=on_select_all)

            # Multiselect for items
            selected_display_names = st.multiselect(
                "Select items to index",
                options=item_names,
                key="item_selector",
            )

            # Store selected items in session state
            st.session_state.selected_items = [
                item_display_map[name] for name in selected_display_names
            ]

            st.info(
                f"Selected {len(st.session_state.selected_items)} items for indexing"
            )
        else:
            st.info("Select a collection to view its items")

    # Indexing section
    st.divider()
    st.header("3️⃣ Index Selected Items")

    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])

    with col_btn1:
        index_button: bool = st.button(
            "🚀 Start Indexing",
            type="primary",
            use_container_width=True,
            disabled=len(st.session_state.selected_items) == 0,
        )

    with col_btn2:
        clear_selection: bool = st.button("🗑️ Clear Selection", use_container_width=True)
        if clear_selection:
            st.session_state.selected_items = []
            st.rerun()

    # Indexing execution
    if index_button:
        if st.session_state.selected_items:
            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                status_text.text("Starting indexing process...")

                def update_progress(p: float):
                    progress_bar.progress(p)

                # Index the selected items
                logger.info(f"Indexing {len(st.session_state.selected_items)} items...")
                result: IndexingResult = st.session_state.indexer.update_index(
                    query_type=QueryType.ITEM_LIST,
                    query_value=st.session_state.selected_items,
                    force=force_reindex,
                    progress_callback=update_progress,
                )

                progress_bar.progress(100)
                st.session_state.indexing_results = result

                # Display results
                st.success("✅ Indexing completed!")

                col_res1, col_res2, col_res3 = st.columns(3)
                with col_res1:
                    st.metric("Total Items", result.total_items)
                with col_res2:
                    st.metric("Successful", result.successful, delta=None)
                with col_res3:
                    st.metric("Failed", result.failed, delta=None)

                st.metric("Total Chunks Created", result.chunks_created)

                # Show failed items if any
                if result.failed > 0:
                    with st.expander("⚠️ View Failed Items"):
                        failed_item: Dict[str, Any]
                        for failed_item in result.failed_items:
                            st.write(f"**Path:** {failed_item['pdf_path']}")
                            st.write(f"**Reason:** {failed_item['reason']}")
                            st.divider()

            except Exception as e:
                st.error(f"❌ Indexing failed: {e}")
                logger.error(f"Indexing error: {e}", exc_info=True)
        else:
            st.warning("Please select items to index")

    # Display previous results if available
    if st.session_state.indexing_results and not index_button:
        st.divider()
        st.subheader("📋 Last Indexing Results")
        result: IndexingResult = st.session_state.indexing_results

        col_res1, col_res2, col_res3 = st.columns(3)
        with col_res1:
            st.metric("Total Items", result.total_items)
        with col_res2:
            st.metric("Successful", result.successful)
        with col_res3:
            st.metric("Failed", result.failed)

        st.metric("Total Chunks Created", result.chunks_created)


if __name__ == "__main__":
    main()
