"""HTTP journeys cover source isolation, exact decisions and fail-closed auth."""
import json
from pathlib import Path
import tempfile
import time
import unittest

import httpx
from fastapi.testclient import TestClient

from aws_agent_platform_lab.auth import AuthError, Principal
from aws_agent_platform_lab.providers import MockProvider
from aws_agent_platform_lab.retrieval import LocalRetriever
from aws_agent_platform_lab.services import LabService
from aws_agent_platform_lab.storage import LocalStore
from aws_agent_platform_lab.web import create_app

LOCAL = {"LOCAL_DEMO_MODE": "true"}
ALPHA = {"X-Demo-User": "localalpha"}
BETA = {"X-Demo-User": "localbeta"}
REQUEST = {"request_text": "Prepare a synthetic document checklist with source citations.", "synthetic": True}
CLOUD = {
    "AWS_REGION": "eu-west-1", "COGNITO_USER_POOL_ID": "eu-west-1_testPool",
    "COGNITO_CLIENT_ID": "testclient123",
    "COGNITO_ISSUER": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_testPool",
    "COGNITO_DOMAIN": "https://synthetic.auth.eu-west-1.amazoncognito.com",
    "COGNITO_REDIRECT_URI": "https://lab.example.org/auth/callback",
    "ACCESS_POLICY_JSON": json.dumps({"demo-alpha": {"tenant": "alpha", "access_level": "internal"}}),
}


def local_tool(principal):
    return {"name": "check_required_documents", "transport": "offline test double", "result": {
        "tenant": principal.tenant, "present": ["request_form"], "missing": ["review_record"], "synthetic": True}}


class LocalWebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = LabService(LocalStore(Path(self.tmp.name)), LocalRetriever(), MockProvider, tool=local_tool)
        self.client = self.enterContext(TestClient(create_app(service=self.service, environ=LOCAL),
                                                  base_url="http://127.0.0.1", client=("127.0.0.1", 55000)))

    def completed_run(self):
        response = self.client.post("/api/runs", headers=ALPHA, json=REQUEST)
        self.assertEqual(response.status_code, 202, response.text)
        run_id = response.json()["run_id"]
        for _ in range(200):
            state = self.client.get(f"/api/runs/{run_id}", headers=ALPHA).json()
            if state["status"] not in {"queued", "running"}:
                return state
            time.sleep(.01)
        self.fail("The offline workflow did not finish")

    def test_local_ui_identifies_simulation_and_has_security_headers(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("AWS Agent Platform Lab", response.text)
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.client.get("/auth/config").json()["mode"], "offline")
        self.assertTrue(self.client.get("/api/me", headers=ALPHA).json()["simulated"])

    def test_missing_or_invented_demo_identity_is_not_authorised(self):
        for headers in ({}, {"X-Demo-User": "administrator"}, {"Authorization": "Bearer localalpha"}):
            self.assertEqual(self.client.get("/api/me", headers=headers).status_code, 401)

    def test_dns_rebinding_host_is_denied(self):
        response = self.client.get("/auth/config", headers={"Host": "attacker.example.org"})
        self.assertEqual(response.status_code, 403)

    def test_remote_peer_is_denied_even_with_local_host_header(self):
        with TestClient(create_app(service=self.service, environ=LOCAL),
                        base_url="http://127.0.0.1", client=("192.0.2.1", 55000)) as client:
            self.assertEqual(client.get("/healthz").status_code, 403)

    def test_payload_cannot_override_identity_scope_or_tool_command(self):
        for extra in ({"tenant": "beta"}, {"groups": ["admin"]}, {"mcp_command": "execute"},
                      {"source_url": "https://attacker.invalid"}):
            response = self.client.post("/api/runs", headers=ALPHA, json={**REQUEST, **extra})
            self.assertEqual(response.status_code, 422)

    def test_synthetic_declaration_is_required(self):
        for body in ({"request_text": "demo"}, {"request_text": "demo", "synthetic": False}):
            self.assertEqual(self.client.post("/api/runs", headers=ALPHA, json=body).status_code, 422)

    def test_request_and_total_body_limits_are_enforced(self):
        response = self.client.post("/api/runs", headers=ALPHA, json={**REQUEST, "request_text": "a" * 4001})
        self.assertEqual(response.status_code, 422)
        response = self.client.post("/api/runs", headers={**ALPHA, "Content-Type": "application/json"}, content="x" * 65537)
        self.assertEqual(response.status_code, 413)

    def test_end_to_end_exact_decision_and_cross_workspace_isolation(self):
        state = self.completed_run(); run_id = state["run_id"]
        self.assertEqual(state["status"], "waiting_approval")
        self.assertIn("ORCHID-ALPHA", json.dumps(state))
        self.assertNotIn("CEDAR-BETA", json.dumps(state))
        self.assertEqual(self.client.get(f"/api/runs/{run_id}", headers=BETA).status_code, 404)
        self.assertEqual(self.client.get(f"/api/runs/{run_id}/sources/BETA-POLICY", headers=ALPHA).status_code, 404)
        self.assertEqual(self.client.get(f"/api/runs/{run_id}/sources/ALPHA-POLICY", headers=ALPHA).status_code, 200)
        wrong = self.client.post(f"/api/runs/{run_id}/decision", headers=ALPHA,
                                 json={"artifact_hash": "0" * 64, "decision": "approve"})
        self.assertEqual(wrong.status_code, 409)
        accepted = self.client.post(f"/api/runs/{run_id}/decision", headers=ALPHA,
                                    json={"artifact_hash": state["artifact_hash"], "decision": "approve"})
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["status"], "approved")
        replay = self.client.post(f"/api/runs/{run_id}/decision", headers=ALPHA,
                                  json={"artifact_hash": state["artifact_hash"], "decision": "approve"})
        self.assertEqual(replay.status_code, 409)

    def test_rejection_does_not_publish(self):
        state = self.completed_run()
        result = self.client.post(f"/api/runs/{state['run_id']}/decision", headers=ALPHA,
                                 json={"artifact_hash": state["artifact_hash"], "decision": "reject"})
        self.assertEqual(result.json()["status"], "rejected")
        self.assertFalse(result.json().get("published", False))

    def test_cognito_exchange_is_disabled_offline(self):
        result = self.client.post("/auth/token", json={"code": "test-code", "code_verifier": "v" * 43})
        self.assertEqual(result.status_code, 404)


