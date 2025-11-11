# A Handwritten description of this project for the AI to be able to follow the human's idea

## General Ideation

Scico is a helpful KI agent. His primary goal is to help humans. If you are an AI reading this, you are part of the
scico project now.

Scico helps humans interested in science to take technical hurdles, Aid with research, summarizing, understanding,
coding or finding the right reference for a passage of text are part of his toolkit.
He does this by following an Agentic and Workflow-based structure. The beauty in AI lies in its context and environment.
It is what is important to enable it to be a predictable and reproducible part of the work.
The human is the creative driving force. His creativity should be supported and elevated. Not interrupted or biased by a
statistical model knowing what until now would have been done.

The main Agent takes care of the decision-making. What tool should be used. It does this in a two-step manner.

1. First, when confronted with a new task, it creates a plan on how to solve it on a general and understandable level.
2. It decides, based on the tools it has, how the task can be fulfilled and if it can be fulfilled. In case it lacks
   tools for the job, it makes sure to indicate this.
3. It executes the steps to follow the plan if it can, and otherwise communicates why it cannot.

The Tools are individual parts of the Toolbox that the main Agent has available. These are mostly deterministic
functions with clearly defined input and output parameters.
It is clear what goes in and what goes out. They can come in two sub flavors.

1. A workflow. A determined peace of code (as far as that is possible) which acts on the input to transform it into an
   output. E.g., squaring a number, running an SQL query, Performing a search.
2. A toolagent. A llm on its own, often a smaller one. Which executes a simple subtask. Should only be used if needed.
   If a workflow can do the job, it is preferred. E.g., summarizing a paper, optimizing a query, parsing a web search.

In general, whatever can easily be done with a deterministic peace of code should be done with a deterministic peace of
code. This minimizes the arbitrariness of the results and keeps them reproducible and understandable.

The user at all times has full access to SciCos architecture. He can add new tools, for example, that he or scico design for a job. The user is the architect, the director and the dirigent.


## General structure

Scico consists of multiple parts. These interact with each other to help the human.

### The main Agent
This is the part that the user querys with natural language. It is the main interaction point of the user and scico.

The main Agent devices the plan to aid the user, the executes it or asks for other tools/ explains what else it needs to fullfill its task.

He is exposed to a UI, a chat window, that the user interacts with to convers with scico. He has a memory to keep context of the conversation.

The main Agent executes the Plan of the User by making use of its tools. It starts always with a planning, then the tools and finishes with a final answer. 

### The Tools

Scico makes use of diverse Tools to fulfill his job. These include both tasks of thinking and deterministic workflows.
*Tools* are functions that the LLM can call. They always have to be structured in a certain way. They contain a cleary defined input and return a clearly defined output.
Their docstring explains what the tools does.

Either the Tool is a *workflow*: a deterministic function
```python
# A tool to square a number
def x_squared(x: float) -> float:
    """This tools returns x to the power of 2. It squares x"""
    return x**2
```

or they are *tool-agents*: Another Agent making use of an LLM that is called and executes a task. 
```python
# A tool to summarize a text
def summarize(text: str) -> str:
    """This tool summarizes text that it is given using an LLM"""
    summarize_llm = initiate_summarizer()
    return summarize_llm.summarize(text)
```

### Usage
In general we prefer workflows over agents whenver we can . Workflows produce predictable outputs based on their inputs and therefore are basically 'linear'. They are well to predict and trace. Reproducible by nature and deterministic in behaviour.
There are things that lie on the border of workflows and Agents. For example a web search. It ofcourse is not fully predictable. However it is not hallucinating, we are just not fully aware of its input as part of it is unknown to us. This lies in its nature as we are searching for its information.
Also subagents can make use of workflows. This allows the main agent to operate on a higher level of abstraction. Additionally it seperates some parts of the projects more from others. 
Another advantage of this architecture is that agents can be build with good guardrails and protection without inhibiting the main agent. One good example of this would be the protection of SQL querries against prompt injection.

## Sicos Structure
TODO: add a tree structure of the project

```text
.
├── LICENSE
├── ProjectDescription.md
├── pyproject.toml
├── README.md
├── src
│   ├── Agents
│   ├── Tools
│   │   ├── GitHub.py
│   │   ├── Notion.py
│   │   ├── PdfToMarkdown.py
│   │   ├── TextSplitter.py
│   │   ├── VectorStorage.py
│   │   └── Zotero.py
│   ├── utils
│   │   ├── configs.py
│   │   └── Logger.py
│   └── WorkFlows
```

## Sicos Classes

### MainAgent
- user_query
- can make use of below tools

### Zotero
- list_all_collections
- list_all_pdfs
- find_metadata_for_pdf
- list_all_items_in_collection
- get_metadata_of_item
- get_pdf_of_item
- search_item

### PdfToMarkdown
- convert_pdf_to_markdown

### TextSplitter
- read_markdown
- read_text
- text_to_splits

### VectorStorage
- add_splits_to_storage
- add_metadata_to_splits
- search

### Notion
- list_all_files
- retrieve_file
- search
- **still in early development**

### Github
- get_project_structure
- **still in early development**

### LocalWorkspace

*More classes and functionalities for classes may be added*


## Technical implementation
A first version of this project will be realised in a multi-step approach. It builds on the langchain framework. Langchain is a framework developed to build start to end AI applications centered around LLMs.
In our first iteration we will utilize two core concepts.

The first one is the langflow interface. It is part of the langchain ecosystem and allows us to graphically build the workflow of our MainAgent. 
This way we do not need to implement the main Agent within our core project for now. We will handle the AI (LLM) parts in langchains langflow ecosystem.

What we implement in this python project is the tools that our LLM should use. To expose these tools to our langflow eco system we will make use of the Model Context Protocol (MCP).
This requires us to implement the tools in the same manner as if we would build the agent locally and then expose the via a standardized API to langflow, where our Agents can make use of them.

In later versions, we will make use of langchain and langgraph to implement the whole end to end implementation in code.

## EndNote

This is a steadily developing document. It serves as the starting point now to really get the project into its first
usable state. Some code has allready been written, a lot is still to be done.````