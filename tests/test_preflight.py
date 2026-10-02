"""Prerequisite classification with mocked tools; no cloud or Docker connection."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import preflight


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        for name in ["Dockerfile", "infra/main.tf", "src/aws_agent_platform_lab/web.py"]:
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        (self.repo / "requirements.txt").write_text("example-package==1.0\n", encoding="utf-8")
        (self.repo / "infra/.terraform/providers").mkdir(parents=True)

    def run_report(self, *, tools=True, aws=False, account=None, results=None):
        calls = []

        def run(args, **kwargs):
            calls.append(args)
            self.assertFalse(kwargs["check"])
            self.assertNotIn("shell", kwargs)
            self.assertEqual(kwargs["env"]["AWS_EC2_METADATA_DISABLED"], "true")
            if results:
                custom = results(args)
                if custom is not None:
                    return custom
            stdout = ""
            if args[1:3] == ["context", "inspect"]:
                stdout = json.dumps("unix:///var/run/docker.sock")
            elif args[1] == "version":
                stdout = '"28.2.2"'
            elif args[1:3] == ["configure", "list-profiles"]:
                stdout = "private-profile-name\n"
            elif args[1:3] == ["sts", "get-caller-identity"]:
                stdout = json.dumps({"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:role/test", "UserId": "private-user"})
            return subprocess.CompletedProcess(args, 0, stdout, "")

        with patch.dict(os.environ, {}, clear=True), patch.object(preflight.shutil, "which", side_effect=lambda n: n if tools else None), patch.object(preflight.metadata, "version", return_value="1.0"), patch.object(preflight.subprocess, "run", side_effect=run):
            report = preflight.inspect(self.repo, aws=aws, expected_account_id=account)
        return report, calls

    def status(self, report, name):
        return next(c["status"] for c in report["checks"] if c["name"] == name)

    def test_offline_default_never_calls_aws_or_mutates_tools(self):
        report, calls = self.run_report()
        self.assertTrue(report["ready_for"]["local_python"])
        self.assertTrue(report["ready_for"]["container_build_prerequisites"])
        self.assertTrue(report["ready_for"]["terraform_syntax"])
        self.assertFalse(report["ready_for"]["aws_identity_verified"])
        self.assertEqual(self.status(report, "aws_identity"), "skipped")
        self.assertEqual(report["deployment_readiness"], "not_assessed")
        self.assertFalse(any(c[0] == "aws" for c in calls))
        self.assertFalse(any(word in c for c in calls for word in ["apply", "init", "login", "build", "push", "invoke-model"]))

    def test_missing_clis_are_blockers_not_success(self):
        report, calls = self.run_report(tools=False, aws=True)
        self.assertFalse(calls)
        self.assertEqual(self.status(report, "docker_daemon"), "blocked")
        self.assertEqual(self.status(report, "terraform_fmt"), "blocked")
        self.assertEqual(self.status(report, "aws_profiles"), "blocked")
        self.assertFalse(report["ready_for"]["aws_identity_verified"])

    def test_timeout_is_unknown_and_does_not_report_secret_output(self):
        with patch.object(preflight.subprocess, "run", side_effect=subprocess.TimeoutExpired("tool", 1, output="SECRET")):
            result = preflight.command(["tool"], repo=self.repo, timeout=1)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.error_kind, "timeout")
        self.assertNotIn("SECRET", str(result))

    def test_executable_disappearing_is_blocked(self):
        with patch.object(preflight.subprocess, "run", side_effect=FileNotFoundError("SECRET")):
            result = preflight.command(["tool"], repo=self.repo, timeout=1)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.error_kind, "missing_executable")
        self.assertNotIn("SECRET", str(result))

    def test_aws_missing_credentials_redacts_raw_errors(self):
        def responses(args):
            if "get-caller-identity" in args:
                return subprocess.CompletedProcess(args, 255, "", "NoCredentials SECRET_ACCESS_KEY=do-not-print")
        report, _ = self.run_report(aws=True, results=responses)
        self.assertEqual(self.status(report, "aws_identity"), "blocked")
        self.assertIn("no_credentials", json.dumps(report))
        self.assertNotIn("do-not-print", json.dumps(report))
        self.assertNotIn("private-profile-name", json.dumps(report))

    def test_sts_success_requires_valid_identity_and_expected_account(self):
        report, _ = self.run_report(aws=True, account="123456789012")
        self.assertTrue(report["ready_for"]["aws_identity_verified"])
        self.assertNotIn("123456789012", json.dumps(report))
        wrong, _ = self.run_report(aws=True, account="999999999999")
        self.assertEqual(self.status(wrong, "aws_identity"), "blocked")

    def test_success_exit_with_malformed_sts_output_is_not_verified(self):
        for invalid in ['{}', '[]', '{"Account": null}', 'not json']:
            def responses(args):
                if "get-caller-identity" in args:
                    return subprocess.CompletedProcess(args, 0, invalid, "")
            with self.subTest(invalid=invalid):
                report, _ = self.run_report(aws=True, results=responses)
                self.assertEqual(self.status(report, "aws_identity"), "unknown")

    def test_remote_docker_context_is_not_contacted(self):
        def responses(args):
            if args[1:3] == ["context", "inspect"]:
                return subprocess.CompletedProcess(args, 0, '"ssh://remote.example"', "")
        report, calls = self.run_report(results=responses)
        self.assertEqual(self.status(report, "docker_daemon"), "unknown")
        self.assertFalse(any(c[0] == "docker" and c[1] == "version" for c in calls))

    def test_null_docker_server_is_not_success(self):
        def responses(args):
            if args[1] == "version":
                return subprocess.CompletedProcess(args, 0, "null", "")
        report, _ = self.run_report(results=responses)
        self.assertEqual(self.status(report, "docker_daemon"), "unknown")
        self.assertFalse(report["ready_for"]["container_build_prerequisites"])

    def test_uninitialized_terraform_is_skipped_without_automatic_init(self):
        (self.repo / "infra/.terraform/providers").rmdir()
        report, calls = self.run_report()
        self.assertEqual(self.status(report, "terraform_validate"), "skipped")
        self.assertFalse(report["ready_for"]["terraform_syntax"])
        self.assertFalse(any("init" in c or "validate" in c for c in calls))

    def test_failed_terraform_check_does_not_claim_ready(self):
        def responses(args):
            if "validate" in args:
                return subprocess.CompletedProcess(args, 1, "secret diagnostic", "")
        report, _ = self.run_report(results=responses)
        self.assertFalse(report["ready_for"]["terraform_syntax"])
        self.assertNotIn("secret diagnostic", json.dumps(report))

    def test_dependency_mismatch_and_unsupported_pin_are_not_pass(self):
        with patch.object(preflight.metadata, "version", return_value="2.0"):
            self.assertEqual(preflight.dependencies(self.repo).status, "blocked")
        (self.repo / "requirements.txt").write_text("example-package>=1.0\n", encoding="utf-8")
        self.assertEqual(preflight.dependencies(self.repo).status, "unknown")

    def test_profile_requires_explicit_aws_opt_in(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            preflight.main(["--repo", str(self.repo), "--profile", "example"])
        self.assertEqual(error.exception.code, 2)

    def test_json_report_exit_is_nonzero_for_unknown_checks(self):
        fake = {"checks": [{"status": "unknown"}], "ready_for": {}}
        with patch.object(preflight, "inspect", return_value=fake), contextlib.redirect_stdout(io.StringIO()) as output:
            code = preflight.main(["--repo", str(self.repo), "--json"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue()), fake)


if __name__ == "__main__":
    unittest.main()
