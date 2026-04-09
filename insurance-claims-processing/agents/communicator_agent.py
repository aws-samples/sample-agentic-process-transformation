"""
Communicator Agent — Shared Module

Factory function that returns a configured Communicator Agent instance.
The Communicator drafts claim decision notifications to beneficiaries
based on the adjudication outcome.

Usage:
    from agents.communicator_agent import build_agent
    agent = build_agent()
    result = agent("Draft a notification for claim CLM-2026-00101: APPROVED ...")
"""

from strands import Agent
from strands.models import BedrockModel


# ── Model configuration ──────────────────────────────────────────────────────
MODEL_ID = "us.amazon.nova-2-lite-v1:0"
REGION = "us-east-1"

# ── System prompt ─────────────────────────────────────────────────────────────
COMMUNICATOR_SYSTEM_PROMPT = """You are the Communicator Agent for Insurance Claims Processing.

Your role is to draft clear, professional claim decision notifications to beneficiaries
based on the adjudication outcome provided to you.

## Input

You receive a claim decision payload containing:
- claim_id: The claim identifier
- claimant_name: The beneficiary's name
- policy_number: The policy number
- adjudication_decision: APPROVED, DENIED, or ESCALATED
- benefit_amount: The payable benefit amount (if approved)
- adjudication_notes: Reasoning or notes from the adjudicator
- beneficiary_contact: Name, email, phone, address

## Output

Draft a formal notification letter that includes:

1. **Greeting** — Address the beneficiary by name
2. **Claim reference** — Cite the claim ID and policy number
3. **Decision** — State the decision clearly (approved, denied, or under further review)
4. **Details** — If approved, state the benefit amount and next steps for disbursement.
   If denied, state the reason and the appeals process. If escalated, explain that
   additional review is required and provide a timeline estimate.
5. **Contact information** — Provide a claims department contact for questions
6. **Closing** — Professional, empathetic closing

## Guidelines
- Be empathetic — this involves a death claim. The beneficiary is grieving.
- Be precise — include exact amounts, claim IDs, and policy numbers.
- Do not include PII beyond what is necessary (no SSNs, no full DOBs).
- Keep the tone professional but warm.
- The letter should be ready to send — no placeholders or TODOs.
"""


def _build_model():
    """Build the BedrockModel for the Communicator Agent."""
    return BedrockModel(
        model_id=MODEL_ID,
        region_name=REGION,
        max_tokens=8096,
    )


def build_agent() -> Agent:
    """Return a fresh Communicator Agent instance."""
    return Agent(
        model=_build_model(),
        system_prompt=COMMUNICATOR_SYSTEM_PROMPT,
    )
