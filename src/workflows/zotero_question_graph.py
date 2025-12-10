"""
Main graph definition for the Zotero Research Assistant.
Handles query generation, iterative retrieval, summarization, and structured answering.
"""
# === import global packages ===
from typing import List, Literal, TypedDict

import numpy as np
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

# === import local file dependencies ===
from src.Tools.zotero_retriever_tools import list_of_documents_to_string
from src.configs.Chroma_storage_config import ChromaStorageConfig
from src.storages.ChromaStorage import ChromaStorage

# === initialize global objects ===
load_dotenv()

VECTOR_STORAGE_CONFIG = ChromaStorageConfig()
VECTOR_STORAGE = ChromaStorage(VECTOR_STORAGE_CONFIG)

# Initialize LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0)

# === define classes ===
## === structured Responses ===
class SearchQuery(BaseModel):
    """Query used in the search functionality of the vector db"""
    semantic_string: str = Field(description="The semantic string used for similarity retrieval on the database")
    # metadata_filter: dict | None = Field(description="An optional filter to narrow the search. Can be used to find information specific to titles, authors, sections or tags", default=None)


class RelevantSource(BaseModel):
    """Structured, pruned, and summarized info from a list of Documents for an item"""
    citation_key: str = Field("citation_key of the source")
    information: str = Field("summarized, truthful information about the source based on the given information")


class Source(BaseModel):
    key: str = Field(description='citation_key or if not present title of the Source.')
    info: str = Field(description='summarized short information about the provided information by the source.')

class KnowledgeSynthesis(BaseModel):
    """Synthesis of knowledge across multiple sources."""
    relevant_sources: List[Source] = Field(
        description="List of relevant information per source. Always reference by citation key or, only if not present, title.")
    synthesis_text: str = Field(
        description="A synthesis of knowledge across the references with citations using the citation key.")


class Assessment(BaseModel):
    """Structured output for the judging step."""
    stop: bool = Field(
        description="True if the provided context is enough to answer the query or if no progress is made in answering the question",
        default=False)
    reasoning: str = Field(
        description="Reasoning for the decision. In case information is missing describe exactly what is missing. Suggest what to iterate on next.")


class FinalAnswer(BaseModel):
    """Final answer to the question, given the whole information of the research"""
    final_answer: str = Field(
        description="The final answer to the users question. Taking account all the provided evidence and reasoning")
    answer_evaluation: str = Field(
        description="A final evaluation on the quality of the information that was found. Taking into account prior assessments.")
    suggestions: str = Field(
        description="Suggestions based on the users question, sources and feedback what other relations to the topic should be explored")
    title: str = Field(description="A short, clear title summarizing the question and answer")


## === GraphState ===
class GraphState(TypedDict):
    """
    Represents the state of the research agent.
    """
    user_query: str
    indexed_items_in_vector_storage: dict
    search_queries: List[str]
    retrieved_documents: List[List[Document]]
    knowledge_strings: List[str]  # Added to track history
    assessment_strings: List[str]
    search_loop_count: int
    max_search_depth: int
    max_docs_per_search: int
    exclude_references: bool
    final_response: str


# === Helper Function ===

def _remove_references_from_documents(documents: List[Document]):
    not_a_reference = []
    for document in documents:
        if 'reference' in document.metadata['levels'].lower():
            continue
        not_a_reference.append(document)
    return not_a_reference



# === Nodes ===

def init_state(state: GraphState) -> Command[Literal["check_for_user_query"]]:
    """Initialize the fields of the state"""
    updates = {}
    if "user_query" not in state:
        updates["user_query"] = "what is integrated information theory"
    if "indexed_items_in_vector_storage" not in state:
        updates["indexed_items_in_vector_storage"] = VECTOR_STORAGE.get_collection_stats()['items']
    if "search_queries" not in state:
        updates["search_queries"] = [
            'No prior queries were generated. Use the users input to find general information on the topic and refine it from there']
    if "retrived_documents" not in state:
        updates["retrieved_documents"] = [[]]
    if "knowledge_strings" not in state:
        updates["knowledge_strings"] = ['This is the first synthesis of the initial information.']
    if "assessment_strings" not in state:
        updates["assessment_strings"] = ['This is the first search. This will supply your initial knowledge.']
    if "search_loop_count" not in state:
        updates["search_loop_count"] = 0
    if "max_search_depth" not in state:
        updates["max_search_depth"] = 5
    if "max_docs_per_search" not in state:
        updates["max_docs_per_search"] = 10
    if "exclude_references" not in state:
        updates["exclude_references"] = False

    # If we have updates, apply them, otherwise just transition
    if updates:
        return Command(update=updates, goto="check_for_user_query")

    return Command(goto="check_for_user_query")


