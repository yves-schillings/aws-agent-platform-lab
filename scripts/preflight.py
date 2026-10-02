"""Read-only prerequisites; offline by default, optional AWS identity lookup.

Never installs, logs in, builds, initializes Terraform, deploys or invokes models.
Raw command output and credential values are deliberately excluded from reports.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from importlib import metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Check:
    """One scoped preflight observation; passing does not imply deployment readiness."""
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class CommandResult:
    """Bounded subprocess outcome used to build a redacted preflight report."""
    status: str
    stdout: str = ""
    error_kind: str = ""


def command(args: list[str], *, repo: Path, timeout: int) -> CommandResult:
    """Run a fixed diagnostic command with a deadline and captured output."""
    env = dict(os.environ)
    env.update(AWS_EC2_METADATA_DISABLED="true", AWS_PAGER="",
               AWS_CLI_AUTO_PROMPT="off", AWS_IGNORE_CONFIGURED_ENDPOINT_URLS="true",
               TF_IN_AUTOMATION="true", GIT_TERMINAL_PROMPT="0")
    try:
        result = subprocess.run(args, cwd=repo, env=env, capture_output=True,
                                text=True, timeout=timeout, check=False,
                                encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return CommandResult("blocked", error_kind="missing_executable")
    except subprocess.TimeoutExpired:
        return CommandResult("unknown", error_kind="timeout")
    except OSError:
        return CommandResult("unknown", error_kind="process_error")
    if result.returncode != 0:
        # Classify only fixed known strings; never expose stderr or exception text.
        error = result.stderr + result.stdout
        category = "command_failed"
        for token, label in [("NoCredentials", "no_credentials"),
                             ("Unable to locate credentials", "no_credentials"),
                             ("ExpiredToken", "expired_credentials"),
                             ("InvalidClientTokenId", "invalid_credentials"),
                             ("AccessDenied", "access_denied")]:
            if token in error:
                category = label
                break
        return CommandResult("blocked", error_kind=category)
    return CommandResult("pass", stdout=result.stdout.strip())


def dependencies(repo: Path) -> Check:
    """Compare the installed environment against the checked-in dependency pins."""
    path = repo / "requirements.txt"
    if not path.is_file():
        return Check("dependencies", "blocked", "requirements.txt is missing.")
    missing, mismatched, unsupported, checked = [], [], False, 0
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        requirement, _, marker = line.partition(";")
        if marker:
            match = re.fullmatch(r"\s*sys_platform\s*==\s*['\"](win32|linux|darwin)['\"]\s*", marker)
            if not match:
                unsupported = True
                continue
            if match.group(1) != sys.platform:
                continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)", requirement.strip())
        if not match:
            unsupported = True
            continue
        package, expected = match.groups()
        checked += 1
        try:
            actual = metadata.version(package)
        except metadata.PackageNotFoundError:
            missing.append(package)
        else:
            if actual != expected:
                mismatched.append(package)
    if missing or mismatched:
        return Check("dependencies", "blocked", f"Missing distributions: {', '.join(missing) or 'none'}; version mismatches: {', '.join(mismatched) or 'none'}. Use the intended virtual environment.")
    if unsupported or not checked:
        return Check("dependencies", "unknown", "A requirement or platform marker needs manual review; not all dependencies were verified.")
    return Check("dependencies", "pass", "Installed distributions match the applicable exact pins; application behavior is not tested here.")


def local_docker_endpoint(value: str) -> bool:
    # Do not contact a remote Docker context during an offline preflight.
    """Allow inspection only of a local Docker transport, not a remote daemon."""
    if value.startswith(("npipe://", "unix://")):
        return True
    try:
        endpoint = urlsplit(value)
        return endpoint.scheme == "tcp" and endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
    except ValueError:
        return False


def inspect(repo: Path, *, aws: bool = False, profile: str | None = None,
            expected_account_id: str | None = None, timeout: int = 15) -> dict:
    """Inspect local prerequisites; AWS identity calls require explicit opt-in.

    This never installs tools, builds images, initializes Terraform or changes
    cloud resources. Unknown and skipped checks remain distinct from success.
    """
    checks: list[Check] = []
    required = ["requirements.txt", "Dockerfile", "infra/main.tf", "src/aws_agent_platform_lab/web.py"]
    absent = [p for p in required if not (repo / p).is_file()]
    checks.append(Check("repository", "blocked" if absent else "pass",
                        "Missing required files: " + ", ".join(absent) if absent else "Expected source and infrastructure files are present."))
    checks.append(Check("python", "pass" if sys.version_info >= (3, 11) else "blocked",
                        f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}; project minimum 3.11, verified baseline 3.12."))
    checks.append(dependencies(repo))

    def run_check(name: str, args: list[str], success: str) -> CommandResult:
        """Record a named diagnostic outcome without exposing raw tool output."""
        result = command(args, repo=repo, timeout=timeout)
        checks.append(Check(name, result.status, success if result.status == "pass" else result.error_kind))
        return result

    docker = shutil.which("docker")
    if not docker:
        checks.append(Check("docker_daemon", "blocked", "Docker CLI not found; container checks were not run."))
    else:
        # DOCKER_CONTEXT overrides DOCKER_HOST, matching Docker's documented precedence.
        context = os.environ.get("DOCKER_CONTEXT")
        host = os.environ.get("DOCKER_HOST") if not context else None
        if not host:
            args = [docker, "context", "inspect"] + ([context] if context else [])
            result = command(args + ["--format", "{{json .Endpoints.docker.Host}}"], repo=repo, timeout=timeout)
            if result.status == "pass":
                try:
                    host = json.loads(result.stdout)
                except (ValueError, TypeError):
                    host = None
            else:
                checks.append(Check("docker_daemon", result.status, result.error_kind))
        if not any(c.name == "docker_daemon" for c in checks):
            if not isinstance(host, str) or not local_docker_endpoint(host):
                checks.append(Check("docker_daemon", "unknown", "Docker endpoint is remote or unrecognised; no daemon connection attempted."))
            else:
                result = command([docker, "version", "--format", "{{json .Server.Version}}"], repo=repo, timeout=timeout)
                if result.status != "pass":
                    checks.append(Check("docker_daemon", result.status, "Local Docker server is unavailable or unverified (" + result.error_kind + "). Start/check the local engine separately."))
                else:
                    try:
                        version = json.loads(result.stdout)
                    except (ValueError, TypeError):
                        version = None
                    valid = isinstance(version, str) and bool(re.fullmatch(r"\d+\.\d+\.\d+[A-Za-z0-9_.+-]*", version))
                    checks.append(Check("docker_daemon", "pass" if valid else "unknown",
                                        "Local Docker server responded; no image was built." if valid else "No valid Docker server version returned."))

    terraform = shutil.which("terraform")
    if not terraform:
        checks.append(Check("terraform_fmt", "blocked", "Terraform CLI not found."))
        checks.append(Check("terraform_validate", "skipped", "Terraform CLI is required."))
    elif not (repo / "infra").is_dir():
        checks.append(Check("terraform_fmt", "blocked", "Infrastructure directory is missing."))
        checks.append(Check("terraform_validate", "skipped", "Infrastructure directory is required."))
    else:
        run_check("terraform_fmt", [terraform, "-chdir=infra", "fmt", "-check", "-recursive"], "Terraform formatting check passed; files were not rewritten.")
        if (repo / "infra/.terraform/providers").is_dir():
            run_check("terraform_validate", [terraform, "-chdir=infra", "validate", "-no-color"], "Terraform configuration validates; account availability and a deployment plan are not verified.")
        else:
            checks.append(Check("terraform_validate", "skipped", "Provider directory is absent; initialization must be a separate explicit step."))

    if not aws:
        checks.append(Check("aws_profiles", "skipped", "Use --aws for read-only profile and STS checks. No AWS command was run."))
        checks.append(Check("aws_identity", "skipped", "No cloud identity or service access was verified."))
    else:
        cli = shutil.which("aws")
        if not cli:
            checks.append(Check("aws_profiles", "blocked", "AWS CLI not found."))
            checks.append(Check("aws_identity", "skipped", "AWS CLI is required."))
        else:
            result = command([cli, "configure", "list-profiles"], repo=repo, timeout=timeout)
            count = len([p for p in result.stdout.splitlines() if p.strip()])
            checks.append(Check("aws_profiles", result.status, f"{count} configured profile(s); names and credential values are not reported." if result.status == "pass" else result.error_kind))
            args = [cli, "sts", "get-caller-identity", "--output", "json", "--no-cli-pager",
                    "--cli-connect-timeout", str(timeout), "--cli-read-timeout", str(timeout)]
            if profile:
                args += ["--profile", profile]
            result = command(args, repo=repo, timeout=timeout)
            if result.status != "pass":
                checks.append(Check("aws_identity", result.status, result.error_kind))
            else:
                try:
                    identity = json.loads(result.stdout)
                    account = identity.get("Account", "")
                    valid = bool(re.fullmatch(r"\d{12}", account)) and isinstance(identity.get("Arn"), str) and identity["Arn"].startswith("arn:") and bool(identity.get("UserId"))
                except (ValueError, TypeError, AttributeError):
                    valid, account = False, ""
                if not valid:
                    checks.append(Check("aws_identity", "unknown", "STS response did not contain a valid identity."))
                elif expected_account_id and account != expected_account_id:
                    checks.append(Check("aws_identity", "blocked", "AWS identity does not match the expected account."))
                else:
                    checks.append(Check("aws_identity", "pass", "STS identity verified" + (" in the expected account." if expected_account_id else "; account authorisation is still an operator decision.") + " Models, quotas and application permissions were not checked."))
    statuses = {c.name: c.status for c in checks}
    all_pass = lambda names: all(statuses.get(n) == "pass" for n in names)
    local = all_pass(["repository", "python", "dependencies"])
    return {"scope": "Read-only prerequisites, not deployment approval or functional application proof.",
            "mode": "aws_identity_opt_in" if aws else "offline",
            "ready_for": {"local_python": local,
                          "container_build_prerequisites": local and all_pass(["docker_daemon"]),
                          "terraform_syntax": all_pass(["terraform_fmt", "terraform_validate"]),
                          "aws_identity_verified": all_pass(["aws_identity"])},
            "deployment_readiness": "not_assessed",
            "checks": [asdict(c) for c in checks]}


def main(argv: list[str] | None = None) -> int:
    """Print the scoped report and fail when a check is blocked or unknown."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--aws", action="store_true", help="Opt in to profile enumeration and read-only STS identity lookup; never logs in.")
    parser.add_argument("--profile", help="Explicit AWS profile, only with --aws.")
    parser.add_argument("--expected-account-id", help="Optional 12-digit account check, only with --aws.")
    parser.add_argument("--timeout", type=int, default=15, help="Per-command timeout, 1–60 seconds.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable report without raw command output.")
    args = parser.parse_args(argv)
    if not 1 <= args.timeout <= 60:
        parser.error("--timeout must be between 1 and 60 seconds")
    if (args.profile or args.expected_account_id) and not args.aws:
        parser.error("--profile and --expected-account-id require --aws")
    if args.expected_account_id and not re.fullmatch(r"\d{12}", args.expected_account_id):
        parser.error("--expected-account-id must contain 12 digits")
    if not args.repo.is_dir():
        parser.error("--repo must be an existing directory")
    report = inspect(args.repo.resolve(), aws=args.aws, profile=args.profile,
                     expected_account_id=args.expected_account_id, timeout=args.timeout)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(report["scope"])
        for c in report["checks"]:
            print(f"{c['status'].upper():7} {c['name']}: {c['detail']}")
        print("Readiness: " + json.dumps(report["ready_for"]))
        print("Deployment readiness: not assessed.")
    return 1 if any(c["status"] in {"blocked", "unknown"} for c in report["checks"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
