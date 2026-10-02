"""Allowlisted stdio MCP host; no model-provided executable, URL or environment."""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import timedelta

from .retrieval import access_scope


async def _call(tenant):
    """Launch the fixed checklist process with a minimal environment and bounded timeout."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    # Child receives no cloud keys, tokens, task credential URI or telemetry secrets.
    env = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP")
           if key in os.environ}
    env.update(LAB_TOOL_TENANT=tenant, PYTHONUTF8="1")
    parameters = StdioServerParameters(command=sys.executable,
        args=["-m", "aws_agent_platform_lab.mcp_server"], env=env)
    async with asyncio.timeout(20):
        with open(os.devnull, "w") as errlog:
            async with stdio_client(parameters, errlog=errlog) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=10)) as session:
                    await session.initialize()
                    result = await session.call_tool("check_required_documents", {
                        "tenant": tenant, "present": ["request_form", "reference_policy"]})
    if result.isError:
        raise ValueError("MCP checklist returned an error")
    data = result.structuredContent
    expected = {"tenant": tenant, "present": ["reference_policy", "request_form"],
                "missing": ["review_record"], "synthetic": True}
    if data != expected:
        raise ValueError("MCP checklist returned an invalid result")
    return {"name": "check_required_documents", "transport": "stdio",
            "selection": "fixed by application, not by the model", "result": data}


def call_checklist(principal):
    """Derive tenant from the principal and return a validated, read-only tool result."""
    tenant, _ = access_scope(principal)
    return asyncio.run(_call(tenant))
