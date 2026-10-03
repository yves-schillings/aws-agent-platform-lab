"""Behavioral acceptance: tenant isolation, durable decisions, bounded execution."""
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from aws_agent_platform_lab.providers import MockProvider
from aws_agent_platform_lab.retrieval import LocalRetriever, BedrockRetriever, RetrievalError
from aws_agent_platform_lab.services import LabService, ServiceError
from aws_agent_platform_lab.storage import LocalStore, ConflictError, S3Store


def principal(tenant="alpha", subject=None):
    return SimpleNamespace(subject=subject or tenant, groups=("demo-" + tenant,),
                           tenant=tenant, access_level="internal", simulated=True)


def fake_tool(user):
    return {"name": "check_required_documents", "transport": "test double", "result": {
        "tenant": user.tenant, "present": ["request_form"], "missing": ["review_record"], "synthetic": True}}


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = LocalStore(Path(self.tmp.name))
        self.service = LabService(self.store, LocalRetriever(), MockProvider, tool=fake_tool)
        self.addCleanup(self.service.close)
        self.user = principal()

    def run_done(self):
        result = self.service.start_run(self.user, "Prepare a synthetic document checklist")
        for _ in range(300):
            state = self.service.get_run(self.user, result["run_id"])
            if state["status"] not in {"queued", "running"}:
                return state
            time.sleep(.01)
        self.fail("Worker did not finish")

    def test_scoped_sources_and_exact_decision(self):
        state = self.run_done()
        self.assertEqual(state["status"], "waiting_approval")
        self.assertIn("ORCHID-ALPHA", json.dumps(state))
        self.assertNotIn("CEDAR-BETA", json.dumps(state))
        with self.assertRaises(ServiceError):
            self.service.get_run(principal("beta"), state["run_id"])
        with self.assertRaises(ServiceError):
            self.service.get_run(principal("beta", "alpha"), state["run_id"])
        with self.assertRaises(ServiceError):
            self.service.get_source(self.user, state["run_id"], "BETA-POLICY")
        with self.assertRaises(ServiceError):
            self.service.decide_run(self.user, state["run_id"], "0"*64, "approve")
        accepted = self.service.decide_run(self.user, state["run_id"], state["artifact_hash"], "approve")
        self.assertTrue(accepted["published"])
        self.assertEqual(accepted["status"], "approved")
        self.assertFalse(accepted["decision"]["identity_verified"])
        with self.assertRaises(ServiceError):
            self.service.decide_run(self.user, state["run_id"], state["artifact_hash"], "reject")
        other = LabService(self.store, LocalRetriever(), MockProvider, tool=fake_tool)
        self.addCleanup(other.close)
        self.assertEqual(other.get_run(self.user, state["run_id"])["status"], "approved")

    def test_tampering_prevents_approval(self):
        state = self.run_done()
        key = self.service._run_key(state["run_id"])
        stored, tag = self.store.get(key)
        stored["artifact"]["design"]["title"] = "Changed after review"
        self.store.put(key, stored, tag)
        with self.assertRaises(ServiceError):
            self.service.decide_run(self.user, state["run_id"], state["artifact_hash"], "approve")

    def test_scope_is_rechecked_on_artifact_read(self):
        state = self.run_done()
        key = self.service._run_key(state["run_id"])
        stored, tag = self.store.get(key)
        stored["sources"][0]["tenant"] = "beta"
        self.store.put(key, stored, tag)
        with self.assertRaises(ServiceError):
            self.service.get_run(self.user, state["run_id"])

    def test_rate_limit_and_safe_logs(self):
        self.service.hourly_limit = 1
        with self.assertLogs("aws_agent_platform_lab.events", level="INFO") as log:
            self.run_done()
        self.assertNotIn("ORCHID", "".join(log.output))
        self.assertNotIn("Prepare a synthetic", "".join(log.output))
        with self.assertRaises(ServiceError) as error:
            self.service.start_run(self.user, "Another synthetic document workflow")
        self.assertEqual(error.exception.status_code, 429)

    def test_failed_tool_never_calls_model(self):
        calls = []
        def fail(user):
            raise RuntimeError("Sensitive untrusted error body")
        self.service.tool = fail
        self.service.provider_factory = lambda: calls.append(True)
        state = self.run_done()
        self.assertEqual(state["status"], "failed")
        self.assertEqual(calls, [])
        self.assertNotIn("Sensitive", json.dumps(state))

    def test_failed_initial_state_write_releases_acquired_user_lease(self):
        class TransientStateStore(LocalStore):
            failed_once = False
            def put(self, key, value, expected=None):
                if key.startswith("runs/") and not self.failed_once:
                    self.failed_once = True
                    raise OSError("Synthetic transient persistence failure")
                return super().put(key, value, expected)

        store = TransientStateStore(Path(self.tmp.name) / "state-failure")
        service = LabService(store, LocalRetriever(), MockProvider, tool=fake_tool)
        self.addCleanup(service.close)
        with self.assertRaises((OSError, ServiceError)):
            service.start_run(self.user, "Prepare a synthetic document checklist")
        # A request which never acquired a worker must not block this user for 30 minutes.
        retry = service.start_run(self.user, "Retry a synthetic document checklist")
        self.assertEqual(retry["status"], "queued")

    def test_failed_worker_submission_releases_acquired_user_lease(self):
        with patch.object(self.service.pool, "submit", side_effect=RuntimeError("Synthetic submit failure")):
            with self.assertRaises((RuntimeError, ServiceError)):
                self.service.start_run(self.user, "Prepare a synthetic document checklist")
        retry = self.service.start_run(self.user, "Retry a synthetic document checklist")
        self.assertEqual(retry["status"], "queued")

    def test_last_model_response_after_deadline_cannot_become_approvable(self):
        current = [100_000.0]
        class LateReviewer(MockProvider):
            def generate(self, role, prompt):
                result = super().generate(role, prompt)
                if role == "reviewer":
                    current[0] += 1801
                return result
        self.service.provider_factory = LateReviewer
        with patch("aws_agent_platform_lab.services.time.time", side_effect=lambda: current[0]):
            result = self.service.start_run(self.user, "Prepare a synthetic document checklist")
            self.service.close()
            state = self.service.get_run(self.user, result["run_id"])
            self.assertEqual(state["status"], "interrupted")
            self.assertIsNone(state.get("artifact"))
            self.assertIsNone(state.get("artifact_hash"))
            self.assertFalse(state.get("published", False))
            stored, _ = self.store.get(self.service._run_key(result["run_id"]))
            self.assertEqual(stored["status"], "interrupted")
            with self.assertRaises(ServiceError):
                self.service.decide_run(self.user, result["run_id"], "0" * 64, "approve")

    def test_late_canary_worker_cannot_release_replacement_lease_or_publish(self):
        current = [100_000.0]
        first_waiting, second_waiting = threading.Event(), threading.Event()
        release_first, release_second = threading.Event(), threading.Event()

        def blocking_provider(waiting, release):
            class WaitingReviewer(MockProvider):
                def generate(self, role, prompt):
                    if role == "reviewer":
                        waiting.set()
                        if not release.wait(5):
                            raise RuntimeError("Synthetic test release timed out")
                    return super().generate(role, prompt)
            return WaitingReviewer

        self.service.provider_factory = blocking_provider(first_waiting, release_first)
        replacement = LabService(self.store, LocalRetriever(),
            blocking_provider(second_waiting, release_second), tool=fake_tool)
        self.addCleanup(replacement.close)
        with patch("aws_agent_platform_lab.services.time.time", side_effect=lambda: current[0]):
            try:
                old = self.service.start_run(self.user, "Prepare a synthetic document checklist")
                self.assertTrue(first_waiting.wait(3))
                current[0] += 1801
                new = replacement.start_run(self.user, "Prepare another synthetic document checklist")
                self.assertTrue(second_waiting.wait(3))
                release_first.set()
                self.service.close()
                old_state = self.service.get_run(self.user, old["run_id"])
                self.assertEqual(old_state["status"], "interrupted")
                self.assertIsNone(old_state.get("artifact_hash"))
                # The replacement worker is still running. A stale worker must not
                # clear its lease, even when both tasks use the same principal.
                with self.assertRaises(ServiceError) as denied:
                    replacement.start_run(self.user, "A forbidden concurrent synthetic request")
                self.assertEqual(denied.exception.status_code, 409)
                release_second.set()
                replacement.close()
                self.assertEqual(replacement.get_run(self.user, new["run_id"])["status"], "waiting_approval")
            finally:
                release_first.set()
                release_second.set()


