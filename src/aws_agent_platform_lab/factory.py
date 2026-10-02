"""Local, simulated five-worker Factory with four durable human gates.

Workers produce inert fixture proposals. No model, tool, candidate code, business
API or deployment is executed. SQLite checkpoints preserve pauses, while a
separate SQLite transaction serializes service access across local processes.
This is not an exactly-once dispatcher or a cloud authorization implementation.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from langsmith import tracing_context

from .models import canonical_bytes, sha256_bytes
from .services import ServiceError


GATES = {"G1": "Scope", "G2": "Design", "G3": "Quality", "G4": "Release"}
COMPANIES = {"alpha": "company-1", "beta": "company-2", "gamma": "company-3"}
PROJECT_ID = "affiliation-demo"
LIMITATIONS = [
    "Local simulation: five deterministic fixture workers; no model or network calls.",
    "Artifacts are inert proposals, not a generated, tested or deployed application.",
    "Tester and reviewer inspect fixture contracts only; no trusted candidate execution.",
    "All gates use the simulated run owner, not production gate-approver roles.",
    "Company sharing is a proposed synthetic contract, not a live connection or grant.",
    "release_ready means proposals reviewed locally; no build, execution or deployment.",
    "SQLite supports local gate restart; no cloud durability or exactly-once effects claimed.",
]


class FactoryState(TypedDict):
    """Serializable LangGraph state: owner, proposals, decisions and safe events."""
    schema_version: int
    run_id: str
    owner: str
    tenant: str
    access_level: str
    company_id: str
    project_id: str
    request_text: str
    status: str
    artifacts: dict[str, Any]
    decisions: list[dict[str, Any]]
    events: list[dict[str, Any]]


def _copy(value):
    """Return JSON data detached from checkpoint values and caller mutations."""
    return json.loads(canonical_bytes(value))


def _event(state, kind, **details):
    """Append an event by returning a new list, preserving prior checkpoint values."""
    return [*state["events"], {"sequence": len(state["events"]) + 1,
                               "kind": kind, "simulated": True, **details}]


def _gate_payload(state, gate):
    # Bind the complete reviewed proposal and prior decisions to this run, scope
    # and gate. The hash cannot be transplanted to another gate or run.
    """Build the exact review package and hash for one named human gate."""
    artifact = {"schema_version": 1, "simulated": True, "gate": gate,
        "run_id": state["run_id"], "company_id": state["company_id"],
        "project_id": state["project_id"], "request_text": state["request_text"],
        "artifacts": state["artifacts"], "prior_decisions": state["decisions"],
        "scope": "inert fixture proposals only; no execution or deployment"}
    return {"gate": gate, "label": GATES[gate], "artifact": artifact,
            "artifact_hash": sha256_bytes(canonical_bytes(artifact))}


def _worker(role):
    """Create one deterministic role node; all generated proposals remain inert data."""
    def work(state):
        """Produce the role-specific proposal from previous artifacts, without model calls."""
        common = {"simulated": True, "worker": role, "version": 1,
                  "kind": "deterministic fixture proposal"}
        if role == "analyst":
            proposal = {
                "application": "Shared Business Platform",
                "purpose": "Read-only consultation of synthetic affiliation records",
                "request": state["request_text"],
                "companies": ["Company 1", "Company 2", "Company 3"],
                "capabilities": ["search", "filters", "effective dates", "owner-authorized fields"],
                "exclusions": ["real personal data", "insurance decisions", "write operations"],
            }
        elif role == "architect":
            proposal = {
                "construction": "Factory workflow; future registered company MCP tools",
                "application_runtime": "Separate application using owner-authorized business APIs",
                "hosting": "AWS is a future POC target, not deployed by this run",
                "sharing_example": {"owner": "Company 2", "recipient": "Company 1",
                    "resource": "synthetic-affiliation-M-001", "operation": "read",
                    "denied_company": "Company 3", "grant_status": "proposed fixture only"},
                "authorization": "Verified identity and owner-registered resource grants",
                "external_connectors": "Selective contract fixtures only; no calls implemented",
            }
        elif role == "code_author":
            proposal = {
                "files": [{"path": "proposed_app/affiliations.py",
                    "content": "# Inert fixture proposal. Not an implemented application.\n"
                               "# Implement read-only affiliation search and effective dates.\n"
                               "# Enforce application and resource-owner authorization.\n"}],
                "candidate_kind": "inert source proposal", "executed": False,
                "built": False, "deployable": False,
            }
        elif role == "tester":
            proposal = {
                "test_cases": [
                    {"case": "Company 1 reads Company 2 permitted fixture", "expected": "allowed fields only"},
                    {"case": "Company 3 has no grant", "expected": "403 before any provider call"},
                    {"case": "wrong service client, resource or expired grant", "expected": "owner denies access"},
                    {"case": "as-of date on validity boundary", "expected": "defined effective-date behaviour"},
                    {"case": "provider unavailable", "expected": "502/504, no fabricated result"},
                ],
                "execution": "not run", "trusted_validation": False,
            }
        else:
            # These checks validate this deterministic proposal envelope. They
            # must never be presented as candidate execution or business tests.
            artifacts = state["artifacts"]
            checks = {
                "five_role_contracts_defined": True,
                "scope_has_three_companies": len(artifacts["analyst"]["companies"]) == 3,
                "candidate_is_inert": artifacts["code_author"]["executed"] is False,
                "test_proposals_present": len(artifacts["tester"]["test_cases"]) == 5,
            }
            proposal = {"checks": checks, "contract_checks_passed": all(checks.values()),
                        "test_execution": "none", "trusted_validation": False,
                        "assessment": "Simulated proposal-contract review only"}
        return {"artifacts": {**state["artifacts"], role: {**common, **proposal}},
                "events": _event(state, "worker_completed", worker=role)}
    return work


def _gate(gate):
    """Create a checkpointed pause that accepts only a matching decision receipt."""
    def pause(state):
        # No side effects before interrupt: this node restarts on resume.
        """Interrupt for review, then reject stale receipts before changing workflow state."""
        payload = _gate_payload(state, gate)
        decision = interrupt(payload)
        if (not isinstance(decision, dict) or decision.get("gate") != gate
                or decision.get("artifact_hash") != payload["artifact_hash"]
                or decision.get("actor") != state["owner"]
                or decision.get("decision") not in {"approve", "reject"}):
            raise ServiceError("The gate decision no longer matches this run", 409)
        action = decision["decision"]
        status = "rejected" if action == "reject" else "release_ready" if gate == "G4" else "running"
        return {"decisions": [*state["decisions"], decision], "status": status,
                "events": _event(state, "gate_decided", gate=gate, decision=action)}
    return pause


def _build_graph(checkpointer):
    """Wire five roles through four gates; rejection terminates immediately.

    LangGraph orders nodes and persists pauses. It does not run inference,
    execute the proposed code, or deploy the proposed application here.
    """
    builder = StateGraph(FactoryState)
    roles = ("analyst", "architect", "code_author", "tester", "reviewer")
    for role in roles:
        builder.add_node(role, _worker(role))
    for gate in GATES:
        builder.add_node(gate, _gate(gate))
    builder.add_edge(START, "analyst")
    builder.add_edge("analyst", "G1")
    builder.add_edge("architect", "G2")
    builder.add_edge("code_author", "tester")
    builder.add_edge("tester", "reviewer")
    builder.add_edge("reviewer", "G3")
    for gate, following in (("G1", "architect"), ("G2", "code_author"), ("G3", "G4")):
        builder.add_conditional_edges(gate,
            lambda state: "stop" if state["status"] == "rejected" else "continue",
            {"stop": END, "continue": following})
    builder.add_edge("G4", END)
    return builder.compile(checkpointer=checkpointer)


class FactoryService:
    """A local-only service. A verified checkpoint thread is never caller-selected."""

    def __init__(self, root: Path):
        """Open local access/checkpoint databases and compile the deterministic graph."""
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._mutex = threading.RLock()
        self._closed = False
        self._registry_path = self.root / "factory-access.sqlite"
        self._connection = sqlite3.connect(self.root / "factory-checkpoints.sqlite",
                                           timeout=30, check_same_thread=False)
        # Explicit strict allowlists: no arbitrary object constructors or pickle
        # fallback, regardless of process-wide LangGraph environment settings.
        serializer = JsonPlusSerializer(pickle_fallback=False,
            allowed_json_modules=None, allowed_msgpack_modules=None)
        self._saver = SqliteSaver(self._connection, serde=serializer)
        try:
            with self._locked() as registry:
                registry.execute("""CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY, owner TEXT NOT NULL, tenant TEXT NOT NULL,
                    access_level TEXT NOT NULL, company_id TEXT NOT NULL,
                    project_id TEXT NOT NULL)""")
                self._saver.setup()
                self._graph = _build_graph(self._saver)
        except Exception:
            self._connection.close()
            raise

    @contextmanager
    def _locked(self):
        # A Python lock alone cannot serialize separate service processes.
        # This database is intentionally separate from checkpoint transactions.
        """Serialize local processes while reading ownership and advancing checkpoints."""
        with self._mutex:
            if self._closed:
                raise ServiceError("The local Factory is closed", 409)
            registry = sqlite3.connect(self._registry_path, timeout=30, isolation_level=None)
            registry.row_factory = sqlite3.Row
            try:
                registry.execute("BEGIN IMMEDIATE")
                with tracing_context(enabled=False):
                    yield registry
                registry.commit()
            except sqlite3.Error:
                registry.rollback()
                raise ServiceError("The local Factory state is temporarily unavailable", 409) from None
            except BaseException:
                registry.rollback()
                raise
            finally:
                registry.close()

    @staticmethod
    def _identity(principal):
        """Accept only supported fixture principals and derive immutable ownership."""
        tenant = getattr(principal, "tenant", None)
        if (getattr(principal, "simulated", None) is not True
                or not isinstance(tenant, str) or tenant not in COMPANIES
                or getattr(principal, "subject", None) != "local" + tenant
                or getattr(principal, "access_level", None) != "internal"
                or getattr(principal, "groups", None) != ("demo-" + tenant,)):
            raise ServiceError("The Factory requires a supported simulated local identity", 403)
        return {"owner": sha256_bytes(principal.subject.encode("utf-8")), "tenant": tenant,
                "access_level": "internal", "company_id": COMPANIES[tenant], "project_id": PROJECT_ID}

    @staticmethod
    def _text(value, name, minimum, maximum):
        """Validate bounded readable text before placing it in persisted state."""
        try:
            if (not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum
                    or any(ord(c) < 32 and c not in "\n\r\t" for c in value)):
                raise ValueError
            value.encode("utf-8")
        except (ValueError, UnicodeError):
            raise ServiceError(f"{name} must contain {minimum} to {maximum} valid text characters", 422) from None
        return value.strip()

    @staticmethod
    def _config(run_id):
        """Bind checkpoint storage to the server-generated run ID with bounded steps."""
        return {"configurable": {"thread_id": run_id}, "recursion_limit": 30, "callbacks": []}

    def _read(self, registry, identity, run_id):
        """Check registry and checkpoint ownership before returning a run snapshot."""
        if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise ServiceError("Factory run not found", 404)
        row = registry.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None or any(row[key] != value for key, value in identity.items()):
            raise ServiceError("Factory run not found", 404)
        snapshot = self._graph.get_state(self._config(run_id))
        state = snapshot.values
        if (not state or state.get("run_id") != run_id
                or any(state.get(key) != value for key, value in identity.items())):
            raise ServiceError("Factory checkpoint ownership does not match", 409)
        return snapshot

    @staticmethod
    def _public(snapshot):
        """Return detached review data, rejecting mismatched or interrupted checkpoints."""
        state = snapshot.values
        interrupts = [item for task in snapshot.tasks for item in task.interrupts]
        pending = None
        if interrupts:
            if len(interrupts) != 1:
                raise ServiceError("Factory checkpoint has an invalid gate", 409)
            pending = interrupts[0].value
            if (not isinstance(pending, dict) or pending.get("gate") not in GATES
                    or pending != _gate_payload(state, pending["gate"])):
                raise ServiceError("Factory checkpoint no longer matches the reviewed proposal", 409)
        elif state["status"] not in {"rejected", "release_ready"}:
            # An interrupted process between nodes is never mislabeled as ready.
            raise ServiceError("Factory execution stopped between gates; start a new run", 409)
        return _copy({"run_id": state["run_id"],
            "status": "waiting_approval" if pending else state["status"],
            "simulated": True, "engine": "langgraph", "pending_gate": pending,
            "artifacts": state["artifacts"], "decisions": state["decisions"],
            "events": state["events"], "company_id": state["company_id"],
            "project_id": state["project_id"], "limitations": LIMITATIONS})

    def start_run(self, principal, request_text):
        """Create an owned run and execute Analyst until G1 Scope requires review."""
        identity = self._identity(principal)
        request = self._text(request_text, "Request", 10, 4000)
        run_id = uuid.uuid4().hex
        with self._locked() as registry:
            registry.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, identity["owner"], identity["tenant"], identity["access_level"],
                 identity["company_id"], identity["project_id"]))
            self._graph.invoke({"schema_version": 1, "run_id": run_id, **identity,
                "request_text": request, "status": "running", "artifacts": {},
                "decisions": [], "events": []}, self._config(run_id), durability="sync")
            return self._public(self._read(registry, identity, run_id))

    def get_run(self, principal, run_id):
        """Inspect only the caller-owned run and its current pending gate."""
        identity = self._identity(principal)
        with self._locked() as registry:
            return self._public(self._read(registry, identity, run_id))

    def decide_run(self, principal, run_id, gate, artifact_hash, decision, reason):
        """Validate owner, gate and exact artifact hash under the shared lock.

        The receipt is explicitly simulated. Resuming G4 records release readiness;
        it never executes or deploys generated code.
        """
        identity = self._identity(principal)
        if (not isinstance(gate, str) or gate not in GATES
                or not isinstance(decision, str) or decision not in {"approve", "reject"}):
            raise ServiceError("A valid gate and approve or reject decision are required", 422)
        reason = self._text(reason, "Decision reason", 1, 1000)
        if not isinstance(artifact_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", artifact_hash):
            raise ServiceError("A valid reviewed artifact hash is required", 422)
        with self._locked() as registry:
            snapshot = self._read(registry, identity, run_id)
            current = self._public(snapshot)
            pending = current["pending_gate"]
            if pending is None or pending["gate"] != gate or pending["artifact_hash"] != artifact_hash:
                raise ServiceError("This decision is stale or does not match the current gate", 409)
            receipt = {"gate": gate, "label": GATES[gate], "artifact_hash": artifact_hash,
                "decision": decision, "reason": reason, "actor": identity["owner"],
                "company_id": identity["company_id"], "project_id": identity["project_id"],
                "simulated": True, "identity_verified": False,
                "decided_at": datetime.now(timezone.utc).isoformat()}
            self._graph.invoke(Command(resume=receipt), self._config(run_id), durability="sync")
            return self._public(self._read(registry, identity, run_id))

    def close(self):
        """Close the checkpoint connection once, after active service work has ended."""
        with self._mutex:
            if not self._closed:
                self._connection.close()
                self._closed = True
