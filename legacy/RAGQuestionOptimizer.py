from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from typing import List
import os


class RAGQuestionOptimizer:
    """
    Optimizes user queries for better RAG retrieval using LLM-powered techniques.
    
    Techniques:
    - Query expansion (generating related terms)
    - Query decomposition (breaking complex queries into sub-queries)
    - Query reformulation (rephrasing for better semantic matching)
    """
    
    def __init__(self, model_name: str = "llama3.2", temperature: float = 0.3):
        self.llm = ChatOllama(
            model=model_name,
            temperature=temperature,
            base_url=os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        )
    
    def expand_query(self, query: str) -> List[str]:
        """
        Generate multiple variations of the query for better retrieval coverage.
        
        Returns a list of query variations including the original.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful assistant that expands scientific queries.
Given a query, generate 2-3 alternative phrasings that maintain the same meaning
but might match different document phrasings. Keep queries concise.

Return only the alternative queries, one per line, without numbering or explanations."""),
            ("user", "{query}")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            response = chain.invoke({"query": query})
            variations = [line.strip() for line in response.split('\n') if line.strip()]
            return [query] + variations  # Include original
        except Exception as e:
            print(f"Query expansion failed: {e}")
            return [query]
    
    def decompose_query(self, query: str) -> List[str]:
        """
        Break down complex queries into simpler sub-queries.
        
        Useful for multi-part questions.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful assistant that breaks down complex questions.
Given a complex scientific query, decompose it into 2-4 simpler sub-questions
that together would answer the original question.

Return only the sub-questions, one per line, without numbering or explanations."""),
            ("user", "{query}")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            response = chain.invoke({"query": query})
            sub_queries = [line.strip() for line in response.split('\n') if line.strip()]
            return sub_queries if len(sub_queries) > 1 else [query]
        except Exception as e:
            print(f"Query decomposition failed: {e}")
            return [query]
    
    def optimize_for_scientific_context(self, query: str) -> str:
        """
        Reformulate query to be more suitable for scientific literature search.
        
        Adds academic terminology and context.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a scientific literature search expert.
Reformulate the given query to be more suitable for searching academic papers.
Use formal academic language and include relevant technical terms.

Return only the reformulated query, nothing else."""),
            ("user", "{query}")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            response = chain.invoke({"query": query})
            return response.strip()
        except Exception as e:
            print(f"Query optimization failed: {e}")
            return query
    
    def generate_hypothetical_answer(self, query: str) -> str:
        """
        Generate a hypothetical answer (HyDE technique).
        
        This answer can be used for retrieval to find similar content.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a scientific expert. Given a question, write a brief 
hypothetical answer (2-3 sentences) as it might appear in a scientific paper.
Use technical language and academic style."""),
            ("user", "{query}")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            response = chain.invoke({"query": query})
            return response.strip()
        except Exception as e:
            print(f"HyDE generation failed: {e}")
            return query