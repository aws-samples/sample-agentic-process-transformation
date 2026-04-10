# Agentic Process Transformation

Patterns, accelerators, and hands-on workshops for building reimagined business processes with multi-agent workflows using:
- [Strands Agents](https://github.com/strands-agents/strands-agents)
- Amazon Bedrock
- Amazon Bedrock AgentCore
- Model Context Protocol (MCP)

[Get started here](#-getting-started--deploy-the-workshop-infrastructure)

---

## What's Inside

This repo has two main sections:

### Agent Orchestration Patterns

A reusable pattern library for building individual agents and orchestrating them together. Each pattern is a self-contained Jupyter notebook that runs in Amazon SageMaker AI Studio.

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
| Authenticator | Amazon Nova 2 Lite | Validates beneficiary identity and coverage via MCP |
| Extractor | Amazon Nova 2 Lite | Extracts structured JSON from 7 document types |
| Policy Verification | Anthropic Claude Sonnet 4 | Cross-document consistency checks against policy terms |
| Communicator | Amazon Nova 2 Lite | Drafts claim decision notifications |

**Notebook sequence:**

| Notebook | What You Build |
|---|---|
| `00_end_to_end_demo/` | Interactive Streamlit app showing the full pipeline — run this first |
| `01_a_simple_agent/` | A simple Authenticator Agent with Amazon Nova 2 Lite reasoning |
| `02_tool_augmented_agents/` | Stub tools → MCP integration, document extraction with JSON schema |
| `03_multi_agent_orchestration/` | Intake Orchestrator with GraphBuilder, end-to-end pipeline |
| `04_agent_core_integration/` | Amazon Bedrock AgentCore Runtime (session isolation) and Memory (cross-phase context) |
| `05_human_in_the_loop_integration/` | AWS Step Functions callback pattern for human adjudication |

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
- [Amazon Bedrock](https://aws.amazon.com/bedrock/) — Managed LLM inference (Amazon Nova 2 Lite, Anthropic Claude Sonnet 4)
- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/) — Agent runtime with session isolation and persistent memory
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) — Standardized tool integration over stdio JSON-RPC
- [AWS Step Functions](https://aws.amazon.com/step-functions/) — Human-in-the-loop callback orchestration

---

## ⚡ Getting Started — Deploy the Workshop Infrastructure

### Prerequisites
- An AWS account with [Amazon Bedrock model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html) enabled for:
  - Amazon Nova 2 Lite (`us.amazon.nova-2-lite-v1:0`)
  - Amazon Nova Multimodal Embeddings (`amazon.nova-2-multimodal-embeddings-v1:0`)
  - Anthropic Claude Sonnet 4 (`us.anthropic.claude-sonnet-4-20250514-v1:0`)
- AWS CLI installed and configured with credentials
- Python 3.10+

### Step 1 — Deploy the CloudFormation stack

This creates the Amazon S3 bucket, Amazon DynamoDB tables, IAM roles, and an Amazon SageMaker execution role with all required permissions.

```bash
aws cloudformation deploy \
  --template-file cfn-workshop-setup.yaml \
  --stack-name agentic-workshop \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

### Step 2 — Get the S3 bucket name from the stack outputs

```bash
aws cloudformation describe-stacks \
  --stack-name agentic-workshop \
  --region us-east-1 \
  --query "Stacks[0].Outputs[?OutputKey=='S3BucketName'].OutputValue" \
  --output text
```

### Step 3 — Upload sample claim documents to S3

```bash
aws s3 cp 01-insurance-claims-processing/sample_data/ \
  s3://<YOUR_BUCKET_NAME>/claims-processing/claimant-data/ \
  --recursive
```

Replace `<YOUR_BUCKET_NAME>` with the output from Step 2.

### Step 4 — Set the bucket name as an environment variable

```bash
export WORKSHOP_S3_BUCKET=<YOUR_BUCKET_NAME>
```

### Step 5 — Install Python dependencies and start Jupyter

```bash
python3 -m venv venv
source venv/bin/activate

# For the orchestration patterns
pip install -r 00-agent-orchestration-patterns/requirements.txt

# For the insurance claims workshop
pip install -r 01-insurance-claims-processing/requirements.txt

jupyter lab
```

### Cleanup

To delete all workshop resources when you're done:

```bash
aws cloudformation delete-stack --stack-name agentic-workshop --region us-east-1
```

> Note: The S3 bucket is retained on stack deletion to prevent accidental data loss. Delete it manually if needed: `aws s3 rb s3://<YOUR_BUCKET_NAME> --force`

## Important Notices

> **Synthetic data only.** All sample documents (PDFs, JSON mock data) in this repository are entirely fictional and generated for educational purposes. No real personally identifiable information (PII), protected health information (PHI), or financial data is included.

> **Not for production use.** This workshop demonstrates agentic patterns for learning purposes. The automated claim adjudication shown here requires human-in-the-loop review for any production deployment involving financial decisions.

## License

This library is licensed under the MIT-0 License. See the [LICENSE](LICENSE) file.
