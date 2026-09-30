"""Authentication checks use freshly generated test keys; no identity network call."""
import json
import time
from types import SimpleNamespace
import unittest

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from aws_agent_platform_lab.auth import AuthError, CognitoSettings, CognitoVerifier, local_demo_mode


AUTH_ENV = {
    "AWS_REGION": "eu-west-1", "COGNITO_USER_POOL_ID": "eu-west-1_testPool",
    "COGNITO_CLIENT_ID": "testclient123",
    "COGNITO_ISSUER": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_testPool",
    "COGNITO_DOMAIN": "https://synthetic.auth.eu-west-1.amazoncognito.com",
    "COGNITO_REDIRECT_URI": "https://lab.example.org/auth/callback",
    "ACCESS_POLICY_JSON": json.dumps({
        "demo-alpha": {"tenant": "alpha", "access_level": "internal"},
        "demo-beta": {"tenant": "beta", "access_level": "internal"}}),
}


class StaticKeys:
    def __init__(self, key):
        self.key = key
        self.calls = 0
    def get_signing_key_from_jwt(self, token):
        self.calls += 1
        if jwt.get_unverified_header(token).get("kid") != "test-key":
            raise jwt.PyJWKClientError("Unknown key")
        return SimpleNamespace(key=self.key)


class AuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self.settings = CognitoSettings.from_env(AUTH_ENV)
        self.keys = StaticKeys(self.private_key.public_key())
        self.verifier = CognitoVerifier(self.settings, jwks_client=self.keys)

    def claims(self, **changes):
        values = {"iss": self.settings.issuer, "sub": "synthetic-subject", "iat": int(time.time()) - 5,
                  "exp": int(time.time()) + 600, "token_use": "access", "client_id": self.settings.client_id,
                  "scope": "openid profile", "cognito:groups": ["demo-alpha"]}
        values.update(changes)
        return values

    def token(self, claims=None, key=None, kid="test-key"):
        return jwt.encode(claims or self.claims(), key or self.private_key,
                          algorithm="RS256", headers={"kid": kid})

    def test_valid_token_derives_scope_only_from_server_policy(self):
        principal = self.verifier.verify(self.token(self.claims(tenant="beta", access_level="admin")))
        self.assertEqual((principal.subject, principal.tenant, principal.access_level),
                         ("synthetic-subject", "alpha", "internal"))
        self.assertFalse(principal.simulated)

    def test_expired_token_is_rejected(self):
        with self.assertRaises(AuthError):
            self.verifier.verify(self.token(self.claims(exp=int(time.time()) - 1)))

    def test_future_token_is_rejected(self):
        with self.assertRaises(AuthError):
            self.verifier.verify(self.token(self.claims(iat=int(time.time()) + 600)))

    def test_foreign_issuer_or_client_or_id_token_is_rejected(self):
        for change in ({"iss": "https://attacker.invalid"}, {"client_id": "another-client"}, {"token_use": "id"}):
            with self.subTest(change=change), self.assertRaises(AuthError):
                self.verifier.verify(self.token(self.claims(**change)))

    def test_wrong_signature_and_unknown_key_are_rejected(self):
        for token in (self.token(key=self.other_key), self.token(kid="unknown")):
            with self.assertRaises(AuthError):
                self.verifier.verify(token)

    def test_unsigned_and_hmac_tokens_are_rejected_before_key_lookup(self):
        values = [jwt.encode(self.claims(), None, algorithm="none"),
                  jwt.encode(self.claims(), "synthetic-test-key" * 4, algorithm="HS256", headers={"kid": "test-key"})]
        for token in values:
            with self.assertRaises(AuthError):
                self.verifier.verify(token)
        self.assertEqual(self.keys.calls, 0)

    def test_unknown_missing_or_conflicting_groups_fail_closed(self):
        for groups in ([], ["unknown"], ["demo-alpha", "demo-beta"], "demo-alpha", [1]):
            with self.subTest(groups=groups), self.assertRaises(AuthError) as error:
                self.verifier.verify(self.token(self.claims(**{"cognito:groups": groups})))
            self.assertEqual(error.exception.status_code, 403)

    def test_required_scope_is_enforced(self):
        with self.assertRaises(AuthError) as error:
            self.verifier.verify(self.token(self.claims(scope="profile")))
        self.assertEqual(error.exception.status_code, 403)

    def test_required_claims_cannot_be_omitted(self):
        for claim in ("exp", "iat", "iss", "sub", "token_use", "client_id"):
            values = self.claims(); del values[claim]
            with self.subTest(claim=claim), self.assertRaises(AuthError):
                self.verifier.verify(self.token(values))

    def test_token_length_and_malformed_tokens_are_bounded(self):
        for token in ("", "not-a-token", "x" * 16385):
            with self.assertRaises(AuthError):
                self.verifier.verify(token)

    def test_missing_callback_or_policy_is_configuration_failure(self):
        for setting in ("COGNITO_REDIRECT_URI", "ACCESS_POLICY_JSON", "COGNITO_ISSUER"):
            env = dict(AUTH_ENV); del env[setting]
            with self.subTest(setting=setting), self.assertRaises(AuthError) as error:
                CognitoSettings.from_env(env)
            self.assertEqual(error.exception.status_code, 503)

    def test_logout_returns_to_origin_root_not_callback_path(self):
        config = self.settings.public_config()
        self.assertEqual(config["redirect_uri"], "https://lab.example.org/auth/callback")
        self.assertEqual(config["logout_uri"], "https://lab.example.org/")

    def test_issuer_cannot_redirect_signing_key_fetch(self):
        with self.assertRaises(AuthError):
            CognitoSettings.from_env({**AUTH_ENV, "COGNITO_ISSUER": "https://attacker.example.org/pool"})

    def test_urls_disallow_http_credentials_query_and_fragment(self):
        for value in ("http://login.example.org", "https://user:pass@login.example.org", "https://login.example.org?q=1", "https://login.example.org/#fragment"):
            with self.subTest(value=value), self.assertRaises(AuthError):
                CognitoSettings.from_env({**AUTH_ENV, "COGNITO_DOMAIN": value})

    def test_scope_policy_requires_safe_lowercase_labels(self):
        for value in ("../outside", "UPPERCASE", "a.b", "a" * 65):
            policy = json.dumps({"demo-alpha": {"tenant": value, "access_level": "internal"}})
            with self.subTest(value=value), self.assertRaises(AuthError):
                CognitoSettings.from_env({**AUTH_ENV, "ACCESS_POLICY_JSON": policy})

    def test_local_mode_is_opt_in_and_invalid_mode_fails_closed(self):
        self.assertFalse(local_demo_mode({}))
        self.assertTrue(local_demo_mode({"LOCAL_DEMO_MODE": "true"}))
        with self.assertRaises(AuthError):
            local_demo_mode({"LOCAL_DEMO_MODE": "yes"})


if __name__ == "__main__":
    unittest.main()
