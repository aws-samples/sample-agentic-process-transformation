# Agent Orchestration Patterns & Accelerators

Sample code accelerators and reusable patterns for building individual agents and orchestrating multi-agent workflows. Each pattern includes working examples using Strands Agents with Amazon Bedrock.

## Structure

```
agent-orchestration-patterns/
│
├── agent-patterns/                          — Patterns for building individual agents
│   ├── 01_rag_agent.ipynb                   — Knowledge retrieval (RAG)
│   ├── 02a_tool_agent_function_calling.ipynb — Agent calls internal functions
│   ├── 02b_tool_agent_mcp.ipynb             — Agent delegates to MCP servers
│   ├── 03_multimodal_agent.ipynb            — Vision, document processing
│   ├── 04_memory_augmented_agent.ipynb      — Short-term + long-term memory
│   └── 05_supervisor_agent.ipynb            — Supervisor that decomposes and delegates
│
├── agent-workflow-patterns/                 — Patterns for orchestrating multiple agents
│   ├── 01_routing.ipynb                     — Dynamic dispatch to specialist agents
│   ├── 02_parallelization.ipynb             — Scatter-gather with synthesis
│   ├── 03_human_in_the_loop.ipynb           — Callback patterns for human review
│   └── 04_reflect_and_refine.ipynb          — Self-evaluation and iteration loops
│
└── common/                                  — Shared setup scripts and sample data
    ├── setup/                               — Infrastructure setup scripts
    └── sample_data/                         — Sample documents
```

## Getting Started

1. Pick a pattern category: **agent-patterns** (individual agents) or **agent-workflow-patterns** (multi-agent orchestration)
2. Choose the specific pattern that matches your use case
3. Follow the notebook — each is self-contained and runs in SageMaker AI Studio
