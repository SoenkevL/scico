import json
import logging
import os
import uuid
from os import PathLike
from pprint import pformat
from typing import Optional

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from semantic_chunkers.chunkers import StatisticalChunker
from semantic_router.encoders import OllamaEncoder

from src.utils.configs import headers_to_split_on

logger = logging.getLogger(__name__)

class MarkdownChunker:

    def __init__(self, md_path: PathLike = None, chunk_size: int = 1000, chunk_overlap: int = 50):
        self.md_path: str = str(md_path)
        self.headers_to_split_on = headers_to_split_on
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.splits = None
        logger.info("MarkdownChunker initialized")

    def set_markdown(self, md_path: PathLike):
        self.md_path = str(md_path)

    def chunk(self, md_path: PathLike = None, method: str = 'markdown+recursive', add_uid: bool = True,
              annotate_tables: bool = True, numerate_splits: bool = True, add_length_to_splits: bool = True,
              metadata: Optional[dict] = None):
        md_path = md_path if md_path else self.md_path
        logger.info(f"Chunking Markdown file: {md_path}")
        plaintextstring = self._load_markdown(md_path)
        if method=='markdown+recursive':
            #initialize splitters
            markdown_splitter = MarkdownHeaderTextSplitter(
                headers_to_split_on=self.headers_to_split_on,
                return_each_line=True
            )
            text_splitter = RecursiveCharacterTextSplitter(
                separators=["\n", '.', '!', '?', ',', ';'],
                chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap
            )
            # Split
            md_header_splits = markdown_splitter.split_text(plaintextstring)
            splits = text_splitter.split_documents(md_header_splits)
        elif method == 'semantic':
            embedding = OllamaEncoder(name='nomic-embed-text')
            semantic_splitter = StatisticalChunker(embedding)
            splits: list[Document] = semantic_splitter(docs=[plaintextstring])
        else:
            logger.error(f"Invalid method: {method}")
            raise Exception("Invalid method. Please choose from 'markdown+recursive' or 'markdown+semantic'")
        # Annotate splits
        if add_uid:
            splits = self._add_uid_to_splits(splits)
        if annotate_tables:
            splits = self._annotate_tables_splits(splits)
        if numerate_splits:
            splits = self._numerate_splits(splits)
        if add_length_to_splits:
            splits = self._add_length_to_splits(splits)
        if metadata:
            splits = self._add_additional_metadata(metadata, splits)
        self.splits = splits
        return splits

    # save the splits to a file
    def save_splits_to_txt(self, splits: Optional[list[Document]] = None):
        splits = splits if splits else self.splits
        mdpath, mdname = os.path.split(self.md_path)
        outname = 'chunks.txt'
        outpath = os.path.join(mdpath, outname)
        with open(outpath, 'w') as f:
            for split in splits:
                f.write(pformat(split, indent=4, compact=True))
                f.write('\n')

    def save_splits_to_json(self, splits: Optional[list[Document]] = None):
        splits = splits if splits else self.splits
        mdpath, mdname = os.path.split(self.md_path)
        outname = 'chunks.json'
        outpath = os.path.join(mdpath, outname)
        json.dump(splits, open(outpath, 'w'), indent=4)

    def _numerate_splits(self, splits: Optional[list[Document]] = None) -> Optional[list[Document]]:
        splits = splits if splits else self.splits
        if not splits:
            raise Exception("No splits found. Please run chunk() first.")
        for i, split in enumerate(splits):
            split.metadata['split_id'] = i
        return splits

    def _add_uid_to_splits(self, splits: Optional[list[Document]] = None) -> Optional[list[Document]]:
        splits = splits if splits else self.splits
        if not splits:
            raise Exception("No splits found. Please run chunk() first.")
        for split in splits:
            split.id = str(uuid.uuid4().hex)
        return splits

    def _add_length_to_splits(self, splits: Optional[list[Document]] = None) -> Optional[list[Document]]:
        splits = splits if splits else self.splits
        if not splits:
            raise Exception("No splits found. Please run chunk() first.")
        for split in splits:
            split.metadata['length'] = len(split.page_content)
        return splits

    def _annotate_tables_splits(self, splits: Optional[list[Document]] = None) -> Optional[list[Document]]:
        splits = splits if splits else self.splits
        if not splits:
            raise Exception("No splits found. Please run chunk() first.")
        # preprocess_chunks to combine and find tables
        last_chunk_table = False
        table_counter = 0
        for chunk in splits:
            content = chunk.page_content
            # check if we are in t table
            if content.startswith('|'):
                # check if we already were in a table
                if last_chunk_table:
                    # we are still in the same table
                    chunk.metadata['table'] = table_counter
                else:
                    # we are starting a new table
                    table_counter += 1
                    chunk.metadata['table'] = table_counter
                last_chunk_table = True
            else:
                # we are not in a table
                last_chunk_table = False
                chunk.metadata['table'] = False
        return splits

    def _add_additional_metadata(self, metadata, splits: Optional[list[Document]] = None) -> Optional[list[Document]]:
        splits = splits if splits else self.splits
        if not splits:
            raise Exception("No splits found. Please run chunk() first.")
        for split in splits:
            split.metadata = {**split.metadata, **metadata}
        return splits

    def _load_markdown(self, md_path: PathLike) -> str:
        md_path = md_path if md_path else self.md_path
        with open(md_path, 'r') as md:
            f = md.read()
        return f


def main():
    import argparse
    # Create argument parser
    parser = argparse.ArgumentParser(description='Chunk Markdown File')

    # Add required argument for PDF file path
    parser.add_argument('--markdown', type=str, required=True,
                        help='Path to the PDF file to be converted')

    # Add optional argument for output directory
    parser.add_argument('--output', type=str, default=None,
                        help='Path to the outputfile, defaults to chunk.txt in markdown folder')

    # Parse arguments
    args = parser.parse_args()
    chunker = MarkdownChunker(md_path=args.markdown)
    splits = chunker.chunk()
    chunker.save_splits_to_json(splits)

if __name__ == '__main__':
    main()
