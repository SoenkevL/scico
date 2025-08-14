import chromadb

class ChromaStorage:
    def __init__(self, index_path, collection_name):
        self.index_path = index_path
        self.chroma_client = chromadb.PersistentClient(path=self.index_path)
        self.current_graph = None
        self.collection = self.chroma_client.get_or_create_collection(name=collection_name)

    def add_documents(self, chunks):
        docs = []
        ids = []
        metadatas = []
        for chunk in chunks:
            docs.append(chunk.get('page_content'))
            ids.append(chunk.get('split_uid'))
            metadatas.append(chunk.get('metadata'))
        self.collection.add(ids=ids, documents=docs, metadatas=metadatas)

    def query(self, query_texts, n_results=5):
            results = self.collection.query(
                query_texts=query_texts,
                n_results=n_results
            )
            return results

    @staticmethod
    def print_results(results):
        for result in results:
            print(f'Result for query: {result["query"]}')
            for hit in result["hits"]:
                print(f'Document: {hit["document"]}')
                print(f'Metadata: {hit["metadata"]}')
                print(f'Score: {hit["score"]}')
                print('---')