"""
Socotra Mock MCP Server

Mock policy administration system providing beneficiary verification,
coverage status, death benefit calculation, and exclusion checks.

Usage:
    python mcp_servers/socotra_mock/server.py
    
    Server runs on http://localhost:8000
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional
#from mcp.server import FastMCP
from mcp.server.fastmcp import FastMCP

import asyncio
from mcp.server.stdio import stdio_server

# Initialize MCP server
mcp = FastMCP("Socotra Policy Admin Mock")

# Load mock data
MOCK_DATA_PATH = Path(__file__).parent / "mock_data.json"
POLICIES_CACHE = {}


def load_mock_data():
    """Load mock policy data from JSON file."""
    global POLICIES_CACHE
    
    if POLICIES_CACHE:
        return POLICIES_CACHE
    
    try:
        with open(MOCK_DATA_PATH, encoding="utf-8") as f:
            data = json.load(f)
            POLICIES_CACHE = {p['policy_number']: p for p in data.get('policies', [])}
            print(f"✅ Loaded {len(POLICIES_CACHE)} policies from mock data", file=sys.stderr)
            return POLICIES_CACHE
    except Exception as e:
        print(f"⚠️ Failed to load mock data: {e}", file=sys.stderr)
        # Fallback to hardcoded data
        POLICIES_CACHE = {
            "POL-WL-2024-001": {
                "policy_number": "POL-WL-2024-001",
                "policy_type": "whole_life",
                "status": "active",
                "death_benefit": 500000,
                "beneficiaries": [{
                    "name": "Sarah Jane Smith",
                    "relationship": "spouse",
                    "percentage": 100,
                    "contact": {
                        "email": "sarah.smith@example.com",
                        "phone": "+1-555-0123",
                        "address": "123 Main St, Springfield, IL 62701"
                    }
                }],
                "exclusions": ["suicide_within_2_years", "war_or_terrorism"]
            }
        }
        return POLICIES_CACHE


@mcp.tool(description="Verify beneficiary identity and retrieve contact details")
def verify_beneficiary_identity(
    policy_number: str,
    claimant_name: str
) -> Dict[str, Any]:
    """
    Verify beneficiary identity against policy records.
    
    Args:
        policy_number: Policy number (e.g., POL-WL-2024-001)
        claimant_name: Name of person filing claim
    
    Returns:
        Verification result with identity_verified, policy_match, beneficiary details
    """
    policies = load_mock_data()
    
    policy = policies.get(policy_number)
    if not policy:
        return {
            "identity_verified": False,
            "policy_match": False,
            "error": f"Policy {policy_number} not found",
            "confidence": 0.0
        }
    
    # Check if claimant matches any beneficiary
    beneficiaries = policy.get('beneficiaries', [])
    matched_beneficiary = None
    
    for beneficiary in beneficiaries:
        # Simple name matching (case-insensitive, partial match)
        if claimant_name.lower() in beneficiary['name'].lower() or \
           beneficiary['name'].lower() in claimant_name.lower():
            matched_beneficiary = beneficiary
            break
    
    if matched_beneficiary:
        return {
            "identity_verified": True,
            "policy_match": True,
            "beneficiary_name": matched_beneficiary['name'],
            "relationship": matched_beneficiary['relationship'],
            "percentage": matched_beneficiary['percentage'],
            "contact": matched_beneficiary['contact'],
            "confidence": 0.95,
            "verification_method": "socotra_mock"
        }
    else:
        return {
            "identity_verified": False,
            "policy_match": False,
            "error": f"Claimant {claimant_name} not found in beneficiaries",
            "beneficiaries_on_file": [b['name'] for b in beneficiaries],
            "confidence": 0.2,
            "verification_method": "socotra_mock"
        }


@mcp.tool(description="Verify policy coverage status (active/lapsed)")
def verify_coverage_status(policy_number: str) -> Dict[str, Any]:
    """
    Check if policy is active or lapsed.
    
    Args:
        policy_number: Policy number
    
    Returns:
        Coverage status with active flag, status, and dates
    """
    policies = load_mock_data()
    
    policy = policies.get(policy_number)
    if not policy:
        return {
            "coverage_active": False,
            "status": "not_found",
            "error": f"Policy {policy_number} not found"
        }
    
    status = policy.get('status', 'unknown')
    is_active = status == 'active'
    
    result = {
        "coverage_active": is_active,
        "status": status,
        "policy_type": policy.get('policy_type'),
        "issue_date": policy.get('issue_date'),
        "premium_status": policy.get('premium_status')
    }
    
    if status == 'lapsed':
        result['lapse_date'] = policy.get('lapse_date')
        result['reason'] = 'Premium payments not current'
    
    return result


@mcp.tool(description="Calculate death benefit amount based on policy terms")
def calculate_death_benefit(
    policy_number: str,
    death_date: str
) -> Dict[str, Any]:
    """
    Calculate death benefit payout amount.
    
    Args:
        policy_number: Policy number
        death_date: Date of death (YYYY-MM-DD)
    
    Returns:
        Death benefit calculation with amount and breakdown
    """
    policies = load_mock_data()
    
    policy = policies.get(policy_number)
    if not policy:
        return {
            "benefit_amount": 0,
            "error": f"Policy {policy_number} not found"
        }
    
    base_benefit = policy.get('death_benefit', 0)
    
    # Simple calculation (no adjustments for workshop)
    return {
        "benefit_amount": base_benefit,
        "base_benefit": base_benefit,
        "adjustments": [],
        "policy_type": policy.get('policy_type'),
        "calculation_date": death_date,
        "currency": "USD"
    }


@mcp.tool(description="Check policy exclusions that may disqualify claim")
def check_exclusions(
    policy_number: str,
    death_circumstances: str
) -> Dict[str, Any]:
    """
    Check if death circumstances trigger policy exclusions.
    
    Args:
        policy_number: Policy number
        death_circumstances: Description of death circumstances
    
    Returns:
        Exclusion check result with triggered exclusions
    """
    policies = load_mock_data()
    
    policy = policies.get(policy_number)
    if not policy:
        return {
            "exclusions_triggered": [],
            "claim_eligible": True,
            "error": f"Policy {policy_number} not found"
        }
    
    exclusions = policy.get('exclusions', [])
    triggered = []
    
    # Simple keyword matching for workshop
    circumstances_lower = death_circumstances.lower()
    
    if 'suicide' in circumstances_lower and 'suicide_within_2_years' in exclusions:
        triggered.append({
            "exclusion": "suicide_within_2_years",
            "description": "Suicide within 2 years of policy issue",
            "requires_review": True
        })
    
    if ('war' in circumstances_lower or 'terrorism' in circumstances_lower) and \
       'war_or_terrorism' in exclusions:
        triggered.append({
            "exclusion": "war_or_terrorism",
            "description": "Death due to war or terrorism",
            "requires_review": True
        })
    
    if 'aviation' in circumstances_lower and 'aviation_non_commercial' in exclusions:
        triggered.append({
            "exclusion": "aviation_non_commercial",
            "description": "Non-commercial aviation accident",
            "requires_review": True
        })
    
    return {
        "exclusions_triggered": triggered,
        "claim_eligible": len(triggered) == 0,
        "all_exclusions": exclusions,
        "requires_manual_review": len(triggered) > 0
    }


@mcp.tool(description="Retrieve full beneficiary details including contact information")
def verify_beneficiary_details(policy_number: str) -> Dict[str, Any]:
    """
    Get complete beneficiary information for a policy.
    
    Args:
        policy_number: Policy number
    
    Returns:
        List of beneficiaries with contact details
    """
    policies = load_mock_data()
    
    policy = policies.get(policy_number)
    if not policy:
        return {
            "beneficiaries": [],
            "error": f"Policy {policy_number} not found"
        }
    
    beneficiaries = policy.get('beneficiaries', [])
    
    return {
        "policy_number": policy_number,
        "beneficiaries": beneficiaries,
        "total_percentage": sum(b.get('percentage', 0) for b in beneficiaries)
    }


def main():
    """Start MCP server."""
    print("=" * 80, file=sys.stderr)
    print("Socotra Mock MCP Server", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    print("Transport: stdio (JSON-RPC)", file=sys.stderr)
    print("Available tools:", file=sys.stderr)
    print("  - verify_beneficiary_identity", file=sys.stderr)
    print("  - verify_coverage_status", file=sys.stderr)
    print("  - calculate_death_benefit", file=sys.stderr)
    print("  - check_exclusions", file=sys.stderr)
    print("  - verify_beneficiary_details", file=sys.stderr)
    print("=" * 80, file=sys.stderr)

    load_mock_data()

    async def _run():
        async with stdio_server() as (read_stream, write_stream):
            await mcp._mcp_server.run(
                read_stream,
                write_stream,
                mcp._mcp_server.create_initialization_options()
            )

    asyncio.run(_run())


if __name__ == "__main__":
    main()