import json
import os
import uuid
from pprint import pformat
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from configs import headers_to_split_on

class MarkdownChunker:
    def load_markdown(self, md_path):
        md_path = md_path if md_path else self.md_path
        with open(md_path, 'r') as md:
            f = md.read()
        return f

    def __init__(self, md_path=None, chunk_size=150, chunk_overlap=50):
        self.md_path: str = str(md_path) if md_path else None
        self.headers_to_split_on = headers_to_split_on
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.splits = None

    def chunk(self, md_path=None, method='markdown+recursive'):
        md_path = md_path if md_path else self.md_path
        plaintextstring = self.load_markdown(md_path)
        if method=='markdown+recursive':
            #initialize splitters
            markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=self.headers_to_split_on)
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap
            )
            # Split
            md_header_splits = markdown_splitter.split_text(plaintextstring)
            splits = text_splitter.split_documents(md_header_splits)
            splits = self.add_metadata_to_splits_and_convert_to_dict(splits)
            self.splits = splits
            return splits
        else:
            return None

    def add_metadata_to_splits_and_convert_to_dict(self, splits):
        new_splits = []
        for i, split in enumerate(splits):
            split_metadata = split.metadata
            additonal_metadata = {
                'filename': os.path.basename(self.md_path),
                'split_id': i,
            }
            metadata = {**split_metadata, **additonal_metadata}
            new_split = {
                'split_uid': str(uuid.uuid4().hex),
                'page_content': split.page_content,
                'metadata': metadata
            }
            new_splits.append(new_split)
        return new_splits



    def save_splits_to_txt(self, splits=None):
        splits = splits if splits else self.splits
        mdpath, mdname = os.path.split(self.md_path)
        outname = 'chunks.txt'
        outpath = os.path.join(mdpath, outname)
        with open(outpath, 'w') as f:
            for split in splits:
                f.write(pformat(split, indent=4, compact=True))
                f.write('\n')


    def save_splits_to_json(self, splits=None):
        splits = splits if splits else self.splits
        mdpath, mdname = os.path.split(self.md_path)
        outname = 'chunks.json'
        outpath = os.path.join(mdpath, outname)
        json.dump(splits, open(outpath, 'w'), indent=4)

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
