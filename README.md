# Agentic Process Transformation

Patterns, accelerators, and a hands-on workshop for building multi-agent workflows with [Strands Agents](https://github.com/strands-agents/strands-agents), Amazon Bedrock, and Model Context Protocol (MCP).

## What's Inside

This repo has two main sections:

### Agent Orchestration Patterns

A reusable pattern library for building individual agents and orchestrating them together. Each pattern is a self-contained Jupyter notebook that runs in SageMaker AI Studio.

**Agent Patterns** — how to build individual agents:

| Pattern | Description |
|---|---|
| RAG Agent | Retrieves external knowledge to ground responses in real data |
| Tool Agent (Function Calling) | Agent calls internal functions — decides which, constructs arguments, executes |
| Tool Agent (MCP) | Agent delegates to an MCP server with its own runtime |
| Multimodal Agent | Processes PDFs, images, and mixed-format documents |
| Memory-Augmented Agent | Short-term and long-term memory across sessions |
| Supervisor Agent | Decomposes tasks, delegates to specialists, synthesizes results |

**Workflow Patterns** — how to orchestrate multiple agents:

| Pattern | Description |
|---|---|
| Routing | Classifies incoming work and dispatches to the right specialist |
| Parallelization | Fan out independent tasks to multiple agents, then aggregate |
| Human-in-the-Loop | Agent pauses at decision points for human approval |
| Reflect and Refine | Generator + reviewer loop with feedback until quality passes |

### Insurance Claims Processing Workshop

A complete end-to-end example: a life insurance death benefit claims pipeline built with four specialized agents. You start with a simple reasoning agent and progressively add tools, MCP integration, multi-agent orchestration, persistent memory, and human-in-the-loop escalation.

**Agents:**

| Agent | Model | Role |
|---|---|---|
| Authenticator | Nova 2 Lite | Validates beneficiary identity and coverage via MCP |
| Extractor | Nova 2 Lite | Extracts structured JSON from 7 document types |
| Policy Verification | Claude Sonnet 4 | Cross-document consistency checks against policy terms |
| Communicator | Nova 2 Lite | Drafts claim decision notifications |

**Notebook sequence:**

| Notebook | What You Build |
|---|---|
| `00_end_to_end_demo/` | Interactive Streamlit app showing the full pipeline — run this first |
| `01_a_simple_agent/` | A simple Authenticator Agent with Nova 2 Lite reasoning |
| `02_tool_augmented_agents/` | Stub tools → MCP integration, document extraction with JSON schema |
| `03_multi_agent_orchestration/` | Intake Orchestrator with GraphBuilder, end-to-end pipeline |
| `04_agent_core_integration/` | AgentCore Runtime (session isolation) and Memory (cross-phase context) |
| `05_human_in_the_loop_integration/` | Step Functions callback pattern for human adjudication |

## Prerequisites

- Python 3.10+
- AWS account with Bedrock model access enabled:
  - Amazon Nova 2 Lite (`us.amazon.nova-2-lite-v1:0`)
  - Claude Sonnet 4 (`us.anthropic.claude-sonnet-4-20250514-v1:0`)
- AWS CLI configured with credentials
- Region: `us-east-1`

## Quick Start

```bash
python3 -m venv venv
source venv/bin/activate

# For the orchestration patterns
pip install -r 00-agent-orchestration-patterns/requirements.txt

# For the insurance claims workshop
pip install -r 01-insurance-claims-processing/requirements.txt

jupyter lab
```

## Project Structure

```
├── 00-agent-orchestration-patterns/
│   ├── agent-patterns/               # 6 individual agent patterns
│   ├── agent-workflow-patterns/      # 4 multi-agent orchestration patterns
│   └── common/                       # Shared MCP servers and sample data
│
├── 01-insurance-claims-processing/
│   ├── agents/                       # 4 agent modules (factory pattern)
│   ├── mcp_servers/socotra_mock/     # Mock policy administration system
│   ├── notebooks/                    # Progressive workshop notebooks (00–05)
│   └── sample_data/                  # 7 sample claim PDFs
```

## Key Technologies

- [Strands Agents](https://github.com/strands-agents/strands-agents) — Agent framework with tool orchestration and graph-based workflows
- [Amazon Bedrock](https://aws.amazon.com/bedrock/) — Managed LLM inference (Nova 2 Lite, Claude Sonnet 4)
- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/) — Agent runtime with session isolation and persistent memory
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) — Standardized tool integration over stdio JSON-RPC
- [AWS Step Functions](https://aws.amazon.com/step-functions/) — Human-in-the-loop callback orchestration

## License

This project is provided for educational purposes.
