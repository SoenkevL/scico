import os
import argparse
import numpy as np
import pandas as pd
import yaml
from txtai import Embeddings
from icecream import ic
import markdown_chunker
import ast

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
        if '.' in pdf_name:
            pdf_folder_path = '/'.join(pdf_path.split('/')[:-1])
            mardkown_folder_name = pdf_name.split('.')[0]
            markdown_folder_path = os.path.join(pdf_folder_path, mardkown_folder_name)
        else:
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

    def return_context_df(self):
        df = pd.DataFrame()
        for x in list(self.current_graph.centrality().keys())[:10]:
            ref = self.embeddings.search("select id, tags, text from txtai where indexid = :id", limit=1, parameters={"id": x})[0]
            ref_dict = ast.literal_eval(ref['tags'])
            ref_dict['text'] = ref['text']
            ref_dict['id'] = ref['id']
            ref_dict['index'] = 0
            ref_dict = {key: [value] for key, value in ref_dict.items()}
            temp_frame = pd.DataFrame.from_dict(ref_dict)
            if df.empty:
                df = temp_frame
            else:
                df = pd.concat([df, temp_frame], axis=0, ignore_index=True)
        return df.reset_index(drop=True).drop(columns='index')

    def extract_title_from_name(self, df):
        title = df['title']
        pdf_name = df['pdf_name']
        if title:
            return title
        else:
            return pdf_name.split('.pdf')[0]

    def format_context_df(self, df):
        df = df.loc[:, ['id', 'title', 'pdf_name', 'section', 'text', 'authors', 'reference']]
        df['title'] = df[['title', 'pdf_name']].apply(self.extract_title_from_name, axis=1)
        return df.set_index(['pdf_name', 'section', 'id']).sort_index()

    def formatted_context_string_from_formatted_df(self, df):
        intro = (f'<BEGIN_CONTEXT>'
                 f'\n This string contains scientifically valid information in order to answer the above question'
                 f'\n It is structured on three levels namely the paper it was taken from,'
                 f'the section and the text from the section'
                 f'\n {"-"*30}')
        current_pdf = None
        current_section = None
        context_string_array = [intro]
        for index in df.index:
            pdf, section, id = index
            if not pdf == current_pdf:
                if current_pdf:
                    context_string_array.append(f'<end_paper>')
                context_string_array.append(f'<begin_paper>: {pdf}')
                current_pdf = pdf
            if not section == current_section:
                if current_section:
                    context_string_array.append(f'\t<end_section>')
                context_string_array.append(f'\t<begin_section>: {section}')
                current_section = section
            context_string_array.append(f'\t\t<begin_text>: \n\t\t\t{df.loc[index, "text"]} \n\t\t<end_text>')
        context_string_array.append('<END_CONTEXT>')
        return '\n'.join(context_string_array)

    def unformatted_context_string_from_formatted_df(self, df):
        intro = (f'<BEGIN_CONTEXT>'
                 f'\n This string contains scientifically valid information in order to answer the above question'
                 f'\n It is structured on three levels namely the paper it was taken from,'
                 f'the section and the text from the section'
                 f'\n {"-"*30}')
        current_pdf = None
        current_section = None
        context_string_array = [intro]
        for index in df.index:
            pdf, section, id = index
            if not pdf == current_pdf:
                context_string_array.append(f'{pdf}: ')
                current_pdf = pdf
            if not section == current_section:
                context_string_array.append(f'\t{section}: ')
                current_section = section
            context_string_array.append(f'\t\t"{df.loc[index, "text"]}"')
        context_string_array.append('<END_CONTEXT>')
        return '\n'.join(context_string_array)


    def ask(self, question, formatting=False):
        self.graph_from_prompt(question, 1100)
        context_df = self.return_context_df()
        formatted_context_df = self.format_context_df(context_df)
        if formatting:
            context_string = self.formatted_context_string_from_formatted_df(formatted_context_df)
        else:
            context_string = self.unformatted_context_string_from_formatted_df(formatted_context_df)
        return context_string

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
    parser.add_argument('-zsp', '--zotero_storage_path', help='path to zotero storage')
    parser.add_argument('-ri', '--reindex', help='True if index should be recomputed from a zotero library')
    args = parser.parse_args()
    index_path = args.index_path
    zotero_path = args.zotero_storage_path
    reindex = args.reindex
    indexer = Indexer('./index')
    if zotero_path:
        indexer.vector_storage_from_prepared_zotero_storage(zotero_path)
    indexer.load_embeddings()
    print(indexer.ask('What is an invariant feature'))
    print(indexer.ask('What is cross frequency coupling'))


