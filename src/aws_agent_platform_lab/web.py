"""FastAPI browser/API boundary. Run with python -m aws_agent_platform_lab.web."""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict
import ipaddress
import logging
import os
from pathlib import Path
import re
import threading
from typing import Literal, Any, Mapping
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .auth import (AuthError, Principal, LOCAL_IDENTITIES, CognitoSettings,
                   CognitoVerifier, local_demo_mode)

STATIC = Path(__file__).parent / "static"


class RunInput(BaseModel):
    """Browser run request; identity and source permissions are never request fields."""
    model_config = ConfigDict(extra="forbid")
    request_text: str = Field(min_length=1, max_length=4_000)
    scenario_language: Literal["en", "nl"] = "en"
    synthetic: Literal[True]


class DecisionInput(BaseModel):
    """Explicit decision bound to the exact artifact displayed to the caller."""
    model_config = ConfigDict(extra="forbid")
    artifact_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: Literal["approve", "reject"]


class FactoryInput(BaseModel):
    """Synthetic request for the separately scoped local Factory prototype."""
    model_config = ConfigDict(extra="forbid")
    request_text: str = Field(min_length=10, max_length=4_000)
    synthetic: Literal[True]


class FactoryDecisionInput(DecisionInput):
    """Gate-specific simulated decision including a human-readable reason."""
    gate: Literal["G1", "G2", "G3", "G4"]
    reason: str = Field(min_length=1, max_length=1_000)


class TokenInput(BaseModel):
    """Authorization code and Proof Key for Code Exchange verifier from browser login."""
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=2048)
    code_verifier: str = Field(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9._~-]+$")


