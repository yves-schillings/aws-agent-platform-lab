# Start development and prove each increment

The immediate development objective is a local, code-first Factory workflow that can be inspected before cloud deployment. It preserves the existing browser demonstration and adds `/factory` as a **prototype and test harness**, pending the user's choice of interface. An existing conversational client such as Claude or Copilot is being considered; the custom browser is not an endorsed final product interface. The agreed business output remains one shared, read-only application for synthetic affiliation consultation. The target Factory will build that application; ordinary application queries will use business APIs directly.

The backend state machine, evidence and approval rules remain common regardless of the client. A future existing-client connection would use a separately authenticated Model Context Protocol (MCP) or API adapter. No such connection is established by this local increment, and the simulated `X-Demo-User` header must never serve as its authentication mechanism.

See [conversational access](conversational-access.md) for the Claude, Codex and Copilot Studio options, the new local stdio adapter's limits, and the separate authentication and human-review work required for a remote AWS connection.

Three uses of the name Claude must stay separate: **Claude through Amazon Bedrock** would be a worker's inference model; a **Claude conversational client** would be an optional user interface connecting to approved backend tools; **Claude Code as an independent reviewer** would examine the implementation and report findings. None of these roles grants human approval authority, and none is invoked by the deterministic local Factory.

## Evidence before this increment

The audit on 1 October 2026 started from commit `86ac8aa`, with documentation changes already present in the working tree. The pre-increment baseline passed **78 application tests and 8 deployment-script tests**. These counts describe that audited baseline, not every later working-tree change. Record the exact revision, dependency lock and new test count after integration.

| Check | Observed result | What it does not establish |
|---|---|---|
| Python environment | Project virtual environment: Python 3.12.10; installed baseline dependency pins matched | A functioning AWS deployment |
| Terraform | 1.12.2; `fmt -check` and `validate` passed with AWS provider 6.66.0 | Account permissions, resource availability or a reviewed plan |
| AWS CLI | 2.37.6 installed; no configured profile; STS returned `NoCredentials` | Authenticated programmatic access despite earlier console access |
| Docker | CLI 28.2.2 installed; local Linux engine unavailable | A new local image build; earlier CI container evidence remains separately documented |
| Deployment inputs | No local `terraform.tfvars` or Terraform state found | Proof that no resources exist elsewhere in the AWS account |
| GitHub CLI | Not found on this workstation | GitHub account or Actions configuration; browser/other tooling may still be available |

The infrastructure is a deployment candidate for the baseline application. It does not yet deliver the complete five-worker Factory, company MCP servers, isolated generated-code execution or a separately deployed generated business application. See the [runtime mapping](factory/runtime-map.md) and [AWS runbook](deployment.md).

## Run the read-only preflight

From the repository root, use the intended virtual environment:

```powershell
.\.venv\Scripts\python.exe scripts/preflight.py
.\.venv\Scripts\python.exe scripts/preflight.py --json
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_preflight.py -v
```

The default mode reads repository files and installed dependency metadata, checks a **local** Docker endpoint, and runs Terraform formatting/validation when applicable. It makes no AWS command call, installs nothing, performs no Terraform initialization, builds no image and modifies no infrastructure. A remote Docker endpoint is reported as unverified and is not contacted.

The report separates `local_python`, `container_build_prerequisites`, `terraform_syntax` and `aws_identity_verified`. `deployment_readiness` always remains `not_assessed`. `pass` describes only the named check; `blocked`, `unknown` and `skipped` do not count as successful evidence. Exit code 1 means at least one blocked or unknown check; exit code 0 means the checks that ran passed, and still requires reading any skipped checks. Timeouts default to 15 seconds per command and can be bounded with `--timeout 1` through `--timeout 60`.

After the operator has established an authorised AWS session separately, opt in to identity checks:

```powershell
.\.venv\Scripts\python.exe scripts/preflight.py --aws --profile aws-agent-lab --json
# Optionally add --expected-account-id followed by the approved 12-digit account.
```

