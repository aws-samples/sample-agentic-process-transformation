"""
AnyComp Telecom NOC Mock MCP Server

Mock Network Operations Center system providing trouble ticket lookup,
device status checks, and network diagnostics.

Usage:
    python common/mcp_servers/noc_mock/server.py
"""

import json
import sys
import os
import asyncio
from pathlib import Path
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP
from mcp.server.stdio import stdio_server

mcp = FastMCP("AnyComp NOC Mock")

MOCK_DATA_PATH = os.environ.get(
    "MOCK_DATA_PATH",
    str(Path(__file__).parent / "mock_data.json"),
)
DATA = {}


def load_data():
    global DATA
    if DATA:
        return DATA
    with open(MOCK_DATA_PATH, encoding="utf-8") as f:
        DATA = json.load(f)
    print(f"Loaded NOC mock data: {len(DATA.get('tickets', {}))} tickets, "
          f"{len(DATA.get('devices', {}))} devices", file=sys.stderr)
    return DATA


@mcp.tool(description="Look up a trouble ticket by ID")
def get_ticket(ticket_id: str) -> Dict[str, Any]:
    """Get details for a trouble ticket.

    Args:
        ticket_id: Ticket identifier (e.g. TKT-4001)
    """
    data = load_data()
    ticket = data.get("tickets", {}).get(ticket_id)
    if not ticket:
        return {"error": f"Ticket {ticket_id} not found",
                "available": list(data.get("tickets", {}).keys())}
    return ticket


@mcp.tool(description="Check the status of a network device")
def check_device_status(device_id: str) -> Dict[str, Any]:
    """Check if a network device is healthy, degraded, or down.

    Args:
        device_id: Device identifier (e.g. TOWER-DT-07)
    """
    data = load_data()
    device = data.get("devices", {}).get(device_id)
    if not device:
        return {"error": f"Device {device_id} not found",
                "available": list(data.get("devices", {}).keys())}
    return device


@mcp.tool(description="Run a network diagnostic test on a device")
def run_diagnostic(device_id: str, test_type: str) -> Dict[str, Any]:
    """Run a diagnostic test (ping, throughput, or signal) on a device.

    Args:
        device_id: Device identifier (e.g. TOWER-DT-07)
        test_type: Type of test — ping, throughput, or signal
    """
    data = load_data()
    device_diags = data.get("diagnostics", {}).get(device_id)
    if not device_diags:
        return {"error": f"No diagnostics available for {device_id}"}
    test = device_diags.get(test_type)
    if not test:
        return {"error": f"Unknown test type: {test_type}",
                "available": list(device_diags.keys())}
    return {"device_id": device_id, "test_type": test_type, **test}


def main():
    print("=" * 60, file=sys.stderr)
    print("AnyComp Telecom NOC Mock MCP Server", file=sys.stderr)
    print("Tools: get_ticket, check_device_status, run_diagnostic", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    load_data()

    async def _run():
        async with stdio_server() as (read_stream, write_stream):
            await mcp._mcp_server.run(
                read_stream, write_stream,
                mcp._mcp_server.create_initialization_options(),
            )

    asyncio.run(_run())


if __name__ == "__main__":
    main()
