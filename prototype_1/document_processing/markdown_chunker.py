"""Chunk markdown documents into smaller segments for vector embedding"""
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from pathlib import Path
import argparse


class MarkdownChunker:
    """
    Splits markdown documents into smaller chunks for processing and indexing.
    
    This class handles the loading and intelligent chunking of markdown content,
    preserving document structure through headers while creating manageable segments.
    """
    
    def __init__(self, chunk_size=500, chunk_overlap=50):
        """
        Initialize the markdown chunker with chunking parameters.
        
        Args:
            chunk_size: Target size for each chunk
            chunk_overlap: Overlap between adjacent chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.headers_to_split_on = [
            ("#", "title"),
            ("##", "section"),
            ("###", "subsection"),
        ]
        
    def load_markdown(self, md_path):
        """
        Load markdown content from a file.
        
        Args:
            md_path: Path to markdown file
            
        Returns:
            str: Content of the markdown file
        """
        md_path = Path(md_path)
        if not md_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {md_path}")
            
        try:
            with open(md_path, 'r', encoding='utf-8') as md_file:
                return md_file.read()
        except Exception as e:
            raise IOError(f"Error reading markdown file: {e}")
            
    def chunk(self, content=None, md_path=None, method='markdown+recursive'):
        """
        Split markdown content into chunks.
        
        Args:
            content: Markdown content as string (optional if md_path provided)
            md_path: Path to markdown file (optional if content provided)
            method: Chunking method to use
            
        Returns:
            list: List of document chunks with metadata
        """
        if content is None and md_path is None:
            raise ValueError("Either content or md_path must be provided")
            
        if content is None:
            content = self.load_markdown(md_path)
            
        if method == 'markdown+recursive':
            # Initialize splitters
            markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=self.headers_to_split_on)
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size, 
                chunk_overlap=self.chunk_overlap
            )
            
            # Split by headers first, then by chunk size
            md_header_splits = markdown_splitter.split_text(content)
            splits = text_splitter.split_documents(md_header_splits)
            return splits
        else:
            raise ValueError(f"Unsupported chunking method: {method}")
            
    def chunk_file(self, md_path, method='markdown+recursive'):
        """
        Convenience method to chunk a markdown file directly.
        
        Args:
            md_path: Path to markdown file
            method: Chunking method to use
            
        Returns:
            list: List of document chunks with metadata
        """
        return self.chunk(md_path=md_path, method=method)


def main():
    """Command-line interface for markdown chunking"""
    parser = argparse.ArgumentParser(description="Split markdown into chunks for indexing")
    parser.add_argument("--file", required=True, help="Path to markdown file")
    parser.add_argument("--size", type=int, default=500, help="Target chunk size")
    parser.add_argument("--overlap", type=int, default=50, help="Chunk overlap size")
    
    args = parser.parse_args()
    
    chunker = MarkdownChunker(chunk_size=args.size, chunk_overlap=args.overlap)
    chunks = chunker.chunk_file(args.file)
    
    print(f"Split markdown into {len(chunks)} chunks")
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i+1}:")
        print(f"  Metadata: {chunk.metadata}")
        print(f"  Content preview: {chunk.page_content[:50]}...")


if __name__ == "__main__":
    main()
