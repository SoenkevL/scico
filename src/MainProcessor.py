# Main class that handles the user interaction and orchestration
import json
import os
from pprint import pprint

from dotenv import load_dotenv
from PdfToMarkdown import convert_pdf_to_markdown
from MarkdownChunker import MarkdownChunker
from VectorStorage import ChromaStorage


class MainProcessor:
    def __init__(self, collection_name=None):
        load_dotenv()
        self.zotero_library_path = os.getenv('ZOTERO_LIBRARY_PATH')
        self.markdown_folder_path = os.getenv('MARKDOWN_FOLDER_PATH')
        self.index_path = os.getenv('INDEX_PATH')
        self.storage = ChromaStorage(self.index_path, collection_name)

    def query_vector_storage(self, query):
        return self.storage.query(query)

    def add_chunks_to_vector_storage(self, chunks):
        self.storage.add_documents(chunks)

    @staticmethod
    def chunk_list_from_json(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            chunk_dicts = json.load(f)
        return chunk_dicts

    def refresh_library(self):
        pass

    def add_pdf(self):
        pass

    def remove_pdf(self):
        pass

    def search_pdf(self):
        pass

    def show_library(self):
        pass

    def exit_program(self):
        pass

def main():
    load_dotenv()
    processor = MainProcessor(os.getenv('COLLECTION_NAME'))
    chunklist = processor.chunk_list_from_json('exampleMarkdown/Chapter Summary - Criticality of Resting-State EEG as a Predictor of Perturbational Complexity and Consciousness Levels During Anesthesia/chunks.json'
                                            )
    processor.add_chunks_to_vector_storage(chunklist)
    answer = (processor.query_vector_storage('What is criticality'))
    pprint(answer)

# loop while waiting of user input
# chatbot commandline interface
    # what is the question of the user
    # optimize for RAG retrieval using llm
    # send request to RAG System
    # summarize sources or retrieve sources

    #keywords:
    # - refresh [library] : re-index the library
    # - add [pdf] : add a pdf to the library
    # - remove [pdf] : remove a pdf from the library
    # - search [question] : search the library for a pdf that answers the question
    # - show [library] : show the library
    # - exit : exit the program




if __name__ == "__main__":
    main()