def create_app(*, service: Any = None, environ: Mapping[str, str] | None = None,
               verifier: Any = None, token_transport: httpx.BaseTransport | None = None,
               factory_service: Any = None) -> FastAPI:
    """Assemble HTTP routes, identity checks and application lifecycle dependencies.

    The baseline AWS mode uses verified Cognito identities. Factory routes
    remain local fixtures and cannot be enabled remotely by a request header.
    """
    env = dict(os.environ if environ is None else environ)
    configuration_error = None
    try:
        local = local_demo_mode(env)
    except AuthError as exc:
        local, configuration_error = False, exc
    settings = None
    if not local and configuration_error is None:
        try:
            settings = CognitoSettings.from_env(env)
            verifier = verifier or CognitoVerifier(settings)
        except AuthError as exc:
            configuration_error = exc

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Construct service resources at startup and close owned resources at shutdown."""
        if service is not None:
            app.state.service = service
        else:
            try:
                from .services import LabService
                app.state.service = LabService.from_env()
            except Exception:
                app.state.service = None
        yield
        if app.state.service is not None:
            app.state.service.close()
        if app.state.factory_service is not None:
            app.state.factory_service.close()

    app = FastAPI(title="AWS Agent Platform Lab", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    app.state.service = service
    app.state.local = local
    app.state.factory_service = factory_service
    factory_enabled = str(env.get("FACTORY_ENABLED", "false")).strip().lower() == "true"
    factory_lock = threading.Lock()
    factory_identities = {
        **LOCAL_IDENTITIES,
        "localgamma": Principal("localgamma", ("demo-gamma",), "gamma", "internal", True),
    }

    @app.middleware("http")
    async def boundaries(request: Request, call_next):
        """Enforce local loopback, bound request bodies and apply browser security headers."""
        if local:
            try:
                host = urlsplit("http://" + request.headers.get("host", "")).hostname
                permitted = (request.client is not None and ipaddress.ip_address(request.client.host).is_loopback
                             and host in {"127.0.0.1", "localhost", "::1"})
            except ValueError:
                permitted = False
            if not permitted:
                return JSONResponse({"detail": "Local demonstration access is limited to loopback."}, status_code=403)
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > 65_536:
            return JSONResponse({"detail": "Request body exceeds the allowed size."}, status_code=413)
        if request.method in {"POST", "PUT", "PATCH"}:
            # Bound chunked bodies too; Starlette caches the body for downstream parsing.
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 65_536:
                    return JSONResponse({"detail": "Request body exceeds the allowed size."}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        if not local:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.exception_handler(AuthError)
    async def auth_error(request, exc):
        """Return only the safe authentication message and required challenge header."""
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code,
                            headers={"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else {})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Do not echo request data, an OAuth code or verifier in validation errors.
        """Reject malformed fields without reflecting tokens or request contents."""
        return JSONResponse({"detail": "Invalid request fields."}, status_code=422)

    def current_principal(request: Request) -> Principal:
        """Resolve an explicit local fixture or verify the AWS Cognito access token."""
        if configuration_error:
            raise configuration_error
        if local:
            chosen = request.headers.get("X-Demo-User", "")
            if chosen not in LOCAL_IDENTITIES:
                raise AuthError("Choose one of the two explicitly simulated local identities.")
            return LOCAL_IDENTITIES[chosen]
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or not header[7:].strip():
            raise AuthError("Sign in with a Cognito access token.")
        return verifier.verify(header[7:].strip())

    def call_service(method: str, *args):
        """Call the configured baseline service and redact unexpected exception text."""
        active = app.state.service
        if active is None:
            raise AuthError("The workflow service is not configured yet.", 503)
        try:
            return getattr(active, method)(*args)
        except Exception as exc:
            # The service explicitly provides safe errors; do not leak other exception text.
            from .services import ServiceError
            if isinstance(exc, ServiceError):
                return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)
            return JSONResponse({"detail": "The workflow operation failed. Inspect its safe trace."}, status_code=500)

    def factory_principal(request: Request) -> Principal:
        # Fixture identities never reach the Cognito/AWS path, even when injected in tests.
        """Resolve a local fixture, or in AWS mode a verified Cognito identity when enabled.

        AWS mode requires FACTORY_ENABLED=true; otherwise Factory routes do not exist.
        """
        if not local:
            if not factory_enabled:
                raise AuthError("The Factory increment is available in local demonstration mode only.", 404)
            return current_principal(request)
        chosen = request.headers.get("X-Demo-User", "")
        if chosen not in factory_identities:
            raise AuthError("Choose a simulated Company 1, Company 2 or Company 3 identity.")
        return factory_identities[chosen]

    def call_factory(method: str, *args):
        """Initialize the local Factory once and translate bounded service failures."""
        from .services import ServiceError
        try:
            with factory_lock:
                if app.state.factory_service is None:
                    from .factory import service_from_environment
                    root = Path(env.get("LAB_DATA_DIR", ".lab-data")) / "factory"
                    app.state.factory_service = service_from_environment(root, env)
            return getattr(app.state.factory_service, method)(*args)
        except ServiceError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)
        except ImportError:
            return JSONResponse({"detail": "Install the pinned Factory dependencies from requirements.txt."}, status_code=503)
        except Exception:
            return JSONResponse({"detail": "The local Factory could not complete the operation. Reload the run before retrying."}, status_code=503)

    @app.get("/healthz")
    def health():
        """Report process responsiveness only; this does not prove cloud integrations."""
        return {"status": "ok"}

    @app.get("/")
    @app.get("/auth/callback")
    def index():
        """Serve the baseline browser client and its sign-in callback shell."""
        return FileResponse(STATIC / "index.html")

    @app.get("/factory")
    def factory_index():
        """Serve the local inspection harness without exposing it in AWS mode."""
        if not local:
            raise AuthError("The Factory increment is available in local demonstration mode only.", 404)
        return FileResponse(STATIC / "factory.html")

    @app.get("/api/factory/config")
    def factory_config():
        """Describe the three simulated companies available to the local harness."""
        if not local:
            raise AuthError("The Factory increment is available in local demonstration mode only.", 404)
        return {"simulated": True, "mode": "offline", "engine": "langgraph", "identities": [
            {"id": key, "label": f"Company {number}"}
            for number, key in enumerate(factory_identities, start=1)
        ]}

    @app.post("/api/factory/runs", status_code=201)
    def factory_start(payload: FactoryInput, principal: Principal = Depends(factory_principal)):
        """Start an owned local Factory run that pauses at G1 Scope."""
        return call_factory("start_run", principal, payload.request_text.strip())

    @app.get("/api/factory/runs/{run_id}")
    def factory_read(run_id: str, principal: Principal = Depends(factory_principal)):
        """Inspect an owned Factory run through the common service boundary."""
        return call_factory("get_run", principal, run_id)

    @app.post("/api/factory/runs/{run_id}/decision")
    def factory_decide(run_id: str, payload: FactoryDecisionInput,
                       principal: Principal = Depends(factory_principal)):
        """Forward the explicit gate/hash decision for locked server-side validation."""
        return call_factory("decide_run", principal, run_id, payload.gate,
                            payload.artifact_hash, payload.decision, payload.reason.strip())

    @app.get("/auth/config")
    def auth_config():
        """Expose safe sign-in settings or clearly marked offline identities."""
        if configuration_error:
            raise configuration_error
        if local:
            return {"mode": "offline", "simulated": True, "identities": list(LOCAL_IDENTITIES)}
        return settings.public_config()

    @app.post("/auth/token")
    def exchange_token(payload: TokenInput):
        """Exchange a code and verifier only at the configured Cognito endpoint.

        Verify the resulting access token before returning it; discard refresh
        and identity tokens and never reflect provider response bodies on failure.
        """
        if configuration_error:
            raise configuration_error
        if local or settings is None:
            raise AuthError("Cognito token exchange is disabled in local demonstration mode.", 404)
        try:
            with httpx.Client(timeout=10, follow_redirects=False, transport=token_transport) as client:
                response = client.post(settings.domain + "/oauth2/token", data={
                    "grant_type": "authorization_code", "client_id": settings.client_id,
                    "code": payload.code, "code_verifier": payload.code_verifier,
                    "redirect_uri": settings.redirect_uri})
            if response.status_code != 200 or len(response.content) > 65_536:
                raise AuthError("Cognito did not accept the sign-in code.")
            result = response.json()
            token = result.get("access_token", "")
            verifier.verify(token)
            # Never deliver or persist the refresh/ID tokens returned by Cognito.
            return {"access_token": token, "token_type": "Bearer"}
        except AuthError:
            raise
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            raise AuthError("Sign-in is temporarily unavailable. Start sign-in again.", 503) from None

    @app.get("/api/me")
    def me(principal: Principal = Depends(current_principal)):
        """Return the caller scope already resolved by the authentication dependency."""
        return asdict(principal)

    @app.post("/api/runs", status_code=202)
    def start_run(payload: RunInput, principal: Principal = Depends(current_principal)):
        """Queue a bounded synthetic baseline run under the authenticated principal."""
        if not payload.request_text.strip():
            return JSONResponse({"detail": "Enter a synthetic request."}, status_code=422)
        return call_service("start_run", principal, payload.request_text.strip(), payload.scenario_language)

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str, principal: Principal = Depends(current_principal)):
        """Return only the run state that the principal is authorized to inspect."""
        return call_service("get_run", principal, run_id)

    @app.post("/api/runs/{run_id}/decision")
    def decision(run_id: str, payload: DecisionInput, principal: Principal = Depends(current_principal)):
        """Record approval or rejection for the exact reviewed baseline artifact."""
        return call_service("decide_run", principal, run_id, payload.artifact_hash, payload.decision)

    @app.get("/api/runs/{run_id}/sources/{source_id}")
    def source(run_id: str, source_id: str, principal: Principal = Depends(current_principal)):
        """Return a cited source after rechecking run and source permissions."""
        return call_service("get_source", principal, run_id, source_id)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


def main() -> None:
    """Start Uvicorn with safe logging and mandatory loopback binding for local mode."""
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for logger_name in ("httpx", "httpcore", "botocore", "boto3", "urllib3"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    local = local_demo_mode()
    configured_host = os.environ.get("HOST", "127.0.0.1" if local else "0.0.0.0")
    if local and configured_host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("LOCAL_DEMO_MODE=true requires a loopback binding.")
    uvicorn.run(create_app(), host="127.0.0.1" if local else configured_host,
                port=int(os.environ.get("PORT", "8000")), proxy_headers=False,
                access_log=False)


if __name__ == "__main__":
    main()
