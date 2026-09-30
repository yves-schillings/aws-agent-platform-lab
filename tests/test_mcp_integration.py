"""Real stdio MCP protocol, entirely local with deterministic synthetic data."""
import importlib.util
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from aws_agent_platform_lab.mcp_tool import call_checklist


@unittest.skipUnless(importlib.util.find_spec("mcp"), "Install the web extra for the MCP protocol test")
class McpIntegrationTests(unittest.TestCase):
    def test_protocol_round_trip_is_scoped_and_read_only(self):
        user = SimpleNamespace(tenant="alpha", access_level="internal")
        result = call_checklist(user)
        self.assertEqual(result["transport"], "stdio")
        self.assertEqual(result["result"]["tenant"], "alpha")
        self.assertEqual(result["result"]["missing"], ["review_record"])

    def test_server_rejects_wrong_scope_and_unknown_document_types(self):
        from aws_agent_platform_lab.mcp_server import check_required_documents
        with patch.dict(os.environ, {"LAB_TOOL_TENANT": "alpha"}):
            with self.assertRaises(ValueError):
                check_required_documents("beta", ["request_form"])
            with self.assertRaises(ValueError):
                check_required_documents("alpha", ["https://untrusted.invalid"])
