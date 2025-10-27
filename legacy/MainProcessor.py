import json
import os
from typing import List, Dict, Any

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from src.Tools.VectorStorage import ChromaStorage
from legacy.RAGQuestionOptimizer import RAGQuestionOptimizer


class MainProcessor:
    def __init__(self, collection_name=None, llm_model: str = "llama3.2"):
        load_dotenv()
        self.zotero_library_path = os.getenv('ZOTERO_LIBRARY_PATH')
        self.markdown_folder_path = os.getenv('MARKDOWN_FOLDER_PATH')
        self.index_path = os.getenv('INDEX_PATH')
        
        # Initialize LangChain-powered vector storage
        self.storage = ChromaStorage(self.index_path, collection_name)
        
        # Initialize LLM for RAG
        self.llm = ChatOllama(
            model=llm_model,
            temperature=0.2,
            base_url=os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        )
        
        # Initialize query optimizer
        self.query_optimizer = RAGQuestionOptimizer(model_name=llm_model)
        
        # Setup RAG chain
        self._setup_rag_chain()
    
    def _setup_rag_chain(self):
        """Setup the LangChain RAG chain for question answering."""
        
        # Create prompt template for RAG
        self.rag_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a scientific research assistant. Answer questions based ONLY on the provided context from scientific papers.

Guidelines:
- Cite sources by mentioning the paper filename when possible
- If the context doesn't contain enough information, say so
- Use technical language appropriate for academic discussion
- Provide detailed explanations when warranted

Context:
{context}"""),
            ("user", "{question}")
        ])
        
        # Get retriever from vector store
        self.retriever = self.storage.as_retriever(
            search_kwargs={'k': 5}
        )
        
        # Format documents for context
        def format_docs(docs):
            formatted = []
            for doc in docs:
                source = doc.metadata.get('filename', 'Unknown source')
                section = doc.metadata.get('level1', '')
                formatted.append(f"[Source: {source}, Section: {section}]\n{doc.page_content}")
            return "\n\n---\n\n".join(formatted)
        
        # Build the RAG chain
        self.rag_chain = (
            {
                "context": self.retriever | format_docs,
                "question": RunnablePassthrough()
            }
            | self.rag_prompt
            | self.llm
            | StrOutputParser()
        )
    
    def ask_question(self, question: str, optimize_query: bool = True) -> Dict[str, Any]:
        """
        Ask a question and get an answer with sources using RAG.
        
        Args:
            question: The question to ask
            optimize_query: Whether to optimize the query before retrieval
            
        Returns:
            Dict with 'answer' and 'sources'
        """
        # Optionally optimize query
        if optimize_query:
            optimized = self.query_optimizer.optimize_for_scientific_context(question)
            print(f"Optimized query: {optimized}")
            search_query = optimized
        else:
            search_query = question
        
        # Get answer from RAG chain
        answer = self.rag_chain.invoke(search_query)
        
        # Get source documents
        source_docs = self.retriever.get_relevant_documents(search_query)
        
        sources = []
        for doc in source_docs:
            sources.append({
                'content': doc.page_content[:200] + "...",
                'filename': doc.metadata.get('filename', 'Unknown'),
                'section': doc.metadata.get('level1', 'N/A')
            })
        
        return {
            'question': question,
            'answer': answer,
            'sources': sources
        }
    
    def multi_query_retrieval(self, question: str, n_results: int = 5) -> List[Dict]:
        """
        Use query expansion for more comprehensive retrieval.
        """
        # Expand query into variations
        query_variations = self.query_optimizer.expand_query(question)
        print(f"Generated {len(query_variations)} query variations")
        
        all_docs = []
        seen_ids = set()
        
        # Retrieve for each variation
        for query in query_variations:
            docs = self.retriever.get_relevant_documents(query)
            for doc in docs:
                doc_id = hash(doc.page_content)
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    all_docs.append(doc)
        
        # Return top n_results
        return all_docs[:n_results]

    def query_vector_storage(self, query, n_results=10):
        """Legacy method for backward compatibility."""
        return self.storage.query(query, n_results=n_results)

    def add_chunks_to_vector_storage(self, chunks):
        """Add chunks to vector storage."""
        self.storage.add_documents(chunks)

    @staticmethod
    def chunk_list_from_json(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            chunk_dicts = json.load(f)
        return chunk_dicts

    # ... existing methods (refresh_library, add_pdf, etc.) ...


def main():
    load_dotenv()
    processor = MainProcessor(os.getenv('COLLECTION_NAME'))
    
    # Example: Ask a question with full RAG
    result = processor.ask_question("What is criticality in EEG signals?")
    
    print("\n" + "="*80)
    print(f"QUESTION: {result['question']}")
    print("="*80)
    print(f"\nANSWER:\n{result['answer']}")
    print("\n" + "="*80)
    print("SOURCES:")
    for i, source in enumerate(result['sources'], 1):
        print(f"\n{i}. {source['filename']} - {source['section']}")
        print(f"   {source['content']}")


if __name__ == "__main__":
    main()