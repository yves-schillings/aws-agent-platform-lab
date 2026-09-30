"""Cognito access-token boundary and explicitly simulated loopback identities.

Only verified token groups resolve server-owned tenant/source permissions.
No unverified JWT claim is used to grant access or choose the JWKS endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from typing import Mapping, Any
from urllib.parse import urlsplit

import jwt


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class Principal:
    subject: str
    groups: tuple[str, ...]
    tenant: str
    access_level: str
    simulated: bool = False


LOCAL_IDENTITIES = {
    "localalpha": Principal("localalpha", ("demo-alpha",), "alpha", "internal", True),
    "localbeta": Principal("localbeta", ("demo-beta",), "beta", "internal", True),
}
_LABEL = re.compile(r"^[a-z0-9_-]{1,64}$")


def local_demo_mode(environ: Mapping[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    raw = env.get("LOCAL_DEMO_MODE", "false").strip().lower()
    if raw not in {"true", "false"}:
        raise AuthError("LOCAL_DEMO_MODE must be explicitly true or false.", 503)
    return raw == "true"


def _https_url(value: str, label: str, *, origin_only: bool = False) -> str:
    try:
        parts = urlsplit(value)
        valid = (parts.scheme == "https" and parts.hostname and "." in parts.hostname
                 and not parts.username and not parts.password and not parts.query
                 and not parts.fragment and parts.port in (None, 443))
        if origin_only and parts.path not in ("", "/"):
            valid = False
    except ValueError:
        valid = False
    if not valid:
        raise AuthError(f"Set a valid HTTPS {label}.", 503)
    return value.rstrip("/") if origin_only else value


@dataclass(frozen=True)
class CognitoSettings:
    region: str
    pool_id: str
    client_id: str
    issuer: str
    domain: str
    redirect_uri: str
    policy: dict[str, dict[str, str]]
    required_scopes: tuple[str, ...] = ("openid",)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "CognitoSettings":
        env = os.environ if environ is None else environ
        def need(name: str) -> str:
            value = env.get(name, "").strip()
            if not value or value.startswith("<"):
                raise AuthError(f"Authentication is not configured: {name} is missing.", 503)
            return value
        region = need("AWS_REGION")
        if not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d", region):
            raise AuthError("AWS_REGION is invalid.", 503)
        pool = need("COGNITO_USER_POOL_ID")
        if not re.fullmatch(re.escape(region) + r"_[A-Za-z0-9]+", pool):
            raise AuthError("Cognito pool and AWS region must match.", 503)
        client = need("COGNITO_CLIENT_ID")
        if not re.fullmatch(r"[A-Za-z0-9]{1,128}", client):
            raise AuthError("COGNITO_CLIENT_ID is invalid.", 503)
        suffix = "amazonaws.com.cn" if region.startswith("cn-") else "amazonaws.com"
        expected_issuer = f"https://cognito-idp.{region}.{suffix}/{pool}"
        issuer = need("COGNITO_ISSUER").rstrip("/")
        if issuer != expected_issuer:
            raise AuthError("COGNITO_ISSUER must identify the configured pool and region.", 503)
        domain = _https_url(need("COGNITO_DOMAIN"), "COGNITO_DOMAIN", origin_only=True)
        redirect = _https_url(need("COGNITO_REDIRECT_URI"), "COGNITO_REDIRECT_URI")
        try:
            policy = json.loads(need("ACCESS_POLICY_JSON"))
        except (ValueError, TypeError):
            raise AuthError("ACCESS_POLICY_JSON must be a group-to-scope object.", 503) from None
        if not isinstance(policy, dict) or not policy or len(policy) > 100:
            raise AuthError("ACCESS_POLICY_JSON must contain explicit group mappings.", 503)
        for group, scope in policy.items():
            if (not isinstance(group, str) or not group or len(group) > 128
                    or not isinstance(scope, dict) or set(scope) != {"tenant", "access_level"}
                    or any(not isinstance(scope[k], str) or not _LABEL.fullmatch(scope[k])
                           for k in ("tenant", "access_level"))):
                raise AuthError("ACCESS_POLICY_JSON contains an invalid group mapping.", 503)
        scopes = tuple(env.get("COGNITO_REQUIRED_SCOPES", "openid").split())
        if not scopes or any(len(scope) > 256 for scope in scopes):
            raise AuthError("Configure at least one required token scope.", 503)
        return cls(region, pool, client, issuer, domain, redirect, policy, scopes)

    def public_config(self) -> dict[str, Any]:
        callback = urlsplit(self.redirect_uri)
        return {"mode": "aws", "authorization_endpoint": self.domain + "/oauth2/authorize",
                "logout_endpoint": self.domain + "/logout", "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "logout_uri": f"{callback.scheme}://{callback.netloc}/",
                "scopes": list(self.required_scopes)}


class CognitoVerifier:
    def __init__(self, settings: CognitoSettings, *, jwks_client: Any = None):
        self.settings = settings
        self.jwks = jwks_client or jwt.PyJWKClient(
            settings.issuer + "/.well-known/jwks.json", cache_jwk_set=True,
            lifespan=300, timeout=5)

    def verify(self, token: str) -> Principal:
        if not isinstance(token, str) or not 1 <= len(token) <= 16_384:
            raise AuthError("A valid Cognito access token is required.")
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise AuthError("Unsupported access token signature.")
            key = self.jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=["RS256"], issuer=self.settings.issuer,
                                options={"verify_aud": False,
                                         "require": ["exp", "iat", "iss", "sub", "token_use", "client_id"]})
        except AuthError:
            raise
        except jwt.PyJWKClientConnectionError:
            raise AuthError("The identity signing keys are temporarily unavailable.", 503) from None
        except (jwt.PyJWTError, ValueError, TypeError):
            raise AuthError("The access token is invalid or expired.") from None
        if claims.get("token_use") != "access" or claims.get("client_id") != self.settings.client_id:
            raise AuthError("The access token is not issued for this application.")
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            raise AuthError("The access token has no valid subject.")
        scope = claims.get("scope", "")
        if not isinstance(scope, str) or not set(self.settings.required_scopes).issubset(scope.split()):
            raise AuthError("The access token lacks the required application scope.", 403)
        groups = claims.get("cognito:groups", [])
        if (not isinstance(groups, list) or len(groups) > 100
                or any(not isinstance(group, str) for group in groups)):
            raise AuthError("The access token contains invalid group membership.", 403)
        resolved = {tuple(self.settings.policy[group][k] for k in ("tenant", "access_level"))
                    for group in groups if group in self.settings.policy}
        if len(resolved) != 1:
            raise AuthError("No unambiguous source access policy is assigned to this identity.", 403)
        tenant, access_level = next(iter(resolved))
        return Principal(claims["sub"], tuple(sorted(set(groups))), tenant, access_level)
