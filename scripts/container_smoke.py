"""Exercise the installed container application through its internal loopback.

Only the explicit offline mode is accepted. No credentials, cloud resources or
host port exposure are required. This is also runnable against a local server.
"""
from __future__ import annotations

import json
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8000"


def request(path: str, *, identity: str | None = None, payload=None):
    headers = {"Content-Type": "application/json"}
    if identity:
        headers["X-Demo-User"] = identity
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    with urlopen(Request(BASE + path, data=data, headers=headers), timeout=5) as response:
        raw = response.read()
        return json.loads(raw) if "application/json" in response.headers.get("Content-Type", "") else raw


def main() -> None:
    deadline = time.monotonic() + 60
    while True:
        try:
            assert request("/healthz")["status"] == "ok"
            break
        except (URLError, TimeoutError):
            if time.monotonic() >= deadline:
                raise RuntimeError("Application did not become healthy") from None
            time.sleep(1)
    assert b"<html" in request("/").lower(), "Installed UI is unavailable"
    assert request("/static/app.js"), "Installed static assets are unavailable"
    config = request("/auth/config")
    assert config["mode"] == "offline" and config["simulated"] is True, "Smoke accepts explicit offline mode only"
    identities = config["identities"]
    assert "localalpha" in identities and "localbeta" in identities
    run = request("/api/runs", identity="localalpha", payload={
        "request_text": "Prepare a synthetic onboarding proposal with the required documents, human review and access controls.",
        "scenario_language": "en", "synthetic": True,
    })
    deadline = time.monotonic() + 60
    while True:
        state = request("/api/runs/" + run["run_id"], identity="localalpha")
        if state["status"] == "waiting_approval":
            assert state["artifact_hash"] and state["artifact"] and state["sources"]
            assert state["identity_simulated"] is True
            print("Offline container smoke passed: installed UI, auth config, retrieval, agents and approval gate.")
            return
        if state["status"] not in {"queued", "running"}:
            raise RuntimeError("Offline workflow did not reach its approval gate: " + state["status"])
        if time.monotonic() >= deadline:
            raise RuntimeError("Offline workflow smoke timed out")
        time.sleep(0.25)


if __name__ == "__main__":
    main()
