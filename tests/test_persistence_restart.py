"""Restart the real local HTTP process against the same isolated evidence store.

This covers durability across process memory loss, not cloud/S3 connectivity.
Inference is mock; the configured stdio MCP tool runs locally. Only loopback
HTTP is used, and the child receives no cloud credential environment variables.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from aws_agent_platform_lab.models import canonical_bytes, sha256_bytes

ROOT = Path(__file__).resolve().parents[1]
WEB_AVAILABLE = all(importlib.util.find_spec(module) for module in ("fastapi", "uvicorn", "jwt", "mcp"))


@unittest.skipUnless(WEB_AVAILABLE, "Install the web extra for HTTP restart verification")
class PersistenceRestartTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="agent-lab-restart-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.data = self.directory / "data"
        self.process = None
        self.process_log = None
        self.starts = 0
        self.addCleanup(self.stop_server)
        # Disable environment-configured proxies even for the loopback requests.
        self.opener = build_opener(ProxyHandler({}))

    def start_server(self):
        self.assertIsNone(self.process)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        self.base_url = f"http://127.0.0.1:{port}"
        self.starts += 1
        env = {name: os.environ[name] for name in ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "HOME")
               if name in os.environ}
        env.update(LOCAL_DEMO_MODE="true", HOST="127.0.0.1", PORT=str(port),
                   LAB_DATA_DIR=str(self.data), LAB_CORPUS_PATH=str(ROOT / "corpus" / "web_knowledge.json"),
                   PYTHONUTF8="1", PYTHONUNBUFFERED="1")
        self.process_log = (self.directory / f"server-{self.starts}.log").open("wb")
        self.process = subprocess.Popen([sys.executable, "-m", "aws_agent_platform_lab.web"],
            cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=self.process_log,
            stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.fail("The isolated local HTTP process exited before becoming healthy")
            try:
                status, response = self.request("GET", "/healthz")
                if status == 200 and response == {"status": "ok"}:
                    return
            except (URLError, TimeoutError, ConnectionError):
                pass
            time.sleep(.05)
        self.fail("The isolated local HTTP process did not become healthy")

    def stop_server(self):
        if self.process is not None:
            # Only the Popen object created by this test is stopped. Completed
            # decisions are already persisted, so even process termination must
            # preserve their exact state when the next process starts.
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.process = None
        if self.process_log is not None:
            self.process_log.close()
            self.process_log = None

    def request(self, method, path, body=None, identity="localalpha"):
        headers = {"X-Demo-User": identity}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        request = Request(self.base_url + path, data=data, method=method, headers=headers)
        try:
            with self.opener.open(request, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def finish_run(self, decision):
        # A previous worker may have persisted its result immediately before
        # releasing its user lease. Wait only for that short handover.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            status, started = self.request("POST", "/api/runs", {
                "request_text": "Prepare a synthetic document checklist with cited controls.",
                "synthetic": True, "scenario_language": "en"})
            if status != 409:
                break
            time.sleep(.05)
        self.assertEqual(status, 202, started)
        run_id = started["run_id"]
        while time.monotonic() < deadline:
            status, state = self.request("GET", f"/api/runs/{run_id}")
            self.assertEqual(status, 200, state)
            if state["status"] not in {"queued", "running"}:
                break
            time.sleep(.05)
        self.assertEqual(state["status"], "waiting_approval", state.get("error"))
        self.assertEqual(state["tool"]["transport"], "stdio")
        status, completed = self.request("POST", f"/api/runs/{run_id}/decision", {
            "artifact_hash": state["artifact_hash"], "decision": decision})
        self.assertEqual(status, 200, completed)
        return completed

    def test_completed_decisions_provenance_and_authorisation_survive_process_restart(self):
        self.start_server()
        originals = [self.finish_run("approve"), self.finish_run("reject")]
        snapshots = {}
        for state in originals:
            self.assertTrue(state["sources"])
            self.assertEqual(state["artifact_hash"], sha256_bytes(canonical_bytes(state["artifact"])))
            self.assertEqual(state["decision"]["artifact_hash"], state["artifact_hash"])
            self.assertEqual(state["published"], state["status"] == "approved")
            snapshots[state["run_id"]] = (self.data / "runs" / state["run_id"] / "state.json").read_bytes()
        self.stop_server()
        self.start_server()

        for original in originals:
            run_id = original["run_id"]
            with self.subTest(status=original["status"]):
                status, restored = self.request("GET", f"/api/runs/{run_id}")
                self.assertEqual(status, 200)
                # Exact comparison covers hash, source versions/text, tool evidence,
                # decision actor/time, publication state and trace provenance.
                self.assertEqual(restored, original)
                self.assertEqual(sum(e.get("stage") == "human_decision" for e in restored["trace"]), 1)
                for source in original["sources"]:
                    self.assertIn("version", source)
                    status, document = self.request("GET", f"/api/runs/{run_id}/sources/{source['id']}")
                    self.assertEqual((status, document), (200, source))
                    status, _ = self.request("GET", f"/api/runs/{run_id}/sources/{source['id']}", identity="localbeta")
                    self.assertEqual(status, 404)
                status, _ = self.request("GET", f"/api/runs/{run_id}", identity="localbeta")
                self.assertEqual(status, 404)
                for action in ("approve", "reject"):
                    status, _ = self.request("POST", f"/api/runs/{run_id}/decision", {
                        "artifact_hash": original["artifact_hash"], "decision": action})
                    self.assertEqual(status, 409)
                self.assertEqual((self.data / "runs" / run_id / "state.json").read_bytes(), snapshots[run_id])
        self.stop_server()

        # The local selector intentionally offers only two identities. Exercise a
        # different subject in the same tenant directly against a fresh service
        # to distinguish ownership checks from cross-tenant checks.
        from aws_agent_platform_lab.auth import Principal
        from aws_agent_platform_lab.services import LabService, ServiceError
        from aws_agent_platform_lab.storage import LocalStore
        from aws_agent_platform_lab.retrieval import LocalRetriever
        from aws_agent_platform_lab.providers import MockProvider
        service = LabService(LocalStore(self.data), LocalRetriever(), MockProvider)
        self.addCleanup(service.close)
        intruder = Principal("another-alpha-subject", ("demo-alpha",), "alpha", "internal", True)
        for original in originals:
            with self.assertRaises(ServiceError) as denied:
                service.get_run(intruder, original["run_id"])
            self.assertEqual(denied.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