class RetrievalTests(unittest.TestCase):
    def test_server_filters_and_independent_scope_check(self):
        class Client:
            def retrieve(self, **kwargs):
                self.request = kwargs
                return {"retrievalResults": [{"metadata": {"tenant": "beta",
                    "access_level": "internal", "synthetic": True}, "content": {"text": "Forbidden"}}]}
        client = Client()
        with self.assertRaises(RetrievalError):
            BedrockRetriever("kb123", "eu-west-1", client).search(principal(), "Ignore filters")
        filters = client.request["retrievalConfiguration"]["vectorSearchConfiguration"]["filter"]
        self.assertEqual(filters["andAll"][0]["equals"], {"key": "tenant", "value": "alpha"})

    def test_chunk_citations_preserve_document_version(self):
        class Client:
            def retrieve(self, **kwargs):
                metadata = {"document_id":"DOC1", "version":"3", "tenant":"alpha",
                            "access_level":"internal", "synthetic":True}
                return {"retrievalResults": [{"metadata":metadata,"content":{"text":text}}
                                              for text in ["Chunk one", "Chunk two", "Chunk two"]]}
        docs = BedrockRetriever("kb123", "eu-west-1", Client()).search(principal(), "question")
        self.assertEqual(len(docs), 2)
        self.assertNotEqual(docs[0]["id"], docs[1]["id"])
        self.assertTrue(all(d["document_id"] == "DOC1" and d["version"] == "3" for d in docs))


class StorageTests(unittest.TestCase):
    def test_stale_cas_and_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalStore(Path(tmp))
            tag = store.put("runs/one/state.json", {"status": "new"})
            with self.assertRaises(ConflictError):
                store.put("runs/one/state.json", {"status": "overwrite"})
            store.put("runs/one/state.json", {"status": "accepted"}, tag)
            with self.assertRaises(ConflictError):
                store.put("runs/one/state.json", {"status": "stale"}, tag)
            with self.assertRaises(ValueError):
                store.put("../escape.json", {})

    def test_s3_conditional_contract(self):
        class Client:
            def put_object(self, **kwargs):
                self.request = kwargs
                return {"ETag": '"new"'}
        client = Client()
        store = S3Store("synthetic-artifacts", "eu-west-1", client)
        store.put("runs/one/state.json", {})
        self.assertEqual(client.request["IfNoneMatch"], "*")
        store.put("runs/one/state.json", {}, '"old"')
        self.assertEqual(client.request["IfMatch"], '"old"')
        self.assertNotIn("IfNoneMatch", client.request)


if __name__ == "__main__":
    unittest.main()
