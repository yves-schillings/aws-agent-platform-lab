"""Local Factory acceptance: ordered gates, isolation, restart and concurrent decisions."""
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from aws_agent_platform_lab.auth import Principal
from aws_agent_platform_lab.factory import FactoryService, GATES
from aws_agent_platform_lab.models import canonical_bytes, sha256_bytes
from aws_agent_platform_lab.services import ServiceError


def principal(tenant="alpha"):
    return Principal("local" + tenant, ("demo-" + tenant,), tenant, "internal", True)


class FactoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.service = FactoryService(self.root)
        self.addCleanup(self.service.close)
        self.user = principal()

    def start(self, user=None):
        return self.service.start_run(user or self.user,
            "Prepare the shared read-only synthetic affiliation consultation application.")

    def decide(self, state, decision="approve", service=None):
        pending = state["pending_gate"]
        return (service or self.service).decide_run(self.user, state["run_id"],
            pending["gate"], pending["artifact_hash"], decision, "Reviewed this simulated proposal.")

    def assert_error(self, status, callback, *args):
        with self.assertRaises(ServiceError) as error:
            callback(*args)
        self.assertEqual(error.exception.status_code, status)

    def test_all_five_workers_and_four_ordered_pauses_end_only_release_ready(self):
        state = self.start()
        expected_roles = {"G1": {"analyst"}, "G2": {"analyst", "architect"},
            "G3": {"analyst", "architect", "code_author", "tester", "reviewer"}}
        for gate, label in GATES.items():
            self.assertEqual(state["status"], "waiting_approval")
            self.assertEqual(state["pending_gate"]["gate"], gate)
            self.assertEqual(state["pending_gate"]["label"], label)
            self.assertEqual(state["pending_gate"]["artifact_hash"],
                sha256_bytes(canonical_bytes(state["pending_gate"]["artifact"])))
            self.assertEqual(set(state["artifacts"]), expected_roles.get(gate, expected_roles["G3"]))
            state = self.decide(state)
        self.assertEqual(state["status"], "release_ready")
        self.assertIsNone(state["pending_gate"])
        self.assertEqual([d["gate"] for d in state["decisions"]], list(GATES))
        self.assertEqual(len(state["events"]), 9)
        self.assertTrue(all(a["simulated"] for a in state["artifacts"].values()))
        self.assertFalse(state["artifacts"]["code_author"]["deployable"])
        self.assertEqual(state["artifacts"]["tester"]["execution"], "not run")
        self.assertFalse(state["artifacts"]["reviewer"]["trusted_validation"])
        self.assertEqual(state["company_id"], "company-1")
        self.assertEqual(state["project_id"], "affiliation-demo")
        self.assertTrue(state["simulated"])
        self.assertEqual(state["engine"], "langgraph")
        self.assertIn("no build, execution or deployment", " ".join(state["limitations"]))

    def test_reject_at_each_gate_stops_all_forward_work(self):
        for rejected_gate in GATES:
            with self.subTest(gate=rejected_gate):
                state = self.start()
                while state["pending_gate"]["gate"] != rejected_gate:
                    state = self.decide(state)
                prior = state
                state = self.decide(state, "reject")
                self.assertEqual(state["status"], "rejected")
                self.assertIsNone(state["pending_gate"])
                self.assertEqual(state["artifacts"], prior["artifacts"])
                self.assertEqual(state["decisions"][-1]["decision"], "reject")
                self.assert_error(409, self.decide, prior)

    def test_stale_hash_wrong_gate_and_duplicate_cannot_advance(self):
        state = self.start()
        pending = state["pending_gate"]
        for gate, hash_ in (("G4", pending["artifact_hash"]), ("G1", "0" * 64)):
            self.assert_error(409, self.service.decide_run, self.user, state["run_id"],
                gate, hash_, "approve", "Reviewed.")
        self.assertEqual(self.service.get_run(self.user, state["run_id"]), state)
        next_state = self.decide(state)
        self.assert_error(409, self.decide, state)
        self.assertEqual(self.service.get_run(self.user, state["run_id"]), next_state)

    def test_all_three_identities_are_isolated_and_scope_cannot_be_forged(self):
        states = {tenant: self.start(principal(tenant)) for tenant in ("alpha", "beta", "gamma")}
        for tenant, state in states.items():
            user = principal(tenant)
            self.assertEqual(self.service.get_run(user, state["run_id"]), state)
            for other in states:
                if other != tenant:
                    self.assert_error(404, self.service.get_run, principal(other), state["run_id"])
                    pending = state["pending_gate"]
                    self.assert_error(404, self.service.decide_run, principal(other), state["run_id"],
                        "G1", pending["artifact_hash"], "approve", "Reviewed.")
        for bad in (replace(self.user, simulated=False), replace(self.user, tenant="beta"),
                    replace(self.user, access_level="public"), replace(self.user, groups=("admin",)),
                    replace(self.user, subject="invented")):
            self.assert_error(403, self.service.start_run, bad, "A synthetic request.")

    def test_read_result_is_detached_and_hash_cannot_cross_runs(self):
        first, second = self.start(), self.start()
        self.assertNotEqual(first["pending_gate"]["artifact_hash"], second["pending_gate"]["artifact_hash"])
        self.assert_error(409, self.service.decide_run, self.user, second["run_id"], "G1",
            first["pending_gate"]["artifact_hash"], "approve", "Reviewed.")
        first["artifacts"]["analyst"]["companies"].append("Tampered")
        self.assertEqual(len(self.service.get_run(self.user, first["run_id"])["artifacts"]["analyst"]["companies"]), 3)

    def test_close_and_reopen_at_each_gate_preserves_exact_pending_proposal(self):
        state = self.start()
        for gate in GATES:
            self.assertEqual(state["pending_gate"]["gate"], gate)
            self.service.close()
            self.service = FactoryService(self.root)
            self.addCleanup(self.service.close)
            self.assertEqual(self.service.get_run(self.user, state["run_id"]), state)
            state = self.decide(state)
        self.service.close()
        self.service = FactoryService(self.root)
        self.addCleanup(self.service.close)
        self.assertEqual(self.service.get_run(self.user, state["run_id"]), state)

    def test_two_service_instances_accept_only_one_concurrent_decision(self):
        other = FactoryService(self.root)
        self.addCleanup(other.close)
        state = self.start()
        barrier = threading.Barrier(2)
        def submit(service):
            barrier.wait(timeout=5)
            try:
                return self.decide(state, service=service)
            except ServiceError as error:
                return error.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, (self.service, other)))
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1)
        self.assertEqual(results.count(409), 1)
        current = self.service.get_run(self.user, state["run_id"])
        self.assertEqual(len(current["decisions"]), 1)
        self.assertEqual(current["pending_gate"]["gate"], "G2")

    def test_process_exit_without_close_preserves_gate_and_prior_decision(self):
        script = """
import json, os, sys
from pathlib import Path
from aws_agent_platform_lab.auth import Principal
from aws_agent_platform_lab.factory import FactoryService
service = FactoryService(Path(sys.argv[1]))
user = Principal('localalpha', ('demo-alpha',), 'alpha', 'internal', True)
state = service.start_run(user, 'Prepare the synthetic affiliation consultation application.')
gate = state['pending_gate']
state = service.decide_run(user, state['run_id'], gate['gate'], gate['artifact_hash'], 'approve', 'Reviewed.')
print(json.dumps(state), flush=True)
os._exit(0)
"""
        result = subprocess.run([sys.executable, "-B", "-c", script, str(self.root)],
                                capture_output=True, text=True, timeout=30, check=True)
        state = json.loads(result.stdout)
        self.assertEqual(state["pending_gate"]["gate"], "G2")
        self.assertEqual(self.service.get_run(self.user, state["run_id"]), state)
        self.assertEqual(self.decide(state)["pending_gate"]["gate"], "G3")

    def test_separate_processes_cannot_both_apply_the_same_decision(self):
        state = self.start()
        script = """
import json, sys
from pathlib import Path
from aws_agent_platform_lab.auth import Principal
from aws_agent_platform_lab.factory import FactoryService
from aws_agent_platform_lab.services import ServiceError
service = FactoryService(Path(sys.argv[1]))
user = Principal('localalpha', ('demo-alpha',), 'alpha', 'internal', True)
print('ready', flush=True)
sys.stdin.readline()
try:
    result = service.decide_run(user, sys.argv[2], 'G1', sys.argv[3], 'approve', 'Reviewed.')
    print(json.dumps({'accepted': result['pending_gate']['gate']}), flush=True)
except ServiceError as error:
    print(json.dumps({'error': error.status_code}), flush=True)
finally:
    service.close()
"""
        processes = []
        try:
            for _ in range(2):
                processes.append(subprocess.Popen([sys.executable, "-B", "-c", script,
                    str(self.root), state["run_id"], state["pending_gate"]["artifact_hash"]],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
            for process in processes:
                self.assertEqual(process.stdout.readline().strip(), "ready")
            for process in processes:
                process.stdin.write("go\n")
                process.stdin.flush()
            results = []
            for process in processes:
                stdout, stderr = process.communicate(timeout=30)
                self.assertEqual(process.returncode, 0, stderr)
                results.append(json.loads(stdout))
            self.assertCountEqual(results, [{"accepted": "G2"}, {"error": 409}])
            self.assertEqual(len(self.service.get_run(self.user, state["run_id"])["decisions"]), 1)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)

    def test_checkpoint_scope_or_proposal_mutation_is_not_approvable(self):
        state = self.start()
        config = self.service._config(state["run_id"])
        snapshot = self.service._graph.get_state(config)
        changed = json.loads(json.dumps(snapshot.values["artifacts"]))
        changed["analyst"]["purpose"] = "Changed after review"
        self.service._graph.update_state(config, {"artifacts": changed})
        self.assert_error(409, self.decide, state)

    def test_invalid_inputs_are_safe_and_do_not_create_runs(self):
        for request in (None, "short", "x" * 4001, "bad\x00request", "bad surrogate \ud800"):
            self.assert_error(422, self.service.start_run, self.user, request)
        for run_id in ("../other", "0" * 32, None):
            self.assert_error(404, self.service.get_run, self.user, run_id)
        state = self.start()
        for reason in ("", "x" * 1001, "\x00", None):
            self.assert_error(422, self.service.decide_run, self.user, state["run_id"], "G1",
                state["pending_gate"]["artifact_hash"], "approve", reason)
        for gate, decision in (([], "approve"), ("G1", []), ("G1", "skip")):
            self.assert_error(422, self.service.decide_run, self.user, state["run_id"], gate,
                state["pending_gate"]["artifact_hash"], decision, "Reviewed.")

    def test_external_tracing_is_disabled_and_pickle_deserialization_is_rejected(self):
        from langsmith.run_helpers import get_tracing_context
        original = self.service._graph.invoke
        seen = []
        def inspect(*args, **kwargs):
            seen.append(get_tracing_context()["enabled"])
            return original(*args, **kwargs)
        with patch.dict("os.environ", {"LANGSMITH_TRACING": "true", "LANGCHAIN_TRACING_V2": "true"}), \
                patch.object(self.service._graph, "invoke", side_effect=inspect):
            state = self.start()
            self.decide(state)
        self.assertEqual(seen, [False, False])
        with self.assertRaises(NotImplementedError):
            self.service._saver.serde.loads_typed(("pickle", b"untrusted"))


if __name__ == "__main__":
    unittest.main()
