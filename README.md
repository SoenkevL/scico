# 🔬 SciCO - Scientific Co-worker

**An AI-assisted research helper that indexes your Zotero PDFs, chunks them, stores semantic vectors, and lets you
retrieve relevant passages with source attribution.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

---

## 🎯 What is SciCO?

SciCO transforms your Zotero library into an intelligent, searchable knowledge base using Retrieval-Augmented
Generation (RAG). Instead of manually searching through dozens of papers, ask questions in natural language and get
relevant excerpts with proper source attribution.

The system focuses on deterministic, reproducible workflows: **PDF → Markdown → chunks → vector store** with optional
LLM tooling for retrieval and question answering.

### **Key Features**

✅ **Zotero Integration** - Direct connection to your Zotero SQLite database or cloud API  
✅ **PDF Processing** - Converts PDFs to structured markdown with `marker-pdf`  
✅ **Semantic Search** - Uses ChromaDB for vector-based retrieval  
✅ **Metadata Extraction** - Preserves authors, DOI, tags, collections, and citation keys  
✅ **LLM Agent** - LangChain-based retriever agent for answers with cited sources  
✅ **Web Interface** - Streamlit GUI for browsing collections and indexing items

---

## 📦 Installation

### **Prerequisites**

1. **Python 3.13+** - Required for this project
   ```bash
   python --version  # Should be 3.13 or higher
   ```

2. **Zotero** - With an existing library
    - Locate your Zotero data directory (usually `~/Zotero`)
    - Ensure `zotero.sqlite` exists in this directory

3. **LLM Backend** (choose at least one):
    - **Ollama** - For local embeddings and chat
      ```bash
      # Install from https://ollama.ai
      # Start Ollama server
      ollama serve
      ```
    - **OpenAI API** - For cloud-based embeddings and chat (requires API key)

### **Setup**

You can use **uv** (recommended) or **pip**.

#### **Using uv (Recommended)**

```
bash
# Clone the repository
git clone https://github.com/yourusername/scico.git
cd scico

# Install uv if not already installed
# See: https://docs.astral.sh/uv/

# Sync dependencies and create virtual environment
uv sync

# Activate the environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

#### **Using pip**

```
bash
# Clone the repository
git clone https://github.com/yourusername/scico.git
cd scico

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode
pip install -e .
```

### **Core Dependencies**

The project uses these major libraries (managed via `pyproject.toml`):

```

langchain, langchain-text-splitters, langchain-chroma
langchain-openai, langchain-ollama
chromadb                # Vector storage
marker-pdf              # PDF → Markdown conversion
sqlalchemy              # Zotero database access
streamlit               # Web interface
fastmcp, mcp            # Future tooling integration
langgraph-cli[inmem]    # Agent deployment
python-dotenv           # Environment management
pandas, numpy           # Data handling
```
---

## ⚙️ Configuration

Create a `.env` file in the project root:

```bash
cp env.example .env
```

Then edit `.env` with your settings:

```bash
# === Paths ===
# Where Markdown output (converted from PDFs) is written
MARKDOWN_FOLDER_PATH='/path/to/markdown/output'

# Path to Chroma DB storage
VECTOR_STORAGE_PATH='example/SciCo.db'

# Path to your Zotero data directory (contains zotero.sqlite)
LOCAL_ZOTERO_PATH='/path/to/Zotero'

# === Zotero Cloud API (recommended) ===
ZOTERO_API_KEY=
ZOTERO_ID=

# === Ollama (optional) ===
OLLAMA_BASE_URL='http://localhost:11434'
OLLAMA_EMBEDDING_MODEL='nomic-embed-text'
OLLAMA_CHAT_MODEL='gpt-oss:latest'

# === OpenAI (optional) ===
OPENAI_API_KEY=  # Required if you set MODEL_PROVIDER=openai

# === LangSmith (optional telemetry) ===
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT='https://api.smith.langchain.com'
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT='SciCo'

# === Agent Model Settings (optional) ===
MODEL_NAME=  # Defaults vary by provider
MODEL_PROVIDER='ollama'  # or 'openai'
MODEL_TEMPERATURE=0.0
```

### **Finding Your Zotero Path**

- **macOS**: `~/Zotero/`
- **Windows**: `C:\Users\YourName\Zotero\`
- **Linux**: `~/Zotero/`

Inside this folder, you should see `zotero.sqlite`.

---

## 🚀 Quick Start

### **Option 1: Streamlit Web Interface (Recommended)**

The easiest way to get started - a GUI to browse collections and index PDFs:

```shell script
streamlit run src/Frontend/ZoteroPdfIndexerApp.py
```

This interface lets you:

1. Browse your Zotero collections
2. Select items to index
3. Monitor processing progress
4. Search your indexed documents

### **Option 2: Programmatic Usage**

Minimal example for indexing and searching:

```python
from pathlib import Path
from src.ZoteroPdfIndexer import IndexingConfig, PdfIndexer

