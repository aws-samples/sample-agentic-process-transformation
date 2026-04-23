# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Extractor Agent — Shared Module

Factory function that returns a configured Extractor Agent instance.
Matches the agent configuration from 02_tool_enabled_agents/02_document_processing_agent.ipynb.

Usage:
    from agents.extractor_agent import build_agent
    agent = build_agent()
    result = agent("Extract all documents: ...")
"""

import json
import re
import boto3
from pathlib import Path
from typing import List
from strands import Agent, tool
from strands.models import BedrockModel


# ── Model configuration ──────────────────────────────────────────────────────
MODEL_ID = "us.amazon.nova-2-lite-v1:0"
REGION = boto3.session.Session().region_name or "us-east-1"

# ── Bedrock Runtime client — used inside extraction helper ────────────────────
_bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)

# ── Configurable output directory (set by caller before invoking agent) ───────
OUTPUT_DIR: Path = Path.cwd()


# ======================================================================================
# JSON SCHEMAS — identical to 02_tool_enabled_agents/02_document_processing_agent.ipynb.
# ======================================================================================

DEATH_CERTIFICATE_SCHEMA = {
    "type": "object",
    "description": "Structured data extracted from a death certificate",
    "properties": {
        "header": {
            "type": "object",
            "description": "Certificate identification fields from the document header",
            "properties": {
                "state_file_no": {"type": "string"},
                "county": {"type": "string"},
                "certificate_no": {"type": "string"},
                "date_filed": {"type": "string", "format": "date"},
            },
        },
        "decedent_information": {
            "type": "object",
            "description": "Personal information about the deceased",
            "properties": {
                "name_last_first": {"type": "string"},
                "sex": {"type": "string"},
                "dob": {"type": "string", "format": "date"},
                "age": {"type": "integer"},
                "ssn_masked": {"type": "string"},
                "marital": {"type": "string"},
                "residence": {"type": "string"},
                "birthplace": {"type": "string"},
            },
        },
        "death_information": {
            "type": "object",
            "description": "Details about the death event",
            "properties": {
                "date_of_death": {"type": "string", "format": "date"},
                "time": {"type": "string"},
                "place_of_death": {"type": "string"},
                "city_co_st": {"type": "string"},
                "location": {"type": "string"},
                "in_hospice": {"type": "string"},
                "manner": {"type": "string"},
                "autopsy": {"type": "string"},
            },
        },
        "cause_of_death": {
            "type": "object",
            "description": "Cause of death chain as recorded on the certificate",
            "properties": {
                "immediate_cause_a": {"type": "string"},
                "interval_a": {"type": "string"},
                "due_to_b": {"type": "string"},
                "interval_b": {"type": "string"},
                "due_to_c": {"type": "string"},
                "interval_c": {"type": "string"},
                "other_conditions": {"type": "string"},
            },
        },
        "informant": {
            "type": "object",
            "description": "Person who provided information for the certificate",
            "properties": {
                "name": {"type": "string"},
                "relationship": {"type": "string"},
                "mailing_address": {"type": "string"},
                "phone": {"type": "string"},
            },
        },
        "certifier": {
            "type": "object",
            "description": "Physician who certified the death",
            "properties": {
                "physician": {"type": "string"},
                "license_no": {"type": "string"},
                "facility": {"type": "string"},
                "phone": {"type": "string"},
                "date_signed": {"type": "string", "format": "date"},
            },
        },
    },
    "required": ["decedent_information", "death_information", "cause_of_death", "certifier"],
}

POLICY_DOCUMENT_SCHEMA = {
    "type": "object",
    "description": "Structured data extracted from a whole life insurance policy",
    "properties": {
        "policy_overview": {
            "type": "object",
            "description": "Core policy identification and status fields",
            "properties": {
                "policy_number": {"type": "string"},
                "plan": {"type": "string"},
                "issue_date": {"type": "string", "format": "date"},
                "status": {"type": "string"},
                "face_amount": {"type": "number"},
                "premium_mode": {"type": "string"},
                "annual_premium": {"type": "number"},
                "paid_to_date": {"type": "string", "format": "date"},
            },
        },
        "insured_owner": {
            "type": "object",
            "description": "Insured and policy owner information",
            "properties": {
                "name": {"type": "string"},
                "date_of_birth": {"type": "string", "format": "date"},
                "ssn_masked": {"type": "string"},
                "address": {"type": "string"},
                "phone": {"type": "string"},
                "email": {"type": "string"},
            },
        },
        "beneficiary_designation": {
            "type": "object",
            "description": "Primary beneficiary designation details",
            "properties": {
                "primary_beneficiary": {"type": "string"},
                "relationship": {"type": "string"},
                "benefit_percent": {"type": "number"},
                "beneficiary_address": {"type": "string"},
                "beneficiary_phone": {"type": "string"},
                "beneficiary_email": {"type": "string"},
            },
        },
        "policy_values": {
            "type": "object",
            "description": "Current policy financial values",
            "properties": {
                "cash_surrender_value": {"type": "number"},
                "outstanding_policy_loan": {"type": "number"},
                "net_death_benefit_estimated": {"type": "number"},
            },
        },
        "customer_service": {
            "type": "object",
            "description": "Carrier contact information",
            "properties": {
                "carrier_name": {"type": "string"},
                "carrier_address": {"type": "string"},
                "phone": {"type": "string"},
                "claims_email": {"type": "string"},
            },
        },
    },
    "required": ["policy_overview", "insured_owner", "beneficiary_designation", "policy_values"],
}

MEDICAL_RECORDS_SCHEMA = {
    "type": "object",
    "description": "Structured data extracted from a medical records continuity of care summary",
    "properties": {
        "patient_information": {
            "type": "object",
            "description": "Patient demographics and provider assignment",
            "properties": {
                "patient_name": {"type": "string"},
                "mrn": {"type": "string"},
                "date_of_birth": {"type": "string", "format": "date"},
                "sex": {"type": "string"},
                "primary_address": {"type": "string"},
                "phone": {"type": "string"},
                "primary_care_provider": {"type": "string"},
                "npi": {"type": "string"},
            },
        },
        "problem_list_active": {
            "type": "array",
            "description": "Active medical conditions from the problem list",
            "items": {"type": "string"},
        },
        "medication_list": {
            "type": "array",
            "description": "Current medications",
            "items": {
                "type": "object",
                "properties": {
                    "medication": {"type": "string"},
                    "dose_route": {"type": "string"},
                    "frequency": {"type": "string"},
                    "indication": {"type": "string"},
                },
            },
        },
        "recent_encounter": {
            "type": "object",
            "description": "Most recent clinical encounter details",
            "properties": {
                "encounter_type": {"type": "string"},
                "date": {"type": "string", "format": "date"},
                "location": {"type": "string"},
                "assessment_and_plan": {"type": "string"},
            },
        },
        "laboratory_results": {
            "type": "array",
            "description": "Recent lab results",
            "items": {
                "type": "object",
                "properties": {
                    "test": {"type": "string"},
                    "date": {"type": "string", "format": "date"},
                    "result": {"type": "string"},
                    "units": {"type": "string"},
                    "reference_range": {"type": "string"},
                },
            },
        },
        "provider_attestation": {
            "type": "object",
            "description": "Physician attestation details",
            "properties": {
                "date": {"type": "string", "format": "date"},
                "printed_name": {"type": "string"},
                "title": {"type": "string"},
            },
        },
    },
    "required": ["patient_information", "problem_list_active", "medication_list"],
}

WILL_DOCUMENT_SCHEMA = {
    "type": "object",
    "description": "Structured data extracted from a Last Will and Testament",
    "properties": {
        "testator": {
            "type": "object",
            "description": "Identity and residence of the person making the will",
            "properties": {
                "name": {"type": "string"},
                "date_of_birth": {"type": "string", "format": "date"},
                "residence": {"type": "string"},
                "marital_status": {"type": "string"},
            },
        },
        "family_information": {
            "type": "object",
            "description": "Family status and living descendants",
            "properties": {
                "marital_status": {"type": "string"},
                "living_descendants": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "relationship": {"type": "string"},
                        },
                    },
                },
            },
        },
        "executor": {
            "type": "object",
            "description": "Appointed executor of the estate",
            "properties": {
                "name": {"type": "string"},
                "role": {"type": "string"},
                "alternate": {"type": "string"},
            },
        },
        "specific_bequests": {
            "type": "array",
            "description": "Specific gifts named in the will",
            "items": {
                "type": "object",
                "properties": {
                    "item": {"type": "string"},
                    "beneficiary": {"type": "string"},
                },
            },
        },
        "residuary_estate": {
            "type": "object",
            "description": "Disposition of the residuary estate",
            "properties": {
                "beneficiary": {"type": "string"},
                "description": {"type": "string"},
            },
        },
        "insurance_proceeds": {
            "type": "object",
            "description": "Treatment of life insurance proceeds under the will",
            "properties": {
                "policy_numbers_referenced": {"type": "array", "items": {"type": "string"}},
                "instruction": {"type": "string"},
            },
        },
        "execution": {
            "type": "object",
            "description": "Signing, witness, and notarization details",
            "properties": {
                "date_signed": {"type": "string", "format": "date"},
                "governing_law": {"type": "string"},
                "witnesses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}, "address": {"type": "string"}},
                    },
                },
                "notary_public": {"type": "string"},
                "commission_expires": {"type": "string", "format": "date"},
                "notarized_date": {"type": "string", "format": "date"},
                "notarized_county": {"type": "string"},
            },
        },
    },
    "required": ["testator", "executor", "residuary_estate", "insurance_proceeds"],
}

TRUST_DOCUMENT_SCHEMA = {
    "type": "object",
    "description": "Structured data extracted from a Revocable Living Trust Agreement",
    "properties": {
        "trust_name": {"type": "string"},
        "agreement_date": {"type": "string", "format": "date"},
        "grantor": {"type": "string"},
        "trustees": {
            "type": "object",
            "description": "Initial and successor trustee designations",
            "properties": {
                "initial_trustee": {"type": "string"},
                "successor_trustee": {"type": "string"},
                "successor_relationship": {"type": "string"},
            },
        },
        "revocability": {"type": "string"},
        "beneficiaries": {
            "type": "object",
            "description": "Beneficiary designations during lifetime and upon death",
            "properties": {
                "lifetime_beneficiary": {"type": "string"},
                "remainder_beneficiaries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}, "percent": {"type": "number"}},
                    },
                },
            },
        },
        "distribution_upon_death": {
            "type": "array",
            "description": "Ordered distribution instructions upon grantor's death",
            "items": {"type": "string"},
        },
        "trustee_powers": {
            "type": "array",
            "description": "Enumerated powers granted to the trustee",
            "items": {"type": "string"},
        },
        "schedule_a_initial_property": {
            "type": "array",
            "description": "Initial property transferred to the trust per Schedule A",
            "items": {
                "type": "object",
                "properties": {"description": {"type": "string"}, "notes": {"type": "string"}},
            },
        },
        "execution": {
            "type": "object",
            "description": "Signing and notarization details",
            "properties": {
                "date_signed": {"type": "string", "format": "date"},
                "grantor_printed_name": {"type": "string"},
                "notary_public": {"type": "string"},
                "commission_expires": {"type": "string", "format": "date"},
                "notarized_date": {"type": "string", "format": "date"},
                "notarized_county": {"type": "string"},
            },
        },
    },
    "required": ["trust_name", "agreement_date", "grantor", "trustees", "beneficiaries"],
}

BENEFICIARY_ID_SCHEMA = {
    "type": "object",
    "description": "Structured data extracted from a government-issued photo ID card",
    "properties": {
        "issuing_state": {"type": "string"},
        "document_type": {"type": "string"},
        "last_name": {"type": "string"},
        "first_name": {"type": "string"},
        "dob": {"type": "string", "format": "date"},
        "sex": {"type": "string"},
        "eyes": {"type": "string"},
        "ht": {"type": "string"},
        "wt": {"type": "integer"},
        "dl_id_number": {"type": "string"},
        "iss": {"type": "string", "format": "date"},
        "exp": {"type": "string", "format": "date"},
        "address": {"type": "string"},
    },
    "required": ["last_name", "first_name", "dob", "dl_id_number", "exp", "address"],
}

POLICE_REPORT_SCHEMA = {
    "type": "object",
    "description": "Structured data extracted from a police incident report",
    "properties": {
        "agency": {
            "type": "object",
            "description": "Law enforcement agency details",
            "properties": {"agency_name": {"type": "string"}, "ori": {"type": "string"}},
        },
        "case_information": {
            "type": "object",
            "description": "Case identification and classification",
            "properties": {
                "case_no": {"type": "string"},
                "report_date": {"type": "string", "format": "date"},
                "incident_type": {"type": "string"},
                "disposition": {"type": "string"},
            },
        },
        "incident_details": {
            "type": "object",
            "description": "Time, location, and responding unit details",
            "properties": {
                "date_time": {"type": "string"},
                "location": {"type": "string"},
                "call_type": {"type": "string"},
                "units": {"type": "array", "items": {"type": "string"}},
                "reporting_officer": {"type": "string"},
                "supervisor": {"type": "string"},
            },
        },
        "persons_involved": {
            "type": "array",
            "description": "All persons documented in the report",
            "items": {
                "type": "object",
                "properties": {
                    "role": {"type": "string"},
                    "name": {"type": "string"},
                    "dob": {"type": "string", "format": "date"},
                    "contact": {"type": "string"},
                    "notes": {"type": "string"},
                },
            },
        },
        "narrative": {"type": "string"},
        "evidence_property": {
            "type": "object",
            "description": "Evidence collected and property inventoried",
            "properties": {
                "evidence_collected": {"type": "string"},
                "property_inventoried": {"type": "string"},
            },
        },
        "officer_certification": {
            "type": "object",
            "description": "Officer signature and certification details",
            "properties": {
                "date": {"type": "string", "format": "date"},
                "printed_name_badge": {"type": "string"},
                "unit": {"type": "string"},
            },
        },
    },
    "required": ["case_information", "incident_details", "persons_involved", "narrative"],
}

SCHEMA_REGISTRY = {
    "death_certificate": DEATH_CERTIFICATE_SCHEMA,
    "policy_document": POLICY_DOCUMENT_SCHEMA,
    "medical_records": MEDICAL_RECORDS_SCHEMA,
    "will_document": WILL_DOCUMENT_SCHEMA,
    "trust_document": TRUST_DOCUMENT_SCHEMA,
    "beneficiary_id": BENEFICIARY_ID_SCHEMA,
    "police_report": POLICE_REPORT_SCHEMA,
}


# ==========================================================================================
# Helper functions — identical to 02_tool_enabled_agents/02_document_processing_agent.ipynb.
# ==========================================================================================

def classify_document(file_path: str, doc_type_hint: str = None) -> str:
    """Maps a document filename to a SCHEMA_REGISTRY key using keyword heuristics."""
    if doc_type_hint:
        return doc_type_hint

    filename = Path(file_path).name.lower()

    if "death" in filename:
        return "death_certificate"
    elif "policy" in filename or "whole_life" in filename:
        return "policy_document"
    elif "medical" in filename or "records" in filename:
        return "medical_records"
    elif "will" in filename or "testament" in filename:
        return "will_document"
    elif "trust" in filename:
        return "trust_document"
    elif "beneficiary_id" in filename or "license" in filename:
        return "beneficiary_id"
    elif "police" in filename or "incident" in filename or "report" in filename:
        return "police_report"
    else:
        return "unknown"


def _call_nova_for_extraction(file_path: str, doc_type: str, schema: dict) -> dict:
    """Call Nova 2 Lite once for a single document extraction."""
    with open(file_path, "rb") as f:
        pdf_bytes = f.read()

    properties = schema.get("properties", schema)
    schema_str = json.dumps(properties, indent=2)

    doc_label = doc_type.replace("_", " ").title()
    prompt = (
        f"You are a document extraction specialist processing a {doc_label}.\n"
        "Extract all information from this document and return ONLY a valid JSON object "
        "with the following fields:\n"
        f"{schema_str}\n"
        "Rules:\n"
        "- Use null for any field you cannot find in the document\n"
        "- Do not guess or hallucinate values\n"
        "- Return dates in YYYY-MM-DD format\n"
        "- Return ONLY the JSON object — no explanation, no markdown fences, no extra text"
    )

    response = _bedrock_runtime.converse(
        modelId=MODEL_ID,
        messages=[{
            "role": "user",
            "content": [
                {
                    "document": {
                        "format": "pdf",
                        "name": doc_type,
                        "source": {"bytes": pdf_bytes},
                    }
                },
                {"text": prompt},
            ],
        }],
        additionalModelRequestFields={
            "reasoningConfig": {"type": "enabled", "maxReasoningEffort": "medium"}
        },
        inferenceConfig={"maxTokens": 8096},
    )

    output_text = ""
    content_blocks = response.get("output", {}).get("message", {}).get("content", [])
    for block in content_blocks:
        if not isinstance(block, dict):
            continue
        if block.get("text", "").strip():
            output_text = block["text"].strip()
            break

    if output_text.startswith("```"):
        lines = output_text.splitlines()
        cleaned_lines = [line for line in lines if not line.strip().startswith("```")]
        output_text = "\n".join(cleaned_lines).strip()

    try:
        return json.loads(output_text)
    except json.JSONDecodeError:
        json_match = re.search(r'\{[\s\S]+\}', output_text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

    return {"error": "JSON parse failed", "raw_response": output_text[:500]}


# =====================================================================================================================
# The @tool function — identical to 02_tool_enabled_agents/02_document_processing_agent.ipynb. process_claim_documents
# =====================================================================================================================

@tool
def process_claim_documents(document_paths: List[str]) -> str:
    """
    Extract structured data from all documents in a claim submission.

    Accepts a list of PDF file paths — one per document in the claim.
    For each document:
      - Classifies the document type from the filename using classify_document()
      - Selects the correct JSON schema from SCHEMA_REGISTRY
      - Calls Nova 2 Lite once per document via bedrock_runtime.converse
      - Parses Nova's plain JSON text response
      - Validates that all required fields are present
      - Writes the extracted JSON to the configured output directory

    Args:
        document_paths: List of file path strings, one per claim document
    """
    extraction_results = {}
    validation_summary = {}
    all_passed = True

    print(f"📋 Processing {len(document_paths)} documents...")
    print()

    for i, file_path in enumerate(document_paths, 1):
        path = Path(file_path)
        print(f"── Document {i}/{len(document_paths)}: {path.name}")

        doc_type = classify_document(file_path)
        if doc_type == "unknown":
            print(f"   ⚠️  Could not classify — skipping")
            extraction_results[path.name] = {"error": f"Unknown document type: {path.name}"}
            validation_summary[path.name] = {"passed": False, "missing_fields": [], "warnings": ["Unknown document type"]}
            all_passed = False
            continue

        print(f"   Type     : {doc_type}")

        schema = SCHEMA_REGISTRY.get(doc_type)
        if not schema:
            print(f"   ❌ No schema found for {doc_type}")
            extraction_results[doc_type] = {"error": f"No schema for: {doc_type}"}
            validation_summary[doc_type] = {"passed": False, "missing_fields": [], "warnings": ["No schema registered"]}
            all_passed = False
            continue

        if not path.exists():
            print(f"   ❌ File not found: {file_path}")
            extraction_results[doc_type] = {"error": f"File not found: {file_path}"}
            validation_summary[doc_type] = {"passed": False, "missing_fields": schema.get("required", []), "warnings": ["File not found"]}
            all_passed = False
            continue

        print(f"   Calling Nova  : schema embedded in prompt")
        try:
            extracted = _call_nova_for_extraction(str(path), doc_type, schema)
        except Exception as e:
            print(f"   ❌ Nova call failed: {e}")
            extracted = {"error": str(e)}

        extraction_results[doc_type] = extracted

        output_file = OUTPUT_DIR / f"{path.stem}_extracted.json"
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(extracted, f, indent=2)
            print(f"   💾 Saved       : {output_file.name}")
        except Exception as e:
            print(f"   ❌ Write failed: {type(e).__name__}: {e}")

        required = schema.get("required", [])
        if "error" in extracted:
            missing = required
            warnings = [f"Extraction failed: {extracted['error']}"]
            passed = False
        else:
            missing = [f for f in required if extracted.get(f) is None]
            warnings = [f"Required field '{f}' is null" for f in required if f in extracted and extracted[f] is None]
            passed = len(missing) == 0

        validation_summary[doc_type] = {"passed": passed, "missing_fields": missing, "warnings": warnings}
        if not passed:
            all_passed = False

        status = "✅ passed" if passed else f"⚠️  missing: {missing}"
        print(f"   Validation    : {status}")
        print()

    consolidated = {
        "extraction_results": extraction_results,
        "validation_summary": validation_summary,
        "ready_for_downstream": all_passed,
    }

    print(f"── Extraction complete. ready_for_downstream: {all_passed}")
    return json.dumps(consolidated, indent=2)


# =======================================================================================
# System prompt — identical to 02_tool_enabled_agents/02_document_processing_agent.ipynb.
# =======================================================================================

EXTRACTOR_SYSTEM_PROMPT = """
You are the Extractor Agent in a life insurance claims processing pipeline.

Your job is to extract structured data from all documents in a claim submission.

## How to Respond

When you receive a claim document manifest (a list of file paths), call the
process_claim_documents tool with the complete list of file paths.

## Output

Include the full consolidated JSON from the tool result in your response.
"""


# =============================================================================
# Factory
# =============================================================================

def _build_model():
    return BedrockModel(
        model_id=MODEL_ID,
        region_name=REGION,
        max_tokens=8096,
        additional_request_fields={
            "reasoningConfig": {"type": "enabled", "maxReasoningEffort": "medium"}
        },
    )


def build_agent(output_dir: Path = None) -> Agent:
    """Return a fresh Extractor Agent instance.

    Args:
        output_dir: Directory where extracted JSON files are written.
                    Defaults to current working directory.
    """
    global OUTPUT_DIR
    if output_dir is not None:
        OUTPUT_DIR = output_dir

    return Agent(
        model=_build_model(),
        system_prompt=EXTRACTOR_SYSTEM_PROMPT,
        tools=[process_claim_documents],
    )