This invokes only profile enumeration and STS `GetCallerIdentity`. Reports omit profile names, account/principal identifiers, credentials and raw subprocess output. AWS documents that this operation identifies the caller and requires no permissions: success is therefore **not evidence of permission to create resources or invoke Bedrock**. [AWS STS reference](https://docs.aws.amazon.com/STS/latest/APIReference/API_GetCallerIdentity.html)

For IAM Identity Center, follow the organisation's real start URL/account/role using the [official SSO configuration flow](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html). For an authorised console identity outside Identity Center, the [AWS local-development sign-in flow](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html) supports temporary credentials with `aws login` and requires the applicable sign-in permission. Choose the existing identity method with the account owner. The preflight never chooses an account, configures a profile, starts login, creates access keys or registers a new AWS account.

## Implementation stages and required proof

| Stage | Concrete change | Evidence needed before calling it complete |
|---|---|---|
| 1. Local Factory state machine | `factory.py`: explicit LangGraph routing through Analyst, Architect, Code Author, Tester and Reviewer; G1 Scope, G2 Design, G3 Quality and G4 Release | Deterministic tests reach every named gate; rejection stops the run without forward work; gate decisions bind to the exact reviewed revision; malformed, stale, replayed and cross-owner decisions fail. Correction/resubmission routing is later work |
| 2. Prototype client and local persistence | `/factory` as the temporary browser harness and `/api/factory/runs`, separate from the baseline `/` and `/api/runs`; local SQLite storage; final client choice pending | Prototype creates a run, shows proposals/evidence and allows simulated owner decisions; restart recovers gate pauses; the local boundary rejects remote requests. A future existing client must use authenticated backend tools and a separate human-approval channel |
| 3. First real AWS baseline | Authorised operator session, exact region/model configuration, supporting Terraform resources, immutable ECR image, ECS Express, Cognito and reviewed synthetic corpus | Exact deployed digest, real user login, successful real retrieval/inference, permitted sources, denied cross-owner access and private evidence persistence; `/healthz` alone is insufficient |
| 4. Cloud Factory execution | Qualify cloud checkpointing, real model adapters and registered remote MCP tools; isolate candidate execution from trusted tests and controller authority | Crash/retry/idempotency tests, company isolation, approved tool identities/contracts, execution/network/resource limits and independently produced test results |
| 5. Generated application and release | Build the shared affiliation application and release an exact approved version into a separate target | Protected candidate build/validation, G4 authorisation bound to target and digest, successful runtime API checks, scoped sharing/revocation, rollback and operator evidence |

**G means Gate: a human approval checkpoint.** The initial five software workers are deterministic role implementations in one Python workflow, not five autonomous deployed services. Local SQLite is local development persistence, not AWS durability, high availability or tenant isolation. Proposal files are inert content: this increment must not execute generated code, invoke a shell, build an untrusted image or deploy an application. An approved G4 in the local simulation records an approval; it is not a cloud release.

The candidate API payloads and run states must be checked against the implemented `web.py`, Factory module and their tests when integrating the increment. This guide does not invent alternative endpoint contracts.

## If an existing conversational client is selected

The current `FactoryService` accepts only supported **simulated local identities**. Its decision endpoint is appropriate for a local demonstration, not a safe approval mechanism for an LLM client. The same fixture owner can currently create/read a run and submit every gate decision. An API-capable local process could therefore approve its own proposals if this endpoint were exposed as a tool.

Keep conversational tools limited to starting an authorised run, reading its state/evidence, and requesting human review. Do not expose `decide_run`, the HTTP decision endpoint, approval credentials or a general-purpose HTTP/shell tool with equivalent access to the conversational client. A chat statement such as “the user approved” is not approval evidence.

Use a separate trusted approval surface or approval service with an authenticated human session and server-owned gate-role policy. It must display the exact artifact and bind the human's explicit decision to company, project, run, gate, version/hash, destination for release, expiry and a single-use decision identifier. Backend checks must reject agent/service identities, forged or stale receipts, replay and wrong-target release; the model cannot supply the approving principal or mint an approval receipt. The conversational client may receive the resulting status after the backend verifies it. This is a proposed integration boundary, not functionality delivered by the local fixture service.

The selected client, identity flow, organisation policy, data handling and connector capabilities require qualification before implementation. No Claude/Copilot connection, subscription action, source upload or paid model call is authorised merely by discussing this option.

## Review and next action

Integrated local verification on 1 October 2026 passed **119 application tests** (42.191 seconds) and **8 deployment-script tests** (0.034 seconds). This includes 12 Factory state/recovery tests, 6 Factory HTTP tests, 9 real local stdio protocol tests and 14 preflight tests, alongside the preserved baseline suite. The protocol tests use a test MCP client, not Claude, Codex or Copilot Studio. Simulated MCP review is disabled by default and requires explicit host opt-in.

`pip check`, Terraform formatting and Terraform validation passed. An isolated `pip-audit` 2.10.1 scan of the pinned requirements reported no known vulnerabilities in the applicable Python packages. This is a dependency advisory check, not a source-code, operating-system or container security certification. The local Docker engine remains unavailable; AWS programmatic credentials and remote client connections remain unverified.

The base commit was `86ac8aa`; these results apply to the **uncommitted working tree**, not that commit alone. A local verification manifest in ignored `artifacts/verification/factory-local-increment.json` records source, tests, scripts, infrastructure and dependency file hashes. Its code-manifest SHA-256 is `3b2db1fd5713a07886266927d588c597fecb6fee99013af25f1e20abeb63dc60`. The dependency report is retained beside it as `factory-dependency-audit.json`. Later code changes require fresh evidence.

Next, qualify a conversational client for describe/start/get using the [MCP access guide](conversational-access.md), establish an authorised AWS operator session, then verify account, region, model access and cost limits before the first real baseline deployment. A local test result does not establish any of those cloud outcomes.

Use the [Claude review brief](claude-review-brief.md) for an independent code review when the user explicitly initiates it. The brief is ready to use, but no paid external-model call or source upload is implied. Human owners retain the gate decisions and the final decision to deploy.