# Configure indexer
config = IndexingConfig(
    markdown_base_path=Path("example/markdown-library"),
    force_reindex=False,
    skip_existing_markdown=True,
    chunk_size=1000,
    chunk_overlap=200,
    chunking_strategy="markdown+recursive",
)
indexer = PdfIndexer(config)

# Index a collection
result = indexer.index_by_collection_name("Your Collection Name")
print(result)

# Search
docs = indexer.search("What is integrated information theory?", n_results=5)
for d in docs:
    print(f"Title: {d.metadata.get('title')}")
    print(f"Excerpt: {d.page_content[:200]}...\n")
```

### **Option 3: AI Agent with Citations**

Use the LangChain-based retriever agent for answers with source attribution:

```python
from src.zotero_retriever_agent import ZoteroRetriever
from src.configs.zotero_retriever_configs import VectorStorageConfig

retriever = ZoteroRetriever(
    vector_storage_config=VectorStorageConfig(),
    model_name="gpt-oss:latest",  # Or OpenAI model
    provider="ollama",  # or "openai"
    temperature=0.0,
)

result = retriever.invoke(
    "Summarize the core idea behind IIT with citations.",
    thread_id="session-1",
    user_id="alice",
    k_documents=8,
    relevance_threshold=1.0,
)

print(retriever.get_response(result))
```


---

## 📚 Project Structure

```
scico/
├── src/
│   ├── ZoteroPdfIndexer.py           # High-level orchestrator (index/search)
│   ├── VectorStorage.py              # ChromaDB wrapper
│   ├── zotero_client.py              # Zotero access + metadata + PDF resolution
│   ├── zotero_retriever_agent.py     # LangChain agent with citations
│   │
│   ├── document_processing/
│   │   ├── PdfToMarkdown.py          # PDF → Markdown conversion
│   │   └── TextSplitter.py           # MarkdownChunker (chunking)
│   │
│   ├── Tools/
│   │   ├── general_tools.py
│   │   ├── zotero_retriever_tools.py
│   │   └── zotero_librarian_tools.py
│   │
│   ├── Frontend/
│   │   └── ZoteroPdfIndexerApp.py    # Streamlit UI
│   │
│   ├── Prompts/                      # Prompt templates
│   │
│   └── configs/
│       ├── chunking_config.py
│       ├── pdf_extractor_config.py
│       └── zotero_retriever_configs.py
│
├── tutorials/                         # Tutorials and examples
├── pyproject.toml                     # Project metadata (PEP 621)
├── uv.lock                           # uv lock file
├── langgraph.json                    # LangGraph CLI config
├── env.example                       # Environment template
├── system_prompt_generator.py        # Generates LLM_INSTRUCTIONS.md
├── directory_tree_generator.py       # Project tree utility
└── README.md                         # This file
```


---

## 🔧 Core Components

### **1. Zotero Integration**

Connects to your Zotero SQLite database or cloud API to retrieve:
- PDF file paths from collections
- Metadata (title, authors, DOI, abstract, tags)
- Citation keys (Better BibTeX support)
- Collections and hierarchy

```python
from src.zotero_client import ZoteroClient

client = ZoteroClient()
# Get all PDFs in a collection
items = client.get_collection_items("My Papers")

# Get full metadata for specific item
metadata = client.get_item_metadata(item_id)
```

### **2. PDF to Markdown Conversion**

Uses `marker-pdf` library to convert PDFs to structured markdown:
- Preserves formatting and structure
- Extracts images
- Uses LLM for enhanced OCR and layout understanding

```python
from src.document_processing.PdfToMarkdown import PdfToMarkdownConverter

converter = PdfToMarkdownConverter()
markdown = converter.convert(
    pdf_path="/path/to/paper.pdf",
    output_path="/path/to/output"
)
```

### **3. Text Chunking**

Splits markdown into semantic chunks using:
- Header-based splitting (H1-H7)
- Recursive character splitting
- Configurable chunk size and overlap

```python
from src.document_processing.Chunker import MarkdownChunker

