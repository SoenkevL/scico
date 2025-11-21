---
apply: by model decision
instructions: Whenever you are asked something about the project, work with project files or interact with the repository. It is the general Philosophy behind the project.
---

## 🤝 SciCo: A Human-Centered Scientific Agent in a Structured Collaborative Environment

### 🌟 Vision and Philosophy

✓ SciCo's core aim is to harness the unparalleled knowledge-embedding and language manipulation abilities of Large
Language Models (LLMs), channeling them into productive, understandable, and human-guided scientific collaboration.

→ The guiding principle is "Human First": SciCo acts as an adaptive scientific coworker—enhancing, summarizing,
strategizing, and gathering information, always with human oversight and agency.

✓ LLMs alone are stateless transformers—they can generate fluent text and complex ideas but lack intrinsic goals,
direction, and persistent context. SciCo’s purpose is to provide that guiding framework, turning powerful language
models into useful, reliable, and accountable collaborators in research.

---

## 🧩 The Environment: Purpose-Built Collaboration

✓ The environment consists of distinct, integrated tools—each fulfilling a specific role within the research workflow:

- **Markdown & Obsidian**: Private, persistent long-term memory and record of conversations and ideas, accessible only
  by SciCo and the human user.
- **Notion**: Collaborative, cloud-based group notepad—where only humans author content, maintaining responsibility and
  transparency for all published work.
- **Zotero**: Shared, structured reference library, promoting robust, traceable, and trustworthy citation practices.
- **GitHub**: Central hub for collaborative coding, supported by SciCo for automation, integration, and reproducibility.
- **IDEs**: User-selected programming interfaces—flexibility and accountability for all code before it enters the
  group’s shared base.

→ This toolset forms a coherent ecosystem, blending private and group spaces, memory, reference, and code—each
reinforcing responsible, productive use of AI.

---

## 🕸️ Embedding Structure: The LangGraph Architecture

✓ To make LLMs “useful coworkers,” SciCo is architected using the LangGraph framework—an open-source, graph-oriented
system designed for modular, resilient agents.

→ LangGraph abstraction:

- **Nodes**: Each node is a well-defined function performing a discrete action (e.g., classify a message, search docs,
  draft a response).
- **State**: A typed, shared dictionary representing the evolving memory of a workflow. All nodes can read from and
  write to the state, maintaining continuity and context.
- **Edges**: Define the potential transitions and control flow between nodes—establishing how logic, data, and decisions
  move through the system.

✓ This structure:

- Mirrors the modular, interconnected thinking of the human brain.
- Allows explicit, traceable, and human-auditable paths through complex tasks.
- Incorporates checkpointing, enabling interruption, human supervision, and safe resumption of work.

---

## 🔄 Guiding Workflow: From Theory to Application

### Breaking Down Complexity:

Every workflow (e.g., handling a support email, synthesizing research, drafting code) is decomposed into discrete,
testable, resilient steps.

### Modular Node Types:

- **LLM Steps**: For understanding, interpreting, and generating human-like text or reasoning.
- **Data Steps**: Integrating external data (e.g., searching literature or databases).
- **Action Steps**: Taking real-world actions (e.g., sending emails, updating issues).
- **User Input Steps**: Seamless integration of human oversight with pausable execution.

### State as Persistent Memory:

Only stores raw, essential information; each node formats and uses this data on-demand, enhancing flexibility and
maintainability.

### Explicit Error Handling:

- Automated retries for transient faults.
- Feedback loops for LLM-correctable issues.
- Human pauses for missing information or critical judgments.
- Immediate surfacing of the unexpected for resolution.

---

## 🧭 Human Accountability and Responsible AI Use

### ✓ Human-Centered Design:

SciCo never acts unilaterally on public, collaborative data—humans remain the authors and owners of all group output.  
All interventions and AI usage are transparent and attributable.

### ✓ Agency, Not Autonomy:

SciCo amplifies the group’s power but does not replace responsibility or critical thinking.

### ✓ Ethical Memory:

Private data remains private; collective work is always deliberate and traceable.

---

## 🧬 Bringing It All Together

✓ SciCo’s vision is the orchestration of human and machine intelligence within a robust, flexible, and context-rich
environment—fusing the fluidity of LLMs with durable structure and human guidance.

→ By leveraging the LangGraph architectural paradigm, SciCo transforms raw language potential into sequenced, auditable,
inherently collaborative workflows.

✓ This allows:

- Persistent, evolving group memory and knowledge.
- Seamless movement between private and public spheres.
- Joint ownership, transparent authorship, and reproducible research.

---

## 📝 Summary

SciCo is more than a toolkit or a chatbot; it’s a human-centered research agent designed from first principles to make
powerful AI both safe and truly useful within a rich ecosystem. By mapping every action to graph nodes, maintaining
clear memory, and always looping back to human agency, SciCo turns state-of-the-art language models into real, reliable
partners in scientific discovery.