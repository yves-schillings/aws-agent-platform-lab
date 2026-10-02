"""Actual local stdio MCP, including human form elicitation and fail-closed paths."""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

from aws_agent_platform_lab.auth import Principal
from aws_agent_platform_lab.factory import FactoryService
from aws_agent_platform_lab.factory_mcp import create_server


def host_env(root, identity="localalpha"):
    env = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP")
           if key in os.environ}
    env.update(PYTHONUTF8="1", LOCAL_DEMO_MODE="true", FACTORY_LOCAL_IDENTITY=identity,
               LAB_DATA_DIR=str(root), AWS_EC2_METADATA_DISABLED="true")
    return env


@asynccontextmanager
async def session(root, callback=None, identity="localalpha", allow_review=False):
    env = host_env(root, identity)
    if allow_review:
        env["FACTORY_ALLOW_SIMULATED_REVIEW"] = "true"
    parameters = StdioServerParameters(command=sys.executable,
        args=["-B", "-m", "aws_agent_platform_lab.factory_mcp"], env=env)
    async with asyncio.timeout(45):
        with open(os.devnull, "w") as error_log:
            async with stdio_client(parameters, errlog=error_log) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=30),
                                         elicitation_callback=callback) as client:
                    await client.initialize()
                    yield client


async def call(client, name, arguments=None):
    result = await client.call_tool(name, arguments or {})
    if result.isError:
        raise AssertionError("Unexpected MCP error: " + str(result.content))
    return result.structuredContent


async def start(client):
    return await call(client, "factory_start", {"request_text":
        "Prepare the read-only synthetic affiliation consultation application.", "synthetic": True})


class FactoryMcpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_real_stdio_describe_start_get_and_accept_four_human_forms(self):
        async def exercise():
            reviewed = []
            async def human(context, params):
                self.assertEqual(set(params.requestedSchema["properties"]), {"decision", "reason"})
                self.assertFalse(params.requestedSchema["additionalProperties"])
                pending = json.loads(params.message.split("Reviewed artifact (JSON):\n", 1)[1])
                self.assertIn("must not choose or auto-fill", params.message)
                self.assertEqual(len(pending["artifact_hash"]), 64)
                self.assertTrue(pending["artifact"]["simulated"])
                reviewed.append(pending)
                return types.ElicitResult(action="accept", content={
                    "decision": "approve", "reason": "I inspected this exact simulated proposal."})
            async with session(self.root, human, allow_review=True) as client:
                description = await call(client, "factory_describe")
                self.assertEqual(len(description["roles"]), 5)
                self.assertEqual([g["gate"] for g in description["gates"]], ["G1", "G2", "G3", "G4"])
                state = await start(client)
                self.assertEqual(await call(client, "factory_get", {"run_id": state["run_id"]}), state)
                for gate in ("G1", "G2", "G3", "G4"):
                    before = state["pending_gate"]
                    state = await call(client, "factory_request_review", {"run_id": state["run_id"]})
                    self.assertEqual(reviewed[-1], before)
                    self.assertEqual(state["decisions"][-1]["gate"], gate)
                    self.assertEqual(state["review_outcome"], "applied")
                self.assertEqual(state["status"], "release_ready")
                self.assertIn("not cryptographic proof", state["review_provenance"])
                self.assertFalse(state["artifacts"]["code_author"]["deployable"])
                replay = await call(client, "factory_request_review", {"run_id": state["run_id"]})
                self.assertEqual(replay["error"]["code"], "no_pending_gate")
        asyncio.run(exercise())

    def test_decline_cancel_and_invalid_accepted_forms_do_not_change_state(self):
        async def exercise():
            responses = iter([
                types.ElicitResult(action="decline"), types.ElicitResult(action="cancel"),
                types.ElicitResult(action="accept", content={"decision": "approve", "reason": ""}),
                types.ElicitResult(action="accept", content={"decision": "approve", "reason": "Reviewed",
                                                             "actor": "FORBIDDEN_SECRET_SENTINEL"}),
            ])
            async def human(context, params):
                return next(responses)
            async with session(self.root, human, allow_review=True) as client:
                state = await start(client)
                for expected in ("declined", "cancelled", "invalid_review", "invalid_review"):
                    result = await call(client, "factory_request_review", {"run_id": state["run_id"]})
                    self.assertEqual(result.get("review_outcome", result.get("error", {}).get("code")), expected)
                    self.assertNotIn("FORBIDDEN_SECRET_SENTINEL", json.dumps(result))
                    self.assertEqual(await call(client, "factory_get", {"run_id": state["run_id"]}), state)
        asyncio.run(exercise())

    def test_explicit_human_rejection_ends_the_run(self):
        async def human(context, params):
            return types.ElicitResult(action="accept", content={"decision": "reject", "reason": "Scope is incomplete."})
        async def exercise():
            async with session(self.root, human, allow_review=True) as client:
                state = await start(client)
                result = await call(client, "factory_request_review", {"run_id": state["run_id"]})
                self.assertEqual(result["status"], "rejected")
                self.assertEqual(result["decisions"][0]["reason"], "Scope is incomplete.")
        asyncio.run(exercise())

    def test_client_without_elicitation_cannot_advance(self):
        async def exercise():
            async with session(self.root, allow_review=True) as client:
                state = await start(client)
                result = await call(client, "factory_request_review", {"run_id": state["run_id"]})
                self.assertEqual(result["error"]["code"], "client_unsupported")
                self.assertEqual(await call(client, "factory_get", {"run_id": state["run_id"]}), state)
        asyncio.run(exercise())

    def test_state_changed_during_elicitation_cannot_receive_stale_decision(self):
        async def exercise():
            captured = {}
            async def human(context, params):
                pending = json.loads(params.message.split("Reviewed artifact (JSON):\n", 1)[1])
                service = FactoryService(self.root / "factory")
                try:
                    user = Principal("localalpha", ("demo-alpha",), "alpha", "internal", True)
                    captured["state"] = service.decide_run(user, pending["artifact"]["run_id"],
                        pending["gate"], pending["artifact_hash"], "approve", "Concurrent human review.")
                finally:
                    service.close()
                return types.ElicitResult(action="accept", content={"decision": "approve", "reason": "Older review."})
            async with session(self.root, human, allow_review=True) as client:
                state = await start(client)
                result = await call(client, "factory_request_review", {"run_id": state["run_id"]})
                self.assertEqual(result["error"]["code"], "stale_review")
                current = await call(client, "factory_get", {"run_id": state["run_id"]})
                self.assertEqual(current, {"ok": True, **captured["state"]})
                self.assertEqual(len(current["decisions"]), 1)
                self.assertEqual(current["pending_gate"]["gate"], "G2")
        asyncio.run(exercise())

    def test_simulated_review_is_disabled_by_default_even_with_capable_client(self):
        async def human(context, params):
            self.fail("Disabled review must never ask the client for a form")
        async def exercise():
            async with session(self.root, human) as client:
                self.assertFalse((await call(client, "factory_describe"))["simulated_review_enabled"])
                state = await start(client)
                result = await call(client, "factory_request_review", {"run_id": state["run_id"]})
                self.assertEqual(result["error"]["code"], "review_disabled")
                self.assertEqual(await call(client, "factory_get", {"run_id": state["run_id"]}), state)
        asyncio.run(exercise())

    def test_tool_schemas_and_runtime_forbid_model_scope_and_decision_arguments(self):
        async def exercise():
            async with session(self.root) as client:
                tools = (await client.list_tools()).tools
                self.assertEqual({tool.name for tool in tools}, {
                    "factory_describe", "factory_start", "factory_get", "factory_request_review"})
                for tool in tools:
                    self.assertFalse(tool.inputSchema["additionalProperties"])
                    self.assertFalse({"actor", "decision", "artifact_hash", "tenant", "company_id"}
                                     & set(tool.inputSchema["properties"]))
                state = await start(client)
                cases = [
                    ("factory_describe", {"tenant": "beta"}),
                    ("factory_start", {"request_text": "A synthetic request.", "synthetic": True,
                                       "company_id": "company-2"}),
                    ("factory_start", {"request_text": "A synthetic request.", "synthetic": False}),
                    ("factory_start", {"request_text": "A synthetic request.", "synthetic": "true"}),
                    ("factory_get", {"run_id": state["run_id"], "actor": "SECRET_SENTINEL"}),
                    ("factory_request_review", {"run_id": state["run_id"], "decision": "approve",
                                                "artifact_hash": state["pending_gate"]["artifact_hash"]}),
                ]
                for name, args in cases:
                    result = await client.call_tool(name, args)
                    self.assertTrue(result.isError)
                    self.assertNotIn("SECRET_SENTINEL", str(result.content))
                self.assertEqual(await call(client, "factory_get", {"run_id": state["run_id"]}), state)
        asyncio.run(exercise())

    def test_host_selected_identities_cannot_read_each_others_runs(self):
        async def exercise():
            async with session(self.root) as client:
                state = await start(client)
            async with session(self.root, identity="localbeta") as client:
                result = await call(client, "factory_get", {"run_id": state["run_id"]})
                self.assertEqual(result["error"]["status"], 404)
                self.assertEqual((await start(client))["company_id"], "company-2")
            async with session(self.root, identity="localgamma") as client:
                self.assertEqual((await start(client))["company_id"], "company-3")
        asyncio.run(exercise())

    def test_missing_host_identity_or_local_mode_fails_before_state_creation(self):
        for missing in ("FACTORY_LOCAL_IDENTITY", "LOCAL_DEMO_MODE", "LAB_DATA_DIR"):
            env = host_env(self.root)
            env.pop(missing)
            with self.assertRaises(ValueError):
                create_server(env)
        self.assertFalse((self.root / "factory").exists())
        env = host_env(self.root)
        env.pop("FACTORY_LOCAL_IDENTITY")
        result = subprocess.run([sys.executable, "-B", "-m", "aws_agent_platform_lab.factory_mcp"],
                                env=env, input="", capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertNotIn(str(self.root), result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse((self.root / "factory").exists())


if __name__ == "__main__":
    unittest.main()