chunker = MarkdownChunker(
    chunk_size=1000,
    chunk_overlap=200,
    strategy='markdown+recursive'
)
chunks = chunker.chunk(markdown_text)
```

### **4. Vector Storage**

ChromaDB wrapper for embedding and retrieval:
- Automatic embedding generation
- Persistent storage
- Semantic similarity search
- Efficient deletion/update by item_id

```python
from src.VectorStorage import ChromaStorage

storage = ChromaStorage(
    persist_path="/path/to/chroma.db",
    collection_name="MyCollection"
)

# Add documents
storage.add_documents(chunks, metadatas=metadata_list)

# Query
results = storage.query(
    query_texts=["What are the main findings?"],
    n_results=5
)
```

### **5. High-Level Indexer**

Orchestrates the entire pipeline from PDF to searchable vectors:

```python
from src.ZoteroPdfIndexer import PdfIndexer, IndexingConfig

config = IndexingConfig(
    markdown_base_path=Path("output/markdown"),
    force_reindex=False,
    skip_existing_markdown=True,
)

indexer = PdfIndexer(config)

# Index by various methods
indexer.index_by_collection_name("Important Papers")
indexer.index_by_item_id("ABCD1234")
indexer.index_by_item_name("My Paper Title")

# Search
docs = indexer.search("your question", n_results=5)
```


---

## 📖 Usage Examples

### **Example 1: Process a Single PDF**

```python
from pathlib import Path
from src.document_processing.PdfToMarkdown import PdfToMarkdownConverter
from src.document_processing.Chunker import MarkdownChunker
from src.VectorStorage import ChromaStorage

# 1. Convert PDF to markdown
converter = PdfToMarkdownConverter()
md_path = converter.convert("paper.pdf", "output/")

# 2. Chunk the markdown
chunker = MarkdownChunker(chunk_size=1000, chunk_overlap=200)
with open(md_path) as f:
    chunks = chunker.chunk(f.read())

# 3. Add to vector database
storage = ChromaStorage("index.db", "MyCollection")
storage.add_documents([c.page_content for c in chunks])

# 4. Search
results = storage.query(["What is the methodology?"], n_results=3)
```


### **Example 2: Process an Entire Zotero Collection**

```python
from src.ZoteroPdfIndexer import PdfIndexer, IndexingConfig
from pathlib import Path

# Configure indexer
config = IndexingConfig(
    markdown_base_path=Path("output/markdown"),
    force_reindex=False,  # Skip already indexed PDFs
    skip_existing_markdown=True,  # Reuse existing markdown
    chunk_size=1000,
    chunk_overlap=200,
)

# Initialize and index
indexer = PdfIndexer(config)
result = indexer.index_by_collection_name("Important Papers")

print(f"Indexed: {result['success']}")
print(f"Failed: {result['failed']}")
```

### **Example 3: Search with AI Agent**

```python
from src.zotero_retriever_agent import ZoteroRetriever

# Initialize agent
retriever = ZoteroRetriever(
    model_name="gpt-4",
    provider="openai",
    temperature=0.0,
)

# Ask a question
result = retriever.invoke(
    "How was consciousness measured in these studies?",
    thread_id="session-1",
    k_documents=8,
)

# Get response with citations
answer = retriever.get_response(result)
print(answer)
```

### **Example 4: Browse and Search via Streamlit**

```shell script
# Start the web interface
streamlit run src/Frontend/ZoteroPdfIndexerApp.py

