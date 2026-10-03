"""Model-backed Factory: validated answers, permitted sources, failures and gates."""
import json
import tempfile
import unittest
from pathlib import Path

from aws_agent_platform_lab.auth import Principal
from aws_agent_platform_lab.factory import (FIXTURES, GATES, MODEL_LIMITATIONS, DynamoRunRegistry,
                                            FactoryService, service_from_environment,
                                            validate_model_output)
from aws_agent_platform_lab.models import ValidationError
from aws_agent_platform_lab.providers import MockProvider
from aws_agent_platform_lab.services import ServiceError

REQUEST = "Prepare the shared read-only synthetic affiliation consultation application."


def principal(tenant="alpha"):
    return Principal("local" + tenant, ("demo-" + tenant,), tenant, "internal", True)


class RecordingProvider(MockProvider):
    """Mock model that records each role prompt it receives."""
    def __init__(self):
        super().__init__()
        self.prompts = []

    def generate(self, role, prompt):
        self.prompts.append((role, json.loads(prompt)))
        return super().generate(role, prompt)


class ScriptedProvider:
    """Return a fixed answer, or raise, for one role; delegate the others to the mock."""
    name = "scripted"

    def __init__(self, role, answer=None, error=None):
        self.role, self.answer, self.error = role, answer, error
        self.mock = MockProvider()
        self.last_usage = {}

    def generate(self, role, prompt):
        if role == self.role:
            if self.error:
                raise self.error
            return self.answer
        return self.mock.generate(role, prompt)


class ModelBackedFactoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def service(self, provider):
        service = FactoryService(self.root / "factory", provider=provider)
        self.addCleanup(service.close)
        return service

    def decide(self, service, state, user=None):
        pending = state["pending_gate"]
        return service.decide_run(user or principal(), state["run_id"], pending["gate"],
                                  pending["artifact_hash"], "approve", "Reviewed the model proposal.")

    def test_five_roles_call_the_model_and_cite_only_permitted_sources(self):
        provider = RecordingProvider()
        service = self.service(provider)
        state = service.start_run(principal(), REQUEST)
        self.assertTrue(state["model_backed"])
        self.assertFalse(state["simulated"])
        self.assertTrue(state["identity_simulated"])
        self.assertEqual(state["provider"], "mock")
        self.assertEqual(state["limitations"], MODEL_LIMITATIONS)
        source_ids = {s["id"] for s in state["sources"]}
        self.assertTrue(source_ids)
        self.assertTrue(all(i.startswith("ALPHA-") for i in source_ids))
        for gate in GATES:
            self.assertEqual(state["pending_gate"]["gate"], gate)
            self.assertFalse(state["pending_gate"]["artifact"]["simulated"])
            state = self.decide(service, state)
        self.assertEqual(state["status"], "release_ready")
        self.assertEqual([r for r, _ in provider.prompts],
                         ["analyst", "architect", "code_author", "tester", "reviewer"])
        for role, artifact in state["artifacts"].items():
            self.assertTrue(artifact["model_backed"], role)
            self.assertFalse(artifact["executed"], role)
            self.assertTrue(set(artifact["citations"]) <= source_ids, role)
        reviewer_prompt = provider.prompts[-1][1]
        self.assertIn("candidate", reviewer_prompt)
        self.assertTrue(reviewer_prompt["candidate"]["files"])
        self.assertIn("untrusted data", reviewer_prompt["instructions"])

    def test_live_model_contract_uses_explicit_types_and_permitted_citations(self):
        from jsonschema import Draft202012Validator
        provider = RecordingProvider()
        service = self.service(provider)
        state = service.start_run(principal(), REQUEST)
        for gate in GATES:
            state = self.decide(service, state)
        for role, prompt in provider.prompts:
            schema = prompt["response_schema"]
            Draft202012Validator.check_schema(schema)
            output = {k: v for k, v in state["artifacts"][role].items()
                      if k in schema["properties"]}
            Draft202012Validator(schema).validate(output)
            output["citations"] = ["OUTSIDE-THE-PERMITTED-SOURCES"]
            self.assertFalse(Draft202012Validator(schema).is_valid(output))
        analyst = provider.prompts[0][1]["response_schema"]
        malformed = {"summary": "S", "requirements": "Prose instead of an array",
                     "citations": provider.prompts[0][1]["documents"][:1]}
        malformed["citations"] = [malformed["citations"][0]["id"]]
        self.assertFalse(Draft202012Validator(analyst).is_valid(malformed))

    def test_each_company_sees_only_its_own_documents(self):
        provider = RecordingProvider()
        service = self.service(provider)
        state = service.start_run(principal("beta"), REQUEST)
        self.assertTrue(state["sources"])
        self.assertTrue(all(s["id"].startswith("BETA-") for s in state["sources"]))
        documents = provider.prompts[0][1]["documents"]
        self.assertTrue(all(d["id"].startswith("BETA-") for d in documents))

    def test_company_without_permitted_documents_is_refused_before_any_model_call(self):
        provider = RecordingProvider()
        service = self.service(provider)
        with self.assertRaises(ServiceError) as error:
            service.start_run(principal("gamma"), REQUEST)
        self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(provider.prompts, [])

    def test_invalid_json_ends_the_run_without_reaching_a_gate(self):
        service = self.service(ScriptedProvider("analyst", answer="not json"))
        state = service.start_run(principal(), REQUEST)
        self.assertEqual(state["status"], "failed")
        self.assertIsNone(state["pending_gate"])
        self.assertEqual(state["artifacts"]["analyst"]["error_type"], "ValidationError")

    def test_citation_outside_the_supplied_documents_is_rejected(self):
        answer = json.dumps({"summary": "S", "requirements": ["R"], "citations": ["BETA-POLICY"]})
        service = self.service(ScriptedProvider("analyst", answer=answer))
        state = service.start_run(principal(), REQUEST)
        self.assertEqual(state["status"], "failed")
        self.assertIsNone(state["pending_gate"])

    def test_provider_error_records_only_its_type(self):
        error = RuntimeError("https://secret-endpoint.example/with?token=abc")
        service = self.service(ScriptedProvider("architect", error=error))
        state = service.start_run(principal(), REQUEST)
        state = self.decide(service, state)
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["artifacts"]["architect"]["error_type"], "RuntimeError")
        self.assertNotIn("secret-endpoint", json.dumps(state))

    def test_proposed_paths_must_stay_inside_the_candidate(self):
        for path in ("../outside.py", "/etc/passwd", "app/../../x.py", "C:/Windows/x.py"):
            data = {"files": [{"path": path, "purpose": "p", "content": "c"}],
                    "notes": [], "citations": ["ALPHA-POLICY"]}
            with self.assertRaises(ValidationError, msg=path):
                validate_model_output("code_author", data, {"ALPHA-POLICY"})

    def test_an_approval_cannot_hide_unresolved_issues(self):
        data = {"approved": True, "issues": ["Missing authorization test."], "citations": ["ALPHA-OPS"]}
        with self.assertRaises(ValidationError):
            validate_model_output("reviewer", data, {"ALPHA-OPS"})

    def test_environment_selects_fixtures_by_default_and_mock_on_request(self):
        fixtures = service_from_environment(self.root / "a", {})
        self.addCleanup(fixtures.close)
        self.assertEqual(fixtures._provider_name, FIXTURES)
        mock = service_from_environment(self.root / "b", {"FACTORY_PROVIDER": "mock"})
        self.addCleanup(mock.close)
        self.assertEqual(mock._provider_name, "mock")
        with self.assertRaises(Exception):
            service_from_environment(self.root / "c", {"FACTORY_PROVIDER": "unknown"})


CLOUD = {
    "AWS_REGION": "eu-west-1", "COGNITO_USER_POOL_ID": "eu-west-1_testPool",
    "COGNITO_CLIENT_ID": "testclient123",
    "COGNITO_ISSUER": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_testPool",
    "COGNITO_DOMAIN": "https://synthetic.auth.eu-west-1.amazoncognito.com",
    "COGNITO_REDIRECT_URI": "https://lab.example.org/auth/callback",
    "ACCESS_POLICY_JSON": json.dumps({"demo-alpha": {"tenant": "alpha", "access_level": "internal"},
                                      "factory-g1-approver": {"tenant": "alpha", "access_level": "internal"},
                                      "factory-g2-approver": {"tenant": "alpha", "access_level": "internal"},
                                      "factory-g3-approver": {"tenant": "alpha", "access_level": "internal"},
                                      "factory-g4-approver": {"tenant": "alpha", "access_level": "internal"},
                                      "demo-beta": {"tenant": "beta", "access_level": "internal"}}),
}
TOKENS = {
    "alpha-token": ("user-alpha", ("demo-alpha",), "alpha"),
    "approver-token": ("user-approver", ("demo-alpha", "factory-g1-approver", "factory-g2-approver",
                                             "factory-g3-approver", "factory-g4-approver"), "alpha"),
    "beta-token": ("user-beta", ("demo-beta",), "beta"),
}


