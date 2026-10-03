"""Neutral local stdio MCP access to the simulated LangGraph Factory.

The host fixes identity and storage before startup. A model can request a review,
but cannot supply a decision, actor or approval hash as tool arguments. The MCP
client must present elicitation to a human; that client behaviour is trusted,
not cryptographically proven. No actual application release is performed.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Mapping

from langsmith import tracing_context
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .auth import Principal
from .factory import COMPANIES, GATES, LIMITATIONS, service_from_environment
from .services import ServiceError


REVIEW_PROVENANCE = (
    "Local simulated identity. Human review relies on the trusted MCP client displaying "
    "the exact artifact and collecting the form from a person; this is not cryptographic proof."
)


class StrictInput(BaseModel):
    """Base tool schema that rejects unknown fields and implicit type coercion."""
    model_config = ConfigDict(extra="forbid", strict=True)


class StartInput(StrictInput):
    """Synthetic request contract; callers cannot choose identity or project scope."""
    request_text: str = Field(min_length=10, max_length=4000)
    synthetic: bool

    @field_validator("synthetic")
    @classmethod
    def synthetic_only(cls, value):
        """Reject requests that are not explicitly marked as synthetic."""
        if value is not True:
            raise ValueError("Only synthetic requests are supported")
        return value


class RunInput(StrictInput):
    """Accept only a server-issued run identifier, not a storage path."""
    run_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class ReviewForm(StrictInput):
    # SDK 1.30's form validator requires a primitive annotation. Expose the enum
    # in JSON Schema and enforce it again in validation, rather than using Literal.
    """Human-facing simulated decision form, separate from model tool arguments."""
    decision: str = Field(description="Your decision on this exact simulated proposal",
                          json_schema_extra={"enum": ["approve", "reject"]})
    reason: str = Field(min_length=1, max_length=1000, description="Explain your decision on the displayed proposal")

    @field_validator("decision")
    @classmethod
    def explicit_decision(cls, value):
        """Require an explicit approve or reject value from the review form."""
        if value not in {"approve", "reject"}:
            raise ValueError("An explicit approve or reject choice is required")
        return value

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value):
        """Reject empty or invalid explanations before persisting a decision."""
        if not value.strip() or any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            raise ValueError("A readable reason is required")
        value.encode("utf-8")
        return value.strip()


INPUTS = {"factory_describe": StrictInput, "factory_start": StartInput,
          "factory_get": RunInput, "factory_request_review": RunInput}


def host_configuration(environ: Mapping[str, str] | None = None):
    """Resolve fixture identity and storage from trusted local host settings."""
    env = os.environ if environ is None else environ
    identity = env.get("FACTORY_LOCAL_IDENTITY", "")
    identities = {"local" + tenant: tenant for tenant in COMPANIES}
    data_dir = env.get("LAB_DATA_DIR", "")
    if (env.get("LOCAL_DEMO_MODE", "").lower() != "true"
            or identity not in identities or not isinstance(data_dir, str) or not data_dir.strip()):
        raise ValueError("Explicit local mode, supported Factory identity and data directory are required")
    tenant = identities[identity]
    return Path(data_dir).expanduser() / "factory", Principal(
        identity, ("demo-" + tenant,), tenant, "internal", True)


def _error(status, code, message):
    """Create a bounded protocol error without provider bodies or host details."""
    return {"ok": False, "simulated": True,
            "error": {"status": status, "code": code, "message": message}}


def _service_call(service, method, *args):
    """Invoke a fixed service method and translate known failures into safe results."""
    try:
        return {"ok": True, **getattr(service, method)(*args)}
    except ServiceError as error:
        messages = {403: "This configured local identity is not permitted.",
                    404: "The Factory run is not available to this identity.",
                    409: "The run changed or is not at the requested gate. Inspect its current state.",
                    422: "The request or review does not meet the local Factory contract."}
        status = error.status_code if error.status_code in messages else 409
        return _error(status, "factory_request_rejected", messages[status])


def _supports_form(ctx):
    """Check negotiated client capability before requesting human form elicitation."""
    parameters = ctx.request_context.session.client_params
    capability = parameters.capabilities.elicitation if parameters else None
    # Legacy empty elicitation capability means form support. URL-only does not.
    return capability is not None and (capability.form is not None or capability.url is None)


async def _request_review(service, principal, run_id, ctx, allow_simulated_review=False):
    """Request a human form for a captured artifact, then recheck it before resume.

    Review is disabled by default. Cancellation, timeout, unsupported clients
    and stale proposals never become approval. Local elicitation is not
    independent proof of a real human identity.
    """
    if not allow_simulated_review:
        return _error(403, "review_disabled", "Simulated client review is disabled by the host. "
            "It requires explicit FACTORY_ALLOW_SIMULATED_REVIEW=true and is not verified human approval.")
    current = _service_call(service, "get_run", principal, run_id)
    if not current["ok"]:
        return current
    pending = current["pending_gate"]
    if pending is None:
        return _error(409, "no_pending_gate", "This run has no pending human gate.")
    if not _supports_form(ctx):
        return _error(409, "client_unsupported",
            "This client has not declared form elicitation. No decision was recorded; use a compatible human-facing client.")
    # Capture the complete review before releasing control to the client. No
    # SQLite lock remains held while a person considers the form.
    message = (
        "Human review required: present this entire exact proposal to the person. "
        "The model must not choose or auto-fill the decision. Accepting the form records "
        "the explicit approve/reject choice below; declining or cancelling records no decision. "
        "All artifacts are simulated and inert, including G4 Release.\n"
        + REVIEW_PROVENANCE + "\nReviewed artifact (JSON):\n"
        + json.dumps(pending, ensure_ascii=False, sort_keys=True, indent=2)
    )
    try:
        async with asyncio.timeout(300):
            response = await ctx.elicit(message=message, schema=ReviewForm)
        if response.action in {"decline", "cancel"}:
            result = _service_call(service, "get_run", principal, run_id)
            return {**result, "review_outcome": "declined" if response.action == "decline" else "cancelled",
                    "review_provenance": REVIEW_PROVENANCE}
        if response.action != "accept":
            return _error(422, "invalid_review", "No valid human review form was accepted; no decision was recorded.")
        form = ReviewForm.model_validate(response.data)
    except ValidationError:
        return _error(422, "invalid_review", "The human review form is invalid; no decision was recorded.")
    except Exception:
        # A timeout, unsupported interaction or remote client error must never
        # become an automatic approval or expose the client's raw exception.
        return _error(409, "review_unavailable", "Human review was unavailable or interrupted; no decision was recorded.")
    latest = _service_call(service, "get_run", principal, run_id)
    if not latest["ok"]:
        return latest
    if latest["pending_gate"] != pending:
        return _error(409, "stale_review", "The proposal changed during human review. Inspect it and request a new review.")
    # The service repeats gate/hash/ownership validation under its cross-process
    # lock, closing the race between this read and the actual decision.
    result = _service_call(service, "decide_run", principal, run_id,
        pending["gate"], pending["artifact_hash"], form.decision, form.reason)
    return {**result, "review_outcome": "applied" if result["ok"] else "not_applied",
            "review_provenance": REVIEW_PROVENANCE}


class LocalFactoryMCP(FastMCP):
    """Forbid extra arguments before SDK coercion and redact unexpected errors."""

    async def list_tools(self):
        """Publish strict schemas that exclude identity, scope and decision overrides."""
        tools = await super().list_tools()
        for tool in tools:
            tool.inputSchema = INPUTS[tool.name].model_json_schema()
        return tools

    async def call_tool(self, name, arguments):
        """Validate tool input before SDK coercion and suppress unsafe error details."""
        if name not in INPUTS:
            raise ToolError("Unknown local Factory tool")
        try:
            validated = INPUTS[name].model_validate(arguments)
        except (ValidationError, TypeError, ValueError):
            raise ToolError("Invalid local Factory tool arguments; extra fields and scope overrides are forbidden") from None
        try:
            with tracing_context(enabled=False):
                return await super().call_tool(name, validated.model_dump())
        except Exception:
            raise ToolError("The local Factory request failed. Inspect the current run before retrying.") from None


def create_server(environ: Mapping[str, str] | None = None):
    """Build the local stdio server; no HTTP listener or remote authentication exists."""
    root, principal = host_configuration(environ)
    env = os.environ if environ is None else environ
    allow_review = env.get("FACTORY_ALLOW_SIMULATED_REVIEW", "").lower() == "true"

    @asynccontextmanager
    async def lifespan(server):
        """Own one Factory service for the protocol session and close its database."""
        with tracing_context(enabled=False):
            service = service_from_environment(root, env)
            try:
                yield {"service": service}
            finally:
                service.close()

    server = LocalFactoryMCP("Secloudis local Factory",
        instructions="Local simulated Factory. Use factory_describe for its architecture. "
        "Only a person may answer review elicitation; never fill it from model output. "
        "No tool accepts an identity, scope, decision or approval hash. Nothing is deployed.",
        lifespan=lifespan, log_level="CRITICAL")
    readonly = ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                               idempotentHint=True, openWorldHint=False)
    mutating = ToolAnnotations(readOnlyHint=False, destructiveHint=False,
                               idempotentHint=False, openWorldHint=False)

    @server.tool(annotations=readonly)
    def factory_describe() -> dict[str, Any]:
        """Explain the implemented local workflow, its five roles, human gates and limitations."""
        return {"ok": True, "simulated": True, "engine": "langgraph", "transport": "stdio",
            "company_id": COMPANIES[principal.tenant], "project_id": "affiliation-demo",
            "simulated_review_enabled": allow_review,
            "application": "Shared read-only synthetic affiliation consultation for Company 1/2/3",
            "roles": ["Analyst", "Architect", "Code author", "Tester", "Reviewer"],
            "gates": [{"gate": gate, "label": label} for gate, label in GATES.items()],
            "construction_vs_runtime": "Factory proposals are separate from the future application's business API calls.",
            "review_provenance": REVIEW_PROVENANCE, "limitations": LIMITATIONS}

    @server.tool(annotations=mutating)
    def factory_start(request_text: str, synthetic: bool, ctx: Context) -> dict[str, Any]:
        """Start a synthetic local proposal under the host-configured identity; stops at G1 Scope."""
        return _service_call(ctx.request_context.lifespan_context["service"],
                             "start_run", principal, request_text)

    @server.tool(annotations=readonly)
    def factory_get(run_id: str, ctx: Context) -> dict[str, Any]:
        """Inspect an owned local run, artifacts, exact pending hash and recorded decisions."""
        return _service_call(ctx.request_context.lifespan_context["service"], "get_run", principal, run_id)

    @server.tool(annotations=mutating)
    async def factory_request_review(run_id: str, ctx: Context) -> dict[str, Any]:
        """Ask the human through client form elicitation to review the exact current proposal. Never auto-answer."""
        return await _request_review(ctx.request_context.lifespan_context["service"],
                                     principal, run_id, ctx, allow_review)

    return server


def main():
    """Start only the explicitly configured local stdio transport; redact startup errors."""
    try:
        create_server().run(transport="stdio")
    except Exception:
        # Configuration or SDK errors may include paths or environment details.
        print("Local Factory MCP could not start or continue. Check explicit local host configuration.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
