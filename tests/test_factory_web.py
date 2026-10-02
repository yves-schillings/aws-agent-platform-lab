"""HTTP boundary for the local, checkpointed Factory increment."""
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from aws_agent_platform_lab.factory import FactoryService
from aws_agent_platform_lab.web import create_app

ALPHA = {"X-Demo-User": "localalpha"}
BETA = {"X-Demo-User": "localbeta"}
GAMMA = {"X-Demo-User": "localgamma"}
REQUEST = {"request_text": "Build a synthetic affiliation consultation application for three companies.", "synthetic": True}


class FactoryWebTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.root = root
        self.factory = FactoryService(root)
        self.client = self.enterContext(TestClient(
            create_app(environ={"LOCAL_DEMO_MODE": "true"}, factory_service=self.factory),
            base_url="http://127.0.0.1", client=("127.0.0.1", 55000)))

    def start(self, headers=ALPHA):
        result = self.client.post("/api/factory/runs", headers=headers, json=REQUEST)
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def test_http_four_gate_journey_and_replay_rejection(self):
        state = self.start()
        url = f"/api/factory/runs/{state['run_id']}/decision"
        for gate in ("G1", "G2", "G3", "G4"):
            self.assertEqual(state["pending_gate"]["gate"], gate)
            body = {"gate": gate, "artifact_hash": state["pending_gate"]["artifact_hash"],
                    "decision": "approve", "reason": "Reviewed the exact synthetic proposal."}
            result = self.client.post(url, headers=ALPHA, json=body)
            self.assertEqual(result.status_code, 200, result.text)
            state = result.json()
            self.assertEqual(self.client.post(url, headers=ALPHA, json=body).status_code, 409)
        self.assertEqual(state["status"], "release_ready")
        self.assertIsNone(state["pending_gate"])
        self.assertTrue(state["simulated"])
        self.assertEqual(len(state["decisions"]), 4)

    def test_identity_required_and_third_company_is_separate(self):
        self.assertEqual(self.client.post("/api/factory/runs", json=REQUEST).status_code, 401)
        state = self.start(GAMMA)
        self.assertEqual(state["company_id"], "company-3")
        url = f"/api/factory/runs/{state['run_id']}"
        self.assertEqual(self.client.get(url, headers=GAMMA).status_code, 200)
        for headers in (ALPHA, BETA):
            self.assertEqual(self.client.get(url, headers=headers).status_code, 404)

    def test_cannot_inject_authority_or_skip_review(self):
        for extra in ({"company_id": "company-2"}, {"project_id": "privileged"}, {"synthetic": False}):
            result = self.client.post("/api/factory/runs", headers=ALPHA, json={**REQUEST, **extra})
            self.assertEqual(result.status_code, 422)
        state = self.start()
        url = f"/api/factory/runs/{state['run_id']}/decision"
        body = {"gate": "G1", "artifact_hash": state["pending_gate"]["artifact_hash"], "decision": "approve", "reason": "Checked."}
        for extra in ({"gate": "G4"}, {"artifact_hash": "0" * 64}):
            self.assertEqual(self.client.post(url, headers=ALPHA, json={**body, **extra}).status_code, 409)
        self.assertEqual(self.client.post(url, headers=ALPHA, json={**body, "approver": "admin"}).status_code, 422)
        self.assertEqual(self.client.post(url, headers=BETA, json=body).status_code, 404)
        self.assertEqual(self.client.post(url, headers=ALPHA, json={**body, "reason": ""}).status_code, 422)

    def test_rejection_is_terminal_and_preserves_evidence(self):
        state = self.start()
        url = f"/api/factory/runs/{state['run_id']}"
        response = self.client.post(url + "/decision", headers=ALPHA, json={
            "gate": "G1", "artifact_hash": state["pending_gate"]["artifact_hash"],
            "decision": "reject", "reason": "Requirements need revision."})
        self.assertEqual(response.json()["status"], "rejected")
        restored = self.client.get(url, headers=ALPHA).json()
        self.assertEqual(restored["decisions"][0]["reason"], "Requirements need revision.")
        self.assertIsNone(restored["pending_gate"])

    def test_browser_assets_and_csp_are_served(self):
        response = self.client.get("/factory")
        self.assertEqual(response.status_code, 200)
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
        for name in ("factory.js", "factory.css"):
            self.assertEqual(self.client.get("/static/" + name).status_code, 200)
        identities = self.client.get("/api/factory/config").json()["identities"]
        self.assertEqual([i["label"] for i in identities], ["Company 1", "Company 2", "Company 3"])

    def test_cloud_mode_never_exposes_fixture_service(self):
        client = TestClient(create_app(environ={}, factory_service=self.factory))
        self.addCleanup(client.close)
        for path in ("/factory", "/api/factory/config", "/api/factory/runs/" + "a" * 32):
            self.assertEqual(client.get(path, headers=ALPHA).status_code, 404)
        self.assertEqual(client.post("/api/factory/runs", headers=ALPHA, json=REQUEST).status_code, 404)


if __name__ == "__main__":
    unittest.main()
