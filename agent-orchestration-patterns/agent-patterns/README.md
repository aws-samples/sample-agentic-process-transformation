# Agent Patterns

Patterns for building individual agents in a business process. Each pattern represents a distinct capability level — from basic reasoning to multimodal perception to stateful memory.

All implementations use Strands Agents with Amazon Bedrock.

## Patterns

| # | Pattern | Description | When to Use |
|---|---|---|---|
| 1 | **RAG Agent** | Retrieves external knowledge to ground responses in real data | When the process needs to *know* — HR policies, technical manuals, regulatory guidance |
| 2a | **Tool Agent: Function Calling** | Agent calls functions — decides which, constructs arguments, executes | When the process needs to *act* — calculations, lookups, rule enforcement |
| 2b | **Tool Agent: MCP** | Agent delegates to an MCP server with its own runtime | When tools need their own runtime — enterprise systems, stateful ops, long-running tasks |
| 3 | **Multimodal Agent** | Processes PDFs, images, and mixed-format documents | When the process uses more than text — document extraction, visual understanding |
| 4 | **Memory-Augmented Agent** | Short-term and long-term memory across sessions | From stateless to stateful intelligence — context persistence, personalization |
| 5 | **Supervisor Agent** | Decomposes tasks, delegates to specialists, synthesizes results | When the process spans multiple domains with different tools and knowledge |