def check_for_user_query(state: GraphState) -> Command[Literal["generate_search_query"]]:
    """
    Has the user provided a query? if not get one from him.
    """
    updates = {}
    if state.get("user_query", "") == "":
        user_input = interrupt({
            "msg": "Please provide a research query to search your Zotero library.",
        })
        updates["user_query"] = user_input
        return Command(update=updates, goto="generate_search_query")

    return Command(goto="generate_search_query")


def generate_search_query(state: GraphState) -> Command[Literal["search"]]:
    """
    Decomposes the user query into specific search terms for the vector DB.
    Only runs once at the beginning.
    """
    search_queries = state['search_queries']
    user_query = state["user_query"]
    assessments = state['assessment_strings']

    prompt = (
        f"Your goal is to create an optimized search query for semantic vector retrieval from a database. \n"
        f"It has to answer this question: \n\t'{user_query}'.\n"
        f"Here are your previous searches: \n\t- {'\n\t- '.join(search_queries)}\n"
        f"And comments what is still missing: \n\t {assessments[-1]}"
        f"Make sure to optimize the query to retrieve different sources than the ones before to find diverese information to fill the current knowledge gaps. \n"
        f"If needed metadata can be added which is used to filter for specific items, authors or tags. Only use this if necessary. Otherwise leave it out"
    )

    structured_llm = llm.with_structured_output(SearchQuery)
    query: SearchQuery = structured_llm.invoke(prompt)
    new_query = query.semantic_string
    search_queries.append(new_query)

    # Update both current search queries and add them to history
    return Command(
        update={
            "search_queries": search_queries
        },
        goto="search"
    )


def search(state: GraphState) -> Command[Literal["synthesize_knowledge"]]:
    """
    Executes the vector search using the current search queries in the state.
    Appends new docs to existing ones to build a comprehensive context.
    """
    # parameters for search
    query = state["search_queries"][-1]
    n_results = state["max_docs_per_search"]

    # search for new fitting documents in vector storage
    new_docs = VECTOR_STORAGE.search(query, n_results=n_results * 2)
    if state['exclude_references']:
        new_docs = _remove_references_from_documents(new_docs)

    # retrieve the already known docs and extract their ids into a list
    current_docs = state["retrieved_documents"]
    flat_current_docs = np.array(current_docs).flatten()
    current_doc_ids = [f"{doc.metadata['item_id']}{doc.metadata['split_id']}" for doc in flat_current_docs]

    # remove any docs already known from the list of new docs
    new_docs_dict = {f'{doc.metadata.get("item_id")}_{doc.metadata.get('split_id')}': doc for doc in new_docs}
    new_doc_ids = list(new_docs_dict.keys())
    if current_doc_ids:
        for doc_id in current_doc_ids:
            if doc_id in new_doc_ids:
                new_docs_dict.pop(doc_id)

    # ensure only the maximum amount is added
    if len(new_docs) > state['max_docs_per_search']:
        new_docs = new_docs[:state['max_docs_per_search']]
    current_docs.append(new_docs)

    return Command(
        update={
            "retrieved_documents": current_docs
        },
        goto="synthesize_knowledge"
    )


def synthesize_knowledge(state: GraphState) -> Command[Literal["judge_information"]]:
    """
    Reduces the information string to a structured synthesis and per-source relevance.
    """
    # We re-construct a context with explicit metadata to ensure the LLM can find citation keys
    new_docs = state['retrieved_documents'][-1]
    user_query = state.get("user_query")
    docs_string = list_of_documents_to_string(new_docs)
    last_synthesis = state['knowledge_strings'][-1]

    structured_llm = llm.with_structured_output(KnowledgeSynthesis)

    prompt = (
        f"Analyze the following document snippets to answer a question from the user.\n"
        f"The question your are trying to answer is: '{user_query}'.\n\n"
        f"The last search has given you this new information:\n{docs_string}\n\n"
        f"In previous searches we have found the following information already: \n"
        f'--- \n{last_synthesis}\n---\n\n'
        f"Provide a structured markdown formatted output containing:\n"
        f"1. Updated information per source.\n"
        f"2. A synthesis of the new knowledge with the old across the references with citations using the citation key from the metadata."
    )

    synthesis: KnowledgeSynthesis = structured_llm.invoke(prompt)

    # Format the structured output back into a string for the 'information_string' state variable
    # This ensures downstream nodes (Judge, Final Answer) get the refined info.
    formatted_output = (f"# Knowledge Synthesis\n"
                        f"## summary\n"
                        f"{synthesis.synthesis_text}\n\n"
                        f"## Relevant Information by Source\n")
    for item in synthesis.relevant_sources:
        formatted_output += (f"### Source: {item.key}\n"
                             f"{item.info}\n\n")

    state['knowledge_strings'].append(formatted_output)
    return Command(
        update={"knowledge_strings": state['knowledge_strings']},
        goto="judge_information"
    )


