"""The cloud entry and shared login callback must keep users in the five-role Factory."""
import json
import unittest

from fastapi.testclient import TestClient

from aws_agent_platform_lab.web import create_app


AWS = {
    "AWS_REGION": "eu-west-1", "COGNITO_USER_POOL_ID": "eu-west-1_testPool",
    "COGNITO_CLIENT_ID": "testclient123",
    "COGNITO_ISSUER": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_testPool",
    "COGNITO_DOMAIN": "https://synthetic.auth.eu-west-1.amazoncognito.com",
    "COGNITO_REDIRECT_URI": "https://lab.example.org/auth/callback",
    "ACCESS_POLICY_JSON": json.dumps({"demo-alpha": {"tenant": "alpha", "access_level": "internal"}}),
}


class FactoryNavigationTests(unittest.TestCase):
    def test_cloud_entry_opens_all_five_roles_and_callback_dispatches_to_initiator(self):
        client = TestClient(create_app(environ={**AWS, "FACTORY_ENABLED": "true"}))
        self.addCleanup(client.close)
        entry = client.get("/", follow_redirects=False)
        self.assertEqual(entry.status_code, 307)
        self.assertEqual(entry.headers["location"], "/factory")
        page = client.get("/")
        self.assertEqual(page.url.path, "/factory")
        for role in ("Analyst", "Architect", "Code Author", "Tester", "Reviewer"):
            self.assertIn(role, page.text)
        self.assertNotIn("Three roles. One visible trail.", page.text)
        callback = client.get("/auth/callback?code=synthetic-code&state=synthetic-state")
        self.assertIn('/static/auth-callback.js', callback.text)
        self.assertNotIn("synthetic-code", callback.text)
        self.assertIn("frame-ancestors 'none'", callback.headers["content-security-policy"])
        self.assertEqual(client.get("/static/auth-callback.js").status_code, 200)
        self.assertIn("Three roles. One visible trail.", client.get("/demo").text)

    def test_factory_disabled_preserves_baseline_login(self):
        client = TestClient(create_app(environ=AWS))
        self.addCleanup(client.close)
        self.assertIn("Three roles. One visible trail.", client.get("/").text)
        self.assertIn('/static/app.js', client.get("/auth/callback").text)
        self.assertEqual(client.get("/factory").status_code, 404)
