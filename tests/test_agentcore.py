"""Offline Runtime contract: real test signatures, mock inference, no AWS calls."""
import io
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from aws_agent_platform_lab.agentcore import create_runtime_app
from aws_agent_platform_lab.agentcore_client import AgentCoreFactoryClient
from aws_agent_platform_lab.auth import Principal
from aws_agent_platform_lab.factory import FactoryService
from aws_agent_platform_lab.providers import MockProvider
from aws_agent_platform_lab.services import ServiceError
from aws_agent_platform_lab.web import create_app
import test_auth


REQUEST = "Build the synthetic three-company affiliation consultation application."
RUNTIME_ENV = {"AGENTCORE_LOCAL_TEST": "true", "AGENTCORE_INBOUND_AUTH": "iam"}
CLIENT_ENV = {"AWS_REGION": "eu-west-1",
              "AGENTCORE_RUNTIME_ARN": "arn:aws:bedrock-agentcore:eu-west-1:123456789012:runtime/test_agent-123"}


class RuntimeFixture:
    """Share test keys without rerunning the separate authentication suite."""
    @classmethod
    def setUpClass(cls):
        test_auth.AuthTests.setUpClass.__func__(cls)

    claims = test_auth.AuthTests.claims
    token = test_auth.AuthTests.token

    def setUp(self):
        test_auth.AuthTests.setUp(self)
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.provider = MockProvider()
        self.factory = FactoryService(self.root, provider=self.provider, verified_identities=True)
        self.addCleanup(self.factory.close)
        self.client = self.enterContext(TestClient(create_runtime_app(
            environ=RUNTIME_ENV, verifier=self.verifier, factory_service=self.factory)))


class RuntimeTests(RuntimeFixture, unittest.TestCase):
    def test_oversized_chunked_body_is_rejected_without_echo(self):
        response = self.client.post('/invocations', content=iter([b'x' * 40000, b'y' * 40000]),
                                    headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json(), {'detail': 'Invocation is too large.'})
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def invoke(self, body, claims=None):
        return self.client.post("/invocations", json={"access_token": self.token(claims), **body})

    def start(self):
        result = self.invoke({"operation": "start", "request_text": REQUEST, "synthetic": True})
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()["result"]

    def test_real_signature_required_and_errors_do_not_echo_tokens(self):
        body = {"operation": "start", "request_text": REQUEST, "synthetic": True}
        self.assertEqual(self.client.post("/invocations", json=body).status_code, 401)
        invalid = self.token(key=self.other_key)
        response = self.client.post("/invocations", json={**body, "access_token": invalid})
        self.assertEqual(response.status_code, 401)
        self.assertNotIn(invalid, response.text)
        response = self.invoke({**body, "tenant": "beta", "principal": {"subject": "admin"}})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json(), {"detail": "Invalid invocation fields."})
        self.assertEqual(self.client.get("/ping").json(), {"status": "Healthy"})

    def test_four_gates_separate_approver_cross_company_and_resume(self):
        state = self.start()
        run_id = state["run_id"]
        beta = self.claims(sub="beta-user", **{"cognito:groups": ["demo-beta"]})
        denied = self.invoke({"operation": "read", "run_id": run_id}, beta).json()
        self.assertEqual(denied["error"]["status_code"], 404)
        # A different Runtime app/session reads the durable service state.
        restarted = FactoryService(self.root, provider=MockProvider(), verified_identities=True)
        self.addCleanup(restarted.close)
        with TestClient(create_runtime_app(environ=RUNTIME_ENV, verifier=self.verifier,
                                          factory_service=restarted)) as resumed:
            response = resumed.post("/invocations", json={"operation": "read", "run_id": run_id,
                                                          "access_token": self.token()})
            self.assertEqual(response.json()["result"]["pending_gate"]["gate"], "G1")
        for gate in ("G1", "G2", "G3", "G4"):
            decision = {"operation": "decide", "run_id": run_id, "gate": gate,
                        "artifact_hash": state["pending_gate"]["artifact_hash"],
                        "decision": "approve", "reason": "Review of exact synthetic proposal."}
            groups = ["demo-alpha", "factory-" + gate.lower() + "-approver"]
            owner_with_role = self.claims(**{"cognito:groups": groups})
            self.assertEqual(self.invoke(decision, owner_with_role).json()["error"]["status_code"], 403)
            approver = self.claims(sub="separate-approver", **{"cognito:groups": groups})
            state = self.invoke(decision, approver).json()["result"]
            self.assertEqual(self.invoke(decision, approver).json()["error"]["status_code"], 409)
        self.assertEqual(state["status"], "release_ready")
        self.assertEqual(len(state["artifacts"]), 5)
        self.assertFalse(state["identity_simulated"])
        self.assertEqual(self.client.get("/ping").json(), {"status": "Healthy"})

    def test_cognito_jwt_mode_requires_header_not_payload_identity(self):
        app = create_runtime_app(environ={**RUNTIME_ENV, "AGENTCORE_INBOUND_AUTH": "cognito-jwt"},
                                 verifier=self.verifier, factory_service=self.factory)
        body = {"operation": "start", "request_text": REQUEST, "synthetic": True}
        with TestClient(app) as client:
            self.assertEqual(client.post("/invocations", json={**body, "access_token": self.token()}).status_code, 401)
            response = client.post("/invocations", json=body,
                                   headers={"Authorization": "Bearer " + self.token()})
            self.assertEqual(response.status_code, 200, response.text)

    def test_production_rejects_ephemeral_persistence_and_unsupported_entra(self):
        for env in ({}, {"AGENTCORE_INBOUND_AUTH": "entra"},
                    {**RUNTIME_ENV, "LOCAL_DEMO_MODE": "true"}):
            with self.subTest(env=env), self.assertRaises(ValueError):
                create_runtime_app(environ=env, verifier=self.verifier, factory_service=self.factory)


