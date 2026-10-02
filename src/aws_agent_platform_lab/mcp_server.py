"""One deterministic, read-only synthetic tool. No file or network access."""
from __future__ import annotations

import os
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

REQUIRED = ("request_form", "reference_policy", "review_record")


class ChecklistResult(BaseModel):
    """Typed response from the deterministic, read-only document checklist."""
    model_config = ConfigDict(extra="forbid")
    tenant: str
    present: list[str]
    missing: list[str]
    synthetic: bool = True


server = FastMCP("Synthetic checklist")


@server.tool()
def check_required_documents(tenant: str, present: list[str] = Field(max_length=3)) -> ChecklistResult:
    """Compare declared synthetic document types with a fixed checklist."""
    if tenant != os.environ.get("LAB_TOOL_TENANT") or not tenant:
        raise ValueError("Scope does not match the host-authorized tenant")
    if len(present) != len(set(present)) or any(value not in REQUIRED for value in present):
        raise ValueError("Unknown or duplicate document type")
    return ChecklistResult(tenant=tenant, present=sorted(present),
                           missing=sorted(set(REQUIRED) - set(present)))


if __name__ == "__main__":
    server.run(transport="stdio")