class FakeVerifier:
    """Stand-in for Cognito: maps fixed test tokens to verified, non-simulated principals."""
    def verify(self, token):
        from aws_agent_platform_lab.auth import AuthError
        if token not in TOKENS:
            raise AuthError("Invalid synthetic test token.")
        subject, groups, tenant = TOKENS[token]
        return Principal(subject, groups, tenant, "internal")


class CognitoFactoryWebTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from aws_agent_platform_lab.web import create_app
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.factory = FactoryService(self.root / "factory", provider=MockProvider(),
                                      verified_identities=True)
        self.addCleanup(self.factory.close)
        self.make = lambda env: self.enterContext(TestClient(create_app(
            environ=env, verifier=FakeVerifier(), factory_service=self.factory)))
        self.client = self.make({**CLOUD, "FACTORY_ENABLED": "true"})

    @staticmethod
    def bearer(token):
        return {"Authorization": "Bearer " + token}

    def test_verified_user_runs_the_model_backed_factory_through_all_gates(self):
        result = self.client.post("/api/factory/runs", headers=self.bearer("alpha-token"),
                                  json={"request_text": REQUEST, "synthetic": True})
        self.assertEqual(result.status_code, 201, result.text)
        state = result.json()
        self.assertFalse(state["identity_simulated"])
        self.assertTrue(state["model_backed"])
        self.assertTrue(any("separate Cognito-authenticated approver" in item for item in state["limitations"]))
        url = f"/api/factory/runs/{state['run_id']}/decision"
        for gate in GATES:
            review = self.client.get(url.removesuffix("/decision"), headers=self.bearer("approver-token"))
            self.assertEqual(review.status_code, 200, review.text)
            pending = review.json()["pending_gate"]
            self.assertEqual(pending["gate"], gate)
            self.assertEqual(pending["artifact"], state["pending_gate"]["artifact"])
            result = self.client.post(url, headers=self.bearer("approver-token"), json={
                "gate": gate, "artifact_hash": pending["artifact_hash"],
                "decision": "approve", "reason": "Reviewed by the authorised approver."})
            self.assertEqual(result.status_code, 200, result.text)
            state = result.json()
        self.assertEqual(state["status"], "release_ready")
        self.assertTrue(all(d["identity_verified"] and not d["simulated"] for d in state["decisions"]))
        gate_events = [event for event in state["events"] if event["kind"] == "gate_decided"]
        self.assertEqual([event["gate"] for event in gate_events], list(GATES))
        self.assertTrue(all(not event["simulated"] for event in gate_events))
        self.assertEqual(self.client.get(url.removesuffix("/decision"), headers=self.bearer("alpha-token")).json()["status"], "release_ready")

    def test_review_read_requires_the_pending_gate_and_exact_source_scope(self):
        from unittest.mock import patch
        state = self.client.post("/api/factory/runs", headers=self.bearer("alpha-token"),
                                 json={"request_text": REQUEST, "synthetic": True}).json()
        run = f"/api/factory/runs/{state['run_id']}"
        for principal in [
            Principal("another-requester", ("demo-alpha",), "alpha", "internal"),
            Principal("later-approver", ("factory-g2-approver",), "alpha", "internal"),
            Principal("other-company", ("factory-g1-approver",), "beta", "internal"),
            Principal("other-scope", ("factory-g1-approver",), "alpha", "restricted"),
        ]:
            with self.subTest(principal=principal.subject), patch.object(FakeVerifier, "verify", return_value=principal):
                self.assertEqual(self.client.get(run, headers=self.bearer("approver-token")).status_code, 404)

    def test_missing_or_invalid_token_is_refused(self):
        body = {"request_text": REQUEST, "synthetic": True}
        self.assertEqual(self.client.post("/api/factory/runs", json=body).status_code, 401)
        self.assertEqual(self.client.post("/api/factory/runs", headers=self.bearer("forged"),
                                          json=body).status_code, 401)
        self.assertEqual(self.client.post("/api/factory/runs", headers={"X-Demo-User": "localalpha"},
                                          json=body).status_code, 401)

    def test_another_verified_user_cannot_read_or_decide_the_run(self):
        state = self.client.post("/api/factory/runs", headers=self.bearer("alpha-token"),
                                 json={"request_text": REQUEST, "synthetic": True}).json()
        run = f"/api/factory/runs/{state['run_id']}"
        self.assertEqual(self.client.get(run, headers=self.bearer("beta-token")).status_code, 404)
        pending = state["pending_gate"]
        decision = self.client.post(run + "/decision", headers=self.bearer("beta-token"), json={
            "gate": pending["gate"], "artifact_hash": pending["artifact_hash"],
            "decision": "approve", "reason": "Attempted by another company."})
        self.assertEqual(decision.status_code, 404)

    def test_run_owner_and_wrong_gate_approver_cannot_approve(self):
        state = self.client.post("/api/factory/runs", headers=self.bearer("alpha-token"),
                                 json={"request_text": REQUEST, "synthetic": True}).json()
        url = f"/api/factory/runs/{state['run_id']}/decision"
        body = {"gate": "G1", "artifact_hash": state["pending_gate"]["artifact_hash"],
                "decision": "approve", "reason": "Attempted self approval."}
        self.assertEqual(self.client.post(url, headers=self.bearer("alpha-token"), json=body).status_code, 403)
        wrong = dict(TOKENS)
        wrong["wrong-gate-token"] = ("user-wrong", ("demo-alpha", "factory-g2-approver"), "alpha")
        original = TOKENS.copy()
        try:
            TOKENS.clear(); TOKENS.update(wrong)
            self.assertEqual(self.client.post(url, headers=self.bearer("wrong-gate-token"), json=body).status_code, 403)
        finally:
            TOKENS.clear(); TOKENS.update(original)

    def test_local_factory_refuses_a_verified_looking_principal(self):
        local = FactoryService(self.root / "local", provider=MockProvider())
        self.addCleanup(local.close)
        with self.assertRaises(ServiceError) as error:
            local.start_run(Principal("user-alpha", ("demo-alpha",), "alpha", "internal"), REQUEST)
        self.assertEqual(error.exception.status_code, 403)

    def test_factory_routes_do_not_exist_in_aws_mode_unless_enabled(self):
        client = self.make(dict(CLOUD))
        result = client.post("/api/factory/runs", headers=self.bearer("alpha-token"),
                             json={"request_text": REQUEST, "synthetic": True})
        self.assertEqual(result.status_code, 404)

    def test_factory_browser_is_available_when_the_aws_factory_is_enabled(self):
        page = self.client.get("/factory")
        config = self.client.get("/api/factory/config")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Factory browser client", page.text)
        self.assertEqual(config.status_code, 200)
        self.assertEqual(config.json(), {"simulated": False, "mode": "aws",
                                         "engine": "langgraph", "identities": []})


