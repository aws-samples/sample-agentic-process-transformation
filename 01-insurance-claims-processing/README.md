# Insurance Claims Processing Workshop

Multi-agent orchestration workshop for life insurance death benefit claims processing using Strands Agents, Amazon Bedrock, and Model Context Protocol (MCP).

## Overview

This workshop walks through building an agentic workflow where specialized agents handle identity verification, document extraction, policy verification, adjudication, and beneficiary communication. You start with a simple reasoning agent and progressively add tools, MCP integration, multi-agent orchestration, persistent memory, and human-in-the-loop escalation.

## Architecture

The pipeline runs in three phases:

1. **Pre-Processing** — Authenticator Agent validates beneficiary identity, Extractor Agent pulls structured data from claim documents using Nova 2 Lite, Policy Verification Agent checks coverage and exclusions against the Socotra policy system
2. **Adjudication** — Business rules flag claims for auto-approval or escalation to a human adjudicator via AWS Step Functions
3. **Post-Processing** — Communicator Agent drafts claim decision notifications to beneficiaries

An Intake Orchestrator (supervisor agent) coordinates the full lifecycle using Strands `GraphBuilder` for the pre-processing DAG and `@tool` functions for each phase.

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
pip install -r requirements.txt
jupyter lab
```

## Notebook Sequence

Start with the end-to-end demo to see the finished product, then build each component from scratch:

| Notebook | What You Build |
|---|---|
| `00_end_to_end_demo/` | Interactive Streamlit app showing the full pipeline — run this first |
| `01_a_simple_agent/` | A simple Authenticator Agent with Nova 2 Lite reasoning |
| `02_tool_augmented_agents/` | Stub tools → MCP integration, document extraction with JSON schema pattern |
| `03_multi_agent_orchestration/` | Intake Orchestrator with GraphBuilder, end-to-end pipeline with S3 and DynamoDB |
| `04_agent_core_integration/` | AgentCore Runtime (session isolation) and Memory (cross-phase context) |
| `05_human_in_the_loop_integration/` | Step Functions callback pattern for human adjudication (optional) |

## Project Structure

```
insurance-claims-processing/
├── agents/                          — Shared agent modules (factory pattern)
│   ├── authenticator_agent.py       — Identity + coverage verification via MCP
│   ├── extractor_agent.py           — Document extraction with Nova 2 Lite
│   ├── policy_verification_agent.py — Policy terms + cross-document consistency
│   └── communicator_agent.py        — Claim decision notification drafting
├── mcp_servers/
│   └── socotra_mock/                — Mock policy administration MCP server
│       ├── server.py                — FastMCP server with 5 tools
│       └── mock_data.json           — 3 sample policies with full claim data
├── notebooks/                       — Workshop notebooks (00–05)
│   └── 00_end_to_end_demo/
│       ├── app.py                   — Streamlit UI (claimant portal + adjudicator dashboard)
│       └── demo_claim_documents/    — Sample PDFs for the demo
├── sample_data/                     — 7 sample claim PDFs
└── requirements.txt
```

## Agents

Each agent module exposes a `build_agent()` factory function that returns a fresh Strands `Agent` instance with empty message history. This avoids state bleed between pipeline runs.

| Agent | Model | Tools | Role |
|---|---|---|---|
| Authenticator | Nova 2 Lite (reasoning) | MCP: verify_beneficiary_identity, verify_coverage_status, check_exclusions, verify_beneficiary_details | Validates identity and coverage |
| Extractor | Nova 2 Lite (reasoning) | @tool: process_claim_documents | Extracts structured JSON from 7 document types |
| Policy Verification | Claude Sonnet 4 | MCP: verify_coverage_status, calculate_death_benefit, check_exclusions | Cross-document consistency checks |
| Communicator | Nova 2 Lite | None | Drafts claim decision letters |

## MCP Server

The Socotra mock server (`mcp_servers/socotra_mock/server.py`) simulates a policy administration system over stdio JSON-RPC. It provides 5 tools:

- `verify_beneficiary_identity` — Match claimant against policy beneficiaries
- `verify_coverage_status` — Check active/lapsed status
- `calculate_death_benefit` — Compute payout amount
- `check_exclusions` — Match death circumstances against policy exclusions
- `verify_beneficiary_details` — Retrieve full beneficiary contact info

## Sample Data

`sample_data/` contains 7 PDF claim documents and their pre-extracted JSON counterparts:

- Death certificate
- Whole life insurance policy
- Medical records
- Will document
- Trust document
- Beneficiary ID (driver's license)
- Police report

## End-to-End Demo

The Streamlit app (`notebooks/00_end_to_end_demo/app.py`) provides three tabs:

- **Claims Pipeline** — Submit a claim and watch the Intake Orchestrator call each tool in sequence
- **Adjudicator Dashboard** — Review escalated claims and submit approve/deny decisions
- **Agent Memory** — View AgentCore short-term events and long-term extracted facts

Run it via the `00_launch_demo.ipynb` notebook.

## License

This workshop is provided for educational purposes.