# Then:
# 1. Select a collection from the sidebar
# 2. Choose items to index
# 3. Click "Index Selected Items"
# 4. Use the search interface to query your documents
```


---

## ⚠️ Current Limitations & Known Issues

This project is in **alpha stage**. Here's what works and what doesn't:

### **✅ Working**
- Zotero database connection and metadata extraction
- PDF to markdown conversion (via marker-pdf)
- Semantic chunking with metadata preservation
- Vector storage and retrieval with ChromaDB
- Streamlit web interface for indexing
- LangChain agent for retrieval with citations
- Support for both Ollama and OpenAI backends

### **⚙️ Experimental**
- Batch processing of multiple PDFs
- Large collection handling (may be slow)
- Complex query optimization
- LangGraph deployment configuration
- Incremental updates (markdowns are safed and are not re-converted)
- Search UI in Streamlit based on metadata

### **🚧 Not Yet Implemented**

- Multi-document synthesis and comparison
- Advanced RAG techniques (reranking, fusion, etc.)
- Comprehensive test suite
- MCP tool integrations (GitHub, Notion)
- Export functionality (markdown, PDF reports)

### **Known Issues**
1. **Performance**: PDF conversion is slow for large documents (5-10 min per 50-page paper)
2. **Memory**: Processing many PDFs simultaneously may consume significant RAM
3. **Ollama Dependency**: Requires Ollama to be running when using local models; will fail if unavailable
4. **Ollama for marker-pdf is not working**: a problem with the marker-pdf library
5. **Zotero Paths**: Some path formats may not be recognized (especially on Windows)
6. **Error Handling**: Limited graceful degradation in batch operations

---

## 🛣️ Roadmap

### **v0.2 - Core Improvements**
- [ ] Better error handling and logging
- [ ] Progress bars for long operations
- [ ] Incremental updates (process only new/modified PDFs)
- [ ] Performance optimizations
- [ ] Comprehensive test suite

### **v0.3 - Enhanced UI**

- [ ] Search interface in Streamlit app
- [ ] Visualization of retrieved sources
- [ ] Export functionality (markdown, PDF)
- [ ] Collection management features

### **v0.4 - Advanced RAG**
- [ ] Multi-document synthesis
- [ ] Reranking and result fusion
- [ ] Query optimization with LLMs
- [ ] Context-aware chunking strategies

### **v0.5 - Integrations**

- [ ] MCP tool integrations (GitHub, Notion)
- [ ] LangGraph deployment finalization
- [ ] API server mode
- [ ] CLI improvements

### **v1.0 - Production Ready**

- [ ] Full test coverage
- [ ] API documentation
- [ ] Docker deployment
- [ ] Performance benchmarks
- [ ] Production-grade error handling

---

## 🤝 Contributing

Contributions are welcome! This is an early-stage project, so there's plenty to improve.

### **Areas Where Help is Needed**
- Error handling and edge cases
- Performance optimization
- Test coverage (unit and integration tests)
- Documentation improvements
- UI/UX design for Streamlit interface
- Support for additional embedding models

### **Development Setup**

```shell script
# Clone and create branch
git clone https://github.com/yourusername/scico.git
cd scico
git checkout -b feature/your-feature

# Install in development mode with uv
uv sync

# Or with pip
pip install -e .

# Generate project documentation
python system_prompt_generator.py
python directory_tree_generator.py

# Run tests (when available)
pytest tests/
```


---

## 🧰 Scripts and Utilities

- **system_prompt_generator.py** - Generates `LLM_INSTRUCTIONS.md` from project metadata and src tree
- **directory_tree_generator.py** - Renders a markdown tree of project directories
- **Streamlit app** - Web interface: `streamlit run src/Frontend/ZoteroPdfIndexerApp.py`
- **LangGraph CLI** - Agent deployment configuration present in `langgraph.json` (documentation TBD)

---

## 🔍 Troubleshooting

### **Common Issues**

**Chroma database errors:**

- Ensure `VECTOR_STORAGE_PATH` points to a writable location
- Check disk space availability

**Zotero connection problems:**

- Verify `LOCAL_ZOTERO_PATH` points to your Zotero data directory
- Ensure `zotero.sqlite` exists in that directory
- Check file permissions

**PDF conversion failures:**

- `marker-pdf` may need additional system dependencies depending on OS
- Ensure sufficient disk space for temporary files
- Check PDF is not corrupted

**Embeddings/LLM errors:**

- If using Ollama: Make sure the server is running (`ollama serve`) and models are pulled
- If using OpenAI: Verify `OPENAI_API_KEY` is set correctly
- Check `OLLAMA_BASE_URL` or API endpoints are accessible

**Import errors:**

- Ensure virtual environment is activated
- Try reinstalling: `uv sync --force` or `pip install -e . --force-reinstall`
- Check Python version matches 3.13+

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

Built with:
- [Marker](https://github.com/VikParuchuri/marker) - PDF to markdown conversion
- [ChromaDB](https://www.trychroma.com/) - Vector database
- [LangChain](https://www.langchain.com/) - LLM framework and text splitting
- [Ollama](https://ollama.ai) - Local LLM inference
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database ORM
- [Streamlit](https://streamlit.io/) - Web interface
- [LangGraph](https://www.langchain.com/langgraph) - Agent deployment

---

## 📧 Contact & Support

- **Issues**: [GitHub Issues](https://github.com/SoenkevL/scico/issues)
- **Discussions**: [GitHub Discussions](https://github.com/SoenkevL/scico/discussions)

---

## 🎓 Learn More

- Explore the `tutorials/` directory for hands-on examples
- Read inline documentation in each module
- Check `LLM_INSTRUCTIONS.md` for developer context
- See `ProjectDescription.md` and `ResearchWorkflowOverview.md` for background

---

**Status**: This project is in active development. Expect breaking changes between versions.

**Version**: 0.1.0-alpha  
**Last Updated**: 2025-11-10