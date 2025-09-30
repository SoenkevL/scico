# 🔬 SciCO - Scientific Co-worker

**A RAG-powered system for semantic search and retrieval from your Zotero library**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

---

## 🎯 What is SciCO?

SciCO transforms your Zotero library into an intelligent, searchable knowledge base using Retrieval-Augmented Generation (RAG). Instead of manually searching through dozens of papers, ask questions in natural language and get relevant excerpts from your sources.

### **Key Features**

✅ **Zotero Integration** - Direct connection to your Zotero SQLite database  
✅ **PDF Processing** - Converts PDFs to structured markdown with `marker`  
✅ **Semantic Search** - Uses ChromaDB for vector-based retrieval  
✅ **Metadata Extraction** - Preserves authors, DOI, tags, and collections  
✅ **Interactive Tutorial** - Jupyter notebook to learn the system step-by-step  

---

## 📦 Installation

### **Prerequisites**

1. **Ollama** - Required for PDF processing
   ```bash
   # Install from https://ollama.ai
   # Start Ollama server
   ollama serve
   ```

2. **Zotero** - With an existing library
   - Locate your Zotero data directory (usually `~/Zotero`)
   - Ensure `zotero.sqlite` exists in this directory

3. **Python 3.13+** with virtualenv

### **Setup**

```bash
# Clone the repository
git clone https://github.com/yourusername/scico.git
cd scico

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```


### **Required Python Packages**

```
beautifulsoup4
click
jinja2
kubernetes
networkx
numpy
pillow
protobuf
pyyaml
requests
scikit-learn
scipy
six
sqlalchemy
sympy
chromadb
langchain-text-splitters
marker-pdf
python-dotenv
```


---

## ⚙️ Configuration

Create a `.env` file in the project root:

```
# Name of your Zotero collection to process
COLLECTION_NAME='Your Collection Name'

# Output folder for markdown files
MARKDOWN_FOLDER_PATH='/path/to/markdown/output'

# Path to your Zotero data folder (contains zotero.sqlite)
ZOTERO_LIBRARY_PATH='/path/to/Zotero'

# Path for the ChromaDB vector database
INDEX_PATH='/path/to/chroma.db'

# (Optional) Test PDF for development
TEST_PDF_PATH='/path/to/test/paper.pdf'
```


### **Finding Your Zotero Path**

- **macOS**: `~/Zotero/`
- **Windows**: `C:\Users\YourName\Zotero\`
- **Linux**: `~/Zotero/`

Inside this folder, you should see `zotero.sqlite`.

---

## 🚀 Quick Start

### **Option 1: Interactive Tutorial (Recommended)**

The easiest way to get started:

```shell script
jupyter notebook SciCO_Interactive_Tutorial.ipynb
```


This notebook walks you through:
1. Configuration validation
2. Connecting to Zotero
3. Processing a sample PDF
4. Creating embeddings
5. Performing semantic searches

### **Option 2: Command Line**

```python
from pathlib import Path
from MainProcessor import MainProcessor
import os

# Initialize processor
processor = MainProcessor(collection_name="YourCollection")

# Query your knowledge base
results = processor.query_vector_storage(
    ["What is the main hypothesis?"],
    n_results=5
)

# Display results
for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
    print(f"Source: {meta['filename']}")
    print(f"Content: {doc[:200]}...\n")
```


---

## 📚 Project Structure

```
scico/
├── src/
│   ├── ZoteroIntegration.py      # SQLite database connector
│   ├── PdfToMarkdown.py          # PDF → Markdown conversion
│   ├── MarkdownChunker.py        # Text splitting & chunking
│   ├── VectorStorage.py          # ChromaDB wrapper
│   ├── MainProcessor.py          # Orchestration layer
│   ├── configs.py                # Configuration settings
│   ├── Logger.py                 # Logging utilities
│   └── RAGQuestionOptimizer.py   # [WIP] Query optimization
│
├── SciCO_Interactive_Tutorial.ipynb  # Step-by-step guide
├── .env                              # Your configuration (create this)
└── README.md                         # This file
```


---

## 🔧 Components

### **1. ZoteroIntegration**

Connects to your Zotero SQLite database and retrieves:
- PDF file paths from collections
- Metadata (title, authors, DOI, abstract, tags)
- Citation keys (Better BibTeX support)

```python
from ZoteroIntegration import ZoteroMetadataRetriever

retriever = ZoteroMetadataRetriever(Path("/path/to/Zotero"))
retriever.initialize()

# Get all PDFs in a collection
pdfs = retriever.get_pdfs_in_collection("My Papers")

# Get full metadata for a specific PDF
metadata = retriever.get_metadata_for_pdf(Path("/path/to/paper.pdf"))
```


### **2. PdfToMarkdown**

Uses `marker` library with Ollama to convert PDFs to structured markdown:
- Preserves formatting and structure
- Extracts images
- Uses LLM for enhanced OCR and layout understanding

```python
from PdfToMarkdown import convert_pdf_to_markdown

convert_pdf_to_markdown(
    pdf_path="/path/to/paper.pdf",
    output_path="/path/to/output"
)
```


### **3. MarkdownChunker**

Splits markdown into semantic chunks using:
- Header-based splitting (H1-H7)
- Recursive character splitting
- Configurable chunk size and overlap

```python
from MarkdownChunker import MarkdownChunker

chunker = MarkdownChunker(
    md_path="paper.md",
    chunk_size=150,
    chunk_overlap=50
)
chunks = chunker.chunk(method='markdown+recursive')
```


### **4. VectorStorage**

ChromaDB wrapper for embedding and retrieval:
- Automatic embedding generation
- Persistent storage
- Semantic similarity search

```python
from VectorStorage import ChromaStorage

