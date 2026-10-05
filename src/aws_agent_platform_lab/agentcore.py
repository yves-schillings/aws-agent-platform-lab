"""AgentCore HTTP contract around the existing five-agent Factory.

IAM inbound authenticates the trusted connector, not a human. Consequently the
connector's Cognito access token is independently verified again here. JWT
inbound uses the Authorization header explicitly allowlisted by Runtime.
Neither mode accepts serialized Principals or caller-supplied company grants.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
import threading
from typing import Annotated, Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .auth import AuthError, CognitoSettings, CognitoVerifier
from .services import ServiceError


class StartInvocation(BaseModel):
    """Start synthetic work; source authority is derived from the token only."""
    model_config = ConfigDict(extra="forbid")
    operation: Literal["start"]
    request_text: str = Field(min_length=10, max_length=4000)
    synthetic: Literal[True]
    access_token: str | None = Field(default=None, min_length=1, max_length=16384, repr=False)


class ReadInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Literal["read"]
    run_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    access_token: str | None = Field(default=None, min_length=1, max_length=16384, repr=False)


class DecideInvocation(ReadInvocation):
    operation: Literal["decide"]
    gate: Literal["G1", "G2", "G3", "G4"]
    artifact_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=1, max_length=1000)


Invocation = Annotated[StartInvocation | ReadInvocation | DecideInvocation,
                       Field(discriminator="operation")]


class InvocationBodyLimit:
    """Bound the ASGI request body without using private Starlette attributes."""
    def __init__(self, app, maximum=65536):
        self.app, self.maximum = app, maximum

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body.extend(message.get('body', b''))
            if len(body) > self.maximum:
                response = JSONResponse({'detail': 'Invocation is too large.'}, status_code=413,
                                        headers={'Cache-Control': 'no-store'})
                return await response(scope, receive, send)
            if not message.get('more_body', False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()

        async def safe_send(message):
            if message['type'] == 'http.response.start':
                message['headers'] = list(message.get('headers', [])) + [(b'cache-control', b'no-store')]
            await send(message)

        await self.app(scope, replay, safe_send)


def create_runtime_app(*, environ=None, verifier=None, factory_service=None):
    """Create the Runtime service; injected services and test keys stay offline.

    Production requires the existing AWS provider and shared DynamoDB tables.
    AGENTCORE_LOCAL_TEST allows injected offline dependencies, never fixture
    identities or unauthenticated invocations.
    """
    env = dict(os.environ if environ is None else environ)
    mode = env.get("AGENTCORE_INBOUND_AUTH", "iam")
    if mode not in {"iam", "cognito-jwt"}:
        raise ValueError("AgentCore inbound mode must be iam or cognito-jwt; Entra is not implemented")
    test_mode = env.get("AGENTCORE_LOCAL_TEST", "false")
    if test_mode not in {"true", "false"}:
        raise ValueError("AGENTCORE_LOCAL_TEST must be true or false")
    if env.get("LOCAL_DEMO_MODE", "false") != "false":
        raise ValueError("AgentCore does not accept local fixture identities")
    if test_mode != "true":
        if (env.get("FACTORY_PROVIDER") not in {"aws", "aws-langchain"}
                or not all(env.get(k) for k in ("FACTORY_CHECKPOINTS_TABLE", "FACTORY_RUNS_TABLE"))):
            raise ValueError("AgentCore requires AWS inference and shared DynamoDB persistence")
    elif factory_service is None:
        raise ValueError("Offline Runtime tests require an explicitly injected Factory service")
    verifier = verifier or CognitoVerifier(CognitoSettings.from_env(env))
    active = 0
    lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        if factory_service is None:
            from .factory import service_from_environment
            app.state.factory = service_from_environment(Path(env.get("LAB_DATA_DIR", "/tmp/factory")), env)
        else:
            app.state.factory = factory_service
        try:
            yield
        finally:
            if factory_service is None:
                app.state.factory.close()

    app = FastAPI(title="AgentCore Factory Runtime", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)

    app.add_middleware(InvocationBodyLimit)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Pydantic's usual error details may contain access tokens or prompts.
        return JSONResponse({"detail": "Invalid invocation fields."}, status_code=422)

    @app.exception_handler(AuthError)
    async def invalid_identity(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)

    @app.get("/ping")
    def ping():
        with lock:
            return {"status": "HealthyBusy" if active else "Healthy"}

    @app.post("/invocations")
    def invoke(payload: Invocation, request: Request):
        nonlocal active
        if mode == "iam":
            token = payload.access_token
        else:
            if payload.access_token is not None:
                raise AuthError("JWT mode requires the allowlisted Authorization header.")
            header = request.headers.get("Authorization", "")
            token = header[7:] if header.startswith("Bearer ") else None
        if not token:
            raise AuthError("A verified Cognito access token is required.")
        principal = verifier.verify(token)
        if principal.simulated is not False:
            raise AuthError("Simulated identities are not allowed.", 403)
        with lock:
            active += 1
        try:
            service = app.state.factory
            if isinstance(payload, StartInvocation):
                state = service.start_run(principal, payload.request_text)
            elif isinstance(payload, DecideInvocation):
                state = service.decide_run(principal, payload.run_id, payload.gate,
                                          payload.artifact_hash, payload.decision, payload.reason)
            else:
                state = service.get_run(principal, payload.run_id)
            return {"result": state}
        except ServiceError as exc:
            # Preserve safe business refusals through InvokeAgentRuntime, whose
            # transport otherwise wraps container 4xx responses as HTTP 424.
            return {"error": {"status_code": exc.status_code, "detail": str(exc)}}
        except Exception:
            # Do not echo provider exceptions, prompt text or access tokens.
            return JSONResponse({"detail": "Factory invocation failed; reload the run before retrying."},
                                status_code=503)
        finally:
            with lock:
                active -= 1

    return app


def main():
    """AgentCore HTTP requires 0.0.0.0:8080; local tests bind loopback."""
    import uvicorn
    local = os.environ.get("AGENTCORE_LOCAL_TEST", "false") == "true"
    # Offline mode intentionally requires injection through create_runtime_app.
    uvicorn.run(create_runtime_app(), host="127.0.0.1" if local else "0.0.0.0",
                port=8080, access_log=False, proxy_headers=False)


if __name__ == "__main__":
    main()
