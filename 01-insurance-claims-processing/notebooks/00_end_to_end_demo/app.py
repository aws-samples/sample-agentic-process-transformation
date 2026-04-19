# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
End-to-End Claims Processing Demo — Streamlit App (v3)

Uses the real Intake Orchestrator (supervisor agent with 5 tools).
Each tool captures its results for step-by-step UI display.
"""

import streamlit as st
import boto3
import json
import sys
import os
import re
import uuid
import time
from pathlib import Path
from datetime import datetime
from decimal import Decimal

# ── Path setup ────────────────────────────────────────────────────────────────
_cwd = Path(__file__).parent.resolve()
REPO_ROOT = _cwd
for _parent in [_cwd] + list(_cwd.parents):
    if (_parent / "agents").is_dir() and (_parent / "mcp_servers").is_dir():
        REPO_ROOT = _parent
        break
sys.path.insert(0, str(REPO_ROOT))

MCP_SERVER_PATH = REPO_ROOT / "mcp_servers" / "socotra_mock"
MOCK_DATA_PATH = MCP_SERVER_PATH / "mock_data.json"
SOCOTRA_SERVER_SCRIPT = str(MCP_SERVER_PATH / "server.py")

# ── AWS config (demo-namespaced) ──────────────────────────────────────────────
REGION = "us-east-1"
S3_BUCKET = os.environ.get("WORKSHOP_S3_BUCKET", "")
S3_SOURCE_PREFIX = "claims-processing/claimant-data/"
DYNAMODB_TABLE = "demo-claims-metadata"

s3_client = boto3.client("s3", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
sfn_client = boto3.client("stepfunctions", region_name=REGION)
sts_client = boto3.client("sts", region_name=REGION)
ACCOUNT_ID = sts_client.get_caller_identity()["Account"]

_config_file = Path(__file__).parent / ".demo_config.json"
if _config_file.exists():
    _cfg = json.loads(_config_file.read_text())
    STATE_MACHINE_ARN = _cfg.get("STATE_MACHINE_ARN", "")
    ACTIVITY_ARN = _cfg.get("ACTIVITY_ARN", "")
else:
    STATE_MACHINE_ARN = f"arn:aws:states:{REGION}:{ACCOUNT_ID}:stateMachine:demo-claims-hitl-adjudication"
    ACTIVITY_ARN = f"arn:aws:states:{REGION}:{ACCOUNT_ID}:activity:demo-claims-human-review"

# ── Strands + AgentCore imports ───────────────────────────────────────────────
from strands import Agent, tool
from strands.models import BedrockModel
from strands.multiagent import GraphBuilder
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters

from agents import authenticator_agent, extractor_agent, policy_verification_agent, communicator_agent

from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig, RetrievalConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager


def get_demo_memory_id():
    memo_file = Path(__file__).parent / ".demo_memory_id"
    if memo_file.exists():
        return memo_file.read_text().strip()
    return os.environ.get("DEMO_MEMORY_ID", "")


DEMO_MEMORY_ID = get_demo_memory_id()
memory_client = MemoryClient(region_name=REGION) if DEMO_MEMORY_ID else None


@st.cache_resource
def get_mcp_client():
    client = MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command=sys.executable,
                args=[SOCOTRA_SERVER_SCRIPT],
                env={"MOCK_DATA_PATH": str(MOCK_DATA_PATH), **os.environ},
            )
        )
    )
    client.__enter__()
    return client


# ── Pipeline trace: each tool appends its results here ────────────────────────
# This dict is populated during a single supervisor run, then read by the UI.
_pipeline_trace = {}


def reset_trace():
    global _pipeline_trace
    _pipeline_trace = {
        "documents": None,
        "auth": None,
        "extraction": None,
        "extraction_data": {},
        "verification": None,
        "adjudication": None,
        "communication": None,
        "persist": None,
        "escalation_arn": None,
    }

# ══════════════════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS — same as NB 03/02 end-to-end orchestration
# Each tool captures results in _pipeline_trace for UI display.
# ══════════════════════════════════════════════════════════════════════════════

LOCAL_DOCS_DIR = Path("demo_claim_documents")
LOCAL_DOCS_DIR.mkdir(exist_ok=True)


@tool
def retrieve_claim_documents(s3_bucket: str, s3_prefix: str) -> str:
    """Download claim PDF documents from S3.
    Args:
        s3_bucket: S3 bucket name
        s3_prefix: S3 key prefix
    """
    response = s3_client.list_objects_v2(Bucket=s3_bucket, Prefix=s3_prefix)
    s3_objects = response.get("Contents", [])
    downloaded = []
    for obj in s3_objects:
        key = obj["Key"]
        filename = key.split("/")[-1]
        if not filename or not filename.endswith(".pdf"):
            continue
        local_path = LOCAL_DOCS_DIR / filename
        s3_client.download_file(s3_bucket, key, str(local_path))
        downloaded.append({"filename": filename, "size": obj["Size"], "path": str(local_path)})
    _pipeline_trace["documents"] = downloaded
    return json.dumps({"status": "success", "document_paths": [d["path"] for d in downloaded]})


auth_passed = True


@tool
def run_preprocessing_graph(claim_prompt: str) -> str:
    """Run the 3-node pre-processing graph: authenticate, extract, verify_policy.
    Args:
        claim_prompt: Full claim submission prompt with all claim details
    """
    global auth_passed
    auth_passed = True
    mcp_client = get_mcp_client()
    mcp_tools = mcp_client.list_tools_sync()

    auth_agent = authenticator_agent.build_agent(mcp_tools)
    output_dir = Path("demo_extracted_output")
    output_dir.mkdir(exist_ok=True)
    extract_agent = extractor_agent.build_agent(output_dir=output_dir)
    verify_agent = policy_verification_agent.build_agent(mcp_tools)

    def check_auth_passed(state):
        return auth_passed

    builder = GraphBuilder()
    builder.add_node(auth_agent, "authenticate")
    builder.add_node(extract_agent, "extract")
    builder.add_node(verify_agent, "verify_policy")
    builder.set_entry_point("authenticate")
    builder.add_edge("authenticate", "extract", condition=check_auth_passed)
    builder.add_edge("extract", "verify_policy")
    graph = builder.build()
    result = graph(claim_prompt)
    result_text = str(result)

    # Capture per-agent results from the graph output
    # The graph result contains all agent outputs concatenated
    _pipeline_trace["preprocessing_raw"] = result_text

    # Try to read extracted JSONs
    for f in output_dir.glob("*_extracted.json"):
        try:
            with open(f, encoding="utf-8") as fh:
                _pipeline_trace["extraction_data"][f.stem.replace("_extracted", "")] = json.load(fh)
        except Exception as e:
            print(f"Warning: failed to load {f.name}: {e}")

    return result_text


@tool
def adjudicate_claim(claim_id: str, verification_summary: str, auth_summary: str) -> str:
    """Apply business rules. Escalate to Step Functions if flags detected.
    Args:
        claim_id: The claim identifier
        verification_summary: Verification decision from pre-processing
        auth_summary: Authentication result
    """
    combined = (verification_summary + " " + auth_summary).upper()
    flags = []
    if "SUICIDE" in combined:
        flags.append("suicide_mentioned")
    # Only flag exclusions if genuinely triggered (not just mentioned as "CLEAR")
    if "TRIGGERED" in combined:
        # Check it's not "no exclusions triggered" or "0 triggered"
        triggered_context = combined.split("TRIGGERED")[0][-80:]
        if "NO " not in triggered_context and "CLEAR" not in triggered_context and "0 " not in triggered_context:
            flags.append("exclusion_triggered")
    if "INCONSISTENC" in combined:
        flags.append("cross_document_inconsistency")

    if not flags:
        adj = {"decision": "APPROVED", "rationale": "All checks passed. No flags detected.", "flags": []}
        _pipeline_trace["adjudication"] = adj
        return json.dumps({"claim_id": claim_id, "adjudication_decision": "APPROVED",
                           "rationale": adj["rationale"], "adjudicated_at": datetime.utcnow().isoformat() + "Z"})

    # Escalate
    adj = {"decision": "ESCALATED", "rationale": f"Flags: {', '.join(flags)}. Requires human review.", "flags": flags}
    _pipeline_trace["adjudication"] = adj

    # Start Step Functions
    try:
        claim_summary = f"Claim {claim_id} flagged: {flags}. Auth: {auth_summary[:300]}. Verify: {verification_summary[:300]}"
        execution = sfn_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=f"demo-{claim_id}-{uuid.uuid4().hex[:8]}",
            input=json.dumps({"claim_id": claim_id, "claim_summary": claim_summary,
                              "flags": json.dumps(flags), "submitted_at": datetime.utcnow().isoformat() + "Z"}),
        )
        _pipeline_trace["escalation_arn"] = execution["executionArn"]
    except Exception as e:
        _pipeline_trace["escalation_arn"] = f"Error: {e}"

    return json.dumps({"claim_id": claim_id, "adjudication_decision": "ESCALATED",
                       "rationale": adj["rationale"], "flags": flags})


@tool
def send_claim_decision(
    claim_id: str, claimant_name: str, policy_number: str,
    adjudication_decision: str, benefit_amount: str,
    adjudication_notes: str, beneficiary_email: str,
) -> str:
    """Draft a claim decision notification using the Communicator Agent.
    Args:
        claim_id: Claim identifier
        claimant_name: Beneficiary name
        policy_number: Policy number
        adjudication_decision: APPROVED, DENIED, or ESCALATED
        benefit_amount: Payable benefit amount
        adjudication_notes: Decision rationale
        beneficiary_email: Beneficiary email
    """
    comm_agent = communicator_agent.build_agent()
    prompt = (
        f"Draft a claim decision notification:\n\n"
        f"Claim ID: {claim_id}\nClaimant: {claimant_name}\nPolicy: {policy_number}\n"
        f"Decision: {adjudication_decision}\nBenefit Amount: {benefit_amount}\n"
        f"Notes: {adjudication_notes}\nBeneficiary Email: {beneficiary_email}\n"
    )
    result = comm_agent(prompt)
    notification_text = str(result)
    _pipeline_trace["communication"] = notification_text
    return json.dumps({"status": "notification_drafted", "claim_id": claim_id,
                       "notification_preview": notification_text[:1000]})


@tool
def persist_claim_to_dynamodb(
    claim_id: str, policy_number: str, claimant_name: str,
    date_of_death: str, auth_summary: str, verification_summary: str,
    adjudication_decision: str, adjudication_notes: str, notification_status: str,
) -> str:
    """Write claim record to DynamoDB with all phase results.
    Args:
        claim_id: Claim identifier
        policy_number: Policy number
        claimant_name: Claimant name
        date_of_death: Date of death
        auth_summary: Auth result
        verification_summary: Verification result
        adjudication_decision: Decision
        adjudication_notes: Rationale
        notification_status: Whether notification was sent
    """
    from botocore.exceptions import ClientError
    stage = "pending_human_review" if adjudication_decision == "ESCALATED" else "pipeline_complete"
    record = {
        "claim_id": claim_id, "policy_number": policy_number,
        "claimant_name": claimant_name, "date_of_death": date_of_death,
        "auth_result_summary": auth_summary[:2000],
        "verification_summary": verification_summary[:3000],
        "adjudication_decision": adjudication_decision,
        "adjudication_notes": adjudication_notes,
        "notification_status": notification_status,
        "stage": stage, "created_at": datetime.utcnow().isoformat() + "Z",
    }
    try:
        table = dynamodb.create_table(
            TableName=DYNAMODB_TABLE,
            KeySchema=[{"AttributeName": "claim_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "claim_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            table = dynamodb.Table(DYNAMODB_TABLE)
        else:
            raise
    table.put_item(Item=record)
    _pipeline_trace["persist"] = {"stage": stage, "claim_id": claim_id}
    return json.dumps({"status": "success", "claim_id": claim_id, "stage": stage})

# ══════════════════════════════════════════════════════════════════════════════
# INTAKE ORCHESTRATOR — Supervisor Agent (same as NB 03/02)
# ══════════════════════════════════════════════════════════════════════════════

SUPERVISOR_SYSTEM_PROMPT = (
    "You are the Intake Orchestrator — the supervisor agent for Insurance Claims Processing.\n\n"
    "## Your Role\n"
    "You coordinate the full claim lifecycle across three phases.\n\n"
    "## Workflow\n"
    "When you receive a claim submission:\n"
    "1. Call retrieve_claim_documents to download claim documents from S3\n"
    "2. Call run_preprocessing_graph — include the EXACT document_paths from retrieve_claim_documents. "
    "Do NOT construct filenames yourself.\n"
    "3. Call adjudicate_claim with the claim_id, verification_summary, and auth_summary\n"
    "4. If adjudication is APPROVED, call send_claim_decision with the claim details and beneficiary email\n"
    "5. Call persist_claim_to_dynamodb with ALL results\n"
    "6. Summarize what you completed across all phases\n\n"
    "## Guidelines\n"
    "- Always run all phases in order — do not skip steps\n"
    "- If adjudication returns ESCALATED, persist with notification_status='PENDING_HUMAN_REVIEW' "
    "and do NOT send notification\n"
    "- In your final summary, report what YOU completed — do not echo specialist agent recommendations\n"
    "- Include the adjudication decision and whether the notification was sent\n"
)

supervisor_model = BedrockModel(
    model_id="us.amazon.nova-2-lite-v1:0",
    region_name=REGION,
    max_tokens=8096,
    additional_request_fields={
        "reasoningConfig": {"type": "enabled", "maxReasoningEffort": "low"}
    },
)


def build_supervisor():
    """Build a fresh Intake Orchestrator agent with all 5 tools."""
    return Agent(
        model=supervisor_model,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        tools=[
            retrieve_claim_documents,
            run_preprocessing_graph,
            adjudicate_claim,
            send_claim_decision,
            persist_claim_to_dynamodb,
        ],
    )


def _summarize_extraction(data, max_fields=8):
    """Compact summary of extracted document data for display."""
    if isinstance(data, dict):
        summary = {}
        count = 0
        for k, v in data.items():
            if count >= max_fields:
                summary["..."] = f"({len(data) - max_fields} more fields)"
                break
            if isinstance(v, dict):
                summary[k] = {sk: sv for i, (sk, sv) in enumerate(v.items()) if i < 4}
            elif isinstance(v, list):
                summary[k] = f"[{len(v)} items]"
            else:
                summary[k] = v
            count += 1
        return summary
    return data

# ══════════════════════════════════════════════════════════════════════════════
# STREAMLIT UI
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="Claims Processing Demo", page_icon="\U0001f3db\ufe0f", layout="wide")
st.title("\U0001f3db\ufe0f Insurance Claims Processing — End-to-End Demo")
st.caption("Powered by the Intake Orchestrator (Supervisor Agent) with Strands Agents, Amazon Bedrock, and AgentCore")

tab1, tab2, tab3 = st.tabs(["\U0001f4cb Claims Pipeline", "\u2696\ufe0f Adjudicator", "\U0001f9e0 Agent Memory"])

# ── Tab 1: Claims Pipeline ────────────────────────────────────────────────────
with tab1:
    st.header("Submit & Process a Claim")
    st.markdown("The **Intake Orchestrator** (supervisor agent) will process your claim through all phases, "
                "calling specialist agents as tools. Each decision is shown below as it happens.")

    with st.form("claim_form"):
        col1, col2 = st.columns(2)
        with col1:
            claim_id = st.text_input("Claim ID", value=f"CLM-2026-{uuid.uuid4().hex[:5].upper()}")
            policy_number = st.text_input("Policy Number", value="WL-4582-1093")
            claimant_name = st.text_input("Claimant Name", value="Lisa Doe")
        with col2:
            date_of_death = st.text_input("Date of Death", value="2026-01-15")
            beneficiary_email = st.text_input("Beneficiary Email", value="lisa.doe@example.com")
            death_circumstances = st.text_area(
                "Death Circumstances",
                value="Natural causes \u2014 congestive heart failure at residence",
                help="Try 'Suicide at residence' to trigger the escalation path",
            )
        submitted = st.form_submit_button("\U0001f680 Process Claim", use_container_width=True)

    if submitted:
        claim = {
            "claim_id": claim_id, "policy_number": policy_number,
            "claimant_name": claimant_name, "date_of_death": date_of_death,
            "death_circumstances": death_circumstances, "beneficiary_email": beneficiary_email,
        }

        session_id = f"demo-{claim_id}-{uuid.uuid4().hex[:8]}"
        if "sessions" not in st.session_state:
            st.session_state.sessions = []
        st.session_state.sessions.append({"claim_id": claim_id, "session_id": session_id})
        if "pipeline_results" not in st.session_state:
            st.session_state.pipeline_results = {}

        # Reset trace
        reset_trace()

        # Build supervisor prompt
        docs_list = "death_certificate, policy_document, medical_records, will_document, trust_document, beneficiary_id, police_report"
        supervisor_prompt = (
            "## New Claim Submission\n\n"
            f"**Claim ID:** {claim_id}\n"
            f"**Policy Number:** {policy_number}\n"
            f"**Claimant Name:** {claimant_name}\n"
            f"**Date of Death:** {date_of_death}\n"
            f"**Death Circumstances:** {death_circumstances}\n"
            f"**Beneficiary Email:** {beneficiary_email}\n\n"
            f"### Documents Submitted\n{docs_list}\n\n"
            f"### S3 Location\nBucket: {S3_BUCKET}\nPrefix: {S3_SOURCE_PREFIX}\n\n"
            "Process this claim through the FULL pipeline: retrieve documents, "
            "run pre-processing, adjudicate, send notification if approved, and persist."
        )

        # Run the Intake Orchestrator
        with st.status("\U0001f916 Intake Orchestrator is processing the claim...", expanded=True) as status:
            st.write("The supervisor agent is deciding which tools to call...")
            try:
                mcp_client = get_mcp_client()
                supervisor = build_supervisor()
                result = supervisor(supervisor_prompt)
                supervisor_response = str(result)
                status.update(label="\u2705 Intake Orchestrator complete", state="complete")
            except Exception as e:
                status.update(label="\u274c Pipeline failed", state="error")
                st.error(f"Error: {e}")
                supervisor_response = None

        # ── Display the Intake Orchestrator's actions ─────────────────────
        if supervisor_response:
            st.markdown("---")
            st.subheader("\U0001f916 Intake Orchestrator Actions")

            # Step 1: Document Retrieval
            docs = _pipeline_trace.get("documents")
            if docs:
                with st.expander("\U0001f4e5 Tool Call: retrieve_claim_documents", expanded=True):
                    st.markdown(f"**Orchestrator decided to:** Retrieve {len(docs)} documents from S3")
                    for d in docs:
                        st.text(f"  \u2705 {d['filename']} ({d['size']:,} bytes)")

            # Step 2: Pre-processing Graph
            raw = _pipeline_trace.get("preprocessing_raw")
            if raw:
                with st.expander("\U0001f504 Tool Call: run_preprocessing_graph", expanded=True):
                    st.markdown("**Orchestrator decided to:** Run the 3-node pre-processing graph "
                                "(Authenticator \u2192 Extractor \u2192 Policy Verification)")

                    # Show extracted document data
                    ext_data = _pipeline_trace.get("extraction_data", {})
                    if ext_data:
                        st.markdown("##### Extracted Document Data")
                        st.caption("This is the structured data the specialist agents produced:")
                        doc_tabs = st.tabs(list(ext_data.keys()))
                        for dt, (dname, ddata) in zip(doc_tabs, ext_data.items()):
                            with dt:
                                st.json(_summarize_extraction(ddata, max_fields=10))

                    # Show raw graph output (truncated)
                    st.markdown("##### Graph Output (summary)")
                    st.text(raw[:2000])

            # Step 3: Adjudication
            adj = _pipeline_trace.get("adjudication")
            if adj:
                with st.expander("\U0001f3db\ufe0f Tool Call: adjudicate_claim", expanded=True):
                    if adj["decision"] == "APPROVED":
                        st.markdown("**Orchestrator decided to:** Auto-adjudicate the claim")
                        st.success(f"\u2705 **{adj['decision']}** — {adj['rationale']}")
                    else:
                        st.markdown("**Orchestrator decided to:** Escalate to human review")
                        st.warning(f"\u26a0\ufe0f **{adj['decision']}** — {adj['rationale']}")
                        st.markdown(f"**Flags:** {', '.join(adj.get('flags', []))}")
                        arn = _pipeline_trace.get("escalation_arn", "")
                        if arn and not arn.startswith("Error"):
                            st.code(f"Step Functions Execution: {arn}", language="text")

            # Step 4: Communication
            comm = _pipeline_trace.get("communication")
            if comm:
                with st.expander("\u2709\ufe0f Tool Call: send_claim_decision", expanded=True):
                    st.markdown("**Orchestrator decided to:** Draft a notification via the Communicator Agent")
                    st.markdown(comm[:3000])

            # Step 5: Persistence
            persist = _pipeline_trace.get("persist")
            if persist:
                with st.expander("\U0001f4be Tool Call: persist_claim_to_dynamodb", expanded=True):
                    st.markdown("**Orchestrator decided to:** Persist the claim record to DynamoDB")
                    st.markdown(f"**Stage:** `{persist['stage']}`")
                    st.markdown(f"**Claim ID:** `{persist['claim_id']}`")

            # Supervisor's own summary
            st.markdown("---")
            st.subheader("\U0001f916 Intake Orchestrator Summary")
            st.markdown(supervisor_response[:3000])

            # If escalated, prompt to switch tabs
            if adj and adj["decision"] == "ESCALATED":
                st.session_state.pipeline_results[claim_id] = {
                    "claim": claim,
                    "preprocessing_raw": raw,
                    "extraction_data": _pipeline_trace.get("extraction_data", {}),
                    "adjudication": adj,
                }
                st.markdown("---")
                st.info("\U0001f449 **Switch to the Adjudicator tab** to review and decide on this claim.")

# ── Tab 2: Adjudicator Dashboard ─────────────────────────────────────────────
with tab2:
    st.header("Adjudicator Dashboard")
    st.markdown("Review escalated claims. You are the **Policy Adjudicator** — review the evidence and decide.")

    pipeline_results = st.session_state.get("pipeline_results", {})

    try:
        table = dynamodb.Table(DYNAMODB_TABLE)
        scan_resp = table.scan(
            FilterExpression="stage = :s",
            ExpressionAttributeValues={":s": "pending_human_review"},
        )
        pending_db = {item["claim_id"]: item for item in scan_resp.get("Items", [])}
    except Exception:
        pending_db = {}

    all_pending = set(list(pipeline_results.keys()) + list(pending_db.keys()))

    if not all_pending:
        st.info("No claims pending review. Submit a claim with 'Suicide at residence' as death circumstances to trigger escalation.")
    else:
        for cid in all_pending:
            pr = pipeline_results.get(cid, {})
            db_item = pending_db.get(cid, {})
            claim_data = pr.get("claim", {})

            st.markdown(f"### \U0001f4cb Claim: {cid}")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Claimant:** {claim_data.get('claimant_name', db_item.get('claimant_name', 'N/A'))}")
                st.markdown(f"**Policy:** {claim_data.get('policy_number', db_item.get('policy_number', 'N/A'))}")
            with col2:
                st.markdown(f"**Circumstances:** {claim_data.get('death_circumstances', db_item.get('death_circumstances', 'N/A'))}")
                flags = pr.get("adjudication", {}).get("flags", [])
                st.markdown(f"**Flags:** :red[{', '.join(flags) if flags else 'None'}]")

            # Evidence
            if pr:
                ext_data = pr.get("extraction_data", {})
                if ext_data:
                    with st.expander("\U0001f4c4 Extracted Documents"):
                        for dname, ddata in ext_data.items():
                            st.markdown(f"**{dname}**")
                            st.json(_summarize_extraction(ddata, max_fields=6))

                raw = pr.get("preprocessing_raw", "")
                if raw:
                    with st.expander("\U0001f50d Pre-Processing Evidence"):
                        st.text(raw[:2000])

            # Decision form
            st.markdown("#### Your Decision")
            decision = st.selectbox("Decision", ["APPROVE", "DENY"], key=f"adj_{cid}")
            notes = st.text_area("Notes", key=f"notes_{cid}", placeholder="Explain your reasoning...")

            if st.button(f"\u2705 Submit Decision for {cid}", key=f"submit_{cid}", use_container_width=True):
                # Get task token from Activity
                task_token = None
                try:
                    resp = sfn_client.get_activity_task(activityArn=ACTIVITY_ARN, workerName="demo-adjudicator")
                    task_token = resp.get("taskToken")
                except Exception as e:
                    print(f"Warning: failed to get activity task: {e}")

                if task_token:
                    try:
                        sfn_client.send_task_success(
                            taskToken=task_token,
                            output=json.dumps({"decision": decision, "notes": notes,
                                               "adjudicated_at": datetime.utcnow().isoformat() + "Z"}),
                        )
                    except Exception as e:
                        print(f"Warning: failed to send task success: {e}")

                # Update DynamoDB
                try:
                    table.update_item(
                        Key={"claim_id": cid},
                        UpdateExpression="SET stage = :s, adjudication_decision = :d, adjudication_notes = :n, adjudicated_at = :t",
                        ExpressionAttributeValues={
                            ":s": "adjudicated", ":d": decision, ":n": notes,
                            ":t": datetime.utcnow().isoformat() + "Z",
                        },
                    )
                except Exception as e:
                    print(f"Warning: failed to update DynamoDB: {e}")

                st.success(f"\u2705 Decision: **{decision}**")

                # Run Communicator if approved
                if decision == "APPROVE":
                    c_data = claim_data if claim_data else {"claim_id": cid, "claimant_name": db_item.get("claimant_name", "N/A"),
                                                            "policy_number": db_item.get("policy_number", "N/A"),
                                                            "beneficiary_email": "lisa.doe@example.com"}
                    with st.status("\u2709\ufe0f Communicator Agent drafting notification...") as sc:
                        comm_agent = communicator_agent.build_agent()
                        prompt = (f"Draft a claim decision notification:\nClaim ID: {cid}\n"
                                  f"Claimant: {c_data.get('claimant_name')}\nPolicy: {c_data.get('policy_number')}\n"
                                  f"Decision: APPROVED\nBenefit Amount: $250,000\nNotes: {notes}\n"
                                  f"Beneficiary Email: {c_data.get('beneficiary_email', 'lisa.doe@example.com')}\n")
                        notification = str(comm_agent(prompt))
                        sc.update(label="\u2705 Notification drafted", state="complete")
                    with st.expander("\u2709\ufe0f Claim Decision Notification", expanded=True):
                        st.markdown(notification[:3000])
                else:
                    st.info("Claim denied. A denial notification would be sent to the claimant.")

                if cid in st.session_state.get("pipeline_results", {}):
                    del st.session_state.pipeline_results[cid]

            st.markdown("---")

# ── Tab 3: Agent Memory ──────────────────────────────────────────────────────
with tab3:
    st.header("Agent Memory")
    if not DEMO_MEMORY_ID:
        st.warning("AgentCore Memory not configured. Run the launcher notebook first.")
    else:
        st.markdown(f"**Memory ID:** `{DEMO_MEMORY_ID}`")
        sessions = st.session_state.get("sessions", [])
        if not sessions:
            st.info("No sessions yet. Submit a claim in the Claims Pipeline tab.")
        else:
            if st.button("\U0001f504 Refresh Memory", use_container_width=True):
                st.rerun()
            for sess in reversed(sessions):
                cid, sid = sess["claim_id"], sess["session_id"]
                with st.expander(f"\U0001f4cb {cid} \u2014 Session `{sid[:30]}...`", expanded=(sess == sessions[-1])):
                    st.markdown("#### Short-Term Memory")
                    try:
                        events = memory_client.list_events(memory_id=DEMO_MEMORY_ID, actor_id="demo-intake-orchestrator", session_id=sid)
                        event_list = events if isinstance(events, list) else events.get("events", [])
                        st.markdown(f"**{len(event_list)} events** captured") if event_list else st.info("No events yet.")
                        for i, evt in enumerate(event_list[:10]):
                            msgs = evt.get("messages", [])
                            if msgs and isinstance(msgs[0], dict):
                                st.text(f"  Event {i+1} [{msgs[0].get('role','?')}]: {str(msgs[0].get('content',''))[:200]}...")
                    except Exception as e:
                        st.warning(f"Could not retrieve events: {e}")

                    st.markdown("#### Long-Term Memory")
                    try:
                        summaries = memory_client.retrieve_memories(memory_id=DEMO_MEMORY_ID,
                            namespace=f"/summaries/demo-intake-orchestrator/{sid}/", query="claim processing summary")
                        s_list = summaries if isinstance(summaries, list) else []
                        if s_list:
                            for rec in s_list[:3]:
                                st.text_area("", value=str(rec.get("content", rec.get("text", str(rec))))[:500],
                                             height=80, disabled=True, key=f"s_{sid}_{id(rec)}")
                        else:
                            st.info("No summaries yet. LTM extraction is async \u2014 wait 30-60s and refresh.")
                    except Exception as e:
                        print(f"Warning: failed to retrieve summaries: {e}")
                    try:
                        facts = memory_client.retrieve_memories(memory_id=DEMO_MEMORY_ID,
                            namespace="/facts/demo-intake-orchestrator/", query=f"claim {cid}")
                        f_list = facts if isinstance(facts, list) else []
                        if f_list:
                            st.markdown("**Extracted Facts:**")
                            for rec in f_list[:5]:
                                st.text(f"  \u2022 {str(rec.get('content', rec.get('text', str(rec))))[:200]}")
                    except Exception as e:
                        print(f"Warning: failed to retrieve facts: {e}")
