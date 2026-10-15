"""Minimal MCP client for the clinical trials server.

Starts the server over stdio (as a subprocess), lists its tools, and runs
one search. Works against the public ClinicalTrials.gov API, so it needs
network access.

Run from the repository root after `make setup`:

    .venv/bin/python examples/minimal_client.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

REPO_ROOT = Path(__file__).resolve().parent.parent


async def main() -> None:
    # Run the server as a module from the source tree, so the example works
    # before the package is installed. After `pip install .`, the same server
    # is available as the `clinical-trials-mcp` command.
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "clinical_trials_mcp.server"],
        cwd=str(REPO_ROOT),
        env=env,
    )
    async with Client(transport) as client:
        tools = await client.list_tools()
        print("Tools offered by the server:")
        for tool in tools:
            print(f"  - {tool.name}")

        result = await client.call_tool(
            "search_trials",
            {"condition": "type 2 diabetes", "statuses": ["RECRUITING"], "page_size": 3},
        )
        data = result.structured_content
        assert data is not None
        print(f"\nSearch found {data['total_count']} matching studies; first page:")
        for trial in data["trials"]:
            print(f"  - {trial['nct_id']}: {trial['title']} ({trial['status']})")


if __name__ == "__main__":
    asyncio.run(main())