def judge_information(state: GraphState) -> Command[Literal["generate_search_query", "final_answer"]]:
    """
    Decides if we have sufficient info. 
    If NO: Generates new queries (avoiding past ones) and loops back.
    If YES: Goes to the final answer.
    """
    update = {}
    user_query = state["user_query"]
    current_knowledge = state["knowledge_strings"][-1]
    current_iteration = state["search_loop_count"]
    search_queries = state["search_queries"]
    last_information_assessment = state["assessment_strings"][-1]

    structured_llm = llm.with_structured_output(Assessment)

    prompt = (
        f"Your goal is to judge if enough information was retrieved to answer the users question.\n"
        f"User Query: {user_query}\n\n"
        f"To answer the question we have retrieved information from a vector database using the following similarity queries:"
        f"So far we have the following information available from our sources:"
        f"{'\n- '.join(search_queries)}"
        f"From which we derived this current state of knowledge based on our sources:"
        f"\n{current_knowledge}\n\n"
        f"Your last judgement on the available information was the following:"
        f"\n{last_information_assessment}\n\n"
        f"Analyze if the available information is sufficient now to provide a comprehensive answer to the users question.\n"
        f"Additionally judge if any good progress was made or if we should stop the search and ask the user to provide further information.\n"
        f"Give a valid and reasoned assessment if the information is sufficient and if we should continue searching for new information or leave it as it is."
    )

    assessment: Assessment = structured_llm.invoke(prompt)

    update["assessment_strings"] = state["assessment_strings"]
    update['assessment_strings'].append(assessment.reasoning)
    update["search_loop_count"] = current_iteration + 1

    if assessment.stop or current_iteration >= state["max_search_depth"]:
        return Command(
            update=update,
            goto="final_answer"
        )
    return Command(
        update=update,
        goto="generate_search_query"
    )


def final_answer(state: GraphState) -> Command[Literal[END]]:
    """
    Constructs the final structured output using the gathered information.
    If info is missing, it explicitly states what was found and what is missing.
    """

    def _generate_research_report(state: GraphState) -> str:
        """generates a markdown formatted report string from the search queries, synthesized texts, and assessments"""
        search_queries = state['search_queries'][1:]
        knowledge_strings = state['knowledge_strings'][1:]
        assessments = state['assessment_strings'][1:]

        report_string = "# Research Report"
        for search_query, knowledge, assessment in zip(search_queries, knowledge_strings, assessments):
            report_string = report_string + (
                f"\n\n## query:\n{search_query}"
                f"\n\n### summarized information:\n{knowledge}"
                f"\n\n### reflection:\n{assessment}"
            )
        return report_string

    report = _generate_research_report(state)
    structured_llm = llm.with_structured_output(FinalAnswer)

    prompt = (
        "You are an advanced researcher. Currently you are exploring: \n"
        f"{state['user_query']} \n\n"
        "You have requested a research report about the question based on a similarity search across your collected documents.\n"
        "In the following you will receive a research report from your assistant who retrieved relevant sources towards the matter from zoteros pool of knowledge.\n"
        f"\n\n {report}\n\n"
        "Based on all you learned give a critical evaluation towards the topic, containing of a final answer with citations to their origins, "
        "an evaluation of the final state of exploration towards the topic, including its limitations, and suggestions what the user might further explore."
        "Finally a short, clear title summarizing this chapter of research"
    )

    response: FinalAnswer = structured_llm.invoke(prompt)
    final_response = (f"# {response.title}\n"
                      f"## Query: \n{state["user_query"]}\n\n"
                      f"## Answer: \n{response.final_answer}\n\n"
                      f"## Assessment of information: \n{response.answer_evaluation}"
                      f"## Further Suggestions: \n{response.suggestions}"
                      f"\n\n --- \n\n"
                      f"{report}"
                      )

    return Command(
        update={"final_response": final_response},
        goto=END
    )


# === Graph Construction ===

workflow = StateGraph(GraphState)

# Add nodes
workflow.add_node("init_state", init_state)
workflow.add_node("check_for_user_query", check_for_user_query)
workflow.add_node("generate_search_query", generate_search_query)
workflow.add_node("search", search)
workflow.add_node("synthesize_knowledge", synthesize_knowledge)
workflow.add_node("judge_information", judge_information)
workflow.add_node("final_answer", final_answer)

# Define edges
workflow.add_edge(START, 'init_state')
## Rest of the edges are defined within the individual nodes

# Compile graph
app = workflow.compile()

if __name__ == '__main__':
    app.invoke(Command(goto='init_state'))