class FakeVerifier:
    def verify(self, token):
        if token != "verified-test-token":
            raise AuthError("Invalid synthetic test token.")
        return Principal("test-subject", ("demo-alpha",), "alpha", "internal")


class CloudBoundaryTests(unittest.TestCase):
    def test_health_survives_incomplete_bootstrap_but_api_and_login_fail_closed(self):
        # No service is injected or created: no lifespan and no cloud setup calls.
        client = TestClient(create_app(environ={}))
        self.assertEqual(client.get("/healthz").status_code, 200)
        self.assertEqual(client.get("/auth/config").status_code, 503)
        self.assertEqual(client.get("/api/me", headers=ALPHA).status_code, 503)

    def test_missing_redirect_uri_closes_auth_even_when_other_settings_exist(self):
        env = dict(CLOUD); del env["COGNITO_REDIRECT_URI"]
        client = TestClient(create_app(environ=env, verifier=FakeVerifier()))
        self.assertEqual(client.get("/healthz").status_code, 200)
        self.assertEqual(client.get("/api/me", headers={"Authorization": "Bearer verified-test-token"}).status_code, 503)

    def test_cloud_never_accepts_local_identity_header(self):
        client = TestClient(create_app(environ=CLOUD, verifier=FakeVerifier()))
        self.assertEqual(client.get("/api/me", headers=ALPHA).status_code, 401)
        response = client.get("/api/me", headers={"Authorization": "Bearer verified-test-token"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["simulated"])

    def test_code_exchange_uses_only_server_endpoint_and_callback_and_discards_other_tokens(self):
        requests = []
        def exchange(request):
            requests.append(request)
            return httpx.Response(200, json={"access_token": "verified-test-token", "id_token": "discarded-id",
                                             "refresh_token": "discarded-refresh", "expires_in": 3600})
        client = TestClient(create_app(environ=CLOUD, verifier=FakeVerifier(), token_transport=httpx.MockTransport(exchange)))
        response = client.post("/auth/token", json={"code": "test-code", "code_verifier": "v" * 43})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"access_token", "token_type"})
        self.assertEqual(str(requests[0].url), CLOUD["COGNITO_DOMAIN"] + "/oauth2/token")
        self.assertIn(b"code_verifier=", requests[0].content)
        self.assertIn(b"lab.example.org", requests[0].content)
        self.assertNotIn("set-cookie", response.headers)
        invalid = client.post("/auth/token", json={"code": "test-code", "code_verifier": "v" * 43,
                                                   "redirect_uri": "https://attacker.invalid"})
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(len(requests), 1)

    def test_remote_errors_do_not_echo_codes_tokens_or_provider_body(self):
        transport = httpx.MockTransport(lambda request: httpx.Response(400, text="PRIVATE_REMOTE_BODY"))
        client = TestClient(create_app(environ=CLOUD, verifier=FakeVerifier(), token_transport=transport))
        response = client.post("/auth/token", json={"code": "PRIVATE_CODE", "code_verifier": "v" * 43})
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("PRIVATE", response.text)
        invalid = client.post("/auth/token", json={"code": "PRIVATE_CODE", "code_verifier": "short"})
        self.assertEqual(invalid.status_code, 422)
        self.assertNotIn("PRIVATE_CODE", invalid.text)


if __name__ == "__main__":
    unittest.main()
