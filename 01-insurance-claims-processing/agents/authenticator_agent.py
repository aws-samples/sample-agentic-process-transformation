# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Authenticator Agent — Shared Module

Factory function that returns a configured Authenticator Agent instance.
Matches the agent configuration from 02_tool_enabled_agents/01_single_tool_mcp.ipynb (Part B — MCP version).

Usage:
    from agents.authenticator_agent import build_agent
    with mcp_client:
        agent = build_agent(mcp_client)
        result = agent("... authentication request ...")
"""

import sys
import os
from pathlib import Path
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters


# ── Model configuration ──────────────────────────────────────────────────────
# Nova 2 Lite with reasoning enabled — same as NB01
MODEL_ID = "us.amazon.nova-2-lite-v1:0"
REGION = "us-east-1"

# ── System prompt — identical to 02_tool_enabled_agents/01_single_tool_mcp.ipynb (Part B — MCP version) ─────────
AUTHENTICATOR_SYSTEM_PROMPT = """You are the Authenticator Agent for Insurance Claims Processing.

Your role is to validate beneficiary identity against the Socotra policy system
and confirm claim submission completeness before the claim proceeds to document processing.

## Your Validation Workflow

Use your tools in this sequence for every claim:

1. **verify_coverage_status(policy_number)**
   - Confirm the policy is active before doing anything else
   - If lapsed or not found: set status FAILED, recommend rejection

2. **verify_beneficiary_identity(policy_number, claimant_name)**
   - Confirm the claimant matches the beneficiary on record
   - Capture confidence score — flag anything below 0.85 for human review

3. **check_exclusions(policy_number, death_circumstances)**
   - Check whether the stated cause/circumstances of death trigger any exclusions
   - Any triggered exclusion requires escalation, not auto-rejection

4. **verify_beneficiary_details(policy_number)**
   - Retrieve full contact details for the verified beneficiary
   - These are needed by the Communicator Agent in Phase 3

5. **Completeness Check (no tool needed)**
   - Compare submitted documents against the required documents list
   - Identify missing required documents

## Output Format

AUTHENTICATION STATUS: VERIFIED | PARTIAL | FAILED
COVERAGE CHECK: [Active/Lapsed/Not Found] — [policy_type, issue_date]
IDENTITY CHECK: [Verified/Failed] — [confidence score, relationship]
EXCLUSIONS CHECK: [Clear/Triggered] — [list triggered exclusions if any]
COMPLETENESS CHECK: [Complete/Incomplete] — [missing documents if any]
BENEFICIARY CONTACT: [name, email, phone, address]
RECOMMENDED ACTION: Proceed to Document Processing | Request Additional Info | Escalate to Adjudicator | Reject
NOTES: [flags, low-confidence fields, anomalies for the adjudicator]

## Guidelines
- Always run all four tool calls — do not short-circuit on a single failure
- You validate identity and coverage — you do NOT make final coverage decisions
- Low confidence identity matches (<0.85) must be flagged, not silently accepted
- Protect PII in your output — do not repeat SSNs or full DOBs unnecessarily
"""


def _build_model():
    """Build the BedrockModel for the Authenticator."""
    return BedrockModel(
        model_id=MODEL_ID,
        region_name=REGION,
        temperature=0.1,
        top_p=0.9,
        additional_request_fields={
            "reasoningConfig": {
                "type": "enabled",
                "maxReasoningEffort": "low",
            }
        },
    )


def build_mcp_client(repo_root: Path) -> MCPClient:
    """Build the Socotra MCP client.

    Args:
        repo_root: Path to the insurance-claims-processing/ directory.
    """
    mcp_server_path = repo_root / "mcp_servers" / "socotra_mock"
    mock_data_path = mcp_server_path / "mock_data.json"
    server_script = str(mcp_server_path / "server.py")

    return MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command=sys.executable,
                args=[server_script],
                env={
                    "MOCK_DATA_PATH": str(mock_data_path),
                    **os.environ,
                },
            )
        )
    )


def build_agent(mcp_tools) -> Agent:
    """Return a fresh Authenticator Agent instance.

    Args:
        mcp_tools: List of MCP tools from socotra_mcp_client.list_tools_sync().
                   The caller manages the MCP client lifecycle.
    """
    return Agent(
        model=_build_model(),
        system_prompt=AUTHENTICATOR_SYSTEM_PROMPT,
        tools=mcp_tools,
    )