class OfflineTransport:
    def __init__(self, http):
        self.http, self.calls, self.streams = http, [], []
    def invoke_agent_runtime(self, **kwargs):
        self.calls.append(kwargs)
        response = self.http.post("/invocations", json=json.loads(kwargs["payload"]))
        stream = io.BytesIO(response.content)
        self.streams.append(stream)
        return {"response": stream, "contentType": "application/json", "statusCode": response.status_code}
    def close(self):
        pass


class ConnectorTests(RuntimeFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.transport = OfflineTransport(self.client)
        self.connector = AgentCoreFactoryClient(CLIENT_ENV, client=self.transport)

    def test_browser_to_connector_to_runtime_without_network(self):
        env = {**self._auth_env(), "FACTORY_ENABLED": "true", "FACTORY_BACKEND": "agentcore"}
        with TestClient(create_app(environ=env, verifier=self.verifier,
                                  factory_service=self.connector)) as web:
            token = self.token()
            headers = {"Authorization": "Bearer " + token}
            reply = web.post("/api/factory/runs", headers=headers,
                             json={"request_text": REQUEST, "synthetic": True})
            self.assertEqual(reply.status_code, 201, reply.text)
            state = reply.json()
            self.assertEqual(state["pending_gate"]["gate"], "G1")
            beta = self.token(self.claims(sub="beta-user", **{"cognito:groups": ["demo-beta"]}))
            self.assertEqual(web.get("/api/factory/runs/" + state["run_id"],
                                     headers={"Authorization": "Bearer " + beta}).status_code, 404)
            body = json.loads(self.transport.calls[0]["payload"])
            self.assertEqual(body["access_token"], token)
            self.assertNotIn("principal", body)
            self.assertNotIn("tenant", body)
            self.assertGreaterEqual(len(self.transport.calls[0]["runtimeSessionId"]), 33)
            self.assertTrue(all(stream.closed for stream in self.transport.streams))

    def _auth_env(self):
        from test_auth import AUTH_ENV
        return AUTH_ENV

    def test_no_cloud_client_constructed_for_bad_configuration(self):
        with self.assertRaises(ValueError):
            AgentCoreFactoryClient({**CLIENT_ENV, "AWS_REGION": "eu-central-1"})
        with self.assertRaises(ServiceError):
            self.connector.invoke("start_run", Principal("localalpha", (), "alpha", "internal", True),
                                  self.token(), REQUEST)
        self.assertFalse(self.transport.calls)


if __name__ == "__main__":
    unittest.main()
