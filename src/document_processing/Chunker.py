import json
import logging
import os
import uuid
from os import PathLike
from pathlib import Path
from pprint import pformat
from typing import Optional

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from src.configs.Chunker_config import MarkdownToChunksConfig

logger = logging.getLogger(__name__)
CONFIG = MarkdownToChunksConfig()


def _markdown_semantic_splitter(
) -> list[Document]:
    """
    Uses a semantic splitter to split the plaintextstring into chunks of langchain Documents
    """
    # embedding = OllamaEncoder(name='nomic-embed-text')
    # semantic_splitter = StatisticalChunker(embedding)
    # splits: list[Document] = semantic_splitter(docs=[plaintextstring])
    # return splits
    return []


def _markdown_recursive_splitter(
        plaintextstring: str, config: MarkdownToChunksConfig
) -> list[Document]:
    """
    uses a combination of markdown header text splitter and recursive character text splitter to split a markdown file into chunks
    :param plaintextstring: string of the markdown file
    :param config: configuration file to use for the chunking, must be of type MarkdownToChunksConfig
    :return: a list of chunks as langchain documents
    """
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=config.headers_to_split_on, return_each_line=True
    )
    text_splitter = RecursiveCharacterTextSplitter(
        separators=config.seperators,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
    )
    # Split
    md_header_splits = markdown_splitter.split_text(plaintextstring)
    splits = text_splitter.split_documents(md_header_splits)
    return splits


def _numerate_splits(splits: Optional[list[Document]] = None) -> list[Document]:
    """
    add a split_id to every split in the order of the content in the markdown string
    """
    if not splits:
        raise Exception("No splits found. Please run chunk() first.")
    for i, split in enumerate(splits):
        split.metadata["split_id"] = i
    return splits


def _add_uid_to_splits(splits: Optional[list[Document]] = None) -> list[Document]:
    """
    adds a unique id to each split
    """
    if not splits:
        raise Exception("No splits found. Please run chunk() first.")
    for split in splits:
        split.id = str(uuid.uuid4().hex)
    return splits


def _add_length_to_splits(splits: Optional[list[Document]] = None) -> list[Document]:
    """
    adds the length in characters as an attribute to the splits metadata
    """
    if not splits:
        raise Exception("No splits found. Please run chunk() first.")
    for split in splits:
        split.metadata["length"] = len(split.page_content)
    return splits


def _annotate_tables_splits(splits: Optional[list[Document]] = None) -> list[Document]:
    """
    annotates the metadata with a boolean field indicating if a chunk consists a table as content
    """
    if not splits:
        raise Exception("No splits found. Please run chunk() first.")
    # preprocess_chunks to combine and find tables
    last_chunk_table = False
    table_counter = 0
    for chunk in splits:
        content = chunk.page_content
        # check if we are in t table
        if content.startswith("|"):
            # check if we already were in a table
            if last_chunk_table:
                # we are still in the same table
                chunk.metadata["table"] = table_counter
            else:
                # we are starting a new table
                table_counter += 1
                chunk.metadata["table"] = table_counter
            last_chunk_table = True
        else:
            # we are not in a table
            last_chunk_table = False
            chunk.metadata["table"] = False
    return splits


def _add_additional_metadata(
        metadata: dict, splits: Optional[list[Document]] = None
) -> list[Document]:
    """
    adds additional metadata to the splits
    """
    if not splits:
        raise Exception("No splits found. Please run chunk() first.")
    for split in splits:
        split.metadata = {**split.metadata, **metadata}
    return splits


def _load_markdown(md_path: PathLike) -> str:
    """
    function to load a markdown from a path to a string
    """
    with open(md_path, "r") as md:
        f = md.read()
    return f


def chunk(
        md_path: PathLike,
        config: MarkdownToChunksConfig = CONFIG,
        metadata: Optional[dict] = None,
) -> list[Document]:
    """
    function to convert a markdown file into chunks for vectorization
    """
    logger.info(f"Chunking Markdown file: {md_path}")
    md_string = _load_markdown(md_path)
    if config.method == "markdown+recursive":
        splits = _markdown_recursive_splitter(md_string, config)
    elif config.method == "semantic":
        splits = _markdown_semantic_splitter(md_string, config)
    else:
        logger.error(f"Invalid method: {config.method}")
        raise Exception(
            "Invalid method. Please choose from 'markdown+recursive' or 'markdown+semantic'"
        )
    # Annotate splits
    if config.add_uid:
        splits = _add_uid_to_splits(splits)
    if config.annotate_tables:
        splits = _annotate_tables_splits(splits)
    if config.numerate_splits:
        splits = _numerate_splits(splits)
    if config.add_length_to_splits:
        splits = _add_length_to_splits(splits)
    if metadata:
        splits = _add_additional_metadata(metadata, splits)
    return splits


# save the splits to a file
def save_splits_to_txt(splits: list[Document], path: Path) -> None:
    """Saves the list of Documents into a txt at path"""
    outname = Path("chunks.txt")
    if not str(path).endswith(".txt"):
        outpath = path / outname
    else:
        outpath = path

    with open(outpath, "w") as f:
        for split in splits:
            f.write(pformat(split, indent=4, compact=True))
            f.write("\n")


def save_splits_to_json(splits: list[Document], path: Path) -> None:
    """saves the list of Documents into a json file at path"""
    if str(path).endswith(".json"):
        outpath = path
    else:
        outpath = path / "chunks.json"
    json.dump(splits, open(outpath, "w"), indent=4)


def main():
    import argparse

    # Create argument parser
    parser = argparse.ArgumentParser(description="Chunk Markdown File")

    # Add required argument for PDF file path
    parser.add_argument(
        "--markdown",
        type=str,
        required=True,
        help="Path to the markdown file to be converted",
    )

    # Add optional argument for output directory
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to the outputfile, defaults to chunks.json in markdown folder",
    )

    # Parse arguments
    args = parser.parse_args()
    splits = chunk(args.markdown)
    save_splits_to_json(splits, os.path.basename(args.markdown))


if __name__ == "__main__":
    main()
