"""
Demo script for ZoteroPdfIndexer - AI Agent "scico" workflow
============================================================

This script demonstrates the capabilities of ZoteroPdfIndexer by simulating
an AI agent that helps researchers find relevant information in their Zotero library.

The agent follows these steps:
1. Initialize the indexing system
2. Index researcher's Zotero resources
3. Process a research query
4. Search for relevant information
5. Present findings
"""

import logging
import os
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv

from src.ZoteroPdfIndexer import PdfIndexer, IndexingConfig

# Configure logging for better visibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScicoAgent:
    """
    AI Agent 'scico' - Scientific Information Collection Officer

    Helps researchers find relevant information in their Zotero library.
    """

    def __init__(self, indexer: PdfIndexer):
        self.indexer = indexer
        self.name = "scico"
        logger.info(f"🤖 Agent '{self.name}' initialized and ready to assist!")

    def greet(self):
        """Introduce the agent."""
        print("\n" + "=" * 70)
        print(f"👋 Hello! I'm {self.name}, your Scientific Information Collection Officer")
        print("I help you find relevant information in your research library.")
        print("=" * 70 + "\n")

    def devise_plan(self, research_query: str) -> Dict[str, Any]:
        """
        Devise a plan to solve the research query.

        Args:
            research_query: The text from the researcher

        Returns:
            Dictionary with the plan and steps
        """
        print(f"\n📋 Research Query Received:")
        print(f"   '{research_query}'")
        print("\n🧠 Devising Search Plan...")

        plan = {
            "query": research_query,
            "steps": [
                "1. Ensure research library is indexed",
                "2. Extract key concepts from query",
                "3. Search vector database for relevant chunks",
                "4. Rank and filter results",
                "5. Present findings to researcher"
            ]
        }

        print("\n✅ Plan Created:")
        for step in plan["steps"]:
            print(f"   {step}")

        return plan

    def index_collection(self, collection_name: str) -> None:
        """
        Index a Zotero collection.

        Args:
            collection_name: Name of the collection to index
        """
        print(f"\n📚 Step 1: Indexing collection '{collection_name}'...")
        print("   Converting PDFs → Markdown → Chunks → Vector Database")

        try:
            result = self.indexer.index_by_collection_name(collection_name)

            print(f"\n✅ Indexing Complete!")
            print(f"   Total items: {result.total_items}")
            print(f"   Successfully indexed: {result.successful}")
            print(f"   Failed: {result.failed}")
            print(f"   Total chunks created: {result.chunks_created}")

            if result.failed > 0:
                print(f"\n⚠️  Failed items:")
                for item in result.failed_items[:3]:  # Show first 3
                    print(f"   - {item['pdf_path']}: {item['reason']}")

        except Exception as e:
            logger.error(f"Error during indexing: {e}")
            print(f"❌ Indexing failed: {e}")

    def search_for_matches(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search the indexed documents for matches.

        Args:
            query: Search query
            top_k: Number of top results to return

        Returns:
            List of matching documents with metadata
        """
        print(f"\n🔍 Step 2-4: Searching for relevant information...")
        print(f"   Query: '{query}'")
        print(f"   Looking for top {top_k} matches...")

        try:
            results = self.indexer.vector_indexer.search(
                query=query,
                n_results=top_k
            )

            print(f"\n✅ Found {len(results)} relevant chunks!")
            return results

        except Exception as e:
            logger.error(f"Search error: {e}")
            print(f"❌ Search failed: {e}")
            return []

    def present_findings(self, results: List[Dict[str, Any]]) -> None:
        """
        Present search results to the researcher.

        Args:
            results: List of search results
        """
        print(f"\n📊 Step 5: Presenting Findings")
        print("=" * 70)

        if not results:
            print("❌ No matching information found in your library.")
            return

        for idx, result in enumerate(results, 1):
            metadata = result.get('metadata', {})
            content = result.get('content', '')
            score = result.get('score', 0)

            print(f"\n🔖 Result {idx}:")
            print(f"   Relevance Score: {score:.4f}")
            print(f"   Source: {metadata.get('title', 'Unknown')}")
            print(f"   Authors: {metadata.get('authors', 'Unknown')}")
            print(f"   Year: {metadata.get('year', 'Unknown')}")

            # Show preview of content
            preview = content[:300] + "..." if len(content) > 300 else content
            print(f"\n   📄 Content Preview:")
            print(f"   {preview}")
            print("   " + "-" * 66)

    def get_index_stats(self) -> None:
        """Display current index statistics."""
        print(f"\n📈 Index Statistics:")
        try:
            stats = self.indexer.get_indexing_stats()
            for key, value in stats.items():
                print(f"   {key}: {value}")
        except Exception as e:
            print(f"   Unable to retrieve stats: {e}")


def main():
    """Main demo workflow."""

    # Load environment variables
    load_dotenv()

    print("\n" + "🚀 " + "=" * 66)
    print("   ZoteroPdfIndexer Demo - AI Agent 'scico' Workflow")
    print("=" * 70)

    # =========================================================================
    # SETUP: Initialize the indexer
    # =========================================================================
    print("\n⚙️  Initializing PdfIndexer...")

    config = IndexingConfig(
        markdown_base_path=Path(os.getenv('MARKDOWN_BASE_PATH', './markdown_output')),
        force_reindex=False,
        skip_existing_markdown=True,
        chunk_size=1000,
        chunk_overlap=200,
        chunking_strategy='markdown+recursive',
    )

    indexer = PdfIndexer(config=config)

    # Initialize the agent
    agent = ScicoAgent(indexer=indexer)
    agent.greet()

    # =========================================================================
    # SCENARIO: Researcher asks for help finding relevant information
    # =========================================================================

    # Example research query
    research_query = (
        "I'm investigating the relationship between machine learning "
        "and climate change prediction. What information do I have "
        "about neural networks used for weather forecasting?"
    )

    # Agent devises a plan
    plan = agent.devise_plan(research_query)

    # =========================================================================
    # STEP 1: Index the researcher's collection
    # =========================================================================

    # Example: Index by collection name
    # Replace with your actual collection name or use item-based indexing
    collection_name = "Machine Learning"  # Example collection

    print("\n" + "=" * 70)
    print("DEMONSTRATION MODE:")
    print("Replace 'Machine Learning' with your actual Zotero collection name")
    print("Or use other indexing methods:")
    print("  - indexer.index_by_item_name('paper_name')")
    print("  - indexer.index_by_item_id('item_id')")
    print("  - indexer.index_by_collection_id('collection_id')")
    print("=" * 70)

    # Uncomment to actually index:
    # agent.index_collection(collection_name)

    # =========================================================================
    # STEP 2-4: Search for relevant information
    # =========================================================================

    # Extract key search terms from query
    search_query = "machine learning neural networks weather forecasting climate prediction"

    # Uncomment to actually search:
    # results = agent.search_for_matches(search_query, top_k=5)

    # =========================================================================
    # STEP 5: Present findings
    # =========================================================================

    # Uncomment to present results:
    # agent.present_findings(results)

    # =========================================================================
    # ADDITIONAL FEATURES: Show other capabilities
    # =========================================================================

    print("\n\n" + "=" * 70)
    print("🎯 Additional Capabilities:")
    print("=" * 70)

    print("\n1️⃣  Update Index (re-index with fresh data):")
    print("   indexer.update_index(QueryType.COLLECTION_NAME, 'Machine Learning', force=True)")

    print("\n2️⃣  Get Index Statistics:")
    agent.get_index_stats()

    print("\n3️⃣  Clear Index (with safety confirmation):")
    print("   indexer.clear_index(confirm=True)")

    print("\n4️⃣  Batch Processing:")
    print("   Configure batch_size in IndexingConfig for processing multiple items")

    print("\n5️⃣  Custom Chunking:")
    print("   Adjust chunk_size, chunk_overlap, and chunking_strategy in config")

    # =========================================================================
    # CONCLUSION
    # =========================================================================

    print("\n\n" + "=" * 70)
    print("✅ Demo Complete!")
    print("=" * 70)
    print(f"\n👋 Agent '{agent.name}' is ready to help with your research!")
    print("\nTo use this in production:")
    print("1. Set up your environment variables (VECTOR_STORAGE_PATH, etc.)")
    print("2. Uncomment the actual indexing and search calls")
    print("3. Replace example collection names with your actual data")
    print("4. Integrate with your research workflow")
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
