"""Adapter contract tests. All network transports are replaced with local fakes."""

import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from aws_agent_platform_lab.providers import (
    AwsBedrockProvider, AzureOpenAIProvider, LangChainBedrockProvider, MockProvider,
    ProviderError, ProviderConfigurationError, _NoRedirects, create_provider,
)


def prompt(role="analyst", **changes):
    data = {
        "role": role, "instructions": "Return the specified JSON object.",
        "scenario": {"id": "demo", "title": "Synthetic change", "request": "Draft a controlled workflow.", "synthetic": True},
        "documents": [{"id": "policy-1", "title": "Demo policy", "text": "A human reviews every output."}],
        "analysis": None, "draft": None, "previous_review": None, "revision": 1,
    }
    data.update(changes)
    return json.dumps(data)


class FakeResponse:
    def __init__(self, payload):
        self.raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, maximum):
        return self.raw[:maximum]


class FakeOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
    def open(self, request, timeout):
        self.calls.append((request, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return FakeResponse(response)


AZURE_ENV = {
    "AZURE_OPENAI_ENDPOINT": "https://example-resource.openai.azure.com",
    "AZURE_OPENAI_DEPLOYMENT": "my-deployment",
    "AZURE_OPENAI_API_KEY": "fake-unit-test-key-not-a-real-secret",
}
AWS_ENV = {"AWS_REGION": "eu-west-1", "BEDROCK_MODEL_ID": "test-model-id"}


def azure_response(text='{"approved": true, "issues": [], "citations": ["policy-1"]}', finish="stop"):
    return {"choices": [{"finish_reason": finish, "message": {"content": text}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20}}


class ProviderTests(unittest.TestCase):
    def test_mock_pipeline_is_deterministic_and_cites_available_sources(self):
        provider = MockProvider()
        analysis = json.loads(provider.generate("analyst", prompt()))
        draft_input = prompt("designer", analysis=analysis)
        draft_text = provider.generate("designer", draft_input)
        self.assertEqual(draft_text, provider.generate("designer", draft_input))
        draft = json.loads(draft_text)
        review = json.loads(provider.generate("reviewer", prompt("reviewer", draft=draft)))
        self.assertTrue(review["approved"])
        self.assertEqual(review["citations"], ["policy-1"])
        self.assertTrue(provider.last_usage["simulated"])
        self.assertEqual(provider.last_usage["estimated_cost_usd"], 0)

    def test_mock_reviewer_rejects_missing_approval_and_unknown_citation(self):
        draft = {"steps": [{"actor": "designer", "source_ids": ["invented"]}], "controls": []}
        result = json.loads(MockProvider().generate("reviewer", prompt("reviewer", draft=draft)))
        self.assertFalse(result["approved"])
        self.assertEqual(len(result["issues"]), 2)

    def test_non_synthetic_and_unknown_roles_are_rejected_before_network(self):
        transport = FakeOpener([])
        provider = AzureOpenAIProvider(environ=AZURE_ENV, opener=transport)
        with self.assertRaises(ProviderError):
            provider.generate("analyst", prompt(scenario={"synthetic": False}))
        with self.assertRaises(ProviderError):
            provider.generate("administrator", prompt())
        self.assertEqual(transport.calls, [])

    def test_unknown_provider_is_clear_error(self):
        with self.assertRaises(ProviderConfigurationError):
            create_provider("unavailable")

    def test_aws_converse_request_response_and_token_usage(self):
        class Client:
            def converse(self, **kwargs):
                self.request = kwargs
                return {"output": {"message": {"content": [{"text": '{"summary":"ok"}'}]}},
                        "stopReason": "end_turn", "usage": {"inputTokens": 17, "outputTokens": 8}}
        client = Client()
        provider = AwsBedrockProvider(environ=AWS_ENV, client=client)
        self.assertEqual(provider.generate("analyst", prompt()), '{"summary":"ok"}')
        self.assertEqual(client.request["modelId"], "test-model-id")
        self.assertEqual(client.request["messages"][0]["role"], "user")
        self.assertEqual(client.request["inferenceConfig"]["maxTokens"], 2048)
        self.assertEqual(provider.last_usage["input_tokens"], 17)
        self.assertIsNone(provider.last_usage["estimated_cost_usd"])

    def test_langchain_bedrock_request_response_and_token_usage(self):
        class Response:
            content = '{"summary":"ok"}'
            usage_metadata = {"input_tokens": 17, "output_tokens": 8}
        class Model:
            def invoke(self, messages):
                self.messages = messages
                return Response()
        model = Model()
        provider = LangChainBedrockProvider(environ=AWS_ENV, model=model)
        self.assertEqual(provider.generate("analyst", prompt()), '{"summary":"ok"}')
        self.assertEqual(model.messages[0].type, "system")
        self.assertEqual(model.messages[1].type, "human")
        self.assertEqual(provider.last_usage["input_tokens"], 17)
        with patch.dict("os.environ", AWS_ENV):
            self.assertEqual(create_provider("aws_langchain").name, "aws-langchain")

    def test_langchain_bedrock_failure_does_not_reveal_remote_body(self):
        class Model:
            def invoke(self, messages):
                raise RuntimeError("secret-value-from-remote-body")
        provider = LangChainBedrockProvider(environ=AWS_ENV, model=Model())
        with self.assertRaises(ProviderError) as caught:
            provider.generate("analyst", prompt())
        self.assertNotIn("secret-value", str(caught.exception))
    def test_aws_failure_does_not_reveal_credentials_or_remote_body(self):
        class Client:
            def converse(self, **kwargs):
                raise RuntimeError("secret-value-from-remote-body")
        provider = AwsBedrockProvider(environ=AWS_ENV, client=Client())
        with self.assertRaises(ProviderError) as caught:
            provider.generate("analyst", prompt())
        self.assertNotIn("secret-value", str(caught.exception))
        self.assertEqual(provider.last_usage, {})

    def test_aws_truncated_output_is_rejected(self):
        class Client:
            def converse(self, **kwargs):
                return {"stopReason": "max_tokens", "output": {"message": {"content": [{"text": "{"}]}}}
        with self.assertRaisesRegex(ProviderError, "complete"):
            AwsBedrockProvider(environ=AWS_ENV, client=Client()).generate("analyst", prompt())

    def test_aws_missing_configuration_fails_without_importing_sdk(self):
        with self.assertRaises(ProviderConfigurationError):
            AwsBedrockProvider(environ={})

    def test_azure_v1_uses_deployment_in_body_and_key_header(self):
        transport = FakeOpener([azure_response()])
        provider = AzureOpenAIProvider(environ=AZURE_ENV, opener=transport)
        provider.generate("analyst", prompt())
        request, timeout = transport.calls[0]
        self.assertEqual(request.full_url, "https://example-resource.openai.azure.com/openai/v1/chat/completions")
        self.assertEqual(json.loads(request.data)["model"], "my-deployment")
        self.assertEqual(request.get_header("Api-key"), AZURE_ENV["AZURE_OPENAI_API_KEY"])
        self.assertEqual(timeout, 45)
        self.assertEqual(provider.last_usage["output_tokens"], 20)

    def test_azure_legacy_endpoint_and_entra_header(self):
        env = dict(AZURE_ENV)
        del env["AZURE_OPENAI_API_KEY"]
        env.update(AZURE_OPENAI_API_VERSION="2024-10-21", AZURE_OPENAI_AD_TOKEN="fake-test-token")
        transport = FakeOpener([azure_response()])
        AzureOpenAIProvider(environ=env, opener=transport).generate("analyst", prompt())
        request, _ = transport.calls[0]
        self.assertTrue(request.full_url.endswith("/openai/deployments/my-deployment/chat/completions?api-version=2024-10-21"))
        self.assertEqual(request.get_header("Authorization"), "Bearer fake-test-token")
        self.assertNotIn("model", json.loads(request.data))

    def test_azure_retries_throttling_with_bounded_attempts(self):
        error = HTTPError("https://unused", 429, "private-remote-body", {}, io.BytesIO())
        transport = FakeOpener([error, azure_response()])
        with patch("aws_agent_platform_lab.providers.time.sleep") as sleep:
            AzureOpenAIProvider(environ=AZURE_ENV, opener=transport).generate("analyst", prompt())
        self.assertEqual(len(transport.calls), 2)
        sleep.assert_called_once_with(1)

    def test_azure_does_not_retry_unauthorized_or_leak_body(self):
        error = HTTPError("https://unused", 401, "private-remote-body", {}, io.BytesIO())
        transport = FakeOpener([error])
        with self.assertRaises(ProviderError) as caught:
            AzureOpenAIProvider(environ=AZURE_ENV, opener=transport).generate("analyst", prompt())
        self.assertEqual(len(transport.calls), 1)
        self.assertIn("401", str(caught.exception))
        self.assertNotIn("private-remote-body", str(caught.exception))

    def test_azure_connection_timeout_is_not_replayed(self):
        transport = FakeOpener([URLError("secret-and-timeout")])
        with self.assertRaises(ProviderError):
            AzureOpenAIProvider(environ=AZURE_ENV, opener=transport).generate("analyst", prompt())
        self.assertEqual(len(transport.calls), 1)

    def test_azure_response_shape_and_truncation_are_rejected(self):
        for response in (b"not json", {}, azure_response(finish="length")):
            with self.subTest(response=response), self.assertRaises(ProviderError):
                AzureOpenAIProvider(environ=AZURE_ENV, opener=FakeOpener([response])).generate("analyst", prompt())

    def test_azure_rejects_untrusted_endpoints(self):
        for endpoint in ("http://example.openai.azure.com", "https://evil.example",
                         "https://example.openai.azure.com.evil.example",
                         "https://user:password@example.openai.azure.com",
                         "https://example.openai.azure.com?key=secret",
                         "https://example.openai.azure.com:8443", "https://[invalid"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ProviderConfigurationError):
                AzureOpenAIProvider(environ={**AZURE_ENV, "AZURE_OPENAI_ENDPOINT": endpoint})

    def test_azure_refuses_redirects(self):
        self.assertIsNone(_NoRedirects().redirect_request(None, None, 302, "", {}, "https://evil.example"))

    def test_azure_rejects_ambiguous_auth_and_unbounded_attempts(self):
        for changes in ({"AZURE_OPENAI_AD_TOKEN": "second-credential"}, {"POC_MAX_ATTEMPTS": "999"},
                        {"POC_TIMEOUT_SECONDS": "999"}, {"POC_MAX_OUTPUT_TOKENS": "999999"}):
            with self.subTest(changes=changes), self.assertRaises(ProviderConfigurationError):
                AzureOpenAIProvider(environ={**AZURE_ENV, **changes})


if __name__ == "__main__":
    unittest.main()
