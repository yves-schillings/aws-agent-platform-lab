"""IAM-signed trusted connector for AgentCore, with no cloud writes at import.

The web server verifies Cognito first. Runtime re-verifies the original token
instead of trusting a JSON object claiming a company, group or approver role.
No automatic retry of mutating operations: a timeout may follow a successful
start or decision. Read the run before attempting recovery.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid

from .services import ServiceError


class AgentCoreFactoryClient:
    """Adapter used only when FACTORY_BACKEND=agentcore is explicitly selected."""
    def __init__(self, environ, *, client=None):
        self.arn = environ.get("AGENTCORE_RUNTIME_ARN", "")
        match = re.fullmatch(r"arn:aws:bedrock-agentcore:([a-z0-9-]+):[0-9]{12}:runtime/[A-Za-z0-9_-]+", self.arn)
        region = environ.get("AWS_REGION", "")
        if not match or match[1] != region:
            raise ValueError("Configure a commercial AWS AgentCore runtime ARN in AWS_REGION")
        self.qualifier = environ.get("AGENTCORE_RUNTIME_QUALIFIER", "DEFAULT")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.qualifier):
            raise ValueError("Invalid AgentCore runtime qualifier")
        if client is None:
            import boto3
            from botocore.config import Config
            client = boto3.client("bedrock-agentcore", region_name=region,
                                  config=Config(connect_timeout=5, read_timeout=300,
                                                retries={"total_max_attempts": 1}))
        self.client = client

    def invoke(self, method, principal, access_token, *args):
        """Forward only an authenticated user's token and bounded operation fields."""
        if (not access_token or getattr(principal, "simulated", None) is not False
                or not isinstance(principal.subject, str) or not principal.subject):
            raise ServiceError("AgentCore requires verified Cognito sign-in", 403)
        from .agentcore import StartInvocation, ReadInvocation, DecideInvocation
        if method == "start_run":
            payload = StartInvocation(operation="start", access_token=access_token,
                                      request_text=args[0], synthetic=True)
            session_seed = uuid.uuid4().hex
        elif method == "get_run":
            payload = ReadInvocation(operation="read", access_token=access_token, run_id=args[0])
            session_seed = args[0]
        elif method == "decide_run":
            payload = DecideInvocation(operation="decide", access_token=access_token, run_id=args[0],
                                       gate=args[1], artifact_hash=args[2], decision=args[3], reason=args[4])
            session_seed = args[0]
        else:
            raise ServiceError("Unsupported AgentCore operation", 422)
        session = hashlib.sha256((principal.subject + ":" + session_seed).encode()).hexdigest()
        stream = None
        try:
            result = self.client.invoke_agent_runtime(agentRuntimeArn=self.arn,
                qualifier=self.qualifier, runtimeSessionId=session, contentType="application/json",
                accept="application/json", payload=payload.model_dump_json(exclude_none=True).encode())
            stream = result["response"]
            raw = stream.read(1048577)
            if (result.get("statusCode", 200) != 200 or len(raw) > 1048576
                    or result.get("contentType", "").split(";")[0] != "application/json"):
                raise ValueError("Invalid runtime response")
            decoded = json.loads(raw)
            if isinstance(decoded, dict) and set(decoded) == {"error"}:
                error = decoded["error"]
                if (isinstance(error, dict) and set(error) == {"status_code", "detail"}
                        and error["status_code"] in {400, 403, 404, 409, 422, 503}
                        and isinstance(error["detail"], str) and len(error["detail"]) <= 1000):
                    raise ServiceError(error["detail"], error["status_code"])
                raise ValueError("Invalid runtime refusal")
            if not isinstance(decoded, dict) or set(decoded) != {"result"} or not isinstance(decoded["result"], dict):
                raise ValueError("Invalid runtime result")
            return decoded["result"]
        except ServiceError:
            raise
        except Exception:
            raise ServiceError("AgentCore invocation failed; reload the run before retrying", 503) from None
        finally:
            if stream is not None:
                stream.close()

    def close(self):
        self.client.close()
