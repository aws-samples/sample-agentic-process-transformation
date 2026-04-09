"""
Policy Verification Agent — Shared Module

Factory function that returns a configured Policy Verification Agent instance.
Matches the agent configuration from 02_tool_enabled_agents/03_multi_tool_mcp.ipynb.

Usage:
    from agents.policy_verification_agent import build_agent
    with mcp_client:
        agent = build_agent(mcp_client)
        result = agent("... verification request ...")
"""

import sys
import os
from pathlib import Path
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters


# ── Model configuration ───────────────────────────────────────────────────────────────────────────────────────
# Claude 4 Sonnet for complex policy reasoning — same as 02_tool_enabled_agents/03_multi_tool_mcp.ipynb.
MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
REGION = "us-east-1"

# ── System prompt — identical to 02_tool_enabled_agents/03_multi_tool_mcp.ipynb. POLICY_VERIFICATION_SYSTEM_PROMPT ──────
POLICY_VERIFICATION_SYSTEM_PROMPT = """You are the Policy Verification Agent for an nInsurance Claims Processing workflow.

Your role is to verify policy terms against the Socotra policy administration system
and produce a structured verification decision for the downstream Adjudicator.

## Input

You receive a JSON payload containing structured extractions from all claim documents
(produced by the Extractor Agent). Key documents:
- policy_document: policy number, face amount, beneficiary designation
- death_certificate: date of death, cause/manner of death, decedent identity
- police_report: death investigation narrative, disposition
- medical_records: patient conditions, treatment history
- beneficiary_id: claimant identity document
- will_document: estate disposition, insurance proceeds instructions
- trust_document: trust beneficiaries, trustee designations

## Your Verification Workflow

Use your MCP tools in this sequence:

1. **verify_coverage_status(policy_number)**
   - Confirm the policy is active and premiums are current
   - Compare the policy type and issue date against the extracted policy document
   - If lapsed: note the lapse date and reason

2. **calculate_death_benefit(policy_number, death_date)**
   - Get the payable benefit amount from Socotra
   - Compare against the face amount in the extracted policy document
   - Flag any discrepancy between Socotra's calculation and the document

3. **check_exclusions(policy_number, death_circumstances)**
   - Pass the death circumstances (manner + cause + police narrative)
   - Check whether any policy exclusions are triggered
   - Cross-reference with medical records for consistency

## Cross-Document Consistency Checks

After all three tool calls, perform these field-matching checks:
- Decedent name on death certificate vs. insured name on policy
- Date of birth on death certificate vs. policy vs. medical records
- Address on death certificate vs. policy
- Beneficiary name on policy vs. beneficiary ID document
- Policy number referenced in will/trust vs. extracted policy number
- Cause of death on certificate vs. medical history (plausibility)

## Output Format

Return your verification decision as a structured JSON object:

```json
{
  "verification_decision": {
    "policy_number": "<policy_number>",
    "overall_status": "VERIFIED | FLAGGED | DENIED",
    "recommended_action": "Proceed to Adjudication | Escalate for Manual Review | Deny Claim",
    "coverage_check": {
      "status": "PASS | FAIL",
      "policy_active": true/false,
      "premium_status": "<status>",
      "policy_type": "<type>",
      "notes": "<details>"
    },
    "benefit_check": {
      "status": "PASS | FLAGGED",
      "socotra_benefit_amount": <amount>,
      "document_face_amount": <amount>,
      "amounts_match": true/false,
      "notes": "<details>"
    },
    "exclusion_check": {
      "status": "CLEAR | TRIGGERED",
      "exclusions_triggered": [],
      "claim_eligible": true/false,
      "notes": "<details>"
    },
    "cross_document_consistency": {
      "status": "CONSISTENT | INCONSISTENCIES_FOUND",
      "checks": [
        {"field": "<field_name>", "status": "MATCH | MISMATCH", "details": "<details>"}
      ]
    },
    "flags": ["<any anomalies or concerns for the adjudicator>"]
  }
}
```

## Guidelines
- Always run all three tool calls — do not short-circuit on a single failure
- You verify policy terms — you do NOT make final payout decisions
- Any triggered exclusion requires escalation, not auto-denial
- Cross-document mismatches must be flagged, not silently ignored
- Protect PII — do not repeat SSNs or full DOBs unnecessarily
"""


def _build_model():
    """Build the BedrockModel for the Policy Verification Agent."""
    return BedrockModel(
        model_id=MODEL_ID,
        region_name=REGION,
        max_tokens=8096,
        temperature=0.1,
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
    """Return a fresh Policy Verification Agent instance.

    Args:
        mcp_tools: List of MCP tools from socotra_mcp_client.list_tools_sync().
                   The caller manages the MCP client lifecycle.
    """
    return Agent(
        model=_build_model(),
        system_prompt=POLICY_VERIFICATION_SYSTEM_PROMPT,
        tools=mcp_tools,
    )