class FactoryDynamoRegistryTests(unittest.TestCase):
    """Shared-registry unit checks without an AWS account or DynamoDB endpoint."""

    class Client:
        def __init__(self):
            self.items = {}

        def put_item(self, *, TableName, Item, ConditionExpression):
            key = Item["run_id"]["S"]
            if key in self.items:
                raise RuntimeError("already exists")
            self.items[key] = Item

        def get_item(self, *, TableName, Key, ConsistentRead):
            item = self.items.get(Key["run_id"]["S"])
            return {} if item is None else {"Item": item}

        def update_item(self, *, TableName, Key, UpdateExpression, ConditionExpression,
                        ExpressionAttributeValues):
            key = Key["run_id"]["S"]
            self.items[key] = {"run_id": {"S": key},
                               "lease_owner": ExpressionAttributeValues[":owner"],
                               "lease_expires": ExpressionAttributeValues[":expires"]}

        def delete_item(self, *, TableName, Key, ConditionExpression, ExpressionAttributeValues):
            key = Key["run_id"]["S"]
            item = self.items.get(key)
            if item is None or item["lease_owner"] != ExpressionAttributeValues[":owner"]:
                raise RuntimeError("not lock owner")
            del self.items[key]

    def test_shared_registry_preserves_scope_and_releases_a_per_run_lease(self):
        client = self.Client()
        registry = DynamoRunRegistry("factory-runs", client=client)
        run_id = "a" * 32
        identity = {"owner": "owner", "tenant": "alpha", "access_level": "internal",
                    "company_id": "company-1", "project_id": "affiliation-demo"}
        registry.create(run_id, identity)
        self.assertEqual(registry.get(run_id), {"run_id": run_id, **identity})
        with registry.locked(run_id):
            self.assertIn(run_id + "#lock", client.items)
        self.assertNotIn(run_id + "#lock", client.items)


if __name__ == "__main__":
    unittest.main()
