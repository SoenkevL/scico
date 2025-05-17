import indexer as indexer
from txtai.pipeline import LLM
import argparse

class Agent:

    def __init__(self, index_path, load_existing=True, storage_path=None):
        self.index_path = index_path
        self.indexer = indexer.Indexer(index_path)
        if load_existing:
            self.indexer.load_embeddings()
        else:
            self.indexer.vector_storage_from_prepared_zotero_storage(storage_path)
            self.indexer.load_embeddings()
        self.llm = LLM("TheBloke/Mistral-7B-OpenOrca-AWQ", gpu=True)

    def create_graph_search_via_llm_from_question(self, question):
        prompt = f"""<|im_start|>system
          You are a converter for questions into a search string optimized to query a graph vector database.<|im_end|>
          <|im_start|>user
          Use the following question, extract its topic and create a search string from it which is optimized for information retrieval from a graph based vector storage via node similarity. Return only the search string for querying as it is directly passed into the vector database query. This is very important.
      
          question: {question} <|im_end|>
          <|im_start|>assistant
          """

        return self.llm(prompt, maxlength=7000)

    def context_from_question(self, question):
        graph_search = self.create_graph_search_via_llm_from_question(question)
        return self.indexer.ask(graph_search, formatting=True)

    def ask_question(self, question):
        context = self.context_from_question(question)
        prompt = f"""<|im_start|>system
        You are a friendly assistant. You answer questions from users.<|im_end|>
        <|im_start|>user
        Answer the following question using only the context below. Only include information specifically discussed. Answers are used in scientific context therefore the accuracy of the answers if of utmost importance and should always be truthful and backed by the provided context. The context consists of chunked up text from a library of pdfs and the citation information for the chunk. Citation information has a field called title which should be used to add citations to the text you provide to the user in the form [<title>] inside of the text.
    
        question: {question}
        context: {context} <|im_end|>
        <|im_start|>assistant
        """

        return self.llm(prompt, maxlength=7000), context

    def add_citations_via_llm_to_answer(self, answer, context):
        prompt = f"""<|im_start|>system
        You are a scientific assistant whose job it is to find out the most likely source for an answer.<|im_end|>
        <|im_start|>user
        You are provided with an answer to a question aswell as the context that was used to answer it. Your job is to go through the context and decide which parts of the context were most likely used. Different parts of the context are split by "{'-'*20}". The part prepended with '<TEXT>:' is the text of the source and the part with '<CITATION>:' its source. Return the unaltered parts of context that you find most likely to be used to create the provided answer. Make sure you include the original name of the pdf, the title and the authors aswell as a short summary of the original content of the citation
    
        answer: {answer}
        context: {context} <|im_end|>
        <|im_start|>assistant
        """

        return self.llm(prompt, maxlength=7000)

    def answer_question_with_citation(self, question):
        assistant_answer, context = self.ask_question(question)
        deprecated_context = self.add_citations_via_llm_to_answer(assistant_answer, context)
        print(f'''
        ANSWER: \n {assistant_answer} \n\n
        Likely CONTEXT: \n {deprecated_context}
        FULL CONTEXT: \n {context}
        ''')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--index_path", help="path to the index folder")
    parser.add_argument('-ri', '--reindex', help='True if index should be recomputed from a zotero library')
    args = parser.parse_args()
    index_path = args.index_path
    print("""
         Welcome to scico your personal zotero based research assisstant.\n
    """)
    # Create Agent
    scico = Agent(index_path)
    # inital message
    print("""
         scico successfully initialized.
         Go ahead and ask questions about your zotero database and I will try my best to answer them\n
    """)
    # main loop
    while True:
        user_input = input('State your question:')
        if user_input == 'exit' or not user_input:
            break
        else:
            scico.answer_question_with_citation(user_input)
    # exit message
    print('scico is shutting down, untill next time')

