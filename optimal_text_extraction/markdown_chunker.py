from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter


class MarkdownChunker:
    def load_markdown(self, md_path):
        md_path = md_path if md_path else self.md_path
        with open(md_path, 'r') as md:
            f = md.read()
        return f

    def __init__(self, md_path=None):
        self.md_path: str = str(md_path) if md_path else None
        self.headers_to_split_on = [
            ("#", "title"),
            ("##", "section"),
            ("###", "subsection"),
        ]
        self.chunk_size = 500
        self.chunk_overlap = 50



    def chunker(self, md_path=None, method='markdown+recursive'):
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
            return splits
        else:
            return None