storage = ChromaStorage(
    index_path="/path/to/chroma.db",
    collection_name="MyCollection"
)

# Add documents
storage.add_documents(chunks)

# Query
results = storage.query(
    query_texts=["What are the main findings?"],
    n_results=5
)
```


### **5. MainProcessor**

High-level orchestration class that ties everything together.

```python
from MainProcessor import MainProcessor

processor = MainProcessor(collection_name="Papers")
results = processor.query_vector_storage(["your question"])
```


---

## 📖 Usage Examples

### **Example 1: Process a Single PDF**

```python
from pathlib import Path
from PdfToMarkdown import convert_pdf_to_markdown
from MarkdownChunker import MarkdownChunker
from VectorStorage import ChromaStorage

# 1. Convert PDF to markdown
convert_pdf_to_markdown("paper.pdf", "output/")

# 2. Chunk the markdown
chunker = MarkdownChunker("output/paper/paper.md")
chunks = chunker.chunk()

# 3. Add to vector database
storage = ChromaStorage("index.db", "MyCollection")
storage.add_documents(chunks)

# 4. Search
results = storage.query(["What is the methodology?"], n_results=3)
```


### **Example 2: Process an Entire Zotero Collection**

```python
from ZoteroIntegration import ZoteroMetadataRetriever
from MainProcessor import MainProcessor
import os

# Get all PDFs from a collection
retriever = ZoteroMetadataRetriever(Path(os.getenv('ZOTERO_LIBRARY_PATH')))
retriever.initialize()
pdfs = retriever.get_pdfs_in_collection("Important Papers")

# Process each PDF (see Interactive Tutorial for full implementation)
processor = MainProcessor("Important Papers")

for pdf in pdfs:
    if pdf['pdf_path']:
        # Convert, chunk, and add to vector DB
        # (implementation in tutorial notebook)
        pass
```


### **Example 3: Search and Display Results**

```python
storage = ChromaStorage("index.db", "MyCollection")

query = "How was consciousness measured?"
results = storage.query([query], n_results=5)

for doc, metadata, distance in zip(
    results['documents'][0],
    results['metadatas'][0],
    results['distances'][0]
):
    similarity = 1 / (1 + distance)
    print(f"Similarity: {similarity:.2%}")
    print(f"Source: {metadata['filename']}")
    print(f"Content: {doc[:300]}...\n")
```


---

## ⚠️ Current Limitations & Known Issues

This project is in **alpha stage**. Here's what works and what doesn't:

### **✅ Working**
- Zotero database connection and metadata extraction
- PDF to markdown conversion (via Ollama + marker)
- Semantic chunking with metadata preservation
- Vector storage and retrieval with ChromaDB
- Basic query functionality

### **⚙️ Experimental**
- Batch processing of multiple PDFs
- Large collection handling (may be slow)
- Complex query optimization

### **🚧 Not Yet Implemented**
- `RAGQuestionOptimizer.py` - Query refinement with LLMs
- Answer generation with citations
- Multi-document synthesis
- Advanced RAG techniques (reranking, fusion, etc.)
- Web interface (Streamlit/Gradio)
- Incremental updates (must reprocess entire PDFs)

### **Known Issues**
1. **Performance**: PDF conversion is slow for large documents (5-10 min per 50-page paper)
2. **Memory**: Processing many PDFs simultaneously may consume significant RAM
3. **Ollama Dependency**: Requires Ollama to be running; will fail if unavailable
4. **Zotero Paths**: Some path formats may not be recognized (especially on Windows)
5. **Error Handling**: Limited graceful degradation in batch operations

---

## 🛣️ Roadmap

### **v0.2 - Core Improvements**
- [ ] Better error handling and logging
- [ ] Progress bars for long operations
- [ ] Incremental updates (process only new PDFs)
- [ ] Performance optimizations

### **v0.3 - Enhanced RAG**
- [ ] Query optimization with LLMs
- [ ] Answer generation with source citations
- [ ] Multi-document synthesis
- [ ] Reranking and result fusion

### **v0.4 - User Interface**
- [ ] Web interface (Streamlit)
- [ ] Chat-like interface
- [ ] Visualization of retrieved sources
- [ ] Export functionality (markdown, PDF)

### **v1.0 - Production Ready**
- [ ] Comprehensive test suite
- [ ] API documentation
- [ ] Docker deployment
- [ ] Performance benchmarks

---

## 🤝 Contributing

Contributions are welcome! This is an early-stage project, so there's plenty to improve.

### **Areas Where Help is Needed**
- Error handling and edge cases
- Performance optimization
- Documentation improvements
- Test coverage
- UI/UX design for web interface

### **Development Setup**

```shell script
# Clone and create branch
git clone https://github.com/yourusername/scico.git
cd scico
git checkout -b feature/your-feature

# Install in development mode
pip install -e .

# Run tests (when available)
pytest tests/
```


---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

Built with:
- [Marker](https://github.com/VikParuchuri/marker) - PDF to markdown conversion
- [ChromaDB](https://www.trychroma.com/) - Vector database
- [Ollama](https://ollama.ai) - Local LLM inference
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database ORM
- [LangChain](https://www.langchain.com/) - Text splitting utilities

---

## 📧 Contact & Support

- **Issues**: [GitHub Issues](https://github.com/SoenkevL/scico/issues)
- **Discussions**: [GitHub Discussions](https://github.com/SoenkevL/scico/discussions)

---

## 🎓 Learn More

- See `SciCO_Interactive_Tutorial.ipynb` for a hands-on walkthrough
- Read inline documentation in each module

---

**Status**: This project is in active development. Expect breaking changes between versions.

**Version**: 0.1.0-alpha  
**Last Updated**: 2025-09-30
