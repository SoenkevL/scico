---
apply: by model decision
instructions: when the following toppics are explicitly mentioned in the user query: agent, workflow, graph, langchain, langgraph
---

## Thinking in graphs

### Step 0: Mandatory Planning & Visualization

**Before writing any Python code**, you MUST perform a structural analysis of the request. Do not skip this step. You  
must follow this 4-part format:

1. **Problem Analysis:** Briefly summarize the workflow logic. Identify where decisions (routing) happen and where
   human  
   intervention might be needed.
2. **Node Definition:** List the specific nodes (functions) required. For each node, describe:
    - **Input:** What state data it needs.
    - **Action:** What it does (LLM reasoning, data fetch, etc.).
    - **Outcome:** What data it updates in the state.
3. **External Dependencies:** Explicitly list any external data sources or tools required (e.g., "Postgres
   Database", "  
   Stripe API", "Filesystem MCP Server").
    - _Note:_ You should **not** implement the actual connection code for these (like SQL drivers or API auth) unless  
      explicitly provided. Instead, implement them as **mocked functions** or clearly commented placeholders that
      return  
      realistic dummy data.
4. **Graph Visualization:** Generate a `mermaid` flowchart that represents the logic. Use dashed lines `-.->` for  
   conditional paths and solid lines `-->` for fixed transitions.

**Example Planning Response:**

**User:** "Build an agent that checks stock prices. If the price is above a target, sell it. If below, buy more. If
the  
market is closed, wait."

**Assistant:**

#### 1. Problem Analysis

The agent needs to fetch real-time data. The main logic is a comparison between current price and target price. There  
are three outcomes: Buy, Sell, or Wait. Market status (open/closed) is a pre-check.

#### 2. Node Definition

- `check_market_status`: **Input**: None. **Action**: Checks if market is open. **Outcome**: Updates `is_open`. Routes  
  to `fetch_price` or `wait`.
- `fetch_price`: **Input**: Ticker symbol. **Action**: Queries API. **Outcome**: Updates `current_price`.
- `evaluate_strategy`: **Input**: `current_price`, `target_price`. **Action**: Logic comparison. **Outcome**: Routes
  to  
  `execute_trade`.
- `execute_trade`: **Input**: Action (buy/sell). **Action**: Performs transaction. **Outcome**: Updates  
  `portfolio_balance`.

#### 3. External Dependencies

- **Market Data API:** (e.g., AlphaVantage or Bloomberg). _I will mock this._
- **Brokerage API:** (e.g., Robinhood or IBKR) for executing trades. _I will mock this._
- **Time Server:** To check market hours.

#### 4. Mermaid Graph

```mermaid  
flowchart TD    
    A[START] --> B[Check Market Status]    
    B -- Open --> C[Fetch Price]    
    B -- Closed --> D[Wait/End]    
        
    C --> E[Evaluate Strategy]    
        
    E -.-> F[Execute Buy]    
    E -.-> G[Execute Sell]    
    E -.-> H[Hold/No Action]    
        
    F --> I[END]    
    G --> I    
    H --> I  
```  

## Using Langgraph for implementation

... When asked to build a LangGraph agent, follow this thought process and code structure. Use the Command pattern for  
dynamic routing inside nodes and interrupt for human-in-the-loop steps. Keep the state "raw" and format prompts within  
the nodes.  
Example:  
User: Build a customer support email agent. It should read emails, classify them (question, bug, urgent), search docs
if  
it's a question, create a ticket if it's a bug, draft a reply, and require human review for urgent items.  
Assistant: Here is the design and implementation for the Customer Support Agent.

1. Graph Design  
   State: Stores raw email data, classification dict, search results list, and the draft.  
   Nodes:  
   classify_intent: Routes to Search, Bug Tracking, or directly to Draft.  
   search_docs: Retries on failure, updates state with docs.  
   draft_response: Formats prompt using raw state, routes to Review or Send.  
   human_review: Uses interrupt to pause for approval.

### Example of a langgraph implementation

```python  
from typing import TypedDict, Literal, List  
from langgraph.graph import StateGraph, START, END  
from langgraph.types import Command, interrupt, RetryPolicy  
from langchain_openai import ChatOpenAI  
  
# --- State Definition ---  
class EmailAgentState(TypedDict):  
    email_content: str    email_id: str    # Raw data storage    classification: dict | None    search_results: List[str] | None    draft_response: str | None  
llm = ChatOpenAI(model="gpt-4")  
  
# --- Nodes ---  
  
def read_email(state: EmailAgentState) -> dict:  
    # In reality, fetch from API    print(f"Processing: {state.get('email_content', 'no email found')}")    return {}  
def classify_intent(state: EmailAgentState) -> Command[Literal["search_docs", "bug_tracking", "draft_response"]]:  
    """Classifies and decides the next step dynamically."""        # Format prompt locally (keep state raw)  
    prompt = f"Classify: {state.get('email_content')}. Return JSON with 'intent' and 'urgency'."    # Mocking LLM structured response for brevity    result = {"intent": "question", "urgency": "medium"}      
    # Logic inside the node determines the path  
    if result['intent'] == 'bug':        goto = "bug_tracking"    elif result['intent'] == 'question':        goto = "search_docs"    else:        goto = "draft_response"            return Command(  
        update={"classification": result},        goto=goto    )  
def search_docs(state: EmailAgentState) -> Command[Literal["draft_response"]]:  
    # Logic to query vector DB    results = ["Doc A: How to reset password...", "Doc B: API limits..."]    return Command(        update={"search_results": results},        goto="draft_response"    )  
def bug_tracking(state: EmailAgentState) -> Command[Literal["draft_response"]]:  
    ticket_id = "BUG-101" # External API call    return Command(        update={"search_results": [f"Created ticket {ticket_id}"]},        goto="draft_response"    )  
def draft_response(state: EmailAgentState) -> Command[Literal["human_review", "send_reply"]]:  
    # Combine raw state data into a prompt    context = "\n".join(state.get("search_results", []))    prompt = f"Draft reply to: {state['email_content']} using context: {context}"        response = llm.invoke(prompt).content  
        # Check urgency for routing  
    is_urgent = state.get('classification', {}).get('urgency') == 'high'    goto = "human_review" if is_urgent else "send_reply"        return Command(  
        update={"draft_response": response},        goto=goto    )  
def human_review(state: EmailAgentState) -> Command[Literal["send_reply", END]]:  
    # Pause execution and wait for input    feedback = interrupt({        "msg": "Review required",        "draft": state.get('draft_response', 'no draft available')  
    })        if feedback.get("approved"):  
        final_text = feedback.get("edited_text", state.get('draft_response'))        return Command(update={"draft_response": final_text}, goto="send_reply")        return Command(goto=END) # Cancelled  
  
def send_reply(state: EmailAgentState) -> dict:  
    print(f"SENT: {state.get('draft_response', 'no email')}")    return {}  
# --- Graph Construction ---  
  
workflow = StateGraph(EmailAgentState)  
  
# Add nodes  
workflow.add_node("read_email", read_email)  
workflow.add_node("classify_intent", classify_intent)  
# Add retry policy for external data steps  
workflow.add_node("search_docs", search_docs, retry_policy=RetryPolicy(max_attempts=3))  
workflow.add_node("bug_tracking", bug_tracking)  
workflow.add_node("draft_response", draft_response)  
workflow.add_node("human_review", human_review)  
workflow.add_node("send_reply", send_reply)  
  
# Wire essential edges (conditional routing is handled by Command in nodes)  
workflow.add_edge(START, "read_email")  
workflow.add_edge("read_email", "classify_intent")  
workflow.add_edge("send_reply", END)  
  
# Checkpointer is required for interrupt/human-in-the-loop  
from langgraph.checkpoint.memory import MemorySaver  
app = workflow.compile(checkpointer=MemorySaver())  
```  

Make sure to always follow the order:

1. Analyze the problem
2. Define a graph and dicuss it with the user
3. Implement the basic state, nodes and stategraph while crealy indicating external connections using mock functions
   and  
   placeholders

All answers are supposed to be in markdown with python blocks indicated as

```python  
  
```  

Now aid the user using your instructions on his requests and questions!