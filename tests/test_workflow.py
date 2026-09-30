"""Offline behavioral checks. No cloud credentials, accounts or network required."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from aws_agent_platform_lab.models import ValidationError, canonical_bytes, parse_json
from aws_agent_platform_lab.providers import MockProvider
from aws_agent_platform_lab.workflow import run_workflow, decide_run

ROOT = Path(__file__).resolve().parents[1]


class ControlledProvider(MockProvider):
    def __init__(self, *, reject_reviews: int = 0, invalid_citations: bool = False):
        super().__init__()
        self.reject_reviews = reject_reviews
        self.invalid_citations = invalid_citations
        self.calls = []

    def generate(self, role, prompt):
        self.calls.append((role, json.loads(prompt)))
        response = json.loads(super().generate(role, prompt))
        if role == "reviewer" and self.reject_reviews:
            self.reject_reviews -= 1
            response.update(approved=False, issues=["Add an explicit human evidence check."])
        if role == "designer" and self.invalid_citations:
            response["citations"] = ["UNAUTHORIZED-DOCUMENT"]
        return json.dumps(response)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="aws-agent-platform-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.run_dir = self.base / "run"

    def run_case(self, provider=None, **kwargs):
        return run_workflow(ROOT / "scenarios" / "demo.json", self.run_dir,
            provider=provider or MockProvider(), corpus_path=ROOT / "corpus" / "knowledge.json", **kwargs)

    def test_run_stops_before_publication_and_is_reproducible(self):
        first = self.run_case()
        self.assertEqual(first["status"], "waiting_approval")
        self.assertFalse((self.run_dir / "published").exists())
        self.assertEqual(len(list(self.run_dir.glob("state.[0-9]*.json"))), 2)
        second = run_workflow(ROOT / "scenarios" / "demo.json", self.base / "second",
            provider=MockProvider(), corpus_path=ROOT / "corpus" / "knowledge.json")
        self.assertEqual(first["artifact_hash"], second["artifact_hash"])
        events = [json.loads(line) for line in (self.run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([e["role"] for e in events if e["event"] == "agent_call"], ["analyst", "designer", "reviewer"])

    def test_approval_publishes_exact_bytes_and_cannot_be_replayed(self):
        state = self.run_case()
        approved = decide_run(self.run_dir, state["artifact_hash"], "approve")
        self.assertEqual(approved["status"], "approved")
        self.assertEqual((self.run_dir / "artifact.json").read_bytes(),
                         (self.run_dir / "published" / "approved_workflow.json").read_bytes())
        with self.assertRaises(ValidationError):
            decide_run(self.run_dir, state["artifact_hash"], "approve")

    def test_wrong_hash_is_refused_without_decision_or_tool(self):
        self.run_case()
        with self.assertRaises(ValidationError):
            decide_run(self.run_dir, "0" * 64, "approve")
        self.assertFalse((self.run_dir / "human_decision.json").exists())
        self.assertFalse((self.run_dir / "published").exists())

    def test_modified_artifact_invalidates_old_approval_hash(self):
        state = self.run_case()
        with (self.run_dir / "artifact.json").open("ab") as handle:
            handle.write(b" ")
        with self.assertRaises(ValidationError):
            decide_run(self.run_dir, state["artifact_hash"], "approve")
        self.assertFalse((self.run_dir / "published").exists())

    def test_rejection_never_publishes(self):
        state = self.run_case()
        rejected = decide_run(self.run_dir, state["artifact_hash"], "reject")
        self.assertEqual(rejected["status"], "rejected")
        self.assertFalse((self.run_dir / "published").exists())

    def test_feedback_reaches_next_designer_and_successful_second_review(self):
        provider = ControlledProvider(reject_reviews=1)
        state = self.run_case(provider)
        self.assertEqual(state["status"], "waiting_approval")
        self.assertEqual(state["revision"], 1)
        next_design = [p for role, p in provider.calls if role == "designer"][1]
        self.assertEqual(next_design["previous_review"]["issues"], ["Add an explicit human evidence check."])

    def test_correction_loop_is_bounded_to_two_corrections(self):
        provider = ControlledProvider(reject_reviews=100)
        state = self.run_case(provider)
        self.assertEqual(state["status"], "review_failed")
        self.assertEqual(len(provider.calls), 7)
        self.assertEqual(state["revision"], 2)
        self.assertFalse((self.run_dir / "artifact.json").exists())

    def test_unknown_citations_cannot_reach_human_approval(self):
        provider = ControlledProvider(invalid_citations=True)
        state = self.run_case(provider)
        self.assertEqual(state["status"], "review_failed")
        self.assertEqual([role for role, _ in provider.calls].count("designer"), 3)
        self.assertEqual([role for role, _ in provider.calls].count("reviewer"), 0)
        self.assertFalse((self.run_dir / "artifact.json").exists())

    def test_existing_output_is_preserved(self):
        self.run_dir.mkdir()
        sentinel = self.run_dir / "existing.txt"
        sentinel.write_text("preserve", encoding="utf-8")
        with self.assertRaises(ValidationError):
            self.run_case()
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve")

    def test_model_paths_and_code_remain_inert_data(self):
        outside = self.base / "must_not_exist.txt"
        class MaliciousText(MockProvider):
            def generate(self, role, prompt):
                result = json.loads(super().generate(role, prompt))
                if role == "designer":
                    result["steps"][0]["action"] = f"__import__('pathlib').Path({str(outside)!r}).write_text('bad')"
                    result["output_path"] = str(outside)
                return json.dumps(result)
        state = self.run_case(MaliciousText())
        decide_run(self.run_dir, state["artifact_hash"], "approve")
        self.assertFalse(outside.exists())
        self.assertTrue((self.run_dir / "published" / "approved_workflow.json").is_file())

    def test_publication_symlink_cannot_redirect_tool(self):
        state = self.run_case()
        outside = self.base / "outside"
        outside.mkdir()
        try:
            os.symlink(outside, self.run_dir / "published", target_is_directory=True)
        except OSError:
            self.skipTest("Creating a test symlink requires platform permission")
        with self.assertRaises(ValidationError):
            decide_run(self.run_dir, state["artifact_hash"], "approve")
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((self.run_dir / "human_decision.json").exists())

    def test_blocked_publication_does_not_consume_decision(self):
        state = self.run_case()
        published = self.run_dir / "published"
        published.mkdir()
        existing = published / "approved_workflow.json"
        existing.write_text("preserve this file", encoding="utf-8")
        with self.assertRaises(ValidationError):
            decide_run(self.run_dir, state["artifact_hash"], "approve")
        self.assertEqual(existing.read_text(encoding="utf-8"), "preserve this file")
        self.assertFalse((self.run_dir / "human_decision.json").exists())
        existing.unlink()
        self.assertEqual(decide_run(self.run_dir, state["artifact_hash"], "approve")["status"], "approved")

    def test_json_boundary_rejects_nonfinite_numbers_and_invalid_unicode(self):
        for payload in ('{"extra": 1e999}', '{"extra": "\\ud800"}', '\ud800'):
            with self.subTest(payload=repr(payload)[:80]), self.assertRaises(ValidationError):
                parse_json(payload)

    def test_non_synthetic_input_rejected_before_output(self):
        scenario = json.loads((ROOT / "scenarios" / "demo.json").read_text(encoding="utf-8"))
        scenario["synthetic"] = False
        path = self.base / "real.json"
        path.write_bytes(canonical_bytes(scenario))
        with self.assertRaises(ValidationError):
            run_workflow(path, self.run_dir, corpus_path=ROOT / "corpus" / "knowledge.json")
        self.assertFalse(self.run_dir.exists())


if __name__ == "__main__":
    unittest.main()
