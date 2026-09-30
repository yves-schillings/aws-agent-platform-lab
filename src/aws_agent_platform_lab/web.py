"""FastAPI browser/API boundary. Run with python -m aws_agent_platform_lab.web."""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict
import ipaddress
import logging
import os
from pathlib import Path
import re
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
    model_config = ConfigDict(extra="forbid")
    request_text: str = Field(min_length=1, max_length=4_000)
    scenario_language: Literal["en", "nl"] = "en"
    synthetic: Literal[True]


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: Literal["approve", "reject"]


class TokenInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=2048)
    code_verifier: str = Field(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9._~-]+$")


def create_app(*, service: Any = None, environ: Mapping[str, str] | None = None,
               verifier: Any = None, token_transport: httpx.BaseTransport | None = None) -> FastAPI:
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

    app = FastAPI(title="AWS Agent Platform Lab", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    app.state.service = service
    app.state.local = local

    @app.middleware("http")
    async def boundaries(request: Request, call_next):
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
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code,
                            headers={"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else {})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Do not echo request data, an OAuth code or verifier in validation errors.
        return JSONResponse({"detail": "Invalid request fields."}, status_code=422)

    def current_principal(request: Request) -> Principal:
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

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    @app.get("/")
    @app.get("/auth/callback")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/auth/config")
    def auth_config():
        if configuration_error:
            raise configuration_error
        if local:
            return {"mode": "offline", "simulated": True, "identities": list(LOCAL_IDENTITIES)}
        return settings.public_config()

    @app.post("/auth/token")
    def exchange_token(payload: TokenInput):
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
        return asdict(principal)

    @app.post("/api/runs", status_code=202)
    def start_run(payload: RunInput, principal: Principal = Depends(current_principal)):
        if not payload.request_text.strip():
            return JSONResponse({"detail": "Enter a synthetic request."}, status_code=422)
        return call_service("start_run", principal, payload.request_text.strip(), payload.scenario_language)

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str, principal: Principal = Depends(current_principal)):
        return call_service("get_run", principal, run_id)

    @app.post("/api/runs/{run_id}/decision")
    def decision(run_id: str, payload: DecisionInput, principal: Principal = Depends(current_principal)):
        return call_service("decide_run", principal, run_id, payload.artifact_hash, payload.decision)

    @app.get("/api/runs/{run_id}/sources/{source_id}")
    def source(run_id: str, source_id: str, principal: Principal = Depends(current_principal)):
        return call_service("get_source", principal, run_id, source_id)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


def main() -> None:
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
