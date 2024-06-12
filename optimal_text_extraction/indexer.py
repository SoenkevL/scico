import os
import argparse
import numpy as np
import yaml
from txtai import Embeddings
from icecream import ic
import markdown_chunker


class Indexer:

    def initialize_embeddings(self):
        embeddings = Embeddings({
            "autoid": "uuid5",
            "path": "intfloat/e5-base",
            "instructions": {
                "query": "query: ",
                "data": "passage: "
            },
            "content": True,
            "graph": {
                "approximate": False,
                "topics": {}
            }
        })
        return embeddings

    def __init__(self, index_path):
        self.index_path = index_path
        self.embeddings = self.initialize_embeddings()
        self.current_graph = None
        pass

    def create_vector_storage(self):
        pass

    def load_vector_storage(self):
        pass

    def check_if_in_vector_storage(self):
        pass

    def index_into_vector_storage(self):
        pass

    def vector_storage_from_prepared_zotero_storage(self, storage_path):
        self.embeddings.index(self.stream(storage_path))
        self.embeddings.save(self.index_path)
        pass

    def graph_from_prompt(self, prompt_for_graph, context_limit):
        self.current_graph = self.embeddings.search(prompt_for_graph, limit=context_limit, graph=True)

    def load_embeddings(self):
        self.embeddings.load(self.index_path)

    def load_yaml_to_dict(self, yaml_path):
        with open(yaml_path, 'r') as f:
            yaml_dict = dict(yaml.safe_load(f))
        return yaml_dict

    def markdown_from_pdf_path(self, pdf_path):
        ic(pdf_path)
        pdf_name = pdf_path.split('/')[-1].split('.pdf')[0]
        markdown_folder_path = pdf_path.split('.pdf')[0]
        markdown_file_path = f'{markdown_folder_path}/{pdf_name}.md'
        return markdown_folder_path, markdown_file_path

    def parse_zotero_metadata_scico(self, metadata_dict):
        title, pdf_name, published, publication, authors, reference, path = (
            None,
            None,
            None,
            None,
            None,
            None,
            None
        )
        if metadata_dict:
            for key, item in metadata_dict.items():
                if key == 'title':
                    title = item
                elif key == 'date':
                    published = item
                elif key == 'authors':
                    authors = item
                elif key == 'publicationTitle':
                    publication = item
                elif key == 'DOI':
                    reference = item

        return {'title':title, 'published':published, 'publication':publication, 'authors':authors, 'reference':reference}

    def stream(self, zotero_storage_path):
        document_idx = 0
        #initialize the extractor
        chunker = markdown_chunker.MarkdownChunker()
        #go through the path checking all subdirs for pdf files
        for root, dirs, files in os.walk(zotero_storage_path):
            for f in files:
                fpath = os.path.join(root, f)
                # Only accept documents
                if f.endswith(("pdf")):
                    document_idx = document_idx + 1
                    print(f"Indexing {fpath}")
                    try:
                        zotero_metadata = self.load_yaml_to_dict(ic(os.path.join(root, 'meta_data.yaml')))
                    except Exception as e:
                        ic(f'No metadata found \n {e}')
                        zotero_metadata = self.parse_zotero_metadata_scico(None)
                    _, md_file = self.markdown_from_pdf_path(fpath)
                    for i, paragraph in enumerate(chunker.chunker(md_file)):
                        # create a custom id for the paragraph
                        uid = self.create_uid_from_ducment_and_paragraph_id(document_idx, i)
                        # connect to zotero
                        meta_data = self.fuse_meta_data(paragraph_meta=paragraph.metadata, zotero_meta=zotero_metadata)
                        yield uid, paragraph.page_content, str(meta_data)

    def fuse_meta_data(self, paragraph_meta, zotero_meta):
        return {**paragraph_meta, **zotero_meta}

    def return_context_string(self):
        chunks = []
        for x in list(self.current_graph.centrality().keys())[:10]:
            text = self.current_graph.node(x)["text"]
            ref = self.embeddings.search("select tags from txtai where indexid = :id", limit=1, parameters={"id": x})[0][
                'tags']
            chunks.append(f"{'-' * 20}\n<TEXT>:\n{text}\n<METADATA_FOR_TEXT>:\n{ref}")
        text = "\n".join(chunks)
        return text

    def ask(self, question):
        self.graph_from_prompt(question, 1100)
        return self.return_context_string()

    def create_uid_from_ducment_and_paragraph_id(self, document_idx, paragraph_idx):
        if paragraph_idx < 2**16:
            return document_idx * 2**16 + paragraph_idx
        else:
            raise('paragraph idx is too high')

    def get_document_and_paragraph_id_from_uid(self, uid):
        document_idx = uid % (2**16)
        paragraph_idx = np.max(0, uid - document_idx * 2**16)
        return document_idx, paragraph_idx


if __name__ == '__main__':
    ic.enable()
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--index_path", help="path to the index folder")
    args = parser.parse_args()
    path = args.index_path
    indexer = Indexer('./index')
    indexer.vector_storage_from_prepared_zotero_storage('/home/soenke/DataspellProjects/scico/optimal_text_extraction/example_bib')
    indexer.load_embeddings()
    print(indexer.ask('What is an invariant feature'))
    print(f'\n{"="*30}'*5)
    print(indexer.ask('What is cross frequency coupling'))


