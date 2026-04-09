# End-to-End Claims Processing Demo

This is the **starting point** of the workshop. Before building anything, you'll interact with a fully working claims processing pipeline to see what you'll be constructing in the following notebooks.

## What You'll See

The demo is a Streamlit web app for two personas:

**Claimant Portal** — Here, claimiants submit a life insurance claim by entering claim details and uploading documents (PDFs). The Intake Orchestrator runs the full pipeline: document retrieval, authentication, extraction, policy verification, adjudication, and (if approved) a notification draft from the Communicator Agent.

**Adjudicator Dashboard** — When a claim is flagged (e.g., an exclusion triggered), it's escalated to a human reviewer via AWS Step Functions. You'll see the pending claim, review the evidence, and make an approve/deny decision. The pipeline then resumes and completes.

**Agent Memory** — See how AgentCore Memory captures the full pipeline conversation (short-term) and extracts facts like policy numbers and verification decisions (long-term). Submit multiple claims to see cross-session context retrieval in action.

## How to Run

1. Open `00_launch_demo.ipynb`
2. Run all cells — this provisions the demo infrastructure (DynamoDB table, Step Functions state machine) and starts the Streamlit app
3. Follow the URL printed in the last cell to open the app
4. Try both flows:
   - **Happy path**: Submit a claim with natural death circumstances → auto-approved → notification drafted
   - **Escalation path**: Submit a claim with "suicide" in the death circumstances → escalated → switch to Adjudicator tab → review and decide

## After the Demo

Run the **Cleanup** cell in the launcher notebook to tear down all demo resources. The demo uses its own isolated resources (`demo-` prefixed) — nothing in notebooks 01-05 depends on them.

## What You'll Build

In the following notebooks, you'll build each component from scratch:

| Folder | What You Build |
|---|---|
| `01_build_a_simple_agent` | Your first Strands agent with a system prompt and model |
| `02_tool_enabled_agents` | Specialist agents with MCP tools and document processing |
| `03_multi_agent_orchestration` | Intake Orchestrator with GraphBuilder, end-to-end pipeline |
| `04_agent_core_integration` | AgentCore Runtime (sessions) and Memory (cross-phase context) |
| `05_human_in_the_loop` | (Optional) Step Functions callback pattern for human adjudication |
