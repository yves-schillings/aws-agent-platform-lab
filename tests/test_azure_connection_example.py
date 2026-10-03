"""The connection example stays offline by default and never prints credentials."""

import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import unittest
from unittest.mock import patch

from aws_agent_platform_lab.providers import AzureOpenAIProvider


spec = importlib.util.spec_from_file_location(
    "azure_connection_example", Path(__file__).parents[1] / "scripts/check_azure_connection.py")
example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(example)


class Transport:
    def __init__(self, text):
        self.text = text
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        return io.BytesIO(json.dumps({
            "choices": [{"finish_reason": "stop", "message": {"content": self.text}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 8},
        }).encode())


class AzureConnectionExampleTests(unittest.TestCase):
    def run_example(self, args, text):
        transport = Transport(text)
        settings = {"AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
                    "AZURE_OPENAI_DEPLOYMENT": "synthetic-deployment",
                    "AZURE_OPENAI_API_KEY": "fake-test-secret"}
        stdout = io.StringIO()
        with patch.dict(example.os.environ, settings, clear=True), redirect_stdout(stdout):
            with patch.object(example, "AzureOpenAIProvider",
                              side_effect=lambda **kw: AzureOpenAIProvider(opener=transport, **kw)):
                status = example.main(args)
        self.assertNotIn("fake-test-secret", stdout.getvalue())
        return status, json.loads(stdout.getvalue()), transport

    def test_default_validates_without_inference(self):
        status, report, transport = self.run_example([], "unused")
        self.assertEqual(status, 0)
        self.assertFalse(report["network_call"])
        self.assertEqual(transport.requests, [])

    def test_explicit_call_sends_only_the_synthetic_contract(self):
        status, report, transport = self.run_example(["--call"], '{"status":"ok","citations":[]}')
        self.assertEqual(status, 0)
        self.assertTrue(report["connection_verified"])
        self.assertEqual(len(transport.requests), 1)
        body = json.loads(transport.requests[0].data)
        prompt = json.loads(body["messages"][1]["content"])
        self.assertTrue(prompt["scenario"]["synthetic"])
        self.assertEqual(prompt["documents"][0]["id"], "CONNECTIVITY-REF")
        self.assertEqual(len(prompt["documents"]), 1)
        self.assertEqual(body["model"], "synthetic-deployment")

    def test_malformed_model_output_is_not_printed_as_evidence(self):
        status, report, _ = self.run_example(["--call"], "remote-private-error-content")
        self.assertEqual(status, 1)
        self.assertFalse(report["connection_verified"])
        self.assertNotIn("remote-private-error-content", json.dumps(report))